from odoo import fields, models


class DailySalesPosTerminal(models.Model):
    _name = 'daily.sales.pos.terminal'
    _description = 'POS Terminal Master Data'
    _rec_name = 'terminal_number'
    _order = 'branch_id, terminal_number'

    terminal_number = fields.Char(
        string='شماره ترمینال پوز', required=True, index=True,
    )
    branch_id = fields.Many2one(
        'daily.sales.branch', string='شعبه', required=True, index=True,
    )
    description = fields.Char(string='توضیحات')
    active = fields.Boolean(string='فعال', default=True)

    _terminal_branch_unique = models.Constraint(
        'unique(branch_id, terminal_number)',
        'این شماره ترمینال قبلاً برای شعبه انتخاب‌شده تعریف شده است.',
    )
