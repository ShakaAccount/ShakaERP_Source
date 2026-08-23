# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.models import Constraint

class EmployeeFreeAllowance(models.Model):
    """Tracks how many free items an employee has already taken today."""
    _name = 'employee.free.allowance'
    _description = 'Employee Daily Free-Item Allowance (max 2)'
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

    MAX_PER_DAY = 2

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
    def claim_for_employee(self, employee):
        """Consume one allowance slot for an employee, or raise a user-facing error."""
        allowance = self._get_or_create_allowance(employee)
        allowance.claim_free_item()
        return allowance

    def claim_free_item(self):
        """Increment used_qty, raise if limit exceeded."""
        self.ensure_one()
        if self.used_qty >= self.MAX_PER_DAY:
            raise UserError(_(
                'You have already claimed your %s free items for today.'
            ) % self.MAX_PER_DAY)
        self.used_qty += 1
        return True
