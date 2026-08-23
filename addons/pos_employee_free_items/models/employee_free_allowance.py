# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.models import Constraint

class EmployeeFreeAllowance(models.Model):
    """Tracks how many free items an employee has already taken today."""
    _name = 'employee.free.allowance'
    _description = 'Employee Daily Free-Item Allowance'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', required=True, ondelete='cascade')
    date = fields.Date(default=fields.Date.context_today, required=True)
    used_qty = fields.Integer(default=0, help='Number of free items already claimed today')
    company_id = fields.Many2one(
        'res.company', default=lambda s: s.env.company, required=True
    )

    _constraints = [
        Constraint(
            'unique(employee_id, date, company_id)',
            'Only one allowance record per employee per day per company.'
        )
    ]

    @api.model
    def _get_daily_limit(self, employee, config=None):
        """Return the daily free-item limit for an employee.
        
        Priority: employee.free_item_daily_limit > config.free_item_daily_limit > 2 (default)
        """
        if employee.free_item_daily_limit:
            return employee.free_item_daily_limit
        if config and config.free_item_daily_limit:
            return config.free_item_daily_limit
        return 2

    @api.model
    def _get_or_create_allowance(self, employee):
        """Return today's allowance record, creating it if necessary."""
        today = fields.Date.context_today(self)
        rec = self.search([
            ('employee_id', '=', employee.id),
            ('date', '=', today),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        if not rec:
            rec = self.create({
                'employee_id': employee.id,
                'date': today,
                'company_id': self.env.company.id,
            })
        return rec

    @api.model
    def claim_for_employee(self, employee, qty=1, config=None):
        """Consume allowance slots for an employee, or raise a user-facing error."""
        allowance = self._get_or_create_allowance(employee)
        allowance.claim_free_items(qty, config)
        return allowance

    def claim_free_items(self, qty=1, config=None):
        """Increment used_qty by qty, raise if limit exceeded."""
        self.ensure_one()
        limit = self._get_daily_limit(self.employee_id, config)
        if self.used_qty + qty > limit:
            raise UserError(_(
                'You have already claimed your %s free items for today (limit: %s).'
            ) % (self.used_qty, limit))
        self.used_qty += qty
        return True
