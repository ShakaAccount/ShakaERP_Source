# from odoo import http


# class GenericLookup(http.Controller):
#     @http.route('/generic_lookup/generic_lookup', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/generic_lookup/generic_lookup/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('generic_lookup.listing', {
#             'root': '/generic_lookup/generic_lookup',
#             'objects': http.request.env['generic_lookup.generic_lookup'].search([]),
#         })

#     @http.route('/generic_lookup/generic_lookup/objects/<model("generic_lookup.generic_lookup"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('generic_lookup.object', {
#             'object': obj
#         })

