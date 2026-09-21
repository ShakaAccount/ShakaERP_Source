from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    win_access_url = fields.Char("API URL", config_parameter="win_access.url")
    win_access_key = fields.Char("API Key", config_parameter="win_access.key")
    win_access_domain = fields.Char("AD Domain", config_parameter="win_access.domain")
