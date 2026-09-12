import datetime as dt

from odoo import api, fields, models, _
from odoo.models import Constraint
from odoo.exceptions import AccessError, UserError, ValidationError


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


class DailySalesPerformance(models.Model):
    _name = 'daily.sales.performance'
    _description = 'Daily Sales Performance'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'shaka.access.mixin']
    _rec_name = 'number'
    _order = 'date desc, id desc'

    # Generated server-side from the Jalali year and must not be required in
    # the web client before the first save (readonly + required + empty causes
    # Odoo to show "Missing required fields").
    number = fields.Char(string='شماره', readonly=True, copy=False)
    sequence_no = fields.Integer(string='ترتیب سالانه', readonly=True, copy=False)
    jalali_year = fields.Integer(string='سال شمسی', readonly=True, copy=False)
    date = fields.Date(
        string='تاریخ', required=True, default=fields.Date.context_today,
        tracking=True,
    )
    branch_id = fields.Many2one(
        'daily.sales.branch', string='شعبه', required=True, tracking=True,
        domain="[]",
        default=lambda self: self.env.user.daily_sales_branch_id,
    )
    created_by = fields.Many2one(
        'res.users', string='ثبت‌کننده', required=True, readonly=True,
        default=lambda self: self.env.user, tracking=True,
    )
    description = fields.Text(string='توضیحات')
    state = fields.Selection([
        ('draft', 'پیش‌نویس'),
        ('submitted', 'ارسال‌شده'),
        ('approved', 'تأییدشده'),
        ('rejected', 'ردشده'),
    ], string='وضعیت', default='draft', required=True, tracking=True)
    reject_reason = fields.Text(string='دلیل رد', tracking=True)
    submitted_by = fields.Many2one('res.users', string='ارسال‌کننده', readonly=True, copy=False)
    submitted_date = fields.Datetime(string='زمان ارسال', readonly=True, copy=False)
    approved_by = fields.Many2one('res.users', string='تأییدکننده', readonly=True, copy=False)
    approved_date = fields.Datetime(string='زمان تأیید', readonly=True, copy=False)
    rejected_by = fields.Many2one('res.users', string='ردکننده', readonly=True, copy=False)
    rejected_date = fields.Datetime(string='زمان رد', readonly=True, copy=False)

    revenue_line_ids = fields.One2many(
        'daily.sales.revenue', 'performance_id', string='درآمدهای روزانه',
        copy=True,
    )
    pos_line_ids = fields.One2many(
        'daily.sales.pos.line', 'performance_id', string='ترمینال‌های پوز',
        copy=True,
    )
    total_revenue = fields.Float(string='جمع کل درآمدها', compute='_compute_totals')
    total_pos_amount = fields.Float(string='جمع کل پوز', compute='_compute_totals')

    @api.depends('number')
    def _compute_display_name(self):
        for record in self:
            record.display_name = record.number or _('عملکرد روزانه جدید')

    _branch_date_unique = Constraint(
        'unique(branch_id, date)',
        'برای هر شعبه در هر تاریخ فقط یک عملکرد روزانه مجاز است.',
    )
    _year_sequence_unique = Constraint(
        'unique(jalali_year, sequence_no)',
        'شماره عملکرد در هر سال شمسی باید یکتا باشد.',
    )

    @api.depends('revenue_line_ids.total_revenue', 'pos_line_ids.pos_amount')
    def _compute_totals(self):
        for record in self:
            record.total_revenue = sum(record.revenue_line_ids.mapped('total_revenue'))
            record.total_pos_amount = sum(record.pos_line_ids.mapped('pos_amount'))

    @api.onchange('date')
    def _onchange_date(self):
        if self.date:
            self.jalali_year = _gregorian_to_jalali(
                self.date.year, self.date.month, self.date.day
            )[0]

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
            if not self.env.user.has_group('base.group_system') \
                    and allowed_branches \
                    and branch not in allowed_branches:
                raise AccessError(_('شما اجازه ثبت عملکرد برای این شعبه را ندارید.'))
            date = fields.Date.to_date(vals.get('date')) or fields.Date.context_today(self)
            jalali_year = _gregorian_to_jalali(date.year, date.month, date.day)[0]
            vals['jalali_year'] = jalali_year
            vals['sequence_no'] = self._next_sequence(jalali_year)
            vals['number'] = str(vals['sequence_no'])
        records = super().create(vals_list)
        for record in records:
            self.env['daily.sales.revenue'].create({'performance_id': record.id})
            record.message_post(body=_('عملکرد روزانه %s ثبت شد.') % record.number)
        return records

    def _next_sequence(self, jalali_year):
        # Serialize numbering per year so two simultaneous creates do not
        # receive the same number.
        self.env.cr.execute(
            'SELECT pg_advisory_xact_lock(hashtext(%s))',
            [f'daily-sales:{jalali_year}'],
        )
        self.env.cr.execute(
            '''SELECT COALESCE(MAX(sequence_no), 0) + 1
               FROM daily_sales_performance
               WHERE jalali_year = %s''',
            [jalali_year],
        )
        return self.env.cr.fetchone()[0]

    def write(self, vals):
        if self:
            self._shaka_check_workflow_access(self[:1].state, 'write')
        workflow_write = self.env.context.get('daily_sales_workflow')
        protected = {'number', 'sequence_no', 'jalali_year', 'created_by', 'state',
                     'submitted_by', 'submitted_date', 'approved_by',
                     'approved_date', 'rejected_by', 'rejected_date'}
        if protected & set(vals) and not workflow_write \
                and not self.env.user.has_group('base.group_system'):
            raise AccessError(_('این فیلدها فقط توسط عملیات گردش‌کار قابل تغییر هستند.'))
        return super().write(vals)

    def unlink(self):
        for record in self:
            record._shaka_check_workflow_access(record.state, 'unlink')
        return super().unlink()

    def action_submit(self):
        self._shaka_check_workflow_access('draft', 'write')
        for record in self:
            if record.state != 'draft':
                raise UserError(_('فقط عملکردهای پیش‌نویس قابل ارسال هستند.'))
            if len(record.revenue_line_ids) != 1:
                raise UserError(_('باید دقیقاً یک ردیف درآمد برای فرم ثبت شود.'))
            record.with_context(daily_sales_workflow=True).write({
                'state': 'submitted',
                'submitted_by': self.env.user.id,
                'submitted_date': fields.Datetime.now(),
            })
            record.message_post(body=_('عملکرد برای بررسی تأمین ارسال شد.'))

    def action_approve(self):
        self._shaka_check_workflow_access('submitted', 'write')
        for record in self:
            if record.state != 'submitted':
                raise UserError(_('فقط عملکردهای ارسال‌شده قابل تأیید هستند.'))
            record.with_context(daily_sales_workflow=True).write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now(),
                'reject_reason': False,
            })
            record.message_post(body=_('عملکرد توسط %s تأیید شد.') % self.env.user.name)

    def action_reject(self):
        self._shaka_check_workflow_access('submitted', 'write')
        if len(self) != 1:
            raise UserError(_('لطفاً رد کردن را برای هر رکورد جداگانه انجام دهید.'))
        if self.state != 'submitted':
            raise UserError(_('فقط عملکردهای ارسال‌شده قابل رد هستند.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('دلیل رد'),
            'res_model': 'daily.sales.performance.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_performance_id': self.id},
        }

    def _reject_with_reason(self, reason):
        self._shaka_check_workflow_access('submitted', 'write')
        if not reason or not reason.strip():
            raise UserError(_('برای رد کردن عملکرد، دلیل رد را وارد کنید.'))
        self.ensure_one()
        self.with_context(daily_sales_workflow=True).write({
            'state': 'rejected',
            'reject_reason': reason.strip(),
            'rejected_by': self.env.user.id,
            'rejected_date': fields.Datetime.now(),
        })
        self.message_post(body=_('عملکرد توسط %s رد شد.') % self.env.user.name)

    def action_reset_to_draft(self):
        for record in self:
            record._shaka_check_workflow_access(record.state, 'write')
            record.with_context(daily_sales_workflow=True).write({
                'state': 'draft', 'reject_reason': False,
            })

    @api.constrains('date', 'branch_id')
    def _check_date_branch(self):
        for record in self:
            allowed_branches = self.env.user.shaka_branch_access_ids.mapped('branch_id')
            if record.date and record.branch_id and record.created_by \
                    and not self.env.user.has_group('base.group_system') \
                    and allowed_branches \
                    and record.branch_id not in allowed_branches:
                raise ValidationError(_('شعبه انتخاب‌شده به کاربر شما تخصیص داده نشده است.'))


