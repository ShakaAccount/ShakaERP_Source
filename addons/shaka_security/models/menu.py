from odoo import models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _visible_menu_ids(self, debug=False):
        """Hide registered form menus when the user has no matrix access.

        Odoo normally decides menu visibility from technical model ACLs. The
        Shaka models deliberately have a base ACL and apply the real policy
        through the access matrix, so menu visibility must follow that same
        matrix as well.
        """
        visible_ids = set(super()._visible_menu_ids(debug))
        if self.env.is_superuser() or self.env.user.has_group('base.group_system'):
            return frozenset(visible_ids)

        forms = self.env['shaka.access.form'].sudo().search([
            ('active', '=', True),
            ('model_name', '!=', False),
        ])
        if not forms:
            return frozenset(visible_ids)

        accesses = self.env['shaka.user.form.access'].sudo().search([
            ('user_id', '=', self.env.uid),
            ('form_id', 'in', forms.ids),
        ])
        allowed_models = set()
        for access in accesses:
            if access.form_id.has_workflow:
                if any(
                    stage.can_read or stage.can_create
                    for stage in access.workflow_access_ids
                ):
                    allowed_models.add(access.form_id.model_name)
            elif access.can_read or access.can_create:
                allowed_models.add(access.form_id.model_name)

        registered_models = set(forms.mapped('model_name'))
        menus = self.sudo().browse(visible_ids).exists()
        for menu in menus:
            action = menu.action
            if (
                action
                and action._name == 'ir.actions.act_window'
                and action.res_model in registered_models
                and action.res_model not in allowed_models
            ):
                visible_ids.discard(menu.id)

        # Remove empty menu folders. This also prevents an application whose
        # user has no permitted forms from becoming the default landing page.
        menu_by_id = {menu.id: menu for menu in menus}
        changed = True
        while changed:
            changed = False
            parent_ids = {
                menu.parent_id.id
                for menu_id, menu in menu_by_id.items()
                if menu_id in visible_ids and menu.parent_id
            }
            for menu_id, menu in menu_by_id.items():
                if menu_id in visible_ids and not menu.action and menu_id not in parent_ids:
                    visible_ids.remove(menu_id)
                    changed = True

        return frozenset(visible_ids)
