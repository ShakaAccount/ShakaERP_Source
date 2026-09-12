from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class ShakaAccessMixin(models.AbstractModel):
    _name = 'shaka.access.mixin'
    _description = 'Shaka User Access Control'

    def _shaka_access_record(self):
        form = self.env['shaka.access.form'].sudo().search([
            ('model_name', '=', self._name), ('active', '=', True),
        ], limit=1)
        if not form or self.env.is_superuser() or self.env.user.has_group('base.group_system'):
            return form, False
        access = self.env['shaka.user.form.access'].sudo().search([
            ('user_id', '=', self.env.uid), ('form_id', '=', form.id),
        ], limit=1)
        return form, access

    def check_access_rights(self, operation, raise_exception=True):
        result = super().check_access_rights(operation, raise_exception)
        form, access = self._shaka_access_record()
        if not form or self.env.is_superuser() or self.env.user.has_group('base.group_system'):
            return result
        if form.has_workflow:
            return result
        allowed = access and getattr(access, f'can_{operation}', False)
        if not allowed:
            if raise_exception:
                raise AccessError(_('Access to operation "%s" on form "%s" is not allowed.') % (operation, form.name))
            return False
        return result

    def _shaka_check_workflow_access(self, stage, operation='write'):
        form, access = self._shaka_access_record()
        if (
            not form
            or self.env.is_superuser()
            or self.env.user.has_group('base.group_system')
            or not form.has_workflow
        ):
            return True
        stage_config = form.stage_ids.filtered(lambda item: item.code == stage)[:1]
        if not stage_config:
            return True
        stage_access = self.env['shaka.user.workflow.access'].sudo().search([
            ('access_id', '=', access.id if access else False),
            ('stage_id', '=', stage_config.id),
        ], limit=1)
        if not stage_access or not getattr(stage_access, f'can_{operation}', False):
            raise AccessError(_('Access to workflow stage "%s" on form "%s" is not allowed.') % (stage_config.name, form.name))
        return True

    def read(self, fields=None, load='_classic_read'):
        for record in self:
            stage = getattr(record, 'state', False)
            if stage:
                record._shaka_check_workflow_access(stage, 'read')
        return super().read(fields=fields, load=load)


class ShakaAccessForm(models.Model):
    _name = 'shaka.access.form'
    _description = 'Shaka Form Access Configuration'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    model_name = fields.Char(string='Model Technical Name', index=True)
    sequence = fields.Integer(default=10)
    has_workflow = fields.Boolean(string='Has Workflow')
    active = fields.Boolean(default=True)
    stage_ids = fields.One2many('shaka.access.form.stage', 'form_id', string='Workflow Stages')

    _model_unique = models.Constraint('unique(model_name)', 'Only one access definition is allowed per model.')

    @api.model
    def _cleanup_legacy_ui(self):
        menus = self.env['ir.ui.menu'].sudo().search([
            ('name', 'in', ['دسترسی کاربران', 'Ø¯Ø³ØªØ±Ø³ÛŒ Ú©Ø§Ø±Ø¨Ø±Ø§Ù†']),
        ])
        menus.write({'active': False})

    def init(self):
        # Move the old XML identifiers and technical model names in place
        # before the central security data file is loaded. This preserves all
        # existing user and workflow permission rows.
        self.env.cr.execute("""
            UPDATE ir_model_data
               SET module = 'shaka_security'
             WHERE module = 'daily_sales_performance'
               AND name LIKE 'access_%'
               AND model IN ('shaka.access.form', 'shaka.access.form.stage')
        """)


class ShakaAccessFormStage(models.Model):
    _name = 'shaka.access.form.stage'
    _description = 'Shaka Form Workflow Stage'
    _order = 'sequence, id'

    form_id = fields.Many2one('shaka.access.form', required=True, ondelete='cascade')
    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)

    _code_unique = models.Constraint('unique(form_id, code)', 'Stage code must be unique per form.')


class ShakaUserFormAccess(models.Model):
    _name = 'shaka.user.form.access'
    _description = 'Shaka User Form Access'
    _order = 'form_id, id'

    user_id = fields.Many2one('res.users', required=True, ondelete='cascade')
    form_id = fields.Many2one('shaka.access.form', required=True, ondelete='cascade')
    has_workflow = fields.Boolean(related='form_id.has_workflow', readonly=True)
    can_read = fields.Boolean(string='Show')
    can_create = fields.Boolean(string='Create')
    can_write = fields.Boolean(string='Edit')
    can_unlink = fields.Boolean(string='Delete')
    workflow_access_ids = fields.One2many('shaka.user.workflow.access', 'access_id', string='Workflow Access')

    _user_form_unique = models.Constraint('unique(user_id, form_id)', 'A user can have one access row per form.')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            missing = record.form_id.stage_ids - record.workflow_access_ids.mapped('stage_id')
            if record.form_id.has_workflow and missing:
                self.env['shaka.user.workflow.access'].create([
                    {'access_id': record.id, 'stage_id': stage.id} for stage in missing
                ])
        self.env.registry.clear_cache()
        return records

    def write(self, vals):
        result = super().write(vals)
        self.env.registry.clear_cache()
        return result

    def unlink(self):
        result = super().unlink()
        self.env.registry.clear_cache()
        return result


class ShakaUserWorkflowAccess(models.Model):
    _name = 'shaka.user.workflow.access'
    _description = 'Shaka User Workflow Access'
    _order = 'stage_id, id'

    access_id = fields.Many2one('shaka.user.form.access', required=True, ondelete='cascade')
    stage_id = fields.Many2one('shaka.access.form.stage', required=True, ondelete='cascade')
    can_read = fields.Boolean(string='Show')
    can_create = fields.Boolean(string='Create')
    can_write = fields.Boolean(string='Edit')
    can_unlink = fields.Boolean(string='Delete')

    _access_stage_unique = models.Constraint('unique(access_id, stage_id)', 'A stage can only be assigned once per form access.')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.registry.clear_cache()
        return records

    def write(self, vals):
        result = super().write(vals)
        self.env.registry.clear_cache()
        return result

    def unlink(self):
        result = super().unlink()
        self.env.registry.clear_cache()
        return result


class ShakaUserBranchAccess(models.Model):
    _name = 'shaka.user.branch.access'
    _description = 'Shaka User Branch Access'
    _order = 'branch_id, id'

    user_id = fields.Many2one('res.users', required=True, ondelete='cascade')
    branch_id = fields.Many2one('daily.sales.branch', required=True, ondelete='cascade')

    _user_branch_unique = models.Constraint('unique(user_id, branch_id)', 'A branch cannot be assigned twice to one user.')

    def _sync_legacy_branch_field(self, users):
        for user in users:
            branches = self.search([('user_id', '=', user.id)]).mapped('branch_id')
            user.sudo().write({'daily_sales_branch_id': branches.id if len(branches) == 1 else False})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._sync_legacy_branch_field(records.mapped('user_id'))
        return records

    def write(self, vals):
        users = self.mapped('user_id')
        result = super().write(vals)
        self._sync_legacy_branch_field(users | self.mapped('user_id'))
        return result

    def unlink(self):
        users = self.mapped('user_id')
        result = super().unlink()
        self._sync_legacy_branch_field(users)
        return result
