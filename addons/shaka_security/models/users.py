from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class ResUsers(models.Model):
    _inherit = 'res.users'

    shaka_form_access_ids = fields.One2many('shaka.user.form.access', 'user_id', string='Form Access')

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        internal_users = users.filtered(lambda user: user.active and not user.share)
        internal_users._prepare_shaka_access_for_users(internal_users)
        return users

    def action_prepare_shaka_access(self):
        if not self.env.is_superuser() and not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only Settings administrators can synchronize form access.'))
        self.env['shaka.access.form'].sudo()._sync_registry_models()
        targets = self.env['res.users'].sudo().search([('active', '=', True), ('share', '=', False)])
        self._prepare_shaka_access_for_users(targets)
        return True

    def _prepare_shaka_access_for_users(self, users):
        forms = self.env['shaka.access.form'].sudo().search([('active', '=', True)])
        forms = forms.filtered(lambda form: form.model_name and form.model_name in self.env)
        for user in users:
            existing = self.env['shaka.user.form.access'].sudo().search([('user_id', '=', user.id)])
            stale = existing.filtered(lambda access: not access.form_id.active or access.form_id.model_name not in self.env)
            if stale:
                stale.unlink()
                existing -= stale
            existing_forms = existing.mapped('form_id')
            new_access = self.env['shaka.user.form.access'].sudo().create([
                {'user_id': user.id, 'form_id': form.id} for form in forms - existing_forms
            ])
            (existing | new_access)._ensure_workflow_stages()
        return True

    def has_group(self, group_ext_id):
        result = super().has_group(group_ext_id)
        if result or group_ext_id != 'base.group_allow_export' or 'shaka.user.form.access' not in self.env:
            return result
        self.ensure_one()
        return bool(self.env['shaka.user.form.access'].sudo().search_count([
            ('user_id', '=', self.id), ('can_export', '=', True), ('form_id.active', '=', True),
        ]))
