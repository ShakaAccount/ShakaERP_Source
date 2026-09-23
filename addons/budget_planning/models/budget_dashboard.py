from odoo import fields, models, tools


class BudgetPlanDashboard(models.Model):
    _name = 'budget.plan.dashboard'
    _inherit = ['shaka.access.mixin']
    _description = 'Budget Planning Dashboard'
    _auto = False
    _rec_name = 'plan_name'
    _order = 'year desc, plan_name'

    plan_id = fields.Many2one('budget.plan', string='برنامه', readonly=True)
    plan_name = fields.Char(string='برنامه', readonly=True)
    year = fields.Char(string='سال مالی', readonly=True)
    company_id = fields.Many2one('res.company', string='شرکت', readonly=True)
    strategy_count = fields.Integer(string='استراتژی', readonly=True)
    target_count = fields.Integer(string='هدف', readonly=True)
    kpi_count = fields.Integer(string='KPI', readonly=True)
    initiative_count = fields.Integer(string='اقدام', readonly=True)
    project_count = fields.Integer(string='پروژه', readonly=True)
    activity_count = fields.Integer(string='فعالیت', readonly=True)
    budget_total = fields.Float(string='بودجه مصوب', readonly=True, digits='Account')
    budget_spent = fields.Float(string='مصرف‌شده', readonly=True, digits='Account')
    budget_consumption = fields.Float(string='درصد مصرف', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f'''
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    p.id AS id,
                    p.id AS plan_id,
                    p.name AS plan_name,
                    fy.name AS year,
                    p.company_id AS company_id,
                    (SELECT count(*) FROM budget_plan_strategy s WHERE s.plan_id = p.id) AS strategy_count,
                    (SELECT count(*) FROM budget_plan_target t WHERE t.plan_id = p.id) AS target_count,
                    (SELECT count(*) FROM budget_plan_kpi k WHERE k.plan_id = p.id) AS kpi_count,
                    (SELECT count(*) FROM budget_plan_initiative i WHERE i.plan_id = p.id) AS initiative_count,
                    (SELECT count(*) FROM budget_plan_project pr WHERE pr.plan_id = p.id) AS project_count,
                    (SELECT count(*) FROM budget_plan_activity a WHERE a.plan_id = p.id) AS activity_count,
                    COALESCE((SELECT sum(bl.approved_amount) FROM budget_plan_budget_line bl WHERE bl.plan_id = p.id), 0) AS budget_total,
                    COALESCE((SELECT sum(bl.spent_amount) FROM budget_plan_budget_line bl WHERE bl.plan_id = p.id), 0) AS budget_spent,
                    CASE WHEN COALESCE((SELECT sum(bl.approved_amount) FROM budget_plan_budget_line bl WHERE bl.plan_id = p.id), 0) = 0 THEN 0
                         ELSE COALESCE((SELECT sum(bl.spent_amount) FROM budget_plan_budget_line bl WHERE bl.plan_id = p.id), 0) * 100 /
                              (SELECT sum(bl.approved_amount) FROM budget_plan_budget_line bl WHERE bl.plan_id = p.id)
                    END AS budget_consumption
                FROM budget_plan p
                LEFT JOIN company_fiscal_year fy ON fy.id = p.fiscal_year_id
            )
        ''')