class DailySalesRevenue(models.Model):
    _name = 'daily.sales.revenue'
    _description = 'Daily Sales Revenue'

    performance_id = fields.Many2one(
        'daily.sales.performance', string='عملکرد روزانه', required=True,
        ondelete='cascade', index=True,
    )
    cash_amount = fields.Float(string='مبلغ نقد روز دریافتی')
    snapp_amount = fields.Float(string='مبلغ اسنپ')
    foodro_amount = fields.Float(string='مبلغ فودرو')
    payment_link_amount = fields.Float(string='مبلغ لینک پرداخت')
    website_amount = fields.Float(string='مبلغ وب‌سایت')
    customer_club_amount = fields.Float(string='مبلغ باشگاه مشتریان')
    palladium_customer_club_amount = fields.Float(string='مبلغ باشگاه مشتریان پلادیوم')
    meeting_room_amount = fields.Float(string='مبلغ رزرو اتاق جلسات')
    total_revenue = fields.Float(string='جمع کل درآمدها', compute='_compute_total')

    @api.depends(
        'cash_amount', 'snapp_amount', 'foodro_amount', 'payment_link_amount',
        'website_amount', 'customer_club_amount',
        'palladium_customer_club_amount', 'meeting_room_amount',
    )
    def _compute_total(self):
        fields_to_sum = [
            'cash_amount', 'snapp_amount', 'foodro_amount', 'payment_link_amount',
            'website_amount', 'customer_club_amount',
            'palladium_customer_club_amount', 'meeting_room_amount',
        ]
        for record in self:
            record.total_revenue = sum(record[field] for field in fields_to_sum)

    @api.constrains(
        'cash_amount', 'snapp_amount', 'foodro_amount', 'payment_link_amount',
        'website_amount', 'customer_club_amount',
        'palladium_customer_club_amount', 'meeting_room_amount',
    )
    def _check_amounts(self):
        for record in self:
            if any(record[field] < 0 for field in (
                'cash_amount', 'snapp_amount', 'foodro_amount', 'payment_link_amount',
                'website_amount', 'customer_club_amount',
                'palladium_customer_club_amount', 'meeting_room_amount',
            )):
                raise ValidationError(_('مبالغ درآمد نمی‌توانند منفی باشند.'))

    def _check_editable(self):
        for record in self:
            if record.performance_id:
                record.performance_id._shaka_check_workflow_access(
                    record.performance_id.state, 'write',
                )

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


