from odoo import api, fields, models

from .md_view import GNR_MODULE_VIEW, refresh_md_view


class RaesGnrModule(models.Model):
    """Direct mapping of the existing gnr.module table.

    Reads and writes go through the public view raes_gnr_module
    created at install time by post_init_hook / init().
    """
    _name = 'raes.gnr.module'
    _table = 'raes_gnr_module'
    _auto = False
    _log_access = False
    _rec_name = 'title'
    _order = 'priority, title'
    _description = 'GNR Module (gnr.module)'

    title = fields.Char(required=True)
    creator_user_id = fields.Integer(
        required=True, default=lambda self: self.env.uid)
    creation_date = fields.Datetime(
        required=True, default=fields.Datetime.now)
    editor_user_id = fields.Integer()
    modification_date = fields.Datetime()
    is_user_defined = fields.Boolean(required=True, default=False)
    priority = fields.Integer(required=True, default=0)

    entity_ids = fields.One2many(
        'raes.md.entity', 'module_id', string='Entities')
    entity_count = fields.Integer(
        compute='_compute_entity_count', string='Entities')

    def init(self):
        refresh_md_view(self.env, *GNR_MODULE_VIEW)

    @api.depends('entity_ids')
    def _compute_entity_count(self):
        for rec in self:
            rec.entity_count = len(rec.entity_ids)

    def write(self, vals):
        vals.setdefault('modification_date', fields.Datetime.now())
        vals.setdefault('editor_user_id', self.env.uid)
        return super().write(vals)

    def action_open_entities(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Entities',
            'res_model': 'raes.md.entity',
            'view_mode': 'list,form',
            'domain': [('module_id', '=', self.id)],
            'context': {'default_module_id': self.id},
        }