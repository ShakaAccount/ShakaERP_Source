import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .group import ApiError, Runner, _call, _q
from odoo.addons.entity.models.md_entity import _persian_normalize, _sql_persian_normalize


_SUFFIX_RX = re.compile(r"\s*\d+$")


def _dw_lookup_cols(cur, ssas_table_name, column_name):
    """(schema, table, id_col, title_col) for the dimension behind an SSAS *ID column, or None.

    Only resolves when `column_name` is the table's OWN business key ('DimBranch' -> 'BranchID'):
    that's the only column whose value identifies *this* row -- a foreign key into another dimension
    (DataSourceID, CompanyID, ...) or the title itself would pair meaninglessly with this row's own
    title, or (picking the title column) crash SQL Server with an ambiguous ORDER BY."""
    # role-playing SSAS tables carry a numeric suffix ('DimParty 1'); the physical table doesn't.
    for t in dict.fromkeys([ssas_table_name, _SUFFIX_RX.sub("", ssas_table_name).strip()]):
        cur.execute("SELECT TABLE_SCHEMA, COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = %s", (t,))
        cols = cur.fetchall()
        if cols:
            schema, table = cols[0][0], t
            break
    else:
        return None
    by_lower = {c.lower(): c for _, c in cols}
    own_id = re.sub(r"^Dim", "", table, flags=re.I).lower() + "id"
    if column_name.lower() != own_id or own_id not in by_lower:
        return None
    id_col = by_lower[own_id]
    # exact match first ('Title'), then any column whose name *contains* title/name ('BankName',
    # 'CodeTitle'), skipping the English variant when a localized one also exists.
    title_col = next((by_lower[c] for c in ("title", "name", "label", "codetitle")
                      if c in by_lower and c != own_id), None)
    if not title_col:
        title_col = next((v for k, v in by_lower.items()
                          if ("title" in k or "name" in k) and "english" not in k and k != own_id), None)
    return (schema, table, id_col, title_col) if title_col else None


def search_dw_members(env, ssas_table_name, column_name, term):
    """Every row of the DW dimension table behind an SSAS *ID column, matching `term` on their title.
    Returns [(numeric_id, title), ...], or [] if the column isn't lookup-able (see _dw_lookup_cols)."""
    conn = _dw_connect(env)
    try:
        cur = conn.cursor()
        resolved = _dw_lookup_cols(cur, ssas_table_name, column_name)
        if not resolved:
            return []
        schema, table, id_col, title_col = resolved
        sql = "SELECT [%s], [%s] FROM [%s].[%s] WHERE [%s] IS NOT NULL AND [%s] <> ''" % (
            id_col, title_col, schema, table, title_col, title_col)
        params = ()
        if term:
            # Arabic/Persian codepoints (ي/ی, ك/ک, ...) vary by data source, so normalize both sides.
            normalized = _persian_normalize(term)
            col_expr = _sql_persian_normalize("[%s]" % title_col, term=normalized, dialect="mssql")
            sql += " AND %s LIKE %%s" % col_expr
            params = ("%" + normalized + "%",)
        cur.execute(sql + " ORDER BY [%s]" % title_col, params)
        return cur.fetchall()
    except ApiError:
        raise
    except Exception as e:
        raise ApiError("Warehouse read failed: %s" % e, _dw_hint(e))
    finally:
        conn.close()


def resolve_dw_member(env, ssas_table_name, column_name, member_id):
    """The title of one specific row, by its id -- a targeted single-row lookup, cheaper than
    fetching the whole dimension via search_dw_members just to display one saved value."""
    if not member_id:
        return None
    conn = _dw_connect(env)
    try:
        cur = conn.cursor()
        resolved = _dw_lookup_cols(cur, ssas_table_name, column_name)
        if not resolved:
            return None
        schema, table, id_col, title_col = resolved
        cur.execute("SELECT [%s] FROM [%s].[%s] WHERE [%s] = %%s" % (title_col, schema, table, id_col),
                   (member_id,))
        row = cur.fetchone()
        return row[0] if row and row[0] else None
    except Exception:
        return None  # display falls back to the raw id; this is a nice-to-have, not critical
    finally:
        conn.close()


def generate_table_dax(env, ssas_table_name, group):
    """Static DAX filter_expression for one SSAS table, scoped to the access records that picked
    `group` among their SSAS roles -- a user in several roles can grant different roles different
    subsets, since SSAS unions a user's roles and a role with no filter on this table would grant
    unrestricted access regardless of what any other role says. Returns None if nothing to push."""
    recs = env["bi.user.access"].search(
        [("ssas_table", "=", ssas_table_name), ("group_ids", "in", group.id)])
    if not recs:
        return None
    clauses = ['1 IN SELECTCOLUMNS(CALCULATETABLE(vwUserAccess, vwUserAccess[UserName] = USERNAME()), '
              '"IsAllReader", vwUserAccess[IsAllReader])']
    for eid in sorted(set(recs.filtered("is_all_member").mapped("entity_id.id"))):
        clauses.append(
            '1 IN SELECTCOLUMNS(CALCULATETABLE(vwUserAccess, vwUserAccess[UserName] = USERNAME(), '
            'vwUserAccess[EntityID] = %d), "IsAllMember", vwUserAccess[IsAllMember])' % eid)
    pairs = sorted({(r.entity_id.id, l.column_name) for r in recs for l in r.line_ids})
    for eid, col in pairs:
        clauses.append(
            '%s[%s] IN SELECTCOLUMNS(CALCULATETABLE(vwUserAccess, vwUserAccess[UserName] = USERNAME(), '
            'vwUserAccess[EntityID] = %d, vwUserAccess[EntityColumnName] = "%s"), "MemberID", '
            'vwUserAccess[MemberID])' % (ssas_table_name, col, eid, col))
    return "\n|| ".join(clauses)


