import datetime
import json
from unittest.mock import MagicMock, patch

from odoo import Command
from odoo.tools import mute_logger

from odoo.addons.hr_expense.tests.common import TestExpenseCommon
from odoo.addons.hr_expense_stripe.controllers.main import StripeIssuingController
from odoo.addons.hr_expense_stripe.utils import format_amount_to_stripe
from odoo.addons.http_routing.tests.common import MockRequest
from odoo.addons.phone_validation.tools import phone_validation

MAKE_STRIPE_REQUEST_PROXY = 'odoo.addons.hr_expense_stripe.{}.make_request_stripe_proxy'


class TestExpenseStripeCommon(TestExpenseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.country_code = False
        cls.euro_currency = cls.env.ref('base.EUR')
        cls.eu_country = cls.env.ref('base.be')

        chart_template_ref = cls.env['account.chart.template']._guess_chart_template(cls.eu_country)
        template_vals = cls.env['account.chart.template']._get_chart_template_mapping()[chart_template_ref]
        template_module = cls.env['ir.module.module']._get(template_vals['module'])
        if template_module.state != 'installed':
            cls.chart_template = 'generic_coa'  # We want the tests to run without l10n_be installed
        cls.stripe_company_data = cls.setup_other_company(
            name='Stripe Company',
            currency_id=cls.euro_currency.id,
            country_id=cls.eu_country.id,
            account_fiscal_country_id=cls.eu_country.id,
        )
        cls.env = cls.env(context={'allowed_company_ids': cls.stripe_company_data['company'].ids})
        cls.company = cls.stripe_company = cls.stripe_company_data['company']
        cls.stripe_journal = cls.env['account.chart.template'].ref('stripe_issuing_journal')

        if cls.stripe_company.account_fiscal_country_id != cls.eu_country:
            # If the generic_coa was installed
            cls.stripe_company.write({
                'country_id': cls.eu_country.id,
                'account_fiscal_country_id': cls.eu_country.id,
                'stripe_currency_id': cls.euro_currency.id,
            })
        tax_group = cls.env['account.tax.group'].create({
            'name': "Tax group for Stripe tests",
            'country_id': cls.eu_country.id,
        })
        cls.stripe_tax = cls.env['account.tax'].create({
            'name': "Tax that is 50%",
            'company_id': cls.stripe_company.id,
            'country_id': cls.eu_country.id,
            'tax_group_id': tax_group.id,
            'amount': 50,
        })
        cls.stripe_company.account_purchase_tax_id = cls.stripe_tax.id
        cls.stripe_company.zip = '1000'
        cls.expense_user_employee.company_ids += cls.env.company
        cls.expense_user_employee.company_id = cls.env.company
        cls.expense_user_employee.partner_id.write({
            'country_id': cls.eu_country,
            'street': '123 Stripe St',
            'city': 'Brussels',
            'zip': '1000',
        })
        cls.expense_user_manager.company_ids += cls.env.company
        cls.expense_user_manager.company_id = cls.env.company
        cls.stripe_manager_employee = cls.env['hr.employee'].sudo().create({
            'name': 'Stripe Manager Employee',
            'user_id': cls.expense_user_manager.id,
            'company_id': cls.stripe_company.id,
        }).sudo(False)
        cls.stripe_employee = cls.env['hr.employee'].sudo().create({
            'name': 'Stripe Employee',
            'user_id': cls.expense_user_employee.id,
            'company_id': cls.stripe_company.id,
            'birthday': datetime.date(1990, 1, 1),
            'address_id': cls.expense_user_employee.partner_id.id,
            'parent_id': cls.stripe_manager_employee.id,
            'work_phone': '+32000000000',
        }).sudo(False)
        cls.iap_key_private = cls.env['certificate.key']._generate_ed25519_private_key(company=cls.stripe_company, name="IAP TEST KEY")
        cls.iap_key_public_bytes = cls.iap_key_private._get_public_key_bytes()
        cls.iap_key_public = cls.env['certificate.key'].create([{
            'name': 'IAP TEST PUBLIC KEY',
            'content': cls.iap_key_public_bytes,
            'company_id': cls.stripe_company.id,
        }])
        cls.Controller = StripeIssuingController()

        # Override the signature validation of the controller for the tests
        cls.Controller._validate_signature = MagicMock()
        cls.Controller._validate_signature.return_value = True

        cls.env['ir.config_parameter'].set_param('hr_expense_stripe.stripe_mode', 'test')  # Just to be sure
        # Set taxes belonging to the proper company on the products

        cls.env['product.mcc.stripe.tag'].search([]).product_id.supplier_taxes_id = [
            Command.set(cls.stripe_company.account_purchase_tax_id.ids),
        ]
        cls.env = cls.env(user=cls.expense_user_employee)

    @classmethod
    def assertIsSubset(cls, expected, actual, msg=None, depth=0):
        """Assert that `actual` contains all key-value pairs in `expected`."""
        errors = []
        if not isinstance(expected, dict) or not isinstance(actual, dict):
            errors.append(f"Both expected and actual must be dictionaries, got {expected.__class__} and {actual.__class__}")

        for key, value in expected.items():
            if key not in actual:
                errors.append(f'Missing key "{key}" in dict')
                continue
            if value == '__ignored__':
                # When we just want to know that the key has a value
                continue
            tested_value = actual[key]
            if isinstance(value, dict) and isinstance(tested_value, dict):
                errors += cls.assertIsSubset(value, tested_value, msg=f'Sub-dict "{key}" error', depth=depth + 1)
            elif value != tested_value:
                errors.append(f'Key "{key}" expected "{value}" as value, {actual[key]}  was found instead')

        if depth > 0:
            if errors:
                return [msg] + errors
            else:
                return []

        if errors:
            raise cls.failureException('\n'.join((msg, *errors)))
        return []

    def patched_make_request_stripe_proxy(self, expected_calls):
        def patched_inner(company, route, route_params=None, payload=None, method="POST", headers=None):
            payload = payload or {}
            if not expected_calls:
                raise ValueError(
                    f"No more calls were expected, but we received: {route} {method} with payload: {payload} for company {company.display_name}"
                )
            expected_call = expected_calls.pop(0)
            self.assertEqual(self.stripe_company.id, company.id)
            self.assertEqual(expected_call.get('route'), route, "Wrong route called")
            self.assertEqual(expected_call.get('method'), method, "Wrong method for request")
            expected_route_params = expected_call.get('route_params')
            if expected_route_params:
                self.assertIsSubset(expected_route_params, route_params, "Wrong route params")
            expected_headers = expected_call.get('headers')
            if expected_headers:
                self.assertDictEqual(expected_headers, headers, "Wrong headers")
            if expected_call.get('payload', '__ignored__') != '__ignored__':
                self.assertIsSubset(
                    expected=expected_call['payload'],
                    actual=payload,
                    msg='Create Stripe connect account request failed with the following errors:',
                )
            return expected_call['return_data']
        return patched_inner

    def patch_stripe_requests(self, method_path, expected_calls):
        """ Helper to patch the stripe request method with expected calls"""
        return patch(
            target=MAKE_STRIPE_REQUEST_PROXY.format(method_path),
            new=self.patched_make_request_stripe_proxy(expected_calls),
        )

    def setup_account_creation(self, funds_amount=0, create_active_card_for=None):
        """ Helper to create the account on the database by mocking required calls

        :param None|float funds_amount: If set, will fund the account with the given amount after creation
        :param None|hr.employee create_active_card_for: If set, will create and activate a virtual card for the given employee after creation
        """
        expected_calls = [
            {
                'route': 'accounts',
                'method': 'POST',
                'payload': {
                    'business_type': 'company',
                    'business_profile[name]': 'Stripe Company',
                    'company[address][country]': 'BE',
                    'country': 'BE',
                    'db_public_key': '__ignored__',
                    'db_uuid': '__ignored__',
                    'db_webhook_url': '__ignored__',
                },
                'return_data': {
                    'id': 'acct_1234567890',
                    'iap_public_key': self.iap_key_public_bytes.decode(),
                    'stripe_pk': 'stripe_public_key',
                },
            },
            {
                'route': 'account_links',
                'method': 'POST',
                'payload': {
                    'account': 'acct_1234567890',
                    'refresh_url': '__ignored__',
                    'return_url': '__ignored__',
                },
                'return_data': {
                    'url': 'WWW.SOME.STRIPE.URL',
                },
            },
        ]
        with self.patch_stripe_requests('models.res_company', expected_calls):
            self.stripe_company.with_context(skip_stripe_account_creation_commit=True)._create_stripe_account()  # To fix in master to use the action method
            self.stripe_company.action_configure_stripe_account()
        if funds_amount:
            self.fund_account(amount=funds_amount)
        if create_active_card_for:
            card = self.create_card(
                card_name='Test Card',
                employee=create_active_card_for,
                create_cardholder=True,
            )
            expected_calls = [{
                'route': 'cards',
                'method': 'POST',
                'payload': '__ignored__',
                'return_data': {
                    'id': 'ic_1234567890',
                    'status': 'active',
                    'type': 'virtual',
                    'cancellation_reason': None,
                    'last4': '1234',
                    'exp_month': 12,
                    'exp_year': 2125,
                    'livemode': False,
                },
            }]
            with self.patch_stripe_requests('models.hr_expense_stripe_card', expected_calls):
                card.action_activate_card()
            return card
        return self.env['hr.expense.stripe.card']

    def fund_account(self, amount=100000.0):
        """ Helper to quickly fund the account on the database by mocking required calls """
        self.simulate_webhook_call(
            self.get_event_balance_updated_data(format_amount_to_stripe(amount, self.euro_currency))
        )
        self.simulate_webhook_call(
            self.get_event_topup_succeeded_updated_data(format_amount_to_stripe(amount, self.euro_currency))
        )

    def create_cardholder(self, card, employee):
        """ Helper to quickly create a cardholder on the database by mocking required calls """
        action = card.sudo().action_open_cardholder_wizard()
        wizard = (
            self.env['hr.expense.stripe.cardholder.wizard']
            .with_context(action['context'])
            .with_user(self.expense_user_manager)
            .browse(action['res_id'])
        )
        wizard.phone_number = '+32000000000'

        expected_calls = [{
            'route': 'cardholders',
            'method': 'POST',  # Even though it's technically a GET request, it generates the new data on Stripe if updated
            'payload': '__ignored__',
            'return_data': {
                'id': 'ich_1234567890',
                'livemode': False,
            },
        }]
        with (
            self.patch_stripe_requests('wizard.hr_expense_stripe_cardholder_wizard', expected_calls),
            patch.object(phone_validation, 'phone_format', new=lambda *args, **kwargs: "+32000000000"),
        ):
            wizard.action_save_cardholder()

    def create_card(self, card_name='Test Card', country_ids=False, mcc_ids=False, employee=None, create_cardholder=True, **kwargs):
        """ Helper to quickly create a card on the database by mocking required calls """
        card_create_vals = {
            'employee_id': (employee or self.stripe_employee).id,
            'name': card_name,
            'company_id': self.env.company.id,
            **kwargs,
        }
        if country_ids:
            card_create_vals['spending_policy_country_tag_ids'] = [Command.set(country_ids)]
        if mcc_ids:
            card_create_vals['spending_policy_category_tag_ids'] = [Command.set(mcc_ids)]
        card = self.env['hr.expense.stripe.card'].with_user(self.expense_user_manager).create([card_create_vals])
        if create_cardholder:
            self.create_cardholder(card=card, employee=employee)
        return card

    @mute_logger('odoo.addons.hr_expense_stripe.controllers.main')
    def simulate_webhook_call(self, stripe_data, company_uuid=None):
        """ Helper to mock a webhook call to the controller """
        result = {}

        def make_json_response(data, **kwargs):
            result.update({'content': data, **kwargs})
            return json.dumps({'content': data}.update(kwargs))

        company_uuid = company_uuid or self.stripe_company.stripe_issuing_iap_webhook_uuid
        with MockRequest(self.env, path=f'/stripe_issuing/webhook/{company_uuid}') as request:
            request.httprequest.method = 'POST'
            request.httprequest.data = str(stripe_data).encode()
            request.httprequest.headers = {
                'Stripe-Signature': f'signature={self.iap_key_public_bytes.decode()}',
                'Iap-Signature': 'signature=1234',
                'Content-Type': 'application/json',
            }

            request.get_json_data = lambda: stripe_data
            request.make_json_response = make_json_response
            self.Controller.stripe_issuing_webhook(company_uuid)
        return result

    def get_event_expected_data(self, account=None, timestamp=0):
        """ helper to get the base event data structure, only contains the important fields """
        account = account or self.stripe_company.stripe_id
        return {
            'id': f'evt_{account}1234567890',
            'account': account,
            'object': 'event',
            'api_version': '2025-01-27.acacia',
            'created': timestamp or datetime.datetime.now().timestamp(),
            'data': {
                'object': {}  # TO FILL
            },
            'livemode': False,
            'pending_webhooks': 1,
            'request': {'id': False, 'idempotency_key': False},
            'type': False,  # TO FILL
        }

    def get_event_balance_updated_data(self, amount, account=None, currency='eur', timestamp=0):
        """ helper to get a `balance.available` event data structure, only contains the important fields """
        account = account or self.stripe_company.stripe_id
        event_data = self.get_event_expected_data(account, timestamp)
        event_data['type'] = 'balance.available'
        event_data['data']['object'] = {
            'object': 'balance',
            'available': [{'amount': 0, 'currency': currency, 'source_types': {}}],
            'instant_available': [{'amount': 0, 'currency': currency, 'source_types': {}}],
            'issuing': {'available': [{'amount': amount, 'currency': currency}]},
            'livemode': False,
            'pending': [{'amount': 0, 'currency': currency, 'source_types': {}}],
            'refund_and_dispute_prefunding': {
                'available': [{'amount': 0, 'currency': currency}],
                'pending': [{'amount': 0, 'currency': currency}],
            }
        }
        return event_data

    def get_event_topup_succeeded_updated_data(self, amount, account=None, currency='eur', timestamp=0):
        """ helper to get a `topup.succeeded` event data structure, only contains the important fields """
        account = account or self.stripe_company.stripe_id
        event_data = self.get_event_expected_data(account, timestamp)
        event_data['type'] = 'topup.succeeded'
        event_data['data']['object'] = {
            'id': 'tu_12345678901234567890',
            'object': 'topup',
            'amount': amount,
            'balance_transaction': 'txn_12345678901234567890',
            'created': timestamp,
            'currency': currency,
            'expected_availability_date': timestamp,
            'livemode': False,
            'metadata': {},
            'source': {},
            'statement_descriptor': None,
            'status': 'succeeded',
            'transfer_group': None,
            'destination_balance': 'issuing',
        }
        return event_data
