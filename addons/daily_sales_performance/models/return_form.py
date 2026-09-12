from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.models import Constraint


class DailySalesReturn(models.Model):
    _name = 'daily.sales.return'
    _description = 'Daily Sales Return'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'shaka.access.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='شماره سند', readonly=True, copy=False)
    date = fields.Date(string='تاریخ', required=True, default=fields.Date.context_today, tracking=True)
    branch_id = fields.Many2one(
        'daily.sales.branch', string='شعبه', required=True, tracking=True,
        default=lambda self: self.env.user.daily_sales_branch_id,
    )
    created_by = fields.Many2one(
        'res.users', string='ایجادکننده', required=True, readonly=True,
        default=lambda self: self.env.user, tracking=True,
    )
    state = fields.Selection([
        ('draft', 'پیش‌نویس'), ('submitted', 'ارسال‌شده'),
        ('approved', 'تأییدشده'), ('rejected', 'ردشده'),
    ], string='وضعیت', default='draft', required=True, tracking=True)
    reject_reason = fields.Text(string='دلیل رد', tracking=True)
    line_ids = fields.One2many(
        'daily.sales.return.line', 'return_id', string='جزئیات عودت', copy=True,
    )
    total_returned_amount = fields.Float(
        string='جمع کل مبلغ عودت‌داده‌شده', compute='_compute_total_returned_amount',
    )

    _date_branch_unique = Constraint(
        'unique(branch_id, date)',
        'برای هر شعبه در هر روز فقط یک فرم عودت مجاز است.',
    )

    @api.depends('line_ids.returned_amount')
    def _compute_total_returned_amount(self):
        for record in self:
            record.total_returned_amount = sum(record.line_ids.mapped('returned_amount'))

    @api.model_create_multi
    def create(self, vals_list):
        self._shaka_check_workflow_access('draft', 'create')
        for vals in vals_list:
            vals.setdefault('created_by', self.env.uid)
            if not vals.get('branch_id'):
                branch = self.env.user.daily_sales_branch_id
                if not branch:
                    raise UserError(_('برای کاربر شما هیچ شعبه‌ای تعریف نشده است.'))
                vals['branch_id'] = branch.id
            branch = self.env['daily.sales.branch'].browse(vals['branch_id'])
            allowed_branches = self.env.user.shaka_branch_access_ids.mapped('branch_id')
            if not self.env.user.has_group('base.group_system') and allowed_branches \
                    and branch not in allowed_branches:
                raise AccessError(_('شما اجازه ثبت عودت برای این شعبه را ندارید.'))
            vals.setdefault('name', self.env['ir.sequence'].next_by_code('daily.sales.return') or '/')
        return super().create(vals_list)

    def write(self, vals):
        if self:
            self._shaka_check_workflow_access(self[:1].state, 'write')
        protected = {'name', 'created_by', 'state'}
        if protected & set(vals) and not self.env.user.has_group('base.group_system') \
                and not self.env.context.get('daily_sales_workflow'):
            raise AccessError(_('این فیلدها فقط از طریق گردش‌کار قابل تغییر هستند.'))
        return super().write(vals)

    def unlink(self):
        for record in self:
            record._shaka_check_workflow_access(record.state, 'unlink')
        return super().unlink()

    def action_submit(self):
        self._shaka_check_workflow_access('draft', 'write')
        for record in self:
            if record.state != 'draft':
                raise UserError(_('فقط فرم‌های پیش‌نویس قابل ارسال هستند.'))
            if not record.line_ids:
                raise UserError(_('حداقل یک سطر عودت باید ثبت شود.'))
            record.with_context(daily_sales_workflow=True).write({'state': 'submitted'})

    def action_approve(self):
        self._shaka_check_workflow_access('submitted', 'write')
        for record in self:
            if record.state != 'submitted':
                raise UserError(_('فقط فرم‌های ارسال‌شده قابل تأیید هستند.'))
            record.with_context(daily_sales_workflow=True).write({
                'state': 'approved', 'reject_reason': False,
            })

    def action_reject(self):
        self._shaka_check_workflow_access('submitted', 'write')
        if len(self) != 1 or self.state != 'submitted':
            raise UserError(_('فقط یک فرم ارسال‌شده قابل رد است.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('دلیل رد'),
            'res_model': 'daily.sales.performance.reject.wizard',
            'view_mode': 'form', 'target': 'new',
            'context': {'default_return_id': self.id},
        }

    def _reject_with_reason(self, reason):
        self._shaka_check_workflow_access('submitted', 'write')
        if not reason or not reason.strip():
            raise UserError(_('برای رد کردن، دلیل رد را وارد کنید.'))
        self.ensure_one()
        self.with_context(daily_sales_workflow=True).write({
            'state': 'rejected', 'reject_reason': reason.strip(),
        })

    def action_reset_to_draft(self):
        for record in self:
            record._shaka_check_workflow_access(record.state, 'write')
            record.with_context(daily_sales_workflow=True).write({
                'state': 'draft', 'reject_reason': False,
            })


class DailySalesReturnLine(models.Model):
    _name = 'daily.sales.return.line'
    _description = 'Daily Sales Return Line'
    _order = 'id'

    return_id = fields.Many2one(
        'daily.sales.return', string='فرم عودت', required=True,
        ondelete='cascade', index=True,
    )
    invoice_number = fields.Char(string='شماره فاکتور', required=True)
    customer_name = fields.Char(string='نام و نام خانوادگی', required=True)
    bank_card_number = fields.Char(string='شماره کارت بانکی', required=True)
    phone = fields.Char(string='تلفن', required=True)
    invoice_amount = fields.Float(string='مبلغ فاکتور (ریال)', required=True)
    return_reason = fields.Text(string='دلیل عودت', required=True)
    payment_confirmed = fields.Boolean(string='تأیید پرداخت')
    returned_amount = fields.Float(string='مبلغ عودت‌داده‌شده (ریال)', required=True)
    description = fields.Char(string='توضیحات')

    @api.constrains('invoice_amount', 'returned_amount')
    def _check_amounts(self):
        for line in self:
            if line.invoice_amount < 0 or line.returned_amount < 0:
                raise ValidationError(_('مبالغ نمی‌توانند منفی باشند.'))
            if line.returned_amount > line.invoice_amount:
                raise ValidationError(_('مبلغ عودت‌داده‌شده نمی‌تواند بیشتر از مبلغ فاکتور باشد.'))

    def _check_editable(self):
        for line in self:
            if line.return_id:
                line.return_id._shaka_check_workflow_access(line.return_id.state, 'write')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_editable()
        return records

    def write(self, vals):
        self._check_editable()
        return super().write(vals)

    def unlink(self):
        self._check_editable()
        return super().unlink()
