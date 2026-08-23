# -*- coding: utf-8 -*-
"""Authenticated endpoints used by the POS free-item interface."""

import base64
import binascii

from odoo import _, http
from odoo.addons.auth_totp.models.totp import TOTP
from odoo.exceptions import AccessDenied, UserError
from odoo.http import request


class PosFreeItemController(http.Controller):
    """Validate an employee's configured TOTP and claim one allowance slot."""

    @staticmethod
    def _allowed_employees(config):
        """Return the employees explicitly enabled on a POS configuration."""
        return (
            config.basic_employee_ids
            | config.advanced_employee_ids
            | config.minimal_employee_ids
        )

    def _validate_totp(self, employee, code):
        user = employee.user_id
        if not user:
            raise UserError(_("The cashier must be linked to an Odoo user with two-factor authentication enabled."))
        if not user.totp_enabled:
            raise UserError(_("Two-factor authentication is not enabled for this cashier."))

        try:
            user._totp_rate_limit('code_check')
            secret = user.sudo().totp_secret
            valid = bool(TOTP(base64.b32decode(secret)).match(int(code)))
        except (TypeError, ValueError, binascii.Error):
            valid = False
        if not valid:
            raise AccessDenied(_("Verification failed. Enter the current 6-digit authenticator code."))
        user._totp_rate_limit_purge('code_check')

    @http.route('/pos_free_item/claim', type='jsonrpc', auth='user', methods=['POST'])
    def claim(self, employee_id, product_id, pos_config_id, code):
        """Validate a complete free-item request and consume one daily allowance."""
        config = request.env['pos.config'].browse(int(pos_config_id)).exists()
        if not config:
            raise UserError(_("The POS configuration could not be found."))
        if config.company_id != request.env.company:
            raise AccessDenied(_("The POS configuration is not available for this company."))

        employee = request.env['hr.employee'].browse(int(employee_id)).exists()
        if not employee:
            raise UserError(_("The selected cashier could not be found."))

        allowed_employees = self._allowed_employees(config)
        if allowed_employees and employee not in allowed_employees:
            raise AccessDenied(_("This cashier is not allowed to use this POS configuration."))

        catalog_item = request.env['pos.free.item.catalog'].search([
            ('product_id', '=', int(product_id)),
            ('active', '=', True),
            ('company_id', '=', config.company_id.id),
        ], limit=1)
        if not catalog_item:
            raise UserError(_("This product is not available as a free item."))

        self._validate_totp(employee, code)
        allowance = request.env['employee.free.allowance'].claim_for_employee(employee)
        return {
            'allowance_id': allowance.id,
            'remaining': allowance.MAX_PER_DAY - allowance.used_qty,
        }
