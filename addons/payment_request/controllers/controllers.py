# from odoo import http


# class PaymentRequest(http.Controller):
#     @http.route('/payment_request/payment_request', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/payment_request/payment_request/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('payment_request.listing', {
#             'root': '/payment_request/payment_request',
#             'objects': http.request.env['payment_request.payment_request'].search([]),
#         })

#     @http.route('/payment_request/payment_request/objects/<model("payment_request.payment_request"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('payment_request.object', {
#             'object': obj
#         })

