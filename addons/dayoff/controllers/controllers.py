# from odoo import http


# class Dayoff(http.Controller):
#     @http.route('/dayoff/dayoff', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/dayoff/dayoff/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('dayoff.listing', {
#             'root': '/dayoff/dayoff',
#             'objects': http.request.env['dayoff.dayoff'].search([]),
#         })

#     @http.route('/dayoff/dayoff/objects/<model("dayoff.dayoff"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('dayoff.object', {
#             'object': obj
#         })

