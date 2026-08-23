# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.models import Constraint

class PosFreeItemCatalog(models.Model):
    """Products that the admin decides can be given for free."""
    _name = 'pos.free.item.catalog'
    _description = 'POS Free-Item Catalogue (admin-defined)'
    _order = 'sequence, name'
    _inherit = ['pos.load.mixin']

    name = fields.Char(related='product_id.display_name', store=True, readonly=True)
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

    _constraints = [
        Constraint(
            'unique(product_id, company_id)',
            'A product can appear only once in the free-item catalogue per company.'
        )
    ]

    @api.model
    def _load_pos_data_domain(self, data, config):
        return [
            ('active', '=', True),
            ('company_id', '=', config.company_id.id),
        ]

    @api.model
    def _load_pos_data_fields(self, config):
        return ['id', 'product_id', 'sequence']
