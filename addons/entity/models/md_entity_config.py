from odoo import _, api, fields, models


class RaesMdEntityConfig(models.Model):
    """Companion table holding per-entity Odoo-side configuration.

    Kept out of the DW mirror because the underlying md.entity table does
    not (and must not) carry this column: it belongs to the ERP side.
    """
    _name = 'raes.md.entity.config'
    _description = 'MD Entity DW Configuration'
    _rec_name = 'entity_id'

    entity_id = fields.Many2one(
        'raes.md.entity', string='Entity',
        required=True, ondelete='cascade', index=True)

    connection_id = fields.Many2one(
        'raes.dw.connection', string='DW Connection',
        ondelete='restrict', index=True)
    # entity_column_name_id = fields.Many2one('raes.md.entity_column', strintg='Entity Name Column')
    _entity_config_uniq = models.Constraint(
        'UNIQUE (entity_id)',
        'Only one configuration row per entity is allowed.')