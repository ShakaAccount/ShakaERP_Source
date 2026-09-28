from odoo import fields, models


class ResUsersSettings(models.Model):
    _inherit = 'res.users.settings'

    is_discuss_sidebar_category_telegram_open = fields.Boolean(
        string="Telegram Category Open", default=True,
        help="If checked, the Telegram category is open in the discuss sidebar")
