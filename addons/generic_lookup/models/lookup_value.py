import re

from odoo import api, models, fields

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

    @api.model_create_multi
    def create(self, vals_list):
        """Allow inline creation from a Many2one dropdown.

        Odoo's quick-create sends only a name.  Lookup values also need a
        technical code, so create a stable unique code automatically.
        """
        for vals in vals_list:
            if vals.get('code') or not vals.get('name'):
                continue
            type_id = vals.get('type_id') or self.env.context.get('default_type_id')
            if not type_id and self.env.context.get('default_type_code'):
                type_id = self.env['lookup.type'].sudo().search([
                    ('code', '=', self.env.context['default_type_code'])
                ], limit=1).id
            base = re.sub(r'\s+', '_', vals['name'].strip().lower())
            base = re.sub(r'[^\w-]', '', base, flags=re.UNICODE).strip('_') or 'value'
            code = base
            suffix = 2
            while type_id and self.sudo().search_count([('type_id', '=', type_id), ('code', '=', code)]):
                code = f'{base}_{suffix}'
                suffix += 1
            vals['code'] = code
            if not vals.get('type_id') and type_id:
                vals['type_id'] = type_id
        return super().create(vals_list)
