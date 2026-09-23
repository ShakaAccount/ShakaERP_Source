from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HoldingBudgetAssumption(models.Model):
    _name = 'holding.budget.assumption'
    _inherit = ['shaka.access.mixin']
    _description = 'Holding Budget Assumptions'
    _order = 'company_id, fiscal_year_id, registration_date desc, id desc'

    name = fields.Char(
        string='عنوان فرم',
        required=True,
        default='مفروضات بودجه',
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='شرکت',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    fiscal_year_id = fields.Many2one(
        'company.fiscal.year',
        string='سال مالی',
        required=True,
        domain="[('company_id', '=', company_id)]",
        ondelete='restrict',
    )
    scenario_line_id = fields.Many2one(
        'holding.budget.scenario.line',
        string='سناریوی بودجه',
        required=True,
        domain="[('scenario_id.company_id', '=', company_id), ('scenario_id.fiscal_year_id', '=', fiscal_year_id)]",
        ondelete='restrict',
    )
    scenario_id = fields.Many2one(
        'holding.budget.scenario',
        string='سناریوی بودجه',
        related='scenario_line_id.scenario_id',
        store=True,
        readonly=True,
    )
    registration_date = fields.Date(
        string='تاریخ ثبت',
        required=True,
        default=fields.Date.context_today,
    )
    line_ids = fields.One2many(
        'holding.budget.assumption.line',
        'assumption_id',
        string='جزئیات مفروضات',
        copy=True,
    )

    @api.constrains('scenario_id', 'company_id', 'fiscal_year_id')
    def _check_scenario_context(self):
        for record in self:
            if record.scenario_id and (
                record.scenario_id.company_id != record.company_id
                or record.scenario_id.fiscal_year_id != record.fiscal_year_id
            ):
                raise ValidationError('سناریوی بودجه باید متعلق به همان شرکت و سال مالی انتخاب‌شده باشد.')


class HoldingBudgetAssumptionLine(models.Model):
    _name = 'holding.budget.assumption.line'
    _description = 'Holding Budget Assumption Line'
    _order = 'sequence, id'

    sequence = fields.Integer(string='ترتیب', default=10)
    assumption_id = fields.Many2one(
        'holding.budget.assumption',
        string='فرم مفروضات بودجه',
        required=True,
        ondelete='cascade',
    )
    assumption_group_id = fields.Many2one(
        'lookup.value',
        string='گروه مفروضات',
        required=True,
        domain="[('type_id.code', '=', 'budget_assumption_group')]",
        ondelete='restrict',
    )
    title = fields.Char(string='عنوان', required=True)
    impact_percent = fields.Float(string='درصد اثرگذاری', required=True, digits=(16, 4))

    _assumption_title_unique = models.Constraint(
        'unique(assumption_id, assumption_group_id, title)',
        'این عنوان در همین گروه مفروضات قبلاً ثبت شده است.',
    )

    @api.constrains('impact_percent')
    def _check_impact_percent(self):
        for record in self:
            if record.impact_percent < 0 or record.impact_percent > 100:
                raise ValidationError('درصد اثرگذاری باید بین صفر تا صد باشد.')