def push_rls_filter(env, group, ssas_table_name):
    """PUT the generated DAX for one table onto `group`'s SSAS role (group is a win.access.group;
    its .name is the role name, .ssas_database_id the database it was created on)."""
    if not group or not group.ssas_database_id:
        raise ApiError("No SSAS role selected.", "Pick at least one SSAS role on the access record.")
    dax = generate_table_dax(env, ssas_table_name, group)
    if not dax:
        return "Nothing to push"
    db, inst = group.ssas_database_id, group.ssas_database_id.parent_id
    _call(env, "PUT", "/ssas/%s/databases/%s/roles/%s/tables/%s" % (
        _q(inst.name), _q(db.name), _q(group.name), _q(ssas_table_name)), {"filter_expression": dax})
    return "Pushed to role %s" % group.name


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
    available_group_ids = fields.Many2many(
        "win.access.group", compute="_compute_available_groups",
        help="win_access groups (= SSAS roles) user_id's Windows account is a member of.")
    group_ids = fields.Many2many(
        "win.access.group", string="SSAS roles",
        help="Which of the user's roles this grant's RLS filter is pushed to on sync. A user in "
             "several roles needs it on each one they view this data through -- SSAS unions a "
             "user's roles, so a role left out here grants unrestricted access on this table instead.")
    state = fields.Selection([("draft", "Not synced"), ("synced", "Synced"), ("error", "Errors")],
                             default="draft", readonly=True)
    sync_result = fields.Json(readonly=True)
    synced_at = fields.Datetime(readonly=True)

    _user_entity_uniq = models.Constraint(
        "UNIQUE (user_id, entity_id)", "This user already has an access record for that entity.")

    @api.depends("user_id.bi_ssas_group_ids")
    def _compute_available_groups(self):
        for r in self:
            r.available_group_ids = r.user_id.bi_ssas_group_ids

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
            for grp in rec.group_ids:
                run.step("Push RLS filter to role %s" % grp.name, lambda r=rec, g=grp: push_rls_filter(
                    self.env, g, r.ssas_table), "ssas:%s" % grp.id, ("dw",))
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
    table_option_id = fields.Many2one("win.access.option", compute="_compute_table_option", store=True,
                                      help="The cached SSAS table this line's column belongs to.")
    column_id = fields.Many2one(
        "win.access.option", "SSAS column", compute="_compute_column_id", store=True, readonly=False,
        help="Auto-matched from column_name; pick a different one to change it.")
    member_option_id = fields.Many2one(
        "win.access.option", "Value", compute="_compute_member_option", store=True, readonly=False,
        help="Auto-resolved from the warehouse so you edit by title, not the raw id. Only possible when "
             "the column is the table's own key; otherwise edit 'Value (MemberID)' directly.")

    @api.depends("access_id.ssas_table")
    def _compute_table_option(self):
        Option = self.env["win.access.option"]
        for l in self:
            table = Option
            if l.access_id.ssas_table:
                table = Option.search([("kind", "=", "ssas_table"), ("name", "=", l.access_id.ssas_table)], limit=1)
                if table:
                    try:
                        table.load_columns()  # so the column_id dropdown has options
                    except ApiError:
                        pass
            l.table_option_id = table

    @api.depends("table_option_id", "column_name")
    def _compute_column_id(self):
        Option = self.env["win.access.option"]
        for l in self:
            opt = Option
            if l.table_option_id and l.column_name:
                opt = Option.search([("kind", "=", "ssas_column"), ("parent_id", "=", l.table_option_id.id),
                                     ("name", "=", l.column_name)], limit=1)
            l.column_id = opt

    @api.onchange("column_id")
    def _onchange_column_id(self):
        if self.column_id:
            self.column_name = self.column_id.name

    @api.depends("column_id", "member_id")
    def _compute_member_option(self):
        Option = self.env["win.access.option"]
        preloaded = set()  # columns already given a first page this batch
        for l in self:
            opt = Option
            if l.column_id and l.member_id:
                if l.column_id.id not in preloaded:
                    preloaded.add(l.column_id.id)
                    try:
                        for value, title in search_dw_members(self.env, l.access_id.ssas_table, l.column_id.name, ""):
                            o = Option.search([("kind", "=", "dw_member"), ("parent_id", "=", l.column_id.id),
                                               ("path", "=", str(value))], limit=1)
                            (o.write if o else Option.create)(
                                {"name": title} if o else {"kind": "dw_member", "parent_id": l.column_id.id,
                                                           "name": title, "path": str(value)})
                    except ApiError:
                        pass  # BI host unreachable; fall back to the plain numeric field
                opt = Option.search([("kind", "=", "dw_member"), ("parent_id", "=", l.column_id.id),
                                     ("path", "=", str(l.member_id))], limit=1)
                if not opt:
                    try:
                        title = resolve_dw_member(self.env, l.access_id.ssas_table, l.column_id.name, l.member_id)
                    except ApiError:
                        title = None
                    if title:
                        opt = Option.create({"kind": "dw_member", "parent_id": l.column_id.id,
                                             "name": title, "path": str(l.member_id)})
            l.member_option_id = opt

    @api.onchange("member_option_id")
    def _onchange_member_option(self):
        if self.member_option_id:
            self.member_id = self.member_option_id.path

    @api.constrains("member_id")
    def _check_member(self):
        for l in self:
            if not re.fullmatch(r"-?\d{1,18}", (l.member_id or "").strip()):
                raise ValidationError("MemberID '%s' must be a whole number (up to 18 digits)." % l.member_id)
