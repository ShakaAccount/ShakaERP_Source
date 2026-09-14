from odoo import api, fields, models

from .md_view import GNR_LOOKUP_VIEW, refresh_md_view


class RaesGnrLookup(models.Model):
    """Direct mapping of the existing gnr.lookup table
    (originally raes_system.GNR.LookUp).

    Reads and writes go through the public view raes_gnr_lookup
    created at install time by post_init_hook / init().
    """
    _name = 'raes.gnr.lookup'
    _table = 'raes_gnr_lookup'
    _auto = False
    _log_access = False
    _rec_name = 'value'
    _order = 'category_code, code'
    _description = 'GNR LookUp'

    # --- category ----------------------------------------------------
    category_code = fields.Char(
        string='Category Code', required=True, index=True)
    category_title_en = fields.Char(
        string='Category Title (EN)', required=True)
    # Persian display title
    category_title = fields.Char(
        string='Category Title', required=True)

    # --- entry -------------------------------------------------------
    code = fields.Integer(string='Code', required=True, index=True)
    value = fields.Char(string='Value', required=True)

    # --- audit -------------------------------------------------------
    creator_user_id = fields.Integer(
        required=True, default=lambda self: self.env.uid)
    creation_date = fields.Datetime(
        required=True, default=fields.Datetime.now)
    editor_user_id = fields.Integer()
    modification_date = fields.Datetime()

    def init(self):
        refresh_md_view(self.env, *GNR_LOOKUP_VIEW)

    @api.depends('category_title', 'value')
    def _compute_display_name(self):
        for rec in self:
            if rec.category_title and rec.value:
                rec.display_name = f'[{rec.category_title}] {rec.value}'
            else:
                rec.display_name = rec.value or rec.category_title or ''

    def write(self, vals):
        vals.setdefault('modification_date', fields.Datetime.now())
        vals.setdefault('editor_user_id', self.env.uid)
        return super().write(vals)