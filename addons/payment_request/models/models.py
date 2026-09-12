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
    # posting notes requires only read access (any user can comment)
    _mail_post_access = 'read'

    # ponytail: not required=True — readonly+required+empty blocks web-client
    # save; create() always fills it from the sequence instead
    number = fields.Char(string='شماره')
    date = fields.Date(string='تاریخ', default=fields.Date.context_today, required=True)
    state = fields.Selection(
        [('draft', 'پیش‌نویس'), ('unit_review', 'در انتظار مدیر واحد'),
         ('rejected', 'رد شده'), ('accountant_review', 'در انتظار حسابدار'),
         ('tax_review', 'در انتظار مالیات'),
         ('acc_mgmt_review', 'در انتظار مدیر حسابداری'),
         ('treasury', 'در انتظار خزانه دار'), ('paid', 'پرداخت شده')],
        string='وضعیت', default='draft', required=True, tracking=True)
    unit_manager_id = fields.Many2one(
        'res.users', string='مدیر واحد',
        help='Unit manager this request is submitted to for approval.')
    owner_id = fields.Many2one(
        'res.users', string='مالک درخواست', index=True,
        default=lambda self: self.env.user,
        help='Only this user sees and edits the request while it is in '
             'draft (پیش‌نویس). Set automatically on create.')
    unit_id = fields.Many2one(
        'odoo.raes.dim.company', string='واحد سازمانی', required=True)
    party_id = fields.Many2one(
        'odoo.raes.dim.party', string='طرف حساب', required=True)
    reason_id = fields.Many2one(
        'lookup.value', string='بابت', required=True,
        domain=[('type_id.code', '=', 'payment_reason')])
    formality = fields.Text(string='رسمی / غیر رسمی', required=True)
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
    is_tax = fields.Boolean(compute='_compute_is_accountant')
    is_acc_mgmt = fields.Boolean(compute='_compute_is_accountant')
    is_treasurer = fields.Boolean(compute='_compute_is_accountant')
    is_site_admin = fields.Boolean(compute='_compute_is_accountant')

    @api.depends_context('uid')
    def _compute_is_accountant(self):
        for rec in self:
            rec.is_accountant = self.env.user.has_group(
                'payment_request.group_accountant')
            rec.is_unit_manager = self.env.user.has_group(
                'payment_request.group_unit_manager')
            rec.is_tax = self.env.user.has_group('payment_request.group_tax')
            rec.is_acc_mgmt = self.env.user.has_group(
                'payment_request.group_acc_mgmt')
            rec.is_treasurer = self.env.user.has_group(
                'payment_request.group_treasurer')
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
            # the creator owns the draft; never trust a client-sent owner
            vals['owner_id'] = vals.get('owner_id') or self.env.user.id
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
            # post before state change: after the write the record leaves the
            # author's record-rule domain and message_post loses read access
            rec.message_post(
                body=f"برای تایید به مدیر واحد ({rec.unit_manager_id.name}) ارسال شد.",
                message_type='comment',
                partner_ids=rec.unit_manager_id.partner_id.ids)
            rec.state = 'unit_review'
            rec._schedule_step_activity()

    def action_manager_accept(self):
        self._check_manager()
        for rec in self:
            grp = self.env.ref('payment_request.group_accountant')
            partners = grp.all_user_ids.mapped('partner_id')
            rec.message_post(
                body="مدیر واحد تایید شد؛ در انتظار بررسی حسابدار.",
                message_type='comment', partner_ids=partners.ids)
            rec.state = 'accountant_review'
            rec._schedule_step_activity()

    def action_manager_reject(self):
        self._check_manager()
        for rec in self:
            rec.message_post(
                body="مدیر واحد درخواست را رد کرد.",
                message_type='comment',
                partner_ids=rec.create_uid.partner_id.ids)
            rec.state = 'rejected'
            rec._schedule_step_activity()

    def action_accountant_accept(self):
        self._check_accountant()
        for rec in self:
            tax_grp = self.env.ref('payment_request.group_tax')
            partners = tax_grp.all_user_ids.mapped('partner_id')
            rec.message_post(
                body="حسابدار تایید کرد؛ در انتظار تکمیل مراحل توسط مالیات.",
                message_type='comment', partner_ids=partners.ids)
            rec.state = 'tax_review'
            rec._schedule_step_activity()

    def action_tax_stages_done(self):
        """گروه مالیات: مراحل را پر کرده و ارسال به مدیر حسابداری."""
        self._check_tax()
        for rec in self:
            if rec.state == 'rejected':
                # pre-save of the form already rejected it (radio reject)
                rec._schedule_step_activity()   # clears the open task
                continue
            if not rec.stage_ids._all_checked():
                bad = rec.stage_ids.filtered(
                    lambda s: s.state != 'checked')
                raise UserError(_(
                    'همه مراحل باید تایید شده باشند. باقی‌مانده: %s',
                    ', '.join(bad.mapped('name'))))
            grp = self.env.ref('payment_request.group_acc_mgmt')
            partners = grp.all_user_ids.mapped('partner_id')
            rec.message_post(
                body="مراحل توسط مالیات تکمیل شد؛ در انتظار تایید مدیر حسابداری.",
                message_type='comment', partner_ids=partners.ids)
            rec.state = 'acc_mgmt_review'
            rec._schedule_step_activity()

    def action_acc_mgmt_accept(self):
        self._check_acc_mgmt()
        for rec in self:
            grp = self.env.ref('payment_request.group_treasurer')
            partners = grp.all_user_ids.mapped('partner_id')
            rec.message_post(
                body="مدیر حسابداری تایید کرد؛ در انتظار پرداخت توسط خزانه دار.",
                message_type='comment', partner_ids=partners.ids)
            rec.state = 'treasury'
            rec._schedule_step_activity()

    def action_treasurer_paid(self):
        self._check_treasurer()
        for rec in self:
            if not rec.paid_ids:
                raise UserError(
                    _('حداقل یک ردیف پرداخت (اطلاعات پرداخت شده) وارد کنید.'))
            rec.message_post(
                body="پرداخت توسط خزانه دار ثبت شد؛ گردش کار تمام شد.",
                message_type='comment',
                partner_ids=rec.create_uid.partner_id.ids)
            rec.state = 'paid'
            rec._schedule_step_activity()

    def _check_manager(self):
        if not self.env.user.has_group('payment_request.group_unit_manager'):
            raise UserError(_('فقط مدیر واحد مجاز است.'))

    def _check_accountant(self):
        if not self.env.user.has_group('payment_request.group_accountant'):
            raise UserError(_('فقط حسابدار مجاز است.'))

    def _check_tax(self):
        if not self.env.user.has_group('payment_request.group_tax'):
            raise UserError(_('فقط گروه مالیات مجاز است.'))

    def _check_acc_mgmt(self):
        if not self.env.user.has_group('payment_request.group_acc_mgmt'):
            raise UserError(_('فقط مدیر حسابداری مجاز است.'))

    def _check_treasurer(self):
        if not self.env.user.has_group('payment_request.group_treasurer'):
            raise UserError(_('فقط خزانه دار مجاز است.'))

    # ---------------- scheduled follow-up tasks (mail.activity) ----------------

    STEP_ACTIVITY = 'payment_request.activity_pr_review'
    STEP_DEADLINE_DAYS = 3
    OPEN_STATES = ('unit_review', 'accountant_review', 'tax_review',
                   'acc_mgmt_review', 'treasury')

    def _step_users(self):
        """Users responsible for the request's CURRENT step."""
        self.ensure_one()
        if self.state == 'unit_review':
            return self.unit_manager_id
        xmlid = {
            'accountant_review': 'payment_request.group_accountant',
            'tax_review': 'payment_request.group_tax',
            'acc_mgmt_review': 'payment_request.group_acc_mgmt',
            'treasury': 'payment_request.group_treasurer',
        }.get(self.state)
        if not xmlid:
            return self.env['res.users']
        users = self.env.ref(xmlid).all_user_ids
        # site admins supervise, they don't get per-step tasks (they are in
        # every group, so without this filter admin receives each task)
        staff = users.filtered(
            lambda u: not u.has_group('base.group_system'))
        return staff or users

    def _schedule_step_activity(self, note=''):
        """Drop the closed step's task and schedule the next one for whoever
        now holds the request. sudo: the workflow assigns the task — the
        acting user loses write access the moment the state moves."""
        for rec in self.sudo():
            rec.activity_unlink([self.STEP_ACTIVITY])
            if rec.state not in self.OPEN_STATES:
                continue
            users = rec._step_users()
            if not users:
                continue
            deadline = fields.Date.context_today(rec) + _dt.timedelta(
                days=self.STEP_DEADLINE_DAYS)
            for user in users:
                rec.activity_schedule(
                    act_type_xmlid=self.STEP_ACTIVITY, user_id=user.id,
                    summary=f'درخواست {rec.number} در انتظار بررسی شما',
                    note=note or 'درخواست پرداخت %s (وضعیت: %s)' % (
                        rec.number, dict(rec._fields['state'].selection)
                        .get(rec.state, rec.state)),
                    date_deadline=deadline)

    @api.model
    def _cron_remind_pending_steps(self):
        """Daily sweep: whoever holds a request gets the task (re)scheduled and
        a chatter nudge, so an idle step cannot sit unnoticed."""
        recs = self.search([('state', 'in', self.OPEN_STATES)])
        for rec in recs:
            if rec.activity_ids:
                continue
            rec._schedule_step_activity()
            rec.message_post(
                body=f"یادآوری: درخواست {rec.number} در انتظار اقدام شما است.",
                message_type='comment',
                partner_ids=rec._step_users().mapped('partner_id').ids)

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
    account_no = fields.Char(string='شماره حساب')
    party_name = fields.Char(string='نام طرف شماره حساب')
    sheba_no = fields.Char(string='شماره شبا')
    description = fields.Char(string='توضیحات')


