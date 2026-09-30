from odoo import api, models


class BaseImportImport(models.TransientModel):
    _inherit = 'base_import.import'

    def _shaka_check_import_permission(self, model_name=None):
        model_name = model_name or self.res_model
        target = self.env.get(model_name) if model_name else None
        if target:
            target._shaka_check_form_permission('import')
        return True

    @api.model
    def get_fields_tree(self, model, depth=3):
        self._shaka_check_import_permission(model)
        return super().get_fields_tree(model, depth=depth)

    def parse_preview(self, options, count=10):
        self._shaka_check_import_permission()
        return super().parse_preview(options, count=count)

    def execute_import(self, fields, columns, options, dryrun=False):
        self._shaka_check_import_permission()
        return super().execute_import(fields, columns, options, dryrun=dryrun)
