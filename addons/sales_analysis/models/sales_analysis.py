from odoo import api, fields, models, _
from odoo.models import Constraint
from odoo.exceptions import ValidationError


def _gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100)
            + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1])
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        return jy, 1 + (days // 31), 1 + (days % 31)
    return jy, 7 + ((days - 186) // 30), 1 + ((days - 186) % 30)


class SalesAnalysis(models.Model):
    _name = 'sales.analysis'
    _description = 'Sales Analysis'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'shaka.access.mixin']
    _rec_name = 'number'
    _order = 'id desc'

    number = fields.Char(string='شماره', readonly=True, copy=False)
    sequence_no = fields.Integer(string='ترتیب سالانه', readonly=True, copy=False)
    jalali_year = fields.Integer(string='سال شمسی', readonly=True, copy=False)
    date_from = fields.Date(string='از تاریخ', required=True)
    date_to = fields.Date(string='تا تاریخ', required=True)
    description = fields.Text(string='توضیحات')
    customer_id = fields.Many2one('sales.analysis.customer', string='مشتری', required=True)
    receipt_link_ids = fields.One2many('sales.analysis.receipt.link', 'analysis_id', string='رسیدهای دریافت', copy=True)
    allocation_ids = fields.One2many('sales.analysis.allocation', 'analysis_id', string='تخصیص‌ها', copy=True)
    total_receipts = fields.Float(compute='_compute_totals', string='جمع رسیدها')
    total_allocated = fields.Float(compute='_compute_totals', string='جمع تخصیص')
    total_unallocated = fields.Float(compute='_compute_totals', string='مانده تخصیص')

    _year_sequence_unique = Constraint(
        'unique(jalali_year, sequence_no)',
        'شماره آنالیز در هر سال شمسی باید یکتا باشد.',
    )

    @api.depends('receipt_link_ids.receipt_amount', 'allocation_ids.allocated_amount')
    def _compute_totals(self):
        for record in self:
            record.total_receipts = sum(record.receipt_link_ids.mapped('receipt_amount'))
            record.total_allocated = sum(record.allocation_ids.mapped('allocated_amount'))
            record.total_unallocated = record.total_receipts - record.total_allocated

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from and record.date_to and record.date_from > record.date_to:
                raise ValidationError(_('Start date cannot be after end date.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            date_from = fields.Date.to_date(vals.get('date_from')) or fields.Date.context_today(self)
            jalali_year = _gregorian_to_jalali(date_from.year, date_from.month, date_from.day)[0]
            vals['jalali_year'] = jalali_year
            vals['sequence_no'] = self._next_sequence(jalali_year)
            vals['number'] = str(vals['sequence_no'])
        return super().create(vals_list)

    def _next_sequence(self, jalali_year):
        self.env.cr.execute(
            'SELECT pg_advisory_xact_lock(hashtext(%s))',
            [f'sales-analysis:{jalali_year}'],
        )
        self.env.cr.execute(
            '''SELECT COALESCE(MAX(sequence_no), 0) + 1
               FROM sales_analysis
               WHERE jalali_year = %s''',
            [jalali_year],
        )
        return self.env.cr.fetchone()[0]

class SalesAnalysisAllocation(models.Model):
    _name = 'sales.analysis.allocation'
    _description = 'Receipt to invoice allocation'
    _order = 'id'

    analysis_id = fields.Many2one('sales.analysis', required=True, ondelete='cascade')
    receipt_id = fields.Many2one('sales.analysis.receipt', string='Receipt', required=True)
    sale_id = fields.Many2one('sales.analysis.sale', string='Sales Invoice', required=True)
    receipt_amount = fields.Float(related='receipt_id.amount', string='Receipt Amount', readonly=True)
    receipt_preview = fields.Char(related='receipt_id.receipt_preview', string='پیش‌نمایش رسید', readonly=True)
    receipt_description = fields.Text(related='receipt_id.description', string='توضیحات رسید', readonly=True)
    invoice_amount = fields.Float(related='sale_id.sum_final', string='Invoice Amount', readonly=True)
    invoice_remaining = fields.Float(related='sale_id.remaining', string='Invoice Remaining', readonly=True)
    invoice_preview = fields.Char(related='sale_id.invoice_preview', string='پیش‌نمایش فاکتور', readonly=True)
    allocated_amount = fields.Float(string='Allocated Amount', required=True)
    description = fields.Char(string='Description')

    @api.constrains('allocated_amount', 'receipt_id', 'sale_id')
    def _check_amounts(self):
        for line in self:
            if line.allocated_amount < 0:
                raise ValidationError(_('Allocation amount cannot be negative.'))
            if line.receipt_amount and line.allocated_amount > line.receipt_amount:
                raise ValidationError(_('Allocation cannot exceed receipt amount.'))
            if line.invoice_remaining and line.allocated_amount > line.invoice_remaining:
                raise ValidationError(_('Allocation cannot exceed invoice remaining amount.'))


class SalesAnalysisReceiptLink(models.Model):
    _name = 'sales.analysis.receipt.link'
    _description = 'Receipt selected for sales analysis'
    _order = 'id'

    analysis_id = fields.Many2one('sales.analysis', required=True, ondelete='cascade')
    customer_id = fields.Many2one(related='analysis_id.customer_id', readonly=True)
    receipt_id = fields.Many2one('sales.analysis.receipt', string='Receipt', required=True, ondelete='restrict',
                                 domain="[('customer_id', '=', customer_id)]")
    receipt_amount = fields.Float(related='receipt_id.amount', string='Receipt Amount', readonly=True)
    receipt_preview = fields.Char(related='receipt_id.receipt_preview', string='پیش‌نمایش رسید', readonly=True)
    receipt_description = fields.Text(related='receipt_id.description', string='توضیحات رسید', readonly=True)
    allocated_amount = fields.Float(compute='_compute_amounts', string='Allocated')
    remaining_amount = fields.Float(compute='_compute_amounts', string='Remaining')

    _sql_constraints = [
        ('analysis_receipt_unique', 'unique(analysis_id, receipt_id)', 'A receipt can be selected only once per analysis.'),
    ]

    @api.depends('analysis_id.allocation_ids.allocated_amount', 'receipt_id.amount')
    def _compute_amounts(self):
        for record in self:
            lines = record.analysis_id.allocation_ids.filtered(lambda line: line.receipt_id.id == record.receipt_id.id)
            record.allocated_amount = sum(lines.mapped('allocated_amount'))
            record.remaining_amount = record.receipt_amount - record.allocated_amount

    def action_open_allocation(self):
        self.ensure_one()
        wizard = self.env['sales.analysis.receipt.allocation.wizard'].create({
            'analysis_id': self.analysis_id.id,
            'receipt_id': self.receipt_id.id,
        })
        existing = self.analysis_id.allocation_ids.filtered(lambda line: line.receipt_id.id == self.receipt_id.id)
        wizard.line_ids = [(0, 0, {'sale_id': line.sale_id.id, 'allocated_amount': line.allocated_amount}) for line in existing]
        return {
            'type': 'ir.actions.act_window',
            'name': 'Allocate Receipt to Invoices',
            'res_model': 'sales.analysis.receipt.allocation.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }
