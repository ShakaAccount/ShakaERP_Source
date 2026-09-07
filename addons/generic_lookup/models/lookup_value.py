from odoo import models, fields

class LookupValue(models.Model):
    _name = 'lookup.value'
    _description = 'Lookup Value'
    _order = 'type_id, sequence, name'

    type_id = fields.Many2one('lookup.type', string='Type', required=True, ondelete='cascade')
    name = fields.Char(string='Label', required=True)
    code = fields.Char(
        string='Code',
        required=True,
        help='Technical key for this value (e.g. "bank_transfer").'
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('type_code_uniq', 'unique(type_id, code)', 'Value code must be unique within a lookup type.'),
    ]
