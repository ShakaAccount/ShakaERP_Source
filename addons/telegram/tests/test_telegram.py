from datetime import date, datetime, timedelta
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.telegram.tools import TelegramApi, TelegramError


@tagged('post_install', '-at_install')
class TestTelegram(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bot = cls.env['telegram.bot'].create({
            'name': 'Bot', 'token': '123:abc', 'bot_username': 'shaka_bot',
            'company_ids': [(6, 0, cls.env.company.ids)],
        })
        cls.user = new_test_user(cls.env, login='tg_user', groups='base.group_user')
        cls.other = new_test_user(cls.env, login='tg_other', groups='base.group_user')
        cls.calls = []

    def _mock_api(self, result=None, error=None):
        calls = self.calls = []

        def _call(api, method, files=None, http_timeout=20, **payload):
            calls.append((method, payload))
            if error and method.startswith('send'):
                raise error
            return result(method) if callable(result) else (result or {'message_id': 1})
        return patch.object(TelegramApi, '_call', _call)

    def test_start_token_links_partner(self):
        self.user.partner_id.with_user(self.user).action_telegram_generate_link()
        token = self.user.partner_id.telegram_link_token
        with self._mock_api():
            self.bot._process_update({'update_id': 1, 'message': {
                'message_id': 5, 'chat': {'id': 777, 'type': 'private'}, 'from': {}, 'text': f'/start {token}'}})
        self.assertEqual(self.user.partner_id.telegram_chat_id, '777')
        self.assertFalse(self.user.partner_id.telegram_link_token)

    def test_cannot_link_colleague(self):
        with self.assertRaises(AccessError):
            self.other.partner_id.with_user(self.user).action_telegram_generate_link()
        with self.assertRaises(AccessError):
            self.other.partner_id.with_user(self.user).write({'telegram_chat_id': '1'})

    def test_notification_forwarded(self):
        self.user.partner_id.sudo().telegram_chat_id = '777'
        record = self.env['res.partner'].create({'name': 'Record'})
        record.message_post(body='Hello there', partner_ids=self.user.partner_id.ids,
                            message_type='comment', subtype_xmlid='mail.mt_comment')
        msg = self.env['telegram.message'].search([('chat_id', '=', '777')])
        self.assertEqual(len(msg), 1)
        self.assertIn('Hello there', msg.body)
        self.assertEqual(msg.state, 'outgoing')

        self.user.telegram_notify = False
        record.message_post(body='Again', partner_ids=self.user.partner_id.ids,
                            message_type='comment', subtype_xmlid='mail.mt_comment')
        self.assertEqual(self.env['telegram.message'].search_count([('chat_id', '=', '777')]), 1)

    def test_inbound_creates_channel_and_reply_is_queued(self):
        with self._mock_api():
            self.bot._process_update({'update_id': 2, 'message': {
                'message_id': 6, 'chat': {'id': 888, 'type': 'private'},
                'from': {'first_name': 'Ali'}, 'text': 'Salam'}})
        channel = self.env['discuss.channel'].search([('telegram_chat_id', '=', '888')])
        self.assertEqual(channel.channel_type, 'telegram')
        self.assertEqual(channel.telegram_partner_id.name, 'Ali')
        self.assertIn('Salam', channel.message_ids[0].body)

        channel.message_post(body='Hi Ali', message_type='comment')
        out = self.env['telegram.message'].search([('chat_id', '=', '888'), ('message_type', '=', 'outbound')])
        self.assertEqual(out.body, 'Hi Ali')

    def test_send_blocked_unlinks_partner(self):
        partner = self.env['res.partner'].create({'name': 'Blocker', 'telegram_chat_id': '999'})
        msg = self.env['telegram.message'].create({'bot_id': self.bot.id, 'chat_id': '999', 'body': 'x'})
        with self._mock_api(error=TelegramError('Forbidden: bot was blocked by the user', 403)):
            msg._send()
        self.assertEqual(msg.state, 'error')
        self.assertFalse(partner.telegram_chat_id)

    def test_send_retry_stays_queued(self):
        msg = self.env['telegram.message'].create({'bot_id': self.bot.id, 'chat_id': '1', 'body': 'x'})
        with self._mock_api(error=TelegramError('timeout', retry=True)):
            msg._send()
        self.assertEqual(msg.state, 'outgoing')
        with self._mock_api():
            msg._send()
        self.assertEqual(msg.state, 'sent')

    def test_composer_with_template(self):
        partner = self.env['res.partner'].create({'name': 'Customer', 'telegram_chat_id': '555'})
        template = self.env['telegram.template'].create({
            'name': 'Hello', 'model_id': self.env['ir.model']._get_id('res.partner'),
            'body': 'Dear {{ object.name }}',
        })
        composer = self.env['telegram.composer'].create({
            'res_model': 'res.partner', 'res_ids': partner.ids, 'template_id': template.id})
        self.assertEqual(composer.body, 'Dear Customer')
        composer.action_send()
        self.assertEqual(self.env['telegram.message'].search([('chat_id', '=', '555')]).body, 'Dear Customer')

    def _queued(self, chat_id):
        return self.env['telegram.message'].search([('chat_id', '=', chat_id), ('state', '=', 'outgoing')])

    def test_email_user_gets_system_notifications(self):
        """ notification_type='email' users get user_notification (activity assigned) too. """
        self.user.notification_type = 'email'
        self.user.partner_id.sudo().telegram_chat_id = '321'
        record = self.env['res.partner'].create({'name': 'Record'})
        record.message_notify(partner_ids=self.user.partner_id.ids, body='Stage changed')
        self.assertIn('Stage changed', self._queued('321').body)

        record.activity_schedule('mail.mail_activity_data_todo', user_id=self.user.id, summary='Check it')
        self.assertTrue(any('Check it' in b for b in self._queued('321').mapped('body')))

    def test_activity_digest(self):
        self.user.partner_id.sudo().telegram_chat_id = '654'
        self.other.partner_id.sudo().telegram_chat_id = '655'
        record = self.env['res.partner'].create({'name': 'Late Record'})
        record.activity_schedule('mail.mail_activity_data_todo', user_id=self.user.id, summary='Late one',
                                 date_deadline=date.today() - timedelta(days=2))
        self.env['telegram.message'].search([]).unlink()
        self.env['res.users']._cron_telegram_activity_digest()
        digest = self._queued('654')
        self.assertEqual(len(digest), 1)
        self.assertIn('Late one', digest.body)
        self.assertIn('Late Record', digest.body)
        self.assertFalse(self._queued('655'))

    def test_calendar_reminder(self):
        attendee = self.env['res.partner'].create({'name': 'Guest', 'telegram_chat_id': '777'})
        alarm = self.env.ref('telegram.alarm_telegram_15_minutes')
        event = self.env['calendar.event'].create({
            'name': 'Budget meeting',
            'start': datetime.now() + timedelta(minutes=10),
            'stop': datetime.now() + timedelta(minutes=70),
            'partner_ids': [(6, 0, attendee.ids)],
            'alarm_ids': [(6, 0, alarm.ids)],
        })
        event._do_telegram_reminder(alarm)
        self.assertIn('Budget meeting', self._queued('777').body)
