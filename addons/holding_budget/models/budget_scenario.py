from odoo import api, fields, models


class HoldingBudgetScenario(models.Model):
    _name = 'holding.budget.scenario'
    _inherit = ['shaka.access.mixin']
    _description = 'Holding Budget Scenarios'
    _order = 'company_id, fiscal_year_id, id desc'

    name = fields.Char(
        string='عنوان فرم',
        required=True,
        default='سناریوهای بودجه',
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
    line_ids = fields.One2many(
        'holding.budget.scenario.line',
        'scenario_id',
        string='سناریوهای بودجه',
        copy=True,
    )


class HoldingBudgetScenarioLine(models.Model):
    _name = 'holding.budget.scenario.line'
    _description = 'Holding Budget Scenario Line'
    _order = 'sequence, id'
    _rec_name = 'scenario_name'

    sequence = fields.Integer(string='ترتیب', default=10)
    scenario_id = fields.Many2one(
        'holding.budget.scenario',
        string='فرم سناریوهای بودجه',
        required=True,
        ondelete='cascade',
    )
    scenario_name = fields.Char(string='عنوان سناریو', required=True)
    description = fields.Text(string='توضیحات')

    _scenario_name_unique = models.Constraint(
        'unique(scenario_id, scenario_name)',
        'این عنوان سناریو قبلاً در همین فرم ثبت شده است.',
    )
