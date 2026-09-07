# from odoo import models, fields, api


# class generic_lookup(models.Model):
#     _name = 'generic_lookup.generic_lookup'
#     _description = 'generic_lookup.generic_lookup'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

