from odoo import api, fields, models

from .md_view import MD_COMPANY_VIEW, refresh_writable_view


class RaesMdCompany(models.Model):
    """Read-only mirror of the DW table md.company.

    Category ownership is keyed on these ids, which are unrelated to Odoo's
    res.company ids; ``res.company.dw_company_id`` maps one to the other.
    """
    _name = 'raes.md.company'
    _table = 'raes_md_company'
    _auto = False
    _log_access = False
    _rec_name = 'title'
    _order = 'title'
    _description = 'DW Company (md.company)'

    parent_id = fields.Many2one('raes.md.company', 'Parent')
    title = fields.Char()
    en_title = fields.Char('Title (EN)')
    code = fields.Integer()
    is_active = fields.Boolean(default=True)

    creator_user_id = fields.Integer(
        required=True, default=lambda self: self.env.uid)
    creation_date = fields.Datetime(
        required=True, default=fields.Datetime.now)
    editor_user_id = fields.Integer()
    modification_date = fields.Datetime()

    def init(self):
        refresh_writable_view(self.env, *MD_COMPANY_VIEW)


class ResCompany(models.Model):
    _inherit = 'res.company'

    dw_company_id = fields.Many2one(
        'raes.md.company', 'DW Company',
        help="The Shaka DW company (md.company) this Odoo company maps to.")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # A new Odoo company gets its own DW company unless one was chosen.
        DwCompany = self.env['raes.md.company'].sudo()
        for rec, vals in zip(records, vals_list):
            if vals.get('dw_company_id'):
                continue
            self.env.cr.execute(
                "SELECT COALESCE(MAX(code), 0) + 1 FROM raes_md_company")
            code = self.env.cr.fetchone()[0]
            rec.dw_company_id = DwCompany.create({
                'title': rec.name[:100], 'en_title': rec.name[:100],
                'parent_id': rec.parent_id.dw_company_id.id or False,
                'code': code,
            })
        return records
