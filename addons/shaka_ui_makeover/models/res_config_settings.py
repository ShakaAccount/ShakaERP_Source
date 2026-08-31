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
        """Reload the page so the server-rendered layout_inject.xml picks up
        the new Company colors and emits them as :root CSS custom properties.
        The button on the settings page calls this; clicking it is equivalent
        to saving the form and reloading."""
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
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