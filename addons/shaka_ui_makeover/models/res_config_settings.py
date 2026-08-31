# -*- coding: utf-8 -*-
from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    shaka_primary_color = fields.Char(
        related='company_id.shaka_primary_color',
        readonly=False,
        string='Button color',
    )
    shaka_button_text_color = fields.Char(
        related='company_id.shaka_button_text_color',
        readonly=False,
        string='Button text color',
    )

    def action_shaka_apply_theme_colors(self):
        """Apply theme colors by updating CSS custom properties via JS message."""
        # This action just triggers a client-side reload of the CSS variables.
        # The actual application happens in the theme_switch.js via the cookie
        # and the CSS variables are picked up from the company fields.
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Theme Colors',
                'message': 'Colors applied. They will be active on next page load.',
                'type': 'success',
                'sticky': False,
            }
        }


class ResCompany(models.Model):
    _inherit = 'res.company'

    shaka_primary_color = fields.Char(
        string='Primary (button) color',
        help='Used for the main buttons across the Shaka ERP UI.',
    )
    shaka_button_text_color = fields.Char(
        string='Button text color',
        help='Text/label colour on primary buttons.',
    )