from collections import OrderedDict
from datetime import datetime, time

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class DailySalesDepositSplit(models.Model):
    _name = 'daily.sales.deposit.split'
    _description = 'Daily Sales Deposit Split'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'shaka.access.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='شماره', readonly=True, copy=False)
    performance_id = fields.Many2one(
        'daily.sales.performance', string='عملکرد روزانه', required=True,
        domain="[]", tracking=True,
    )
    date = fields.Date(string='تاریخ', related='performance_id.date', store=True, readonly=True)
    branch_id = fields.Many2one(
        'daily.sales.branch', string='شعبه', related='performance_id.branch_id',
        store=True, readonly=True,
    )
    state = fields.Selection([
        ('draft', 'پیش‌نویس'), ('submitted', 'ارسال‌شده'),
        ('approved', 'تأییدشده'), ('rejected', 'ردشده'),
    ], string='وضعیت', default='draft', required=True, tracking=True)
    created_by = fields.Many2one(
        'res.users', string='ثبت‌کننده', required=True, readonly=True,
        default=lambda self: self.env.user,
    )
    pos_line_ids = fields.One2many(
        'daily.sales.deposit.split.pos', 'split_id', string='پوزها', copy=True,
    )
    deposit_line_ids = fields.One2many(
        'daily.sales.deposit.line', 'split_id', string='واریزی‌ها', copy=True,
    )
    total_pos_amount = fields.Float(string='جمع مبلغ پوز', compute='_compute_totals')
    total_deposit_amount = fields.Float(string='جمع واریزی', compute='_compute_totals')
    balance_amount = fields.Float(string='مانده', compute='_compute_totals')
    reject_reason = fields.Text(string='دلیل رد')

    @api.depends('pos_line_ids.pos_amount', 'deposit_line_ids.deposit_amount')
    def _compute_totals(self):
        for record in self:
            record.total_pos_amount = sum(record.pos_line_ids.mapped('pos_amount'))
            record.total_deposit_amount = sum(record.deposit_line_ids.mapped('deposit_amount'))
            record.balance_amount = record.total_pos_amount - record.total_deposit_amount

    @api.onchange('performance_id')
    def _onchange_performance_id(self):
        for record in self:
            if record.performance_id:
                record.pos_line_ids = record._prepare_pos_commands()
                record.deposit_line_ids = [(5, 0, 0)]

    @api.model_create_multi
    def create(self, vals_list):
        self._shaka_check_workflow_access('draft', 'create')
        for vals in vals_list:
            if vals.get('performance_id'):
                performance = self.env['daily.sales.performance'].browse(vals['performance_id'])
                if False and performance.state != 'approved':
                    raise UserError(_('فقط عملکردهای تأییدشده قابل تفکیک واریزی هستند.'))
                if self.search_count([('performance_id', '=', performance.id)]):
                    raise UserError(_('برای این عملکرد قبلاً فرم تفکیک واریزی ساخته شده است.'))
            vals.setdefault('name', self.env['ir.sequence'].next_by_code('daily.sales.deposit.split') or '/')
            vals.setdefault('created_by', self.env.uid)
        records = super().create(vals_list)
        for record in records:
            if not record.pos_line_ids and record.performance_id:
                record._copy_performance_pos_lines()
        return records

    def _copy_performance_pos_lines(self):
        self.ensure_one()
        self.pos_line_ids = self._prepare_pos_commands()

    def _prepare_pos_commands(self):
        """Copy the selected performance POS values grouped by terminal."""
        self.ensure_one()
        grouped = OrderedDict()
        for line in self.performance_id.pos_line_ids:
            terminal = (line.terminal_number or '').strip()
            if terminal not in grouped:
                grouped[terminal] = {
                    'terminal_number': terminal,
                    'pos_amount': 0.0,
                    'performance_pos_id': line.id,
                }
            grouped[terminal]['pos_amount'] += line.pos_amount or 0.0
        return [(0, 0, values) for values in grouped.values()]

    def _check_editable(self):
        for record in self:
            record._shaka_check_workflow_access(record.state, 'write')

    def write(self, vals):
        if self:
            self._shaka_check_workflow_access(self[:1].state, 'write')
        self._check_editable()
        if 'performance_id' in vals:
            raise UserError(_('عملکرد مرتبط پس از ایجاد قابل تغییر نیست.'))
        return super().write(vals)

    def unlink(self):
        for record in self:
            record._shaka_check_workflow_access(record.state, 'unlink')
        return super().unlink()

    def action_submit(self):
        self._shaka_check_workflow_access('draft', 'write')
        self._check_editable()
        for record in self:
            if not record.pos_line_ids:
                raise UserError(_('حداقل یک پوز باید وجود داشته باشد.'))
            if record.state != 'draft':
                raise UserError(_('فقط فرم پیش‌نویس قابل ارسال است.'))
            record.write({'state': 'submitted'})

    def action_approve(self):
        self._shaka_check_workflow_access('submitted', 'write')
        self.write({'state': 'approved'})

    def action_reject(self):
        self._shaka_check_workflow_access('submitted', 'write')
        if len(self) != 1:
            raise UserError(_('لطفاً رد کردن را برای هر رکورد جداگانه انجام دهید.'))
        if self.state != 'submitted':
            raise UserError(_('فقط فرم‌های ارسال‌شده قابل رد هستند.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('دلیل رد'),
            'res_model': 'daily.sales.performance.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_deposit_split_id': self.id},
        }

    def _reject_with_reason(self, reason):
        self._shaka_check_workflow_access('submitted', 'write')
        if not reason or not reason.strip():
            raise UserError(_('برای رد کردن تفکیک واریزی، دلیل رد را وارد کنید.'))
        self.ensure_one()
        self.with_context(daily_sales_workflow=True).write({
            'state': 'rejected',
            'reject_reason': reason.strip(),
        })
        self.message_post(body=_('تفکیک واریزی توسط %s رد شد.') % self.env.user.name)
        self.write({'state': 'rejected'})


