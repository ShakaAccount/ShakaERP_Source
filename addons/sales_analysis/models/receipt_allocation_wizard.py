from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SalesAnalysisReceiptAllocationWizard(models.TransientModel):
    _name = 'sales.analysis.receipt.allocation.wizard'
    _description = 'تخصیص رسید به فاکتورها'

    analysis_id = fields.Many2one('sales.analysis', required=True, readonly=True)
    customer_id = fields.Many2one(related='analysis_id.customer_id', readonly=True)
    receipt_id = fields.Many2one('sales.analysis.receipt', string='رسید دریافت', required=True, readonly=True)
    receipt_amount = fields.Float(related='receipt_id.amount', string='مبلغ رسید', readonly=True)
    receipt_preview = fields.Char(related='receipt_id.receipt_preview', string='پیش‌نمایش رسید', readonly=True)
    receipt_description = fields.Text(related='receipt_id.description', string='توضیحات رسید', readonly=True)
    line_ids = fields.One2many('sales.analysis.receipt.allocation.wizard.line', 'wizard_id', string='فاکتورها')
    allocated_amount = fields.Float(compute='_compute_amounts', string='تخصیص‌یافته')
    remaining_amount = fields.Float(compute='_compute_amounts', string='مانده رسید')

    @api.depends('line_ids.allocated_amount')
    def _compute_amounts(self):
        for record in self:
            record.allocated_amount = sum(record.line_ids.mapped('allocated_amount'))
            record.remaining_amount = record.receipt_amount - record.allocated_amount

    def action_save(self):
        self.ensure_one()
        if self.allocated_amount < 0 or self.allocated_amount > self.receipt_amount:
            raise ValidationError(_('جمع تخصیص‌ها باید بین صفر و مبلغ رسید باشد.'))
        self.analysis_id.allocation_ids.filtered(
            lambda line: line.receipt_id == self.receipt_id
        ).unlink()
        self.env['sales.analysis.allocation'].create([
            {
                'analysis_id': self.analysis_id.id,
                'receipt_id': line.receipt_id.id,
                'sale_id': line.sale_id.id,
                'allocated_amount': line.allocated_amount,
            }
            for line in self.line_ids if line.allocated_amount
        ])
        return {'type': 'ir.actions.act_window_close'}


class SalesAnalysisReceiptAllocationWizardLine(models.TransientModel):
    _name = 'sales.analysis.receipt.allocation.wizard.line'
    _description = 'ردیف تخصیص رسید'

    wizard_id = fields.Many2one('sales.analysis.receipt.allocation.wizard', required=True, ondelete='cascade')
    receipt_id = fields.Many2one(related='wizard_id.receipt_id', readonly=True)
    customer_id = fields.Many2one(related='wizard_id.customer_id', readonly=True)
    sale_id = fields.Many2one('sales.analysis.sale', string='فاکتور فروش', required=True)
    invoice_preview = fields.Char(related='sale_id.invoice_preview', string='پیش‌نمایش فاکتور', readonly=True)
    invoice_amount = fields.Float(related='sale_id.sum_final', string='مبلغ فاکتور', readonly=True)
    invoice_remaining = fields.Float(related='sale_id.remaining', string='مانده فاکتور', readonly=True)
    allocated_amount = fields.Float(string='مبلغ تخصیص', required=True)

    @api.onchange('sale_id')
    def _onchange_sale_id(self):
        if self.sale_id:
            self.allocated_amount = min(
                self.invoice_remaining or self.invoice_amount,
                self.wizard_id.remaining_amount,
            )
