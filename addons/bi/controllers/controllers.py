# from odoo import http


# class Bi(http.Controller):
#     @http.route('/bi/bi', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/bi/bi/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('bi.listing', {
#             'root': '/bi/bi',
#             'objects': http.request.env['bi.bi'].search([]),
#         })

#     @http.route('/bi/bi/objects/<model("bi.bi"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('bi.object', {
#             'object': obj
#         })

