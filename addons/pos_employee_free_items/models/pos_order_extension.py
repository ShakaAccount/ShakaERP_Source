# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class PosOrder(models.Model):
    _inherit = 'pos.order'

    free_item_line_ids = fields.One2many(
        'pos.order.line', 'order_id',
        domain=[('is_free_item', '=', True)],
        string='Free-Item Lines'
    )

class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    is_free_item = fields.Boolean(
        string='Free Item',
        help='True when this line was added via the employee free-item flow.'
    )
    free_item_allowance_id = fields.Many2one(
        'employee.free.allowance',
        string='Free-Item Allowance',
        ondelete='set null',
        readonly=True,
    )