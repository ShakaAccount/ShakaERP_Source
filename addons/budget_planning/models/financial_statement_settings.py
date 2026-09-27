from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class BudgetFinancialStatementSettings(models.TransientModel):
    _name = 'budget.financial.statement.settings'
    _description = 'Global Financial Statement Budget Settings'

    budget_balance_root_id = fields.Many2one(
        'raes.md.category', string='گروه‌بندی حساب معین ترازنامه',
        domain="[('parent_id', '=', False), ('entity_id.name', '=', 'DimSubsidiaryLedger')]")
    budget_income_root_id = fields.Many2one(
        'raes.md.category', string='گروه‌بندی حساب معین سود و زیان',
        domain="[('parent_id', '=', False), ('entity_id.name', '=', 'DimSubsidiaryLedger')]")
    @api.model
    def default_get(self, fields_list):
        self._check_admin()
        values = super().default_get(fields_list)
        params = self.env['ir.config_parameter'].sudo()
        for section in ('balance', 'income'):
            value = int(params.get_param('budget_planning.%s_root_id' % section) or 0) or False
            field = 'budget_%s_root_id' % section
            if field in fields_list:
                values[field] = value
        return values

    def _check_admin(self):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError('فقط مدیر سیستم می‌تواند تنظیمات گروه‌بندی را تغییر دهد.')

    @api.model_create_multi
    def create(self, vals_list):
        self._check_admin()
        return super().create(vals_list)

    def write(self, vals):
        self._check_admin()
        return super().write(vals)

    def action_save(self):
        self._check_admin()
        self.ensure_one()
        params = self.env['ir.config_parameter'].sudo()
        for section in ('balance', 'income'):
            root = self['budget_%s_root_id' % section]
            if root and (root.parent_id or root.entity_id.name != 'DimSubsidiaryLedger'):
                raise ValidationError('گروه‌بندی باید سرگروه حساب معین باشد.')
            params.set_param('budget_planning.%s_root_id' % section, root.id or '')
        return {'type': 'ir.actions.act_window_close'}
