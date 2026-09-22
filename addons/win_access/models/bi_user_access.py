import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .group import ApiError, Runner


def match_ssas_tables(entity_name, table_names):
    """Tables named exactly like the entity, or followed by an optional space and digits:
    DimParty -> DimParty, 'DimParty 1'; DimDate -> DimDate, DimDate1. Never DimPartyType."""
    rx = re.compile(r"^%s\s*\d*$" % re.escape(entity_name or ""), re.I)
    return [t for t in table_names if rx.match(t)]


def _dw_connect(env):
    """pymssql connection to the warehouse, reusing the DW connector's helper."""
    conn = env["raes.dw.connection"].search([], limit=1)
    if not conn:
        raise ApiError("No warehouse connection is configured.", "Create one in the DW connector first.")
    try:
        return env["raes.dw.catalog"]._mssql_connect(conn)
    except UserError as e:
        raise ApiError(str(e.args[0]), "Check the warehouse connection.")
    except Exception as e:
        raise ApiError("Cannot connect to the warehouse: %s" % e, "Check host, port and credentials of the DW connection.")


def _dw_hint(e):
    if "invalid column name" in str(e).lower() or "invalid object name" in str(e).lower():
        return "Run addons/win_access/scripts/01_md_useraccess.sql on Shaka_DW first."
    return "See the message above."


