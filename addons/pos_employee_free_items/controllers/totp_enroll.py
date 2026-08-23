# -*- coding: utf-8 -*-
import pyotp
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessDenied, UserError

class TotpEnrollController(http.Controller):

    @http.route('/pos_free_item/totp/enroll', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def enroll(self):
        """Return a provisioning URI + secret for the current user."""
        user = request.env.user
        if user.totp_secret:
            raise UserError('TOTP already enrolled.')

        secret = pyotp.random_base32()
        user.write({'totp_secret': secret})
        uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.login,
            issuer_name=request.env['ir.config_parameter'].sudo().get_param('web.base.url', 'Odoo')
        )
        return {'secret': secret, 'uri': uri}

    @http.route('/pos_free_item/totp/verify', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def verify(self, code):
        """Validate a TOTP code entered on the POS."""
        user = request.env.user
        if not user.totp_secret:
            raise AccessDenied('TOTP not enrolled.')
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(str(code), valid_window=1):
            raise AccessDenied('Invalid TOTP code.')
        return {'success': True}

    @http.route('/pos_free_item/claim', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def claim(self, employee_id):
        emp = request.env['hr.employee'].browse(employee_id)
        if not emp.exists():
            raise UserError('Employee not found')
        try:
            allowance = request.env['employee.free.allowance']._get_or_create_allowance(emp)
            allowance.claim_free_item()
            return {'allowed': True}
        except UserError as e:
            return {'allowed': False, 'error': str(e)}