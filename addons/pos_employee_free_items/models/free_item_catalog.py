# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class PosFreeItemCatalog(models.Model):
    """Products that the admin decides can be given for free."""
    _name = 'pos.free.item.catalog'
    _description = 'POS Free-Item Catalogue (admin-defined)'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        domain=[('available_in_pos', '=', True), ('type', '!=', 'service')],
        help='Product that may be given for free.'
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', default=lambda s: s.env.company, required=True
    )

    _sql_constraints = [
        ('uniq_product_company', 'unique(product_id, company_id)',
         'A product can appear only once in the free-item catalogue per company.')
    ]