from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models.bi_user_access import match_ssas_tables, search_dw_members
from ..models.group import ApiError


class BiUserAccessWizard(models.TransientModel):
    """Popup 1: module -> entity -> SSAS table. Creates the access record, then opens popup 2."""
    _name = "bi.user.access.wizard"
    _description = "Add BI access"

    user_id = fields.Many2one("res.users", required=True, readonly=True)
    module_id = fields.Many2one("raes.gnr.module", required=True)
    entity_id = fields.Many2one("raes.md.entity", required=True)
    available_table_ids = fields.Many2many("win.access.option", compute="_compute_available_tables")
    table_id = fields.Many2one("win.access.option", "SSAS table", required=True)
    available_group_ids = fields.Many2many("win.access.group", related="user_id.bi_ssas_group_ids")
    group_ids = fields.Many2many(
        "win.access.group", string="SSAS roles",
        help="Which of the user's roles this grant's filter is pushed to. Pick more than one if the "
             "user needs the same access under several roles.")
    ols = fields.Selection(
        [("default", "Default"), ("none", "None"), ("read", "Read")], default="default", required=True,
        string="OLS (table visibility)",
        help="'None' hides this table entirely for the role -- no row filter is meaningful on top of "
             "that, so picking it skips the column/value step.")

    @api.model
    def default_get(self, fields_list):
        Option = self.env["win.access.option"]
        Option.autorefresh()
        if not Option.search_count([("kind", "=", "ssas_table")]):  # first use after an upgrade: cache is empty
            try:
                Option.refresh()
            except ApiError:
                pass  # shown by the empty table dropdown; the API error is stored by autorefresh
        return super().default_get(fields_list)

    @api.depends("entity_id")
    def _compute_available_tables(self):
        tables = self.env["win.access.option"].search([("kind", "=", "ssas_table")])
        for w in self:
            names = match_ssas_tables(w.entity_id.name, tables.mapped("name")) if w.entity_id else []
            w.available_table_ids = tables.filtered(lambda t: t.name in names)

    @api.onchange("module_id")
    def _onchange_module(self):
        if self.entity_id.module_id != self.module_id:
            self.entity_id = False

    @api.onchange("entity_id")
    def _onchange_entity(self):
        # a single match is the common case (111 of 114 entities), so pick it for the user
        self.table_id = self.available_table_ids if len(self.available_table_ids) == 1 else False

    def action_confirm(self):
        self.ensure_one()
        if self.table_id not in self.available_table_ids:
            raise UserError("Pick one of the SSAS tables that match the entity.")
        Access = self.env["bi.user.access"]
        rec = Access.search([("user_id", "=", self.user_id.id), ("entity_id", "=", self.entity_id.id)], limit=1)
        vals = {"module_id": self.module_id.id, "ssas_table": self.table_id.name, "ols": self.ols,
               "group_ids": [(6, 0, self.group_ids.ids)]}
        if rec:
            rec.write(vals)
        else:
            rec = Access.create({**vals, "user_id": self.user_id.id, "entity_id": self.entity_id.id})
        if self.ols == "none":
            rec.line_ids.unlink()  # no row filter is meaningful once the table itself is hidden
            return {"type": "ir.actions.act_window_close"}
        return rec._action_add_line()


class BiUserAccessLineWizard(models.TransientModel):
    """Popup 2: a column of the chosen SSAS table and the value the user may see."""
    _name = "bi.user.access.line.wizard"
    _description = "Add BI access value"

    access_id = fields.Many2one("bi.user.access", required=True, readonly=True)
    table_id = fields.Many2one("win.access.option", readonly=True)
    column_id = fields.Many2one("win.access.option", "SSAS column", required=True,
                                domain="[('kind', '=', 'ssas_column'), ('parent_id', '=', table_id)]")
    member_option_id = fields.Many2one(
        "win.access.option", "Value",
        domain="[('kind', '=', 'dw_member'), ('parent_id', '=', column_id)]",
        help="Auto-loaded from the warehouse when the column is that dimension's own id (e.g. WarehouseID, "
             "BranchID). Type to filter. If the row you want isn't listed, type its numeric id below instead.")
    member_id = fields.Char("Value (MemberID)", required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        access = self.env["bi.user.access"].browse(res.get("access_id") or self.env.context.get("default_access_id"))
        if access:
            # the popup-1 dropdown is limited to tables that exist, so the name resolves to one option
            table = self.env["win.access.option"].search(
                [("kind", "=", "ssas_table"), ("name", "=", access.ssas_table)], limit=1)
            if table:
                try:
                    table.load_columns()
                except ApiError as e:
                    raise UserError("Could not load the columns of %s: %s %s" % (table.name, e.msg, e.hint))
                res["table_id"] = table.id
        return res

    def _search_members(self):
        self.ensure_one()
        if not self.column_id:
            return
        rows = search_dw_members(self.env, self.table_id.name, self.column_id.name, "")
        Option = self.env["win.access.option"]
        for value, title in rows:
            opt = Option.search([("kind", "=", "dw_member"), ("parent_id", "=", self.column_id.id),
                                 ("path", "=", str(value))], limit=1)
            if opt:
                opt.name = title
            else:
                Option.create({"kind": "dw_member", "parent_id": self.column_id.id, "name": title, "path": str(value)})

    @api.onchange("column_id")
    def _onchange_column(self):
        self.member_option_id = False
        if self.column_id:
            self._search_members()

    @api.onchange("member_option_id")
    def _onchange_member_option(self):
        if self.member_option_id:
            self.member_id = self.member_option_id.path

    def _save(self):
        self.env["bi.user.access.line"].create({
            "access_id": self.access_id.id, "column_name": self.column_id.name, "member_id": self.member_id})

    def action_save(self):
        self._save()
        return {"type": "ir.actions.act_window_close"}

    def action_save_more(self):
        self._save()
        return self.access_id._action_add_line()