class BiUserAccess(models.Model):
    """What one Windows user may see of one entity, through the warehouse's MD.UserAccess table.

    The SSAS RLS filter is generic DAX that looks the current USERNAME() up in vwUserAccess, so these
    rows *are* the permission; no per-user SSAS role or DAX is needed."""
    _name = "bi.user.access"
    _description = "BI Row Access"
    _rec_name = "entity_id"

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade")
    module_id = fields.Many2one("raes.gnr.module", required=True)
    entity_id = fields.Many2one("raes.md.entity", required=True, domain="[('module_id', '=', module_id)]",
                                help="The id of this entity is the EntityID written to the warehouse.")
    ssas_table = fields.Char("SSAS table", required=True)
    is_all_reader = fields.Boolean("Sees everything", help="IsAllReader: unrestricted on every entity.")
    is_all_member = fields.Boolean("All members of this entity", help="IsAllMember for this entity.")
    line_ids = fields.One2many("bi.user.access.line", "access_id", string="Column values")
    state = fields.Selection([("draft", "Not synced"), ("synced", "Synced"), ("error", "Errors")],
                             default="draft", readonly=True)
    sync_result = fields.Json(readonly=True)
    synced_at = fields.Datetime(readonly=True)

    _user_entity_uniq = models.Constraint(
        "UNIQUE (user_id, entity_id)", "This user already has an access record for that entity.")

    @api.onchange("module_id")
    def _onchange_module(self):
        if self.entity_id.module_id != self.module_id:
            self.entity_id = False

    def _dw_rows(self):
        """MD.UserAccess rows for this user+entity: (member, column, reader, all_member)."""
        self.ensure_one()
        rows = []
        if self.is_all_reader or self.is_all_member:
            rows.append((None, None, int(self.is_all_reader), int(self.is_all_member)))
        rows += [(int(l.member_id), l.column_name, 0, 0) for l in self.line_ids]
        return rows

    def _check_user(self):
        self.ensure_one()
        if not (self.user_id.bi_username or "").strip():
            raise ApiError("This user has no Windows account for BI.",
                           "Fill 'Windows account' on the user's BI Access tab (for example RAEES\\name).")
        return self.user_id.bi_username

    def _write_rows(self):
        """Replace every warehouse row of this user+entity with the current ones, in one transaction."""
        self.ensure_one()
        name, eid, ename = self.user_id.bi_username.strip(), self.entity_id.id, self.entity_id.name
        rows = self._dw_rows()
        conn = _dw_connect(self.env)
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM MD.UserAccess WHERE UserName = %s AND EntityID = %s", (name, eid))
            for member, column, reader, allm in rows:
                cur.execute(
                    "INSERT INTO MD.UserAccess (UserName, EntityID, EntityName, MemberID, IsAllReader, "
                    "IsAllMember, EntityColumnName) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (name, eid, ename, member, reader, allm, column))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise ApiError("Warehouse write failed: %s" % e, _dw_hint(e))
        finally:
            conn.close()
        return "%d row(s) written for %s" % (len(rows), name) if rows else "All rows removed for %s" % name

    def _action_add_line(self):
        """Open popup 2 for this record."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": "Add value", "res_model": "bi.user.access.line.wizard",
            "view_mode": "form", "target": "new", "context": {"default_access_id": self.id},
        }

    def action_sync(self):
        for rec in self:
            run = Runner()
            run.step("Windows account", rec._check_user, "user")
            run.step("Replace access rows of %s" % rec.entity_id.name, rec._write_rows, "dw", ("user",))
            rec.write({"state": "error" if run.failed else "synced", "sync_result": run.data(),
                       "synced_at": fields.Datetime.now()})

    def unlink(self):
        # the warehouse must not keep access that Odoo no longer knows about
        for rec in self.filtered(lambda r: r.state == "synced"):
            try:
                rec._check_user()
                rec.line_ids.unlink()
                rec.is_all_reader = rec.is_all_member = False
                rec._write_rows()
            except ApiError as e:
                raise UserError("Could not remove the warehouse rows, so nothing was deleted: %s %s" % (e.msg, e.hint))
        return super().unlink()

    @api.model
    def import_user(self, user):
        """Create/update this user's records from MD.vwUserAccess. Returns (records, skipped_entities)."""
        if not (user.bi_username or "").strip():
            raise UserError(_("Fill the user's Windows account first."))
        try:
            conn = _dw_connect(self.env)
            try:
                cur = conn.cursor()
                cur.execute("SELECT EntityId, MemberID, IsAllReader, IsAllMember, EntityColumnName "
                            "FROM MD.vwUserAccess WHERE UserName = %s", (user.bi_username.strip(),))
                data = cur.fetchall()
            finally:
                conn.close()
        except ApiError as e:
            raise UserError("%s %s" % (e.msg, e.hint))
        except Exception as e:
            raise UserError("Warehouse read failed: %s %s" % (e, _dw_hint(e)))
        per = {}
        for eid, member, reader, allm, col in data:
            per.setdefault(int(eid), []).append((member, reader, allm, col))
        tables = self.env["win.access.option"].search([("kind", "=", "ssas_table")]).mapped("name")
        done = self.browse()
        skipped = 0
        for eid, rows in per.items():
            entity = self.env["raes.md.entity"].browse(eid).exists()
            if not entity:
                skipped += 1
                continue
            rec = self.search([("user_id", "=", user.id), ("entity_id", "=", eid)], limit=1)
            vals = {
                "is_all_reader": any(r[1] for r in rows), "is_all_member": any(r[2] for r in rows),
                "line_ids": [(5, 0, 0)] + [(0, 0, {"column_name": r[3], "member_id": str(r[0])})
                                            for r in rows if r[0] is not None and r[3]],
            }
            if rec:
                rec.write(vals)
            else:
                hit = match_ssas_tables(entity.name, tables)
                rec = self.create({**vals, "user_id": user.id, "module_id": entity.module_id.id,
                                   "entity_id": eid, "ssas_table": hit[0] if hit else entity.name})
            # the rows came from the warehouse, so they are already in sync
            rec.write({"state": "synced", "synced_at": fields.Datetime.now()})
            done |= rec
        return done, skipped


class BiUserAccessLine(models.Model):
    _name = "bi.user.access.line"
    _description = "BI Row Access Value"

    access_id = fields.Many2one("bi.user.access", required=True, ondelete="cascade")
    column_name = fields.Char("SSAS column", required=True)
    member_id = fields.Char("Value (MemberID)", required=True)

    @api.constrains("member_id")
    def _check_member(self):
        for l in self:
            if not re.fullmatch(r"-?\d{1,18}", (l.member_id or "").strip()):
                raise ValidationError("MemberID '%s' must be a whole number (up to 18 digits)." % l.member_id)