class DailySalesPosLine(models.Model):
    _name = 'daily.sales.pos.line'
    _description = 'Daily Sales POS Line'
    _rec_name = 'terminal_number'
    _order = 'id'

    performance_id = fields.Many2one(
        'daily.sales.performance', string='عملکرد روزانه', required=True,
        ondelete='cascade', index=True,
    )
    branch_id = fields.Many2one(
        'daily.sales.branch', related='performance_id.branch_id',
        string='شعبه', store=True, readonly=True,
    )
    terminal_id = fields.Many2one(
        'daily.sales.pos.terminal', string='شماره ترمینال پوز', index=True,
    )
    # Kept as a stored snapshot for existing reports and deposit splits.
    terminal_number = fields.Char(string='شماره ذخیره‌شده ترمینال', readonly=True)
    pos_amount = fields.Float(string='مبلغ پوز', required=True)

    _terminal_unique_per_performance = Constraint(
        'unique(performance_id, terminal_number)',
        'شماره ترمینال در یک عملکرد نباید تکراری باشد.',
    )

    @api.constrains('pos_amount', 'terminal_id', 'performance_id')
    def _check_values(self):
        for record in self:
            if record.pos_amount < 0:
                raise ValidationError(_('مبلغ پوز نمی‌تواند منفی باشد.'))
            if not record.terminal_id:
                raise ValidationError(_('انتخاب شماره ترمینال پوز الزامی است.'))
            if record.performance_id and record.terminal_id.branch_id != record.performance_id.branch_id:
                raise ValidationError(_('ترمینال انتخاب‌شده متعلق به شعبه این عملکرد نیست.'))

    @api.onchange('terminal_id')
    def _onchange_terminal_id(self):
        for record in self:
            record.terminal_number = record.terminal_id.terminal_number or False

    def _check_editable(self):
        for record in self:
            if record.performance_id:
                record.performance_id._shaka_check_workflow_access(
                    record.performance_id.state, 'write',
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('terminal_id'):
                terminal = self.env['daily.sales.pos.terminal'].browse(vals['terminal_id'])
                vals['terminal_number'] = terminal.terminal_number
        records = super().create(vals_list)
        records._check_editable()
        return records

    def write(self, vals):
        self._check_editable()
        if vals.get('terminal_id'):
            terminal = self.env['daily.sales.pos.terminal'].browse(vals['terminal_id'])
            vals['terminal_number'] = terminal.terminal_number
        return super().write(vals)

    def unlink(self):
        self._check_editable()
        return super().unlink()

    def init(self):
        """Create terminal master rows from historical manually entered data."""
        self.env.cr.execute("""
            INSERT INTO daily_sales_pos_terminal
                (terminal_number, branch_id, active)
            SELECT DISTINCT btrim(line.terminal_number), performance.branch_id, TRUE
              FROM daily_sales_pos_line AS line
              JOIN daily_sales_performance AS performance
                ON performance.id = line.performance_id
             WHERE NULLIF(btrim(line.terminal_number), '') IS NOT NULL
               AND performance.branch_id IS NOT NULL
            ON CONFLICT (branch_id, terminal_number) DO NOTHING
        """)
        self.env.cr.execute("""
            UPDATE daily_sales_pos_line AS line
               SET terminal_id = terminal.id
              FROM daily_sales_performance AS performance,
                   daily_sales_pos_terminal AS terminal
             WHERE performance.id = line.performance_id
               AND terminal.branch_id = performance.branch_id
               AND terminal.terminal_number = btrim(line.terminal_number)
               AND line.terminal_id IS NULL
        """)
