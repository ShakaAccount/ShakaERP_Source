# from odoo import models, fields, api


# class dim_company_dashboard(models.Model):
#     _name = 'dim_company_dashboard.dim_company_dashboard'
#     _description = 'dim_company_dashboard.dim_company_dashboard'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

