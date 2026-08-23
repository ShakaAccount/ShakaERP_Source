# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    free_item_daily_limit = fields.Integer(
        string='Daily Free Item Limit',
        default=0,
        help='Maximum number of free items this employee can claim per day. '
             '0 means use the POS configuration default (or global default of 2).'
    )


class PosConfig(models.Model):
    _inherit = 'pos.config'

    free_item_daily_limit = fields.Integer(
        string='Default Daily Free Item Limit',
        default=0,
        help='Default maximum number of free items an employee can claim per day '
             'at this POS. 0 means use global default of 2. '
             'Employee-specific limit takes precedence.'
    )