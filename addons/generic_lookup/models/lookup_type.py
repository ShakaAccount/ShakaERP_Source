from odoo import models, fields

class LookupType(models.Model):
    _name = 'lookup.type'
    _description = 'Lookup Type'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(
        string='Code',
        required=True,
        help='Technical key used by other modules to reference this lookup type (e.g. "payment_method").'
    )
    active = fields.Boolean(default=True)
    value_ids = fields.One2many('lookup.value', 'type_id', string='Values')
    value_count = fields.Integer(compute='_compute_value_count', string='Value Count')

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Lookup type code must be unique.'),
    ]

    def _compute_value_count(self):
        for rec in self:
            rec.value_count = len(rec.value_ids)