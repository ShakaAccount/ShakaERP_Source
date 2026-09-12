from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DailySalesPerformanceRejectWizard(models.TransientModel):
    _name = 'daily.sales.performance.reject.wizard'
    _description = 'Daily Sales Performance Reject Wizard'

    performance_id = fields.Many2one('daily.sales.performance', readonly=True)
    deposit_split_id = fields.Many2one('daily.sales.deposit.split', readonly=True)
    corrective_invoice_id = fields.Many2one('daily.sales.corrective.invoice', readonly=True)
    return_id = fields.Many2one('daily.sales.return', readonly=True)
    reason = fields.Text(string='دلیل رد', required=True)

    @api.constrains('performance_id', 'deposit_split_id', 'corrective_invoice_id', 'return_id')
    def _check_target(self):
        for wizard in self:
            targets = [wizard.performance_id, wizard.deposit_split_id, wizard.corrective_invoice_id, wizard.return_id]
            if sum(bool(target) for target in targets) != 1:
                raise ValidationError('باید دقیقاً یک فرم برای رد انتخاب شود.')

    def action_confirm(self):
        self.ensure_one()
        if self.performance_id:
            self.performance_id._reject_with_reason(self.reason)
        elif self.deposit_split_id:
            self.deposit_split_id._reject_with_reason(self.reason)
        elif self.corrective_invoice_id:
            self.corrective_invoice_id._reject_with_reason(self.reason)
        else:
            self.return_id._reject_with_reason(self.reason)
        return {'type': 'ir.actions.act_window_close'}
