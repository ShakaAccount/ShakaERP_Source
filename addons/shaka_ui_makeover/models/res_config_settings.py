# -*- coding: utf-8 -*-
import json

from markupsafe import Markup

from odoo import fields, models, api
from odoo.exceptions import ValidationError


# Single source of truth for the shipped palette. The admin edits a JSON copy
# of this structure in Settings; any key left out falls back to these values.
SHAKA_DEFAULT_PALETTE = {
    'light': {
        'bg': '#F2F6F3',
        'surface': '#FFFFFF',
        'elevated': '#EAF8EF',
        'border': '#DCE8E0',
        'input': '#FFFFFF',
        'hover': '#EAF8EF',
        'text': '#1C2922',
        'muted': '#718078',
        'primary': '#16A34A',
        'primary_dark': '#0B7A35',
        'on_primary': '#FFFFFF',
        'link': '#0B6B35',
        'pill_bg': '#E5F2E8',
        'pill_text': '#0B6B35',
        'success': '#16A34A',
        'warning': '#D99A16',
        'danger': '#DC2626',
    },
    'dark': {
        'bg': '#070A08',
        'surface': '#101812',
        'elevated': '#17251B',
        'border': '#2B4935',
        'input': '#080D0A',
        'hover': '#234D30',
        'text': '#F3FFF6',
        'muted': '#B9CDBF',
        'primary': '#22C55E',
        'primary_dark': '#16A34A',
        'on_primary': '#FFFFFF',
        'link': '#7BE49B',
        'pill_bg': '#1D3B28',
        'pill_text': '#9AF0B0',
        'success': '#22C55E',
        'warning': '#E0A83A',
        'danger': '#F87171',
    },
}


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    shaka_theme_palette = fields.Text(
        related='company_id.shaka_theme_palette',
        readonly=False,
        string='Theme palette (JSON)',
    )

    def get_values(self):
        """Force the company-depend palette into the values dict so the
        transient form always shows the current Company value, even in
        single-company mode where `company_id` may be False on the wizard.
        A company that never saved a palette shows the shipped defaults, so
        the admin always starts from a complete, editable document."""
        res = super().get_values()
        company = self.env.company
        res['shaka_theme_palette'] = (
            company.shaka_theme_palette or company._shaka_default_palette_json()
        )
        return res

    def set_values(self):
        """Persist the palette back onto the Company (single-company:
        write to the active company regardless of the wizard's company_id)."""
        super().set_values()
        self.env.company.shaka_theme_palette = self.shaka_theme_palette or False

    def action_shaka_apply_theme_colors(self):
        """Reload the page so the server-rendered layout_inject.xml picks up
        the new Company colors and emits them as :root CSS custom properties.
        The button on the settings page calls this; clicking it is equivalent
        to saving the form and reloading."""
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_shaka_reset_theme_palette(self):
        """Drop the customised palette and put the shipped colors back."""
        default_json = self.env['res.company']._shaka_default_palette_json()
        self.env.company.shaka_theme_palette = default_json
        self.shaka_theme_palette = default_json
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }


class ResCompany(models.Model):
    _inherit = 'res.company'

    shaka_theme_palette = fields.Text(
        string='Theme palette (JSON)',
        default=lambda self: self._shaka_default_palette_json(),
        help='Light and dark mode colors as JSON. Every value is a hex color '
             'such as #16A34A. Missing keys fall back to the shipped palette.',
    )

    @api.model
    def _shaka_default_palette_json(self):
        return json.dumps(SHAKA_DEFAULT_PALETTE, indent=2)

    def _shaka_valid_color(self, value, fallback):
        value = (value or '').strip().upper()
        if len(value) in (4, 7) and value.startswith('#') and all(c in '0123456789ABCDEF' for c in value[1:]):
            return value
        return fallback

    @api.constrains('shaka_theme_palette')
    def _check_shaka_theme_palette(self):
        for company in self:
            company._shaka_palette(strict=True)

    def _shaka_palette(self, strict=False):
        """Return {'light': {...}, 'dark': {...}} with every key resolved.

        With `strict` the stored document is validated instead of repaired, so
        a typo is reported when saving rather than silently ignored later.
        """
        self.ensure_one()
        raw = (self.shaka_theme_palette or '').strip()
        document = {}
        if raw:
            try:
                document = json.loads(raw)
            except ValueError as error:
                if strict:
                    raise ValidationError(
                        f'The theme palette is not valid JSON: {error}'
                    ) from error
                document = {}
        if not isinstance(document, dict):
            if strict:
                raise ValidationError('The theme palette must be a JSON object.')
            document = {}

        palette = {}
        for mode, defaults in SHAKA_DEFAULT_PALETTE.items():
            given = document.get(mode) or {}
            if not isinstance(given, dict):
                if strict:
                    raise ValidationError(f'"{mode}" must be a JSON object of colors.')
                given = {}
            if strict:
                unknown = sorted(set(given) - set(defaults))
                if unknown:
                    raise ValidationError(
                        f'Unknown color keys in "{mode}": {", ".join(unknown)}.'
                    )
            resolved = {}
            for key, fallback in defaults.items():
                value = given.get(key)
                if strict and value is not None and not self._shaka_valid_color(value, None):
                    raise ValidationError(
                        f'"{mode}.{key}" must be a hex color such as #16A34A '
                        f'(got {value!r}).'
                    )
                resolved[key] = self._shaka_valid_color(value, fallback)
            palette[mode] = resolved
        return palette

    def _shaka_runtime_css(self):
        self.ensure_one()
        palette = self._shaka_palette()
        light = palette['light']
        dark = palette['dark']

        def variables(palette):
            return (
                f'--shaka-bg:{palette["bg"]};--shaka-surface:{palette["surface"]};'
                f'--shaka-soft:{palette["elevated"]};--shaka-green:{palette["primary"]};'
                f'--shaka-green-dark:{palette["primary_dark"]};--shaka-text:{palette["text"]};'
                f'--shaka-muted:{palette["muted"]};--shaka-border:{palette["border"]};'
                f'--shaka-input:{palette["input"]};--shaka-hover:{palette["hover"]};'
                f'--lg-bg-base:{palette["bg"]};--lg-bg-surface:{palette["surface"]};'
                f'--lg-bg-elevated:{palette["elevated"]};--lg-accent:{palette["primary"]};'
                f'--lg-accent-strong:{palette["primary_dark"]};--lg-link:{palette["link"]};'
                f'--lg-text:{palette["text"]};--lg-text-secondary:{palette["muted"]};'
                f'--lg-text-muted:{palette["muted"]};--lg-border:{palette["border"]};'
                f'--lg-input:{palette["input"]};--lg-hover:{palette["hover"]};'
                f'--lg-text-on-accent:{palette["on_primary"]};--lg-pill-bg:{palette["pill_bg"]};'
                f'--lg-pill-text:{palette["pill_text"]};--lg-success:{palette["success"]};'
                f'--lg-warning:{palette["warning"]};--lg-danger:{palette["danger"]};'
                f'--lg-accent-start:{palette["primary_dark"]};--lg-accent-end:{palette["primary"]};'
            )

        def rules(selector):
            return (
                f'{selector} body.o_web_client,'
                f'{selector} body.o_web_client .o_action_manager,'
                f'{selector} body.o_web_client .o_content{{background:var(--shaka-bg)!important;color:var(--shaka-text)!important}}'
                f'{selector} body.o_web_client .o_form_sheet,'
                f'{selector} body.o_web_client .card,'
                f'{selector} body.o_web_client .o_card{{background:var(--shaka-surface)!important;color:var(--shaka-text)!important;border-color:var(--shaka-border)!important}}'
                f'{selector} body.o_web_client input,'
                f'{selector} body.o_web_client textarea,'
                f'{selector} body.o_web_client select,'
                f'{selector} body.o_web_client .o_input{{background:var(--shaka-input)!important;color:var(--shaka-text)!important;border-color:var(--shaka-border)!important}}'
                f'{selector} body.o_web_client .o_control_panel,'
                f'{selector} body.o_web_client .o_notebook .nav-link,'
                f'{selector} body.o_web_client .o_pager{{background:var(--shaka-surface)!important;color:var(--shaka-text)!important;border-color:var(--shaka-border)!important}}'
                f'{selector} body.o_web_client .o_notebook .nav-link.active,'
                f'{selector} body.o_web_client .o_control_panel .btn:hover,'
                f'{selector} body.o_web_client .o_list_renderer tr:hover{{background:var(--shaka-hover)!important;color:var(--shaka-text)!important}}'
                f'{selector} body.o_web_client .btn-primary,'
                f'{selector} body.o_web_client .o_form_button_save{{background:var(--shaka-green-dark)!important;color:var(--lg-text-on-accent)!important;border-color:var(--shaka-green)!important}}'
                f'{selector} body.o_web_client .o_form_label,'
                f'{selector} body.o_web_client label{{color:var(--shaka-text)!important}}'
                f'{selector} body.o_web_client .o_field_widget.o_field_badge,'
                f'{selector} body.o_web_client .o_field_badge,'
                f'{selector} body.o_web_client .o_list_renderer .o_field_badge{{background:transparent!important;background-color:transparent!important;color:var(--lg-text)!important;border-color:transparent!important;box-shadow:none!important}}'
                f'{selector} body.o_web_client .o_field_widget.o_field_badge>.badge,'
                f'{selector} body.o_web_client .o_field_badge>.badge,'
                f'{selector} body.o_web_client .o_list_renderer .o_field_badge>.badge{{background:var(--lg-pill-bg)!important;background-color:var(--lg-pill-bg)!important;color:var(--lg-pill-text)!important;border:1px solid var(--lg-border)!important;box-shadow:none!important}}'
                f'{selector} body.o_web_client .o_main_navbar .o_menu_sections a.o_nav_entry.active,'
                f'{selector} body.o_web_client .o_main_navbar .o_menu_sections a.o_nav_entry[aria-current="page"],'
                f'{selector} body.o_web_client .o_main_navbar .o_menu_sections .o_nav_entry.active{{background:var(--lg-bg-elevated)!important;background-color:var(--lg-bg-elevated)!important;color:var(--lg-text)!important;border-color:transparent!important;box-shadow:none!important}}'
                f'{selector} body.o_web_client .o_main_navbar .o_menu_brand,'
                f'{selector} body.o_web_client .o_main_navbar .o_menu_brand:hover,'
                f'{selector} body.o_web_client .o_main_navbar .o_menu_brand:focus{{background:transparent!important;background-color:transparent!important;background-image:none!important;color:var(--lg-text)!important;border:0!important;box-shadow:none!important}}'
                f'{selector} body.o_web_client .o_list_renderer .o_list_table tbody td:has(.o_field_badge),'
                f'{selector} body.o_web_client .o_list_renderer .o_list_table tbody td:has(.badge){{background:transparent!important;background-color:transparent!important;background-image:none!important}}'
                f'{selector} body.o_web_client .o_form_statusbar{{background:transparent!important;background-color:transparent!important;background-image:none!important;border-color:transparent!important;box-shadow:none!important}}'
            )

        light_selector = 'html[data-theme="glass"]'
        dark_selector = 'html[data-theme="glass"].shaka-dark-mode'
        return Markup(
            '<style id="shaka-runtime-theme">'
            f'html[data-theme="glass"]{{{variables(light)}}}'
            f'{rules(light_selector)}'
            f'html[data-theme="glass"].shaka-dark-mode{{{variables(dark)}}}'
            f'{rules(dark_selector)}'
            '</style>'
        )
