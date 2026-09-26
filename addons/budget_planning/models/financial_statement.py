from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError, UserError


class BudgetFinancialStatement(models.Model):
    _name = 'budget.financial.statement'
    _description = 'Monthly Budget Financial Statements'
    _inherit = ['shaka.access.mixin']
    _order = 'fiscal_year_id desc, id desc'
    _rec_name = 'name'

    company_id = fields.Many2one('res.company', string='شرکت', required=True,
                                 default=lambda self: self.env.company)
    fiscal_year_id = fields.Many2one('company.fiscal.year', string='سال مالی', required=True,
                                     domain="[('company_id', '=', company_id)]")
    scenario_id = fields.Many2one('holding.budget.scenario.line', string='سناریو', required=True,
                                  domain="[('scenario_id.company_id', '=', company_id), ('scenario_id.fiscal_year_id', '=', fiscal_year_id)]")
    number = fields.Integer(string='شماره', readonly=True, copy=False)
    description = fields.Text(string='توضیحات')
    entry_mode = fields.Selection([('monthly', 'ورود ماهانه'), ('annual', 'ورود جمع کل')],
                                  string='شیوهٔ ورود جزئیات', copy=False)
    name = fields.Char(compute='_compute_name')
    balance_line_ids = fields.One2many('budget.financial.statement.line', 'statement_id',
                                       string='ترازنامه', domain=[('section', '=', 'balance')])
    income_line_ids = fields.One2many('budget.financial.statement.line', 'statement_id',
                                      string='سود و زیان', domain=[('section', '=', 'income')])

    _sql_constraints = [
        ('fiscal_year_number_unique', 'unique(fiscal_year_id, number)',
         'شماره فرم در هر سال مالی باید یکتا باشد.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            fiscal_year_id = vals.get('fiscal_year_id')
            if fiscal_year_id and not vals.get('number'):
                last = self.search([('fiscal_year_id', '=', fiscal_year_id)],
                                   order='number desc, id desc', limit=1)
                vals['number'] = int(last.number or 0) + 1
        return super().create(vals_list)

    @api.depends('number')
    def _compute_name(self):
        for record in self:
            record.name = str(record.number or '')

    @api.onchange('company_id')
    def _onchange_company(self):
        self.fiscal_year_id = False
        self.scenario_id = False

    @api.onchange('fiscal_year_id')
    def _onchange_year(self):
        self.scenario_id = False

    @api.constrains('company_id', 'fiscal_year_id', 'scenario_id')
    def _check_relations(self):
        for record in self:
            if record.fiscal_year_id.company_id != record.company_id:
                raise ValidationError('سال مالی باید متعلق به شرکت انتخاب‌شده باشد.')
            scenario = record.scenario_id.scenario_id
            if scenario.company_id != record.company_id or scenario.fiscal_year_id != record.fiscal_year_id:
                raise ValidationError('سناریو باید متعلق به شرکت و سال مالی انتخاب‌شده باشد.')
    @api.model
    def action_open_settings(self):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError('فقط مدیر سیستم می‌تواند تنظیمات گروه‌بندی را باز کند.')
        return {
            'type': 'ir.actions.act_window',
            'name': 'تنظیمات گروه‌بندی حساب',
            'res_model': 'res.config.settings',
            'view_mode': 'form',
            'views': [(self.env.ref('budget_planning.view_financial_statement_settings_form').id, 'form')],
            'target': 'new',
        }

    def write(self, vals):
        if 'entry_mode' in vals:
            for record in self:
                if record.entry_mode != vals['entry_mode'] and (
                    record.balance_line_ids | record.income_line_ids
                ).filtered(lambda line: line.total):
                    raise ValidationError('پس از ثبت مبلغ در جزئیات، شیوهٔ ورود قابل تغییر نیست.')
        return super().write(vals)




class BudgetFinancialStatementLine(models.Model):
    _name = 'budget.financial.statement.line'
    _description = 'Monthly Budget Account Line'
    _order = 'sequence, id'

    statement_id = fields.Many2one('budget.financial.statement', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='statement_id.company_id', store=True)
    section = fields.Selection([('balance', 'ترازنامه'), ('income', 'سود و زیان')], required=True)
    sequence = fields.Integer()
    title = fields.Char(string='عنوان خام حساب', required=True)
    display_title = fields.Char(string='عنوان حساب', compute='_compute_display_title')
    category_id = fields.Many2one('raes.md.category', readonly=True)
    member_id = fields.Char(readonly=True)
    depth = fields.Integer()
    row_type = fields.Selection([('category', 'گروه'), ('member', 'حساب')],
                                required=True, default='member')
    input_mode = fields.Selection([('empty', 'بدون مبلغ'), ('annual', 'جمع کل'),
                                   ('monthly', 'ماهانه')],
                                  string='منبع مبلغ', default='empty', required=True)
    annual_amount = fields.Float(string='جمع کل', digits='Account')
    month_1 = fields.Float(string='ماه ۱', digits='Account')
    month_2 = fields.Float(string='ماه ۲', digits='Account')
    month_3 = fields.Float(string='ماه ۳', digits='Account')
    month_4 = fields.Float(string='ماه ۴', digits='Account')
    month_5 = fields.Float(string='ماه ۵', digits='Account')
    month_6 = fields.Float(string='ماه ۶', digits='Account')
    month_7 = fields.Float(string='ماه ۷', digits='Account')
    month_8 = fields.Float(string='ماه ۸', digits='Account')
    month_9 = fields.Float(string='ماه ۹', digits='Account')
    month_10 = fields.Float(string='ماه ۱۰', digits='Account')
    month_11 = fields.Float(string='ماه ۱۱', digits='Account')
    month_12 = fields.Float(string='ماه ۱۲', digits='Account')
    total = fields.Float(string='جمع کل', compute='_compute_total', digits='Account')

    @api.model
    def account_tree(self, company_id, section):
        """Category nodes for the account dropdown; members load on expansion."""
        company = self.env['res.company'].browse(int(company_id or self.env.company.id))
        if company not in self.env.companies:
            raise ValidationError('به شرکت انتخاب‌شده دسترسی ندارید.')
        if section not in ('balance', 'income'):
            raise ValidationError('بخش صورت مالی نامعتبر است.')
        root_id = self.env['ir.config_parameter'].sudo().get_param(
            'budget_planning.%s_root_id' % section)
        selected_root = self.env['raes.md.category'].browse(int(root_id or 0)).exists()
        if selected_root:
            if selected_root.parent_id or selected_root.entity_id.name != 'DimSubsidiaryLedger':
                raise ValidationError('گروه‌بندی سراسری معتبر نیست؛ مدیر سیستم باید آن را اصلاح کند.')
            categories = self.env['raes.md.category'].search([
                ('id', 'child_of', selected_root.id),
            ], order='code, title, id')
            roots = selected_root
        else:
            categories = self.env['raes.md.category'].search([
                ('company_id', '=', company.id),
                ('entity_id.name', '=', 'DimSubsidiaryLedger'),
            ], order='code, title, id')
            roots = categories.filtered(lambda c: not c.parent_id and 'گروه بندی حساب معین' in
                                        (c.title or '').replace('‌', ' '))
            if not roots:
                roots = categories.filtered(lambda c: not c.parent_id)
        allowed = set()
        def visit(node):
            if node.id in allowed:
                return
            allowed.add(node.id)
            for child in categories.filtered(lambda c: c.parent_id.id == node.id):
                visit(child)
        for root in roots:
            visit(root)
        return [{'id': c.id, 'company_id': c.company_id.id,
                 'parent_id': c.parent_id.id if c.parent_id.id in allowed else False,
                 'title': c.title} for c in categories if c.id in allowed]

    @api.model
    def account_members(self, category_id, company_id, section):
        category = self.env['raes.md.category'].browse(int(category_id)).exists()
        if not category or category.company_id.id != int(company_id):
            raise ValidationError('زیرگروه نامعتبر است.')
        if section not in ('balance', 'income'):
            raise ValidationError('بخش صورت مالی نامعتبر است.')
        root_id = int(self.env['ir.config_parameter'].sudo().get_param(
            'budget_planning.%s_root_id' % section) or 0)
        if root_id:
            if category.id != root_id and category.root_id.id != root_id:
                raise ValidationError('زیرگروه خارج از گروه‌بندی تنظیم‌شده است.')
        elif category.company_id not in self.env.companies:
            raise ValidationError('به شرکت انتخاب‌شده دسترسی ندارید.')
        result = self.env['raes.md.entity'].sudo().with_company(category.company_id).get_items_in_category(
            category.entity_id.id, category.id, 0, 10000)
        if result.get('reason'):
            raise UserError('دریافت حساب‌های زیرگروه ممکن نشد: %s' % result['reason'])
        if result.get('total', 0) > 10000:
            raise UserError('تعداد حساب‌های زیرگروه بیش از حد مجاز است.')
        return [{'id': item['id'],
                 'title': (item.get('subsidiaryledgertitle') or item.get('label') or '').strip(),
                 'code': str(item.get('subsidiaryledgercode') or '')}
                for item in result['records']]

    @api.depends('title', 'depth', 'row_type')
    def _compute_display_title(self):
        for line in self:
            line.display_title = ('　' * min(line.depth, 12)) + (
                '▸ ' if line.row_type == 'category' else '• ') + (line.title or '')

    @api.depends('input_mode', 'annual_amount', *(f'month_{n}' for n in range(1, 13)))
    def _compute_total(self):
        for line in self:
            line.total = line.annual_amount if line.input_mode == 'annual' else sum(
                line[f'month_{n}'] for n in range(1, 13))

    @staticmethod
    def _month_names():
        return [f'month_{n}' for n in range(1, 13)]

    @staticmethod
    def _distributed(amount):
        monthly = round(amount / 12, 2)
        return {f'month_{n}': monthly if n < 12 else amount - 11 * monthly
                for n in range(1, 13)}

    @api.onchange('annual_amount')
    def _onchange_total(self):
        for line in self:
            if line.row_type == 'category' or line.statement_id.entry_mode != 'annual':
                continue
            line.input_mode = 'annual'
            for name, value in self._distributed(line.annual_amount).items():
                line[name] = value

    @api.onchange(*[f'month_{n}' for n in range(1, 13)])
    def _onchange_months(self):
        for line in self:
            if line.row_type == 'category' or line.statement_id.entry_mode != 'monthly':
                continue
            amount = sum(line[name] for name in self._month_names())
            line.input_mode = 'monthly'
            line.annual_amount = amount

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            statement = self.env['budget.financial.statement'].browse(vals['statement_id'])
            statement.check_access_rights('write')
            self._prepare_amounts(vals, statement)
        return super().create(vals_list)

    def write(self, vals):
        for line in self:
            line.statement_id.check_access_rights('write')
            prepared = dict(vals)
            line._prepare_amounts(prepared, line.statement_id, line)
            super(BudgetFinancialStatementLine, line).write(prepared)
        return True

    def read(self, fields=None, load='_classic_read'):
        for statement in self.mapped('statement_id'):
            statement.check_access_rights('read')
        return super().read(fields=fields, load=load)

    def unlink(self):
        for statement in self.mapped('statement_id'):
            statement.check_access_rights('write')
        return super().unlink()

    def _prepare_amounts(self, vals, statement, record=None):
        months = self._month_names()
        row_type = vals.get('row_type', record.row_type if record else 'member')
        if row_type == 'category':
            if vals.get('annual_amount') or any(vals.get(name) for name in months):
                raise ValidationError('مبلغ فقط در ردیف حساب قابل ثبت است.')
            return
        mode = statement.entry_mode
        if not mode:
            raise ValidationError('ابتدا شیوهٔ ورود اطلاعات جزئیات را انتخاب کنید.')
        changed_months = any(name in vals for name in months)
        changed_total = 'annual_amount' in vals
        values = {name: vals.get(name, record[name] if record else 0.0) for name in months}
        amount = vals.get('annual_amount', record.annual_amount if record else 0.0)
        if mode == 'annual':
            if changed_months and not changed_total:
                raise ValidationError('در شیوهٔ جمع کل، مبلغ را در ستون جمع کل وارد کنید.')
            vals['input_mode'] = 'annual'
            vals.update(self._distributed(amount))
        else:
            if changed_total and not changed_months and amount:
                raise ValidationError('در شیوهٔ ماهانه، مبلغ را در ستون‌های ماه وارد کنید.')
            vals['input_mode'] = 'monthly'
            vals['annual_amount'] = sum(values.values())
