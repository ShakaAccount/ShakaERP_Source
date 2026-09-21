from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class BudgetPlanningNumberMixin(models.AbstractModel):
    _name = 'budget.planning.number.mixin'
    _description = 'Budget Planning Number Helper'

    number = fields.Integer(string='شماره', readonly=True, copy=False, index=True)

    @api.model
    def _next_number(self, domain):
        # Sequence generation must see all records of the selected scope.
        # Company record rules are for UI visibility and must not make the
        # allocator reuse an existing number hidden from the current user.
        last = self.sudo().search(domain, order='number desc, id desc', limit=1)
        return max(last.number or 0, 0) + 1


class BudgetPlan(BudgetPlanningNumberMixin, models.Model):
    _name = 'budget.plan'
    _description = 'Budget and Planning Plan'
    _inherit = ['mail.thread', 'shaka.access.mixin']
    _order = 'fiscal_year_id desc, number desc, id desc'

    name = fields.Char(string='عنوان برنامه', required=True, tracking=True)
    number = fields.Integer(string='شماره برنامه', readonly=True, copy=False, index=True, default=1)
    company_id = fields.Many2one('res.company', string='شرکت', required=True, default=lambda self: self.env.company, index=True)
    fiscal_year_id = fields.Many2one('company.fiscal.year', string='سال مالی', required=True, ondelete='restrict', domain="[('company_id', '=', company_id)]", tracking=True)
    owner_role_id = fields.Many2one('company.board.role', string='متولی برنامه / نقش شرکت', ondelete='restrict')
    description = fields.Text(string='توضیحات')
    state = fields.Selection([
        ('draft', 'پیش‌نویس'), ('submitted', 'ارسال‌شده'),
        ('approved', 'تأییدشده'), ('rejected', 'ردشده'),
    ], string='وضعیت', default='draft', required=True, tracking=True)
    unlocked_step = fields.Integer(string='آخرین مرحله فعال', default=1, required=True, copy=False)
    strategy_ids = fields.One2many('budget.plan.strategy', 'plan_id', string='استراتژی‌ها', copy=True)
    target_ids = fields.One2many('budget.plan.target', 'plan_id', string='اهداف', copy=True)
    kpi_ids = fields.One2many('budget.plan.kpi', 'plan_id', string='KPIها', copy=True)
    initiative_ids = fields.One2many('budget.plan.initiative', 'plan_id', string='اقدامات', copy=True)
    project_ids = fields.One2many('budget.plan.project', 'plan_id', string='پروژه‌ها', copy=True)
    activity_ids = fields.One2many('budget.plan.activity', 'plan_id', string='فعالیت‌ها', copy=True)
    budget_line_ids = fields.One2many('budget.plan.budget.line', 'plan_id', string='تخصیص بودجه', copy=True)
    strategy_count = fields.Integer(compute='_compute_counts')
    target_count = fields.Integer(compute='_compute_counts')
    kpi_count = fields.Integer(compute='_compute_counts')
    initiative_count = fields.Integer(compute='_compute_counts')
    project_count = fields.Integer(compute='_compute_counts')
    activity_count = fields.Integer(compute='_compute_counts')
    budget_total = fields.Float(compute='_compute_budget_totals', digits='Account')
    budget_spent = fields.Float(compute='_compute_budget_totals', digits='Account')
    budget_consumption = fields.Float(compute='_compute_budget_totals')

    _plan_number_unique = models.Constraint(
        'unique(company_id, fiscal_year_id, number)',
        'شماره برنامه در هر سال مالی باید یکتا باشد.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        self._shaka_check_workflow_access('draft', 'create')
        for vals in vals_list:
            company_id = vals.get('company_id') or self.env.company.id
            fiscal_year_id = vals.get('fiscal_year_id')
            if not fiscal_year_id:
                raise ValidationError('انتخاب سال مالی الزامی است.')
            vals['number'] = self._next_number([
                ('company_id', '=', company_id), ('fiscal_year_id', '=', fiscal_year_id),
            ])
        return super().create(vals_list)

    @api.onchange('company_id', 'fiscal_year_id')
    def _onchange_number_preview(self):
        """Show the real next number on a new form instead of Odoo's 0."""
        for record in self:
            if record.id:
                continue
            company_id = record.company_id.id or self.env.company.id
            if not record.fiscal_year_id:
                record.number = 1
                continue
            record.number = self._next_number([
                ('company_id', '=', company_id),
                ('fiscal_year_id', '=', record.fiscal_year_id.id),
            ])

    def write(self, vals):
        for record in self:
            record._shaka_check_workflow_access(record.state, 'write')
        return super().write(vals)

    def unlink(self):
        for record in self:
            record._shaka_check_workflow_access(record.state, 'unlink')
        return super().unlink()

    @api.depends('strategy_ids', 'target_ids', 'kpi_ids', 'initiative_ids', 'project_ids', 'activity_ids')
    def _compute_counts(self):
        for record in self:
            record.strategy_count = len(record.strategy_ids)
            record.target_count = len(record.target_ids)
            record.kpi_count = len(record.kpi_ids)
            record.initiative_count = len(record.initiative_ids)
            record.project_count = len(record.project_ids)
            record.activity_count = len(record.activity_ids)

    @api.depends('budget_line_ids.approved_amount', 'budget_line_ids.spent_amount')
    def _compute_budget_totals(self):
        for record in self:
            record.budget_total = sum(record.budget_line_ids.mapped('approved_amount'))
            record.budget_spent = sum(record.budget_line_ids.mapped('spent_amount'))
            record.budget_consumption = record.budget_spent / record.budget_total * 100 if record.budget_total else 0

    def action_submit(self):
        self._shaka_check_workflow_access('draft', 'write')
        self.write({'state': 'submitted'})

    def action_unlock_next_step(self):
        self._shaka_check_workflow_access('draft', 'write')
        requested_step = int(self.env.context.get('bp_step', 1))
        requested_step = max(1, min(requested_step, 6))
        for record in self:
            record.unlocked_step = max(record.unlocked_step or 1, requested_step + 1)

    def action_approve(self):
        self._shaka_check_workflow_access('submitted', 'write')
        self.write({'state': 'approved'})

    def action_reject(self):
        self._shaka_check_workflow_access('submitted', 'write')
        self.write({'state': 'rejected'})

    def action_reset_draft(self):
        self._shaka_check_workflow_access(self[:1].state, 'write')
        self.write({'state': 'draft'})


class BudgetPlanChildMixin(BudgetPlanningNumberMixin):
    _name = 'budget.plan.child.mixin'
    _description = 'Budget Planning Child'

    plan_id = fields.Many2one('budget.plan', string='برنامه', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='plan_id.company_id', store=True, index=True)
    fiscal_year_id = fields.Many2one(related='plan_id.fiscal_year_id', store=True, index=True)

    @api.constrains('plan_id')
    def _check_plan_state(self):
        for record in self:
            if record.plan_id.state == 'approved' and not self.env.user.has_group('base.group_system'):
                raise UserError('برنامه تأییدشده قابل تغییر نیست.')


class BudgetPlanStrategy(BudgetPlanChildMixin, models.Model):
    _name = 'budget.plan.strategy'
    _description = 'Budget Strategy'
    _rec_name = 'title'
    _order = 'number, id'
    title = fields.Char(string='عنوان استراتژی', required=True)
    horizon_start = fields.Char(string='سال شروع افق', size=4)
    horizon_end = fields.Char(string='سال پایان افق', size=4)
    owner_role_id = fields.Many2one('company.board.role', string='متولی', ondelete='restrict')
    target_ids = fields.One2many('budget.plan.target', 'strategy_id', string='اهداف', copy=True)
    _number_unique = models.Constraint('unique(plan_id, number)', 'شماره استراتژی در این برنامه باید یکتا باشد.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            plan_id = vals.get('plan_id') or self.env.context.get('default_plan_id')
            vals['number'] = self._next_number([('plan_id', '=', plan_id)])
        return super().create(vals_list)

    @api.constrains('horizon_start', 'horizon_end')
    def _check_horizon_years(self):
        for record in self:
            for field_name in ('horizon_start', 'horizon_end'):
                value = (record[field_name] or '').strip()
                if value and (not value.isdigit() or len(value) != 4):
                    raise ValidationError('سال شروع و پایان افق زمانی باید به‌صورت چهاررقمی ثبت شود؛ مانند 1405.')


class BudgetPlanTarget(BudgetPlanChildMixin, models.Model):
    _name = 'budget.plan.target'
    _description = 'Budget Target'
    _rec_name = 'title'
    _order = 'strategy_id, number, id'
    strategy_id = fields.Many2one('budget.plan.strategy', string='استراتژی', required=True, ondelete='cascade', index=True)
    title = fields.Char(string='عنوان هدف', required=True)
    current_value = fields.Float(string='مقدار فعلی')
    target_value = fields.Float(string='مقدار هدف', required=True)
    unit_id = fields.Many2one(
        'lookup.value', string='واحد اندازه‌گیری', required=True,
        domain="[('type_id.code', '=', 'budget_measurement_unit')]", ondelete='restrict',
    )
    description = fields.Text(string='توضیحات')
    kpi_ids = fields.One2many('budget.plan.kpi', 'target_id', string='KPIها', copy=True)
    _number_unique = models.Constraint('unique(strategy_id, number)', 'شماره هدف برای این استراتژی باید یکتا باشد.')

    @api.onchange('strategy_id')
    def _onchange_strategy_id(self):
        if self.strategy_id:
            self.plan_id = self.strategy_id.plan_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            strategy = self.env['budget.plan.strategy'].browse(vals.get('strategy_id'))
            vals['plan_id'] = strategy.plan_id.id
            vals['number'] = self._next_number([('strategy_id', '=', strategy.id)])
        return super().create(vals_list)


class BudgetPlanKpi(BudgetPlanChildMixin, models.Model):
    _name = 'budget.plan.kpi'
    _description = 'Budget KPI'
    _rec_name = 'title'
    _order = 'target_id, number, id'
    target_id = fields.Many2one('budget.plan.target', string='هدف', required=True, ondelete='cascade', index=True)
    title = fields.Char(string='عنوان KPI', required=True)
    unit_id = fields.Many2one(
        'lookup.value', string='واحد', required=True,
        domain="[('type_id.code', '=', 'budget_measurement_unit')]", ondelete='restrict',
    )
    target_value = fields.Float(string='هدف', required=True)
    weight = fields.Float(string='وزن')
    current_value = fields.Float(string='مقدار فعلی')
    achievement = fields.Float(string='درصد تحقق', compute='_compute_achievement', store=True)
    initiative_ids = fields.One2many('budget.plan.initiative', 'kpi_id', string='اقدامات', copy=True)
    _number_unique = models.Constraint('unique(target_id, number)', 'شماره KPI برای این هدف باید یکتا باشد.')

    @api.depends('target_value', 'current_value')
    def _compute_achievement(self):
        for record in self:
            record.achievement = min(100, record.current_value / record.target_value * 100) if record.target_value else 0

    @api.onchange('target_id')
    def _onchange_target_id(self):
        if self.target_id:
            self.plan_id = self.target_id.plan_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            target = self.env['budget.plan.target'].browse(vals.get('target_id'))
            vals['plan_id'] = target.plan_id.id
            vals['number'] = self._next_number([('target_id', '=', target.id)])
        return super().create(vals_list)


class BudgetPlanInitiative(BudgetPlanChildMixin, models.Model):
    _name = 'budget.plan.initiative'
    _description = 'Budget Initiative'
    _rec_name = 'title'
    _order = 'kpi_id, number, id'
    kpi_id = fields.Many2one('budget.plan.kpi', string='KPI', required=True, ondelete='cascade', index=True)
    title = fields.Char(string='عنوان اقدام', required=True)
    owner_role_id = fields.Many2one('company.board.role', string='مالک اقدام', ondelete='restrict')
    weight = fields.Float(string='وزن')
    project_ids = fields.One2many('budget.plan.project', 'initiative_id', string='پروژه‌ها', copy=True)
    budget_line_ids = fields.One2many('budget.plan.budget.line', 'initiative_id', string='بودجه', copy=True)
    _number_unique = models.Constraint('unique(kpi_id, number)', 'شماره اقدام برای این KPI باید یکتا باشد.')

    @api.onchange('kpi_id')
    def _onchange_kpi_id(self):
        if self.kpi_id:
            self.plan_id = self.kpi_id.plan_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            kpi = self.env['budget.plan.kpi'].browse(vals.get('kpi_id'))
            vals['plan_id'] = kpi.plan_id.id
            vals['number'] = self._next_number([('kpi_id', '=', kpi.id)])
        return super().create(vals_list)


class BudgetPlanProject(BudgetPlanChildMixin, models.Model):
    _name = 'budget.plan.project'
    _description = 'Budget Project'
    _rec_name = 'title'
    _order = 'initiative_id, number, id'
    initiative_id = fields.Many2one('budget.plan.initiative', string='اقدام', required=True, ondelete='cascade', index=True)
    title = fields.Char(string='عنوان پروژه', required=True)
    responsible_role_id = fields.Many2one('company.board.role', string='مسئول پروژه', ondelete='restrict')
    date_start = fields.Date(string='شروع')
    date_end = fields.Date(string='پایان')
    approved_amount = fields.Float(string='بودجه مصوب', digits='Account')
    actual_amount = fields.Float(string='هزینه واقعی', digits='Account')
    physical_progress = fields.Float(string='پیشرفت فیزیکی %')
    financial_progress = fields.Float(string='پیشرفت مالی %', compute='_compute_financial_progress', store=True)
    activity_ids = fields.One2many('budget.plan.activity', 'project_id', string='فعالیت‌ها', copy=True)
    _number_unique = models.Constraint('unique(initiative_id, number)', 'شماره پروژه برای این اقدام باید یکتا باشد.')

    @api.depends('approved_amount', 'actual_amount')
    def _compute_financial_progress(self):
        for record in self:
            record.financial_progress = record.actual_amount / record.approved_amount * 100 if record.approved_amount else 0

    @api.onchange('initiative_id')
    def _onchange_initiative_id(self):
        if self.initiative_id:
            self.plan_id = self.initiative_id.plan_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            initiative = self.env['budget.plan.initiative'].browse(vals.get('initiative_id'))
            vals['plan_id'] = initiative.plan_id.id
            vals['number'] = self._next_number([('initiative_id', '=', initiative.id)])
        return super().create(vals_list)


class BudgetPlanActivity(BudgetPlanChildMixin, models.Model):
    _name = 'budget.plan.activity'
    _description = 'Budget Activity'
    _rec_name = 'title'
    _order = 'project_id, number, id'
    project_id = fields.Many2one('budget.plan.project', string='پروژه', required=True, ondelete='cascade', index=True)
    title = fields.Char(string='عنوان فعالیت', required=True)
    quantity = fields.Float(string='مقدار')
    unit_id = fields.Many2one(
        'lookup.value', string='واحد',
        domain="[('type_id.code', '=', 'budget_measurement_unit')]", ondelete='restrict',
    )
    cost = fields.Float(string='هزینه', digits='Account')
    status_id = fields.Many2one(
        'lookup.value', string='وضعیت',
        domain="[('type_id.code', '=', 'budget_activity_status')]", ondelete='restrict',
    )
    _number_unique = models.Constraint('unique(project_id, number)', 'شماره فعالیت برای این پروژه باید یکتا باشد.')

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id:
            self.plan_id = self.project_id.plan_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            project = self.env['budget.plan.project'].browse(vals.get('project_id'))
            vals['plan_id'] = project.plan_id.id
            vals['number'] = self._next_number([('project_id', '=', project.id)])
        return super().create(vals_list)


class BudgetPlanBudgetLine(BudgetPlanChildMixin, models.Model):
    _name = 'budget.plan.budget.line'
    _description = 'Budget Allocation Line'
    _rec_name = 'title'
    _order = 'initiative_id, number, id'
    initiative_id = fields.Many2one('budget.plan.initiative', string='اقدام', required=True, ondelete='cascade', index=True)
    title = fields.Char(string='عنوان ردیف', required=True)
    approved_amount = fields.Float(string='بودجه مصوب', digits='Account')
    allocated_amount = fields.Float(string='تخصیص‌یافته', digits='Account')
    spent_amount = fields.Float(string='مصرف‌شده', digits='Account')
    consumption = fields.Float(string='درصد مصرف', compute='_compute_consumption', store=True)
    balance = fields.Float(string='مانده', compute='_compute_consumption', store=True)
    _number_unique = models.Constraint('unique(initiative_id, number)', 'شماره ردیف بودجه برای این اقدام باید یکتا باشد.')

    @api.depends('approved_amount', 'spent_amount')
    def _compute_consumption(self):
        for record in self:
            record.consumption = record.spent_amount / record.approved_amount * 100 if record.approved_amount else 0
            record.balance = record.approved_amount - record.spent_amount

    @api.onchange('initiative_id')
    def _onchange_initiative_id(self):
        if self.initiative_id:
            self.plan_id = self.initiative_id.plan_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            initiative = self.env['budget.plan.initiative'].browse(vals.get('initiative_id'))
            vals['plan_id'] = initiative.plan_id.id
            vals['number'] = self._next_number([('initiative_id', '=', initiative.id)])
        return super().create(vals_list)
