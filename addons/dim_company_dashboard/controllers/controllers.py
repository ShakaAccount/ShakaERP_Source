# from odoo import http


# class DimCompanyDashboard(http.Controller):
#     @http.route('/dim_company_dashboard/dim_company_dashboard', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/dim_company_dashboard/dim_company_dashboard/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('dim_company_dashboard.listing', {
#             'root': '/dim_company_dashboard/dim_company_dashboard',
#             'objects': http.request.env['dim_company_dashboard.dim_company_dashboard'].search([]),
#         })

#     @http.route('/dim_company_dashboard/dim_company_dashboard/objects/<model("dim_company_dashboard.dim_company_dashboard"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('dim_company_dashboard.object', {
#             'object': obj
#         })

