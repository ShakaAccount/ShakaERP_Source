from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.models import Constraint


class DailySalesTip(models.Model):
    _name = 'daily.sales.tip'
    _description = 'Daily Sales Tip'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'shaka.access.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='شماره سند', readonly=True, copy=False)
    date = fields.Date(string='تاریخ', required=True, default=fields.Date.context_today, tracking=True)
    branch_id = fields.Many2one(
        'daily.sales.branch', string='شعبه', required=True, tracking=True,
        default=lambda self: self.env.user.daily_sales_branch_id,
    )
    created_by = fields.Many2one(
        'res.users', string='ثبت‌کننده', required=True, readonly=True,
        default=lambda self: self.env.user, tracking=True,
    )
    state = fields.Selection([
        ('draft', 'پیش‌نویس'), ('submitted', 'ارسال‌شده'),
        ('approved', 'تأییدشده'), ('rejected', 'ردشده'),
    ], string='وضعیت', default='draft', required=True, tracking=True)
    reject_reason = fields.Text(string='دلیل رد', tracking=True)
    pos_tip_amount = fields.Float(string='انعام پوز (ریال)', tracking=True)
    cash_tip_amount = fields.Float(string='انعام نقد (ریال)', tracking=True)
    total_tip_amount = fields.Float(
        string='جمع کل انعام', compute='_compute_total_tip_amount',
    )

    _date_branch_unique = Constraint(
        'unique(branch_id, date)',
        'برای هر شعبه در هر تاریخ فقط یک فرم انعام مجاز است.',
    )

    @api.depends('pos_tip_amount', 'cash_tip_amount')
    def _compute_total_tip_amount(self):
        for record in self:
            record.total_tip_amount = record.pos_tip_amount + record.cash_tip_amount

    @api.constrains('pos_tip_amount', 'cash_tip_amount')
    def _check_amounts(self):
        for record in self:
            if record.pos_tip_amount < 0 or record.cash_tip_amount < 0:
                raise ValidationError(_('مبالغ انعام نمی‌توانند منفی باشند.'))

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
                raise AccessError(_('شما اجازه ثبت انعام برای این شعبه را ندارید.'))
            vals.setdefault('name', self.env['ir.sequence'].next_by_code('daily.sales.tip') or '/')
        return super().create(vals_list)

    def write(self, vals):
        if self:
            self._shaka_check_workflow_access(self[:1].state, 'write')
        if not self.env.user.has_group('base.group_system') \
                and {'state', 'name', 'created_by'} & set(vals):
            raise UserError(_('این فیلدها فقط از طریق گردش‌کار قابل تغییر هستند.'))
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
            record.with_context(daily_sales_workflow=True).write({'state': 'submitted'})

    def action_approve(self):
        self._shaka_check_workflow_access('submitted', 'write')
        self.with_context(daily_sales_workflow=True).write({
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
            'context': {'default_tip_id': self.id},
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
