from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    daily_sales_branch_id = fields.Many2one('daily.sales.branch', string='Assigned Branch')
    shaka_form_access_ids = fields.One2many('shaka.user.form.access', 'user_id', string='Form Access')
    shaka_branch_access_ids = fields.One2many('shaka.user.branch.access', 'user_id', string='Branch Access')

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users.action_prepare_shaka_access()
        return users

    def action_prepare_shaka_access(self):
        forms = self.env['shaka.access.form'].sudo().search([('active', '=', True)])
        for user in self:
            existing = self.env['shaka.user.form.access'].sudo().search([('user_id', '=', user.id)])
            existing_forms = existing.mapped('form_id')
            self.env['shaka.user.form.access'].sudo().create([
                {'user_id': user.id, 'form_id': form.id} for form in forms - existing_forms
            ])
        return True
