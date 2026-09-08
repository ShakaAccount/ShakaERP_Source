import datetime as _dt

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


# ponytail: stdlib jalali converter (~25 lines) instead of jdatetime dep;
# swap to `jdatetime` package if more calendar math is ever needed
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


def _jalali_to_gregorian(jy, jm, jd):
    jy += 1595
    days = (-355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4)
            + jd + ((jm - 1) * 31 if jm < 7 else ((jm - 7) * 30) + 186))
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0
    for gm, mdays in enumerate([31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31], 1):
        if gd <= mdays:
            return gy, gm, gd
        gd -= mdays


class PaymentRequest(models.Model):
    _name = 'payment_request.payment_request'
    _description = 'Payment Request'
    _rec_name = 'number'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ponytail: not required=True — readonly+required+empty blocks web-client
    # save; create() always fills it from the sequence instead
    number = fields.Char(string='شماره')
    date = fields.Date(string='تاریخ', default=fields.Date.context_today, required=True)
    state = fields.Selection(
        [('draft', 'پیش‌نویس'), ('unit_review', 'در انتظار مدیر واحد'),
         ('rejected', 'رد شده'), ('accounting', 'در انتظار حسابدار'),
         ('accounting_approved', 'تایید حسابدار'), ('paid', 'پرداخت شده')],
        string='وضعیت', default='draft', required=True, tracking=True)
    unit_manager_id = fields.Many2one(
        'res.users', string='مدیر واحد',
        help='Unit manager this request is submitted to for approval.')
    unit_id = fields.Many2one(
        'odoo.raes.dim.company', string='واحد سازمانی', required=True)
    party_id = fields.Many2one(
        'odoo.raes.dim.party', string='طرف حساب', required=True)
    reason_id = fields.Many2one(
        'lookup.value', string='بابت', required=True,
        domain=[('type_id.code', '=', 'payment_reason')])
    formality = fields.Selection(
        [('official', 'رسمی'), ('informal', 'غیر رسمی')],
        string='رسمی / غیر رسمی', default='official', required=True)
    description = fields.Text(string='توضیحات')
    detail_ids = fields.One2many(
        'payment_request.detail', 'request_id', string='جزئیات درخواست پرداخت')

    _number_uniq = models.Constraint(
        'UNIQUE (number)', 'شماره must be unique')
    extra_ids = fields.One2many(
        'payment_request.extra', 'request_id', string='اطلاعات تکمیلی')
    paid_ids = fields.One2many(
        'payment_request.paid', 'request_id', string='اطلاعات پرداخت شده')
    is_accountant = fields.Boolean(compute='_compute_is_accountant')
    is_unit_manager = fields.Boolean(compute='_compute_is_accountant')
    is_site_admin = fields.Boolean(compute='_compute_is_accountant')

    def _compute_is_accountant(self):
        for rec in self:
            rec.is_accountant = self.env.user.has_group(
                'payment_request.group_accountant')
            rec.is_unit_manager = self.env.user.has_group(
                'payment_request.group_unit_manager')
            rec.is_site_admin = self.env.user.has_group('base.group_system')
    stage_ids = fields.One2many(
        'payment_request.stage', 'request_id', string='مرحله پرداخت')

    # ponytail: steps hardcoded here; move to ir.model.data rows when admins
    # need to edit steps without a code deploy
    STAGE_STEPS = [
        (1, 'فاکتور رسمی'),
        (2, 'ثبت در سامانه مودیان'),
        (3, 'صحیح بودن نام کالا در سامانه مودیان'),
        (4, 'ثبت رسید انبار'),
        (5, 'صحیح بودن مانده بدهی'),
        (6, 'ضمیمه شده قرارداد های امضا شده'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('number'):
                vals['number'] = self._next_number(vals.get('date'))
            # stages are system-managed; never accept from client
            vals.pop('stage_ids', None)
        recs = super().create(vals_list)
        # sudo: submitting user lacks stage create perm (accountant-only)
        for rec in recs:
            rec.sudo().stage_ids = [
                (0, 0, {'sequence': s, 'name': n, 'state': 'unattended'})
                for s, n in self.STAGE_STEPS]
            rec.message_subscribe(
                partner_ids=rec.create_uid.partner_id.ids)
            rec.message_post(
                body=f"درخواست {rec.number} ثبت شد.", message_type='comment')
        return recs

    # ---------------- workflow ----------------

    def action_submit(self):
        for rec in self:
            if not rec.unit_manager_id:
                raise UserError(_('مدیر واحد را انتخاب کنید.'))
            rec.state = 'unit_review'
            rec.message_post(
                body=f"برای تایید به مدیر واحد ({rec.unit_manager_id.name}) ارسال شد.",
                message_type='comment',
                partner_ids=rec.unit_manager_id.partner_id.ids)

    def action_manager_accept(self):
        self._check_manager()
        for rec in self:
            rec.state = 'accounting'
            accountant_grp = self.env.ref('payment_request.group_accountant')
            partners = accountant_grp.all_user_ids.mapped('partner_id')
            rec.message_post(
                body="مدیر واحد تایید شد؛ در انتظار بررسی حسابدار.",
                message_type='comment', partner_ids=partners.ids)

    def action_manager_reject(self):
        self._check_manager()
        for rec in self:
            rec.state = 'rejected'
            rec.message_post(
                body="مدیر واحد درخواست را رد کرد.",
                message_type='comment',
                partner_ids=rec.create_uid.partner_id.ids)

    def action_accountant_accept(self):
        self._check_accountant()
        for rec in self:
            rec.state = 'accounting_approved'
            rec.message_post(
                body="حسابدار تایید کرد.",
                message_type='comment',
                partner_ids=rec.create_uid.partner_id.ids)

    def action_accountant_mark_paid(self):
        self._check_accountant()
        for rec in self:
            rec.state = 'paid'
            rec.message_post(
                body="پرداخت انجام شد.",
                message_type='comment',
                partner_ids=rec.create_uid.partner_id.ids)

    def _check_manager(self):
        if not self.env.user.has_group('payment_request.group_unit_manager'):
            raise UserError(_('فقط مدیر واحد مجاز است.'))

    def _check_accountant(self):
        if not self.env.user.has_group('payment_request.group_accountant'):
            raise UserError(_('فقط حسابدار مجاز است.'))

    def _next_number(self, date=None):
        # max number among this jalali year's records + 1; resets at 1 Farvardin
        if not date:
            date = fields.Date.context_today(self)
        if isinstance(date, str):
            date = fields.Date.to_date(date)
        jy, _, _ = _gregorian_to_jalali(date.year, date.month, date.day)
        gy, gm, gd = _jalali_to_gregorian(jy, 1, 1)
        year_start = _dt.date(gy, gm, gd)
        self.env.cr.execute(
            """SELECT MAX(number::bigint) FROM payment_request_payment_request
               WHERE number ~ '^[0-9]+$' AND date >= %s""",
            [fields.Date.to_date(year_start)],
        )
        return str((self.env.cr.fetchone()[0] or 0) + 1)


class PaymentRequestDetail(models.Model):
    _name = 'payment_request.detail'
    _description = 'Payment Request Detail'
    _order = 'sequence, id'

    request_id = fields.Many2one(
        'payment_request.payment_request', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    line_no = fields.Integer(string='#', compute='_compute_line_no')

    @api.depends('request_id', 'request_id.detail_ids.sequence')
    def _compute_line_no(self):
        for req in self.request_id:
            for i, line in enumerate(req.detail_ids.sorted('sequence'), 1):
                line.line_no = i
    name = fields.Char(string='شرح')
    paytype_id = fields.Many2one(
        'lookup.value', string='نوع پرداخت',
        domain=[('type_id.code', '=', 'payment_type')])
    costcenter_id = fields.Many2one(
        'odoo.raes.dim.cost_center', string='مرکز هزینه')
    amount = fields.Float(string='مبلغ')
    vat = fields.Float(string='ارزش افزوده')
    net_amount = fields.Float(
        string='مبلغ خالص', compute='_compute_net_amount')
    agreed_date = fields.Date(string='تاریخ توافقی پرداخت')

    @api.depends('amount', 'vat')
    def _compute_net_amount(self):
        for rec in self:
            rec.net_amount = rec.amount + rec.vat


class PaymentRequestExtra(models.Model):
    _name = 'payment_request.extra'
    _description = 'Payment Request Extra Info'
    _order = 'sequence, id'

    request_id = fields.Many2one(
        'payment_request.payment_request', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    key = fields.Char(string='عنوان', required=True)
    value = fields.Char(string='مقدار')


class PaymentRequestPaid(models.Model):
    _name = 'payment_request.paid'
    _description = 'Payment Request Paid Info'
    _order = 'sequence, id'

    request_id = fields.Many2one(
        'payment_request.payment_request', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    date = fields.Date(string='تاریخ')
    amount = fields.Float(string='مبلغ')
    description = fields.Char(string='شرح')


class PaymentRequestStage(models.Model):
    _name = 'payment_request.stage'
    _description = 'Payment Request Stage'
    _order = 'sequence, id'

    request_id = fields.Many2one(
        'payment_request.payment_request', required=True, ondelete='cascade')
    sequence = fields.Integer(string='ترتیب')
    name = fields.Char(string='مرحله')
    state = fields.Selection(
        [('unattended', 'بررسی نشده'), ('checked', 'تایید شده'),
         ('failed', 'رد شده')],
        string='وضعیت', default='unattended', required=True)
