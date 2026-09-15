# from odoo import http


# class Entity(http.Controller):
#     @http.route('/entity/entity', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/entity/entity/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('entity.listing', {
#             'root': '/entity/entity',
#             'objects': http.request.env['entity.entity'].search([]),
#         })

#     @http.route('/entity/entity/objects/<model("entity.entity"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('entity.object', {
#             'object': obj
#         })

