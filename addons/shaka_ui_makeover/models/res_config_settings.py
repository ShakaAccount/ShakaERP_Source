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

    def get_values(self):
        """Force the company-depend colour fields into the values dict so the
        transient form always shows the current Company values, even in
        single-company mode where `company_id` may be False on the wizard."""
        res = super().get_values()
        company = self.env.company
        res.update({
            'shaka_primary_color': company.shaka_primary_color or False,
            'shaka_button_text_color': company.shaka_button_text_color or False,
        })
        return res

    def set_values(self):
        """Persist the colour fields back onto the Company (single-company:
        write to the active company regardless of the wizard's company_id)."""
        super().set_values()
        company = self.env.company
        company.write({
            'shaka_primary_color': self.shaka_primary_color or False,
            'shaka_button_text_color': self.shaka_button_text_color or False,
        })

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