from contextvars import ContextVar

from odoo import api, fields, models, _
from odoo.exceptions import AccessError
from odoo.orm.domains import Domain
from odoo.tools import SQL


_WORKFLOW_WRITE_AUTHORIZED = ContextVar('shaka_workflow_write_authorized', default=False)


class ShakaBaseAccess(models.AbstractModel):
    """Apply configured Shaka permissions to every model, not only mixin users."""

    _inherit = 'base'

    def check_access(self, operation):
        form, _access = self._shaka_access_configuration()
        if not form or self.env.su:
            return super().check_access(operation)
        self._shaka_check_form_permission(operation)
        # On centrally managed forms, the per-user matrix supplies model CRUD
        # permissions. Keep Odoo record rules as the row-level boundary.
        if any(self._ids):
            Rule = self.env['ir.rule']
            domain = Rule._compute_domain(self._name, operation)
            if domain and (forbidden := self - self.sudo().with_context(active_test=False).filtered_domain(domain)):
                raise Rule._make_access_error(operation, forbidden)
        return None

    def has_access(self, operation):
        form, _access = self._shaka_access_configuration()
        if not form or self.env.su:
            return super().has_access(operation)
        try:
            self._shaka_check_form_permission(operation)
        except AccessError:
            return False
        if any(self._ids):
            Rule = self.env['ir.rule']
            domain = Rule._compute_domain(self._name, operation)
            if domain and self != self.sudo().with_context(active_test=False).filtered_domain(domain):
                return False
        return True

    def export_data(self, fields_to_export):
        self._shaka_check_form_permission('export')
        return super().export_data(fields_to_export)

    @api.model
    def load(self, fields, data):
        self._shaka_check_form_permission('import')
        return super().load(fields, data)

    @api.model_create_multi
    def create(self, vals_list):
        form, _access = self._shaka_access_configuration()
        if form and form.has_workflow:
            for vals in vals_list:
                if vals.get('state', 'draft') != 'draft':
                    raise AccessError(_('Workflow records must be created in the draft stage.'))
                self._shaka_check_form_permission('create', 'draft')
        return super().create(vals_list)

    def write(self, vals):
        form, _access = self._shaka_access_configuration()
        if form and form.has_workflow and 'state' in vals and not _WORKFLOW_WRITE_AUTHORIZED.get():
            raise AccessError(_('Change the workflow stage through its authorized workflow action.'))
        return super().write(vals)

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, *, active_test=True, bypass_access=False):
        form, access = self._shaka_access_configuration()
        if form and form.has_workflow and not bypass_access and 'state' in self._fields:
            allowed_codes = access.workflow_access_ids.filtered(
                lambda item: item.can_read
            ).mapped('stage_id.code') if access else []
            domain = Domain(domain) & Domain('state', 'in', allowed_codes)
        elif form and access and not access.can_read and access.can_create and not bypass_access:
            # Let create-only users open a list action with no existing rows.
            domain = Domain(domain) & Domain('id', '=', 0)
        return super()._search(
            domain, offset=offset, limit=limit, order=order,
            active_test=active_test, bypass_access=bypass_access,
        )

    def _shaka_is_internal_workflow_write(self):
        return _WORKFLOW_WRITE_AUTHORIZED.get()

    def _shaka_workflow_write(self, vals, expected_state=None):
        """Write workflow-only fields from a checked private server method."""
        if 'state' in vals:
            if expected_state is None:
                raise AccessError(_('A workflow transition must declare its expected current stage.'))
            form, _access = self._shaka_access_configuration()
            if form and form.has_workflow and not form.stage_ids.filtered(
                lambda item: item.code == vals['state']
            ):
                raise AccessError(_('The destination workflow stage is not configured.'))
            for record in self:
                if record.state != expected_state:
                    raise AccessError(_('This workflow action is not valid from the current stage.'))
                record._shaka_check_workflow_access(record.state, 'write')
        token = _WORKFLOW_WRITE_AUTHORIZED.set(True)
        try:
            return self.write(vals)
        finally:
            _WORKFLOW_WRITE_AUTHORIZED.reset(token)

    def _shaka_access_configuration(self):
        if self.env.is_superuser() or self.env.user.has_group('base.group_system'):
            return False, False
        if 'shaka.access.form' not in self.env:
            return False, False
        form = self.env['shaka.access.form'].sudo().search([
            ('model_name', '=', self._name), ('active', '=', True),
        ], limit=1)
        if not form:
            return False, False
        access = self.env['shaka.user.form.access'].sudo().search([
            ('user_id', '=', self.env.uid), ('form_id', '=', form.id),
        ], limit=1)
        return form, access

    def _shaka_check_form_permission(self, operation, stage=None):
        """Check central CRUD/import/export rights for a configured form.

        Unconfigured models keep Odoo's native ACL and record-rule behavior.
        Workflow record checks read the state directly from SQL so checking a
        read permission cannot recursively trigger another ORM read.
        """
        form, access = self._shaka_access_configuration()
        if not form:
            return True
        if operation in ('import', 'export'):
            allowed = access and getattr(access, f'can_{operation}', False)
            if not allowed:
                raise AccessError(_('Excel %(operation)s is not allowed for form "%(form)s".',
                                   operation=operation, form=form.name))
            return True
        if operation not in ('read', 'create', 'write', 'unlink'):
            return True
        if not access:
            raise AccessError(_('No access is configured for form "%s".') % form.name)

        if not form.has_workflow:
            if operation == 'read' and not self and access.can_create:
                return True
            if not getattr(access, f'can_{operation}', False):
                raise AccessError(_('Access to operation "%s" on form "%s" is not allowed.') % (operation, form.name))
            return True

        if stage is not None:
            stages = form.stage_ids.filtered(lambda item: item.code == stage)
            stage_config = stages[:1]
            if not stage_config:
                raise AccessError(_('Workflow stage "%s" is not configured for form "%s".') % (stage, form.name))
            stage_access = access.workflow_access_ids.filtered(lambda item: item.stage_id == stage_config)
            if not stage_access or not getattr(stage_access[:1], f'can_{operation}', False):
                raise AccessError(_('Access to workflow stage "%s" on form "%s" is not allowed.') % (stage_config.name, form.name))
            return True

        if operation == 'create':
            # Workflow documents are created in draft. Fail closed if that
            # stage or its create permission has not been configured.
            return self._shaka_check_form_permission(operation, 'draft')

        if self and 'state' in self._fields and self._table:
            rows = self.env.execute_query(SQL(
                "SELECT id, state FROM %s WHERE id = ANY(%s)",
                SQL.identifier(self._table), list(self.ids),
            ))
            for _record_id, state in rows:
                self._shaka_check_form_permission(operation, state)
            return True

        # Empty recordsets are used for model-level permission checks before
        # search/create. Permit them only if at least one configured stage
        # grants the operation; concrete records are checked again by stage.
        if not any(
            getattr(stage_access, f'can_{operation}', False)
            or (operation == 'read' and stage_access.can_create)
            for stage_access in access.workflow_access_ids
        ):
            raise AccessError(_('Access to operation "%s" on form "%s" is not allowed.') % (operation, form.name))
        return True


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

    def _shaka_check_workflow_access(self, stage, operation='write'):
        form, _access = self._shaka_access_record()
        if not form or not form.has_workflow:
            return True
        return self._shaka_check_form_permission(operation, stage)

    def write(self, vals):
        if 'state' not in vals or not hasattr(self, 'message_notify'):
            return super().write(vals)
        old_states = {record.id: record.state for record in self}
        result = super().write(vals)
        for record in self:
            if record.state != old_states[record.id]:
                record._shaka_notify_stage_change(old_states[record.id])
        return result

    def _shaka_notify_stage_change(self, old_state):
        """ Tell the users who can act on the new stage, and the creator, that the
        record moved (inbox, email or Telegram, per their preferences). """
        self.ensure_one()
        form = self.env['shaka.access.form'].sudo().search([
            ('model_name', '=', self._name), ('active', '=', True), ('has_workflow', '=', True),
        ], limit=1)
        if not form:
            return
        stage = form.stage_ids.filtered(lambda s: s.code == self.state)[:1]
        stage_users = self.env['shaka.user.workflow.access'].sudo().search([
            ('stage_id', '=', stage.id), ('can_write', '=', True),
        ]).access_id.user_id if stage else self.env['res.users']
        creator = getattr(self, 'created_by', False) or self.create_uid
        partners = (stage_users | creator).filtered('active').partner_id - self.env.user.partner_id
        if not partners:
            return
        labels = dict(self._fields['state']._description_selection(self.env))
        old_name = form.stage_ids.filtered(lambda s: s.code == old_state)[:1].name or labels.get(old_state, old_state)
        new_name = stage.name or labels.get(self.state, self.state)
        self.sudo().message_notify(
            partner_ids=partners.ids,
            body=_('%(form)s %(record)s: %(old)s → %(new)s (%(user)s)',
                   form=form.name, record=self.display_name, old=old_name, new=new_name,
                   user=self.env.user.name),
            subject=_('%(form)s %(record)s: %(new)s', form=form.name, record=self.display_name, new=new_name),
        )

class ShakaAccessForm(models.Model):
    _name = 'shaka.access.form'
    _description = 'Shaka Form Access Configuration'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    model_name = fields.Char(string='Model Technical Name', index=True)
    sequence = fields.Integer(default=10)
    has_workflow = fields.Boolean(
        string='Has Workflow',
        help='Enable stage-based access for models with a state workflow. Stage codes must match the model state values.',
    )
    active = fields.Boolean(
        default=True,
        help='When disabled, Shaka Security stops enforcing this form and Odoo native ACLs apply.',
    )
    stage_ids = fields.One2many('shaka.access.form.stage', 'form_id', string='Workflow Stages')

    _model_unique = models.Constraint('unique(model_name)', 'Only one access definition is allowed per model.')

    def write(self, vals):
        result = super().write(vals)
        if 'has_workflow' in vals:
            accesses = self.env['shaka.user.form.access'].sudo().search([('form_id', 'in', self.ids)])
            accesses._ensure_workflow_stages()
        return result

    @api.model
    def _sync_registry_models(self):
        """Register window-action models so add-on developers need no XML entry."""
        actions = self.env['ir.actions.act_window'].sudo().search([('res_model', '!=', False)])
        model_names = set(actions.mapped('res_model'))
        model_names.update(self.sudo().search([('model_name', '!=', False)]).mapped('model_name'))
        model_names.difference_update({
            'res.users', 'ir.model', 'ir.model.access', 'base_import.import',
            'shaka.access.form', 'shaka.access.form.stage',
            'shaka.user.form.access', 'shaka.user.workflow.access',
        })
        ir_models = self.env['ir.model'].sudo().search([
            ('model', 'in', list(model_names)), ('abstract', '=', False), ('transient', '=', False),
        ])
        existing_names = set(self.sudo().search([
            ('model_name', 'in', ir_models.mapped('model')),
        ]).mapped('model_name'))
        vals_list = []
        for model in ir_models:
            registered_model = self.env.get(model.model)
            if registered_model and getattr(registered_model, '_auto', False) and model.model not in existing_names:
                vals_list.append({
                    'name': model.name or model.model,
                    'model_name': model.model,
                    'sequence': 100,
                })
        if vals_list:
            self.sudo().create(vals_list)
        return True

    def action_sync_registry_models(self):
        if not self.env.is_superuser() and not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only Settings administrators can synchronize access forms.'))
        self._sync_registry_models()
        users = self.env['res.users'].sudo().search([('active', '=', True), ('share', '=', False)])
        users._prepare_shaka_access_for_users(users)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Access forms synchronized'),
                'message': _('Installed window-action models are now available in user access settings.'),
                'type': 'success',
                'sticky': False,
            },
        }

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

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_user_access_rows()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._ensure_user_access_rows()
        return result

    def _ensure_user_access_rows(self):
        access_model = self.env['shaka.user.form.access'].sudo()
        workflow_model = self.env['shaka.user.workflow.access'].sudo()
        for stage in self:
            if not stage.form_id.has_workflow:
                continue
            accesses = access_model.search([('form_id', '=', stage.form_id.id)])
            existing = workflow_model.search([
                ('access_id', 'in', accesses.ids), ('stage_id', '=', stage.id),
            ]).mapped('access_id')
            missing = accesses - existing
            if missing:
                workflow_model.create([
                    {'access_id': access.id, 'stage_id': stage.id} for access in missing
                ])
        return True


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
    can_import = fields.Boolean(string='Excel Import')
    can_export = fields.Boolean(string='Excel Export')
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
        self._ensure_workflow_stages()
        self.env.registry.clear_cache()
        return result

    def _ensure_workflow_stages(self):
        for record in self.filtered(lambda item: item.form_id.has_workflow):
            missing = record.form_id.stage_ids - record.workflow_access_ids.mapped('stage_id')
            if missing:
                self.env['shaka.user.workflow.access'].create([
                    {'access_id': record.id, 'stage_id': stage.id} for stage in missing
                ])
        return True

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
