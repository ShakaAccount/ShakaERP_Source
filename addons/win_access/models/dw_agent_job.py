from odoo import api, fields, models

DEFAULT_INSTANCE = "MSSQLSERVER"  # the API's name for the default SSAS instance


class RaesDwAgentJob(models.Model):
    """SSAS instance / database pickers for the ETL job's "Process SSAS" step,
    fed by the BI server API's lists (win.access.option cache). They map onto
    the connector's plain ssas_server / ssas_database fields, which stay the
    source of truth: default instance -> empty server (= DW connection host),
    named instance -> HOST\\INSTANCE."""
    _inherit = "raes.dw.agent.job"

    ssas_instance_id = fields.Many2one(
        "win.access.option", "SSAS instance", domain=[("kind", "=", "ssas_instance")],
        compute="_compute_ssas_options", inverse="_inverse_ssas_options")
    ssas_database_id = fields.Many2one(
        "win.access.option", "SSAS database", domain=[("kind", "=", "ssas_db")],
        compute="_compute_ssas_options", inverse="_inverse_ssas_options")
    options_error = fields.Char(compute="_compute_options_error")

    @api.depends("ssas_server", "ssas_database")
    def _compute_ssas_options(self):
        Opt = self.env["win.access.option"]
        for rec in self:
            name = (rec.ssas_server or "").partition("\\")[2] or DEFAULT_INSTANCE
            inst = Opt.search([("kind", "=", "ssas_instance"), ("name", "=ilike", name)], limit=1)
            rec.ssas_instance_id = inst
            rec.ssas_database_id = inst and rec.ssas_database and Opt.search(
                [("kind", "=", "ssas_db"), ("parent_id", "=", inst.id),
                 ("name", "=ilike", rec.ssas_database)], limit=1)

    def _inverse_ssas_options(self):
        for rec in self:
            inst = rec.ssas_instance_id.name
            rec.ssas_server = (False if not inst or inst.upper() == DEFAULT_INSTANCE
                               else "%s\\%s" % (rec.connection_id.host, inst))
            if rec.ssas_database_id:
                rec.ssas_database = rec.ssas_database_id.name

    @api.onchange("ssas_instance_id")
    def _onchange_ssas_instance(self):
        if self.ssas_database_id.parent_id != self.ssas_instance_id:
            self.ssas_database_id = False

    def _compute_options_error(self):
        err = self.env["ir.config_parameter"].sudo().get_param("win_access.options_err")
        for rec in self:
            rec.options_error = err

    @api.model
    def default_get(self, fields_list):
        self.env["win.access.option"].autorefresh()
        return super().default_get(fields_list)

    def web_read(self, specification):
        self.env["win.access.option"].autorefresh()
        return super().web_read(specification)