class PaymentRequestPaid(models.Model):
    _name = 'payment_request.paid'
    _description = 'Payment Request Paid Info'
    _order = 'sequence, id'

    request_id = fields.Many2one(
        'payment_request.payment_request', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    paid_amount = fields.Float(string='مبلغ پرداخت شده')
    tracking_no = fields.Char(string='شماره پیگیری')
    cheque_no = fields.Char(string='شماره چک')
    payment_declaration_no = fields.Char(string='شماره اعلامیه پرداخت')
    description = fields.Char(string='توضیحات')


class PaymentRequestStage(models.Model):
    _name = 'payment_request.stage'
    _description = 'Payment Request Stage'
    _order = 'sequence, id'

    request_id = fields.Many2one(
        'payment_request.payment_request', required=True, ondelete='cascade')
    sequence = fields.Integer(string='ترتیب')
    name = fields.Char(string='مرحله')
    parent_id = fields.Many2one(
        'payment_request.stage', string='مرحله والد', index=True,
        domain="[('request_id', '=', request_id), "
              "('id', '!=', id), ('parent_id', '=', False)]")
    child_ids = fields.One2many(
        'payment_request.stage', 'parent_id', string='زیرمرحله‌ها')
    allow_reject = fields.Boolean(
        string='قابل رد', default=True,
        help='If off, the reject option is disabled for this step.')
    state = fields.Selection(
        [('unattended', 'بررسی نشده'), ('checked', 'تایید شده'),
         ('failed', 'رد شده')],
        string='وضعیت', default='unattended', required=True)
    # radio selector: '', 'accept', 'reject'
    decision = fields.Selection(
        [('accept', 'تایید'), ('reject', 'رد')],
        string='تصمیم', default=False)
    is_frontier = fields.Boolean(compute='_compute_is_frontier')

    def _compute_is_frontier(self):
        for rec in self:
            rec.is_frontier = bool(rec.id) and rec._frontier().id == rec.id

    def _frontier(self):
        """First row whose state != checked, over the request's full set."""
        rows = (self.mapped('request_id.stage_ids') or self).sorted('sequence')
        for row in rows:
            if row.state != 'checked':
                return row
        return rows[-1:] if rows else self.browse()

    # ---------------- radio decision ----------------

    @api.onchange('decision')
    def _onchange_decision(self):
        # visual live feedback in the form only; persisted on save, where
        # write() runs the real waterfall
        if not self.decision:
            return
        rows = self.request_id.stage_ids.sorted('sequence')
        idx = rows.ids.index(self.id) if self.id in rows.ids else -1
        if self.decision == 'accept':
            rows[:idx + 1].filtered(
                lambda s: s.state != 'checked').state = 'checked'
            rows[idx + 1:].filtered(
                lambda s: s.state == 'failed').state = 'unattended'
        elif self.decision == 'reject' and self.allow_reject:
            self.state = 'failed'

    def write(self, vals):
        recs = super().write(vals)
        if vals.get('decision'):
            self._apply_decision()
        return recs

    def _apply_decision(self):
        """accept: this row + every row above become checked, rows below
        reset to pending. reject: row failed -> whole request rejected."""
        for rec in self:
            rows = rec.request_id.stage_ids.sorted('sequence')
            idx = rows.ids.index(rec.id)
            if rec.decision == 'accept':
                above = rows[:idx + 1]
                above.filtered(
                    lambda s: s.state != 'checked').state = 'checked'
                below = rows[idx + 1:]
                below.filtered(lambda s: s.state == 'failed').state = (
                    'unattended')
                rec.request_id.message_post(
                    body=f"تا مرحله «{rec.name}» تایید شد.",
                    message_type='comment')
            elif rec.decision == 'reject':
                if not rec.allow_reject:
                    rec.decision = False
                    raise UserError(_('این مرحله قابل رد کردن نیست.'))
                rec.state = 'failed'
                rec.child_ids.state = 'failed'
                req = rec.request_id
                req.state = 'rejected'
                req.sudo()._schedule_step_activity()
                req.message_post(
                    body=f"مرحله «{rec.name}» رد شد؛ درخواست رد شد.",
                    message_type='comment',
                    partner_ids=req.create_uid.partner_id.ids)
            rec.decision = False  # radio is an action, not a stored state

    def _all_checked(self):
        return all(s.state == 'checked' for s in self)
