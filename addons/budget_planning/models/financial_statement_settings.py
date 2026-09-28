from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class BudgetFinancialStatementSettings(models.TransientModel):
    _name = 'budget.financial.statement.settings'
    _description = 'Global Financial Statement Budget Settings'

    company_id = fields.Many2one(
        'res.company', string='شرکت', required=True,
        default=lambda self: self.env.company)
    budget_balance_root_id = fields.Many2one(
        'raes.md.category', string='گروه‌بندی حساب معین ترازنامه',
        domain="[('parent_id', '=', False), ('entity_id.name', '=', 'DimSubsidiaryLedger'), ('company_id', '=', company_id)]")
    budget_income_root_id = fields.Many2one(
        'raes.md.category', string='گروه‌بندی حساب معین سود و زیان',
        domain="[('parent_id', '=', False), ('entity_id.name', '=', 'DimSubsidiaryLedger'), ('company_id', '=', company_id)]")

    @staticmethod
    def _param_key(section, company_id):
        return 'budget_planning.%s_root_id.%s' % (section, company_id)

    def _root_id_for_company(self, section, company_id):
        params = self.env['ir.config_parameter'].sudo()
        root_id = int(params.get_param(self._param_key(section, company_id)) or 0)
        # Keep the existing installation usable until each company has saved
        # its own setting.  The caller still verifies the root's company.
        if not root_id:
            root_id = int(params.get_param('budget_planning.%s_root_id' % section) or 0)
        root = self.env['raes.md.category'].browse(root_id).exists()
        return root.id if root and root.company_id.id == company_id else False
    @api.model
    def default_get(self, fields_list):
        self._check_admin()
        values = super().default_get(fields_list)
        company_id = values.get('company_id') or self.env.company.id
        for section in ('balance', 'income'):
            field = 'budget_%s_root_id' % section
            if field in fields_list:
                values[field] = self._root_id_for_company(section, company_id)
        return values

    @api.onchange('company_id')
    def _onchange_company_id(self):
        for record in self:
            for section in ('balance', 'income'):
                record['budget_%s_root_id' % section] = record._root_id_for_company(
                    section, record.company_id.id) if record.company_id else False

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
            if root and (root.company_id != self.company_id or root.parent_id or
                         root.entity_id.name != 'DimSubsidiaryLedger'):
                raise ValidationError('گروه‌بندی باید سرگروه حساب معین باشد.')
            params.set_param(self._param_key(section, self.company_id.id), root.id or '')
        return {'type': 'ir.actions.act_window_close'}
