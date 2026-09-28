from odoo import fields, models

from .md_view import MD_COMPANY_VIEW, refresh_md_view


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
    is_active = fields.Boolean()

    def init(self):
        refresh_md_view(self.env, *MD_COMPANY_VIEW)


class ResCompany(models.Model):
    _inherit = 'res.company'

    dw_company_id = fields.Many2one(
        'raes.md.company', 'DW Company',
        help="The Shaka DW company (md.company) this Odoo company maps to.")
