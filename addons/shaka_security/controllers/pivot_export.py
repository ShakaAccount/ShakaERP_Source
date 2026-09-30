import json

from werkzeug.datastructures import FileStorage

from odoo import http, _
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.addons.web.controllers.pivot import TableExporter


class ShakaTableExporter(TableExporter):

    @http.route('/web/pivot/export_xlsx', type='http', auth='user', readonly=True)
    def export_xlsx(self, data, **kw):
        payload = json.load(data) if isinstance(data, FileStorage) else json.loads(data)
        if isinstance(data, FileStorage):
            data.seek(0)
        model_name = payload.get('model') if payload else None
        model = request.env.get(model_name) if model_name else None
        if not model:
            raise AccessError(_('Invalid model for Excel export.'))
        model._shaka_check_form_permission('export')
        return super().export_xlsx(data, **kw)
