from odoo import models, fields

class MyDirectoryModel(models.Model):
    _name = 'my.directory'
    _description = 'Directory Record'

    name = fields.Char(string='Name', required=True)
    description = fields.Text(string='Description')