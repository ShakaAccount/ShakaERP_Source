from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    bi_username = fields.Char(
        "Windows account for BI", compute="_compute_bi_username", store=True, readonly=False,
        help="The name SSAS sees as USERNAME(), e.g. RAEES\\jane. Defaulted from the AD domain and the login; "
             "correct it if the domain differs.")
    bi_access_ids = fields.One2many("bi.user.access", "user_id", string="BI Access")
    bi_ssas_group_ids = fields.Many2many(
        "win.access.group", compute="_compute_bi_ssas_groups",
        help="win_access groups (= SSAS roles) this Windows account is a member of.")
    bi_ssas_group_id = fields.Many2one(
        "win.access.group", "SSAS role", compute="_compute_bi_ssas_group_id", store=True, readonly=False,
        help="The RLS filter is pushed to this role's tables on sync. Auto-picked when you're in only "
             "one win_access group; pick one yourself if you're in several.")

    @api.depends("login")
    def _compute_bi_username(self):
        icp = self.env["ir.config_parameter"].sudo()
        domain = icp.get_param("win_access.domain") or icp.get_param("win_access.domain_netbios")
        for u in self:
            if not u.bi_username and u.login and domain:
                u.bi_username = "%s\\%s" % (domain, u.login)

    @api.depends("bi_username")
    def _compute_bi_ssas_groups(self):
        groups = self.env["win.access.group"].search([("ssas_database_id", "!=", False)])
        for u in self:
            name = (u.bi_username or "").strip().lower()
            u.bi_ssas_group_ids = groups.filtered(
                lambda g: name and any((m.principal or "").strip().lower() == name for m in g.member_ids))

    @api.depends("bi_ssas_group_ids")
    def _compute_bi_ssas_group_id(self):
        for u in self:
            if not u.bi_ssas_group_id or u.bi_ssas_group_id not in u.bi_ssas_group_ids:
                u.bi_ssas_group_id = u.bi_ssas_group_ids[:1]

    def action_bi_add(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": "Add BI access", "res_model": "bi.user.access.wizard",
            "view_mode": "form", "target": "new", "context": {"default_user_id": self.id},
        }

    def action_bi_sync_all(self):
        self.bi_access_ids.action_sync()

    def action_bi_import(self):
        self.ensure_one()
        recs, skipped = self.env["bi.user.access"].import_user(self)
        msg = "Imported %d access record(s) from the warehouse." % len(recs)
        if skipped:
            msg += " %d entity id(s) are unknown to Odoo and were skipped." % skipped
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "BI access", "message": msg, "type": "success" if recs else "warning"}}
