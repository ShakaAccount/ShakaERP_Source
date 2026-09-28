from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    telegram_proxy_url = fields.Char(
        string="Telegram Proxy", config_parameter='telegram.proxy_url',
        help="e.g. http://host:3128 or socks5h://host:1080 (SOCKS needs the PySocks package).")
