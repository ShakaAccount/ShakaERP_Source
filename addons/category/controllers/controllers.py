# from odoo import http


# class Category(http.Controller):
#     @http.route('/category/category', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/category/category/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('category.listing', {
#             'root': '/category/category',
#             'objects': http.request.env['category.category'].search([]),
#         })

#     @http.route('/category/category/objects/<model("category.category"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('category.object', {
#             'object': obj
#         })