class DailySalesDepositSplitPos(models.Model):
    _name = 'daily.sales.deposit.split.pos'
    _description = 'Deposit Split POS'

    split_id = fields.Many2one('daily.sales.deposit.split', required=True, ondelete='cascade')
    performance_pos_id = fields.Many2one('daily.sales.pos.line', string='پوز عملکرد', readonly=True)
    terminal_number = fields.Char(string='شماره ترمینال پوز', readonly=True)
    pos_amount = fields.Float(string='مبلغ پوز (ریال)', readonly=True)
    deposit_line_ids = fields.One2many('daily.sales.deposit.line', 'split_pos_id', string='واریزی‌ها')
    total_deposit_amount = fields.Float(string='جمع واریزی', compute='_compute_total')
    balance_amount = fields.Float(string='مانده', compute='_compute_total')

    @api.depends(
        'deposit_line_ids.deposit_amount', 'pos_amount',
        'split_id.deposit_line_ids.deposit_amount',
        'split_id.deposit_line_ids.performance_pos_id',
    )
    def _compute_total(self):
        for record in self:
            lines = record.split_id.deposit_line_ids.filtered(
                lambda line: line.split_pos_id == record
                or line.performance_pos_id == record.performance_pos_id
            )
            record.total_deposit_amount = sum(lines.mapped('deposit_amount'))
            record.balance_amount = record.pos_amount - record.total_deposit_amount


class DailySalesDepositLine(models.Model):
    _name = 'daily.sales.deposit.line'
    _description = 'POS Deposit Line'
    _order = 'deposit_datetime, id'

    split_id = fields.Many2one('daily.sales.deposit.split', required=True, ondelete='cascade')
    split_pos_id = fields.Many2one(
        'daily.sales.deposit.split.pos', string='ترمینال واسط',
        domain="[('split_id', '=', split_id)]",
    )
    performance_pos_id = fields.Many2one(
        'daily.sales.pos.line', string='ترمینال پوز', required=True,
        domain="[('performance_id', '=', split_id.performance_id)]",
    )
    terminal_number = fields.Char(
        related='performance_pos_id.terminal_number', string='شماره ترمینال', readonly=True,
    )
    deposit_datetime = fields.Datetime(string='تاریخ و ساعت واریز', readonly=True)
    deposit_date = fields.Date(
        string='تاریخ واریز', compute='_compute_datetime_parts',
        inverse='_inverse_date', store=True,
    )
    deposit_time = fields.Float(
        string='ساعت واریز', compute='_compute_datetime_parts',
        inverse='_inverse_time', store=True,
    )
    deposit_amount = fields.Float(string='مبلغ واریزی (ریال)', required=True)
    description = fields.Char(string='توضیحات')

    @api.depends('deposit_datetime')
    def _compute_datetime_parts(self):
        for line in self:
            value = fields.Datetime.to_datetime(line.deposit_datetime)
            line.deposit_date = value.date() if value else fields.Date.context_today(line)
            line.deposit_time = (value.hour + value.minute / 60.0) if value else 0.0

    def _set_datetime_from_parts(self):
        for line in self:
            if not line.deposit_date:
                continue
            total_minutes = max(0, min(1439, round((line.deposit_time or 0.0) * 60)))
            hours, minutes = divmod(total_minutes, 60)
            line.deposit_datetime = datetime.combine(
                fields.Date.to_date(line.deposit_date), time(hours, minutes),
            )

    def _inverse_date(self):
        self._set_datetime_from_parts()

    def _inverse_time(self):
        self._set_datetime_from_parts()


    @api.constrains('deposit_amount')
    def _check_amount(self):
        if any(line.deposit_amount < 0 for line in self):
            raise ValidationError(_('مبلغ واریزی نمی‌تواند منفی باشد.'))

    @api.constrains('deposit_time')
    def _check_time(self):
        if any(line.deposit_time < 0 or line.deposit_time >= 24 for line in self):
            raise ValidationError(_('ساعت واریز باید بین ۰۰:۰۰ تا ۲۳:۵۹ باشد.'))

    @api.onchange('split_pos_id')
    def _onchange_split_pos(self):
        for line in self:
            if line.split_pos_id:
                line.split_id = line.split_pos_id.split_id

    @api.constrains('performance_pos_id', 'split_id')
    def _check_performance_pos(self):
        for line in self:
            if line.performance_pos_id and line.split_id \
                    and line.performance_pos_id.performance_id != line.split_id.performance_id:
                raise ValidationError(_('ترمینال انتخاب‌شده متعلق به عملکرد این فرم نیست.'))
