from odoo import models

TELEGRAM_MESSAGE_TYPES = {'comment', 'notification', 'user_notification', 'email', 'auto_comment'}


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _notify_thread_by_web_push(self, message, recipients_data, msg_vals=False, **kwargs):
        """ Telegram behaves like a push notification: same recipients, same text. """
        super()._notify_thread_by_web_push(message, recipients_data, msg_vals=msg_vals, **kwargs)
        self._notify_thread_by_telegram(message, recipients_data, msg_vals=msg_vals, **kwargs)

    def _notify_thread_by_telegram(self, message, recipients_data, msg_vals=False, **kwargs):
        # unlike web push, keep system notifications (activity assigned, stage changes)
        # for users whose Odoo setting is "email": Telegram is their inbox
        msg_vals = msg_vals or {}
        msg_type = msg_vals.get('message_type') or message.sudo().message_type
        if msg_type not in TELEGRAM_MESSAGE_TYPES:
            return
        author_id = msg_vals.get('author_id') or message.sudo().author_id.id
        internal_pids = {
            r['id'] for r in recipients_data
            if r['active'] and r['id'] and r['uid'] and not r['share'] and r['id'] != author_id
        }
        if not internal_pids:
            return
        users = self.env['res.users'].sudo().search([
            ('partner_id', 'in', list(internal_pids)),
            ('telegram_notify', '=', True),
            ('partner_id.telegram_chat_id', '!=', False),
        ])
        if not users:
            return
        payload = self._notify_by_web_push_prepare_payload(
            message, msg_vals=msg_vals, force_record_name=kwargs.get('force_record_name'))
        text = f"{payload['title']}\n\n{payload['options']['body']}".strip()
        data = payload['options']['data']
        if self and data['model'] and data['res_id']:
            text += '\n\n' + self[:1]._notify_get_action_link('view', model=data['model'], res_id=data['res_id'])
        vals_list = []
        for user in users:
            bot = self.env['telegram.bot']._get_bot(user.company_id)
            if bot:
                vals_list.append({
                    'bot_id': bot.id,
                    'chat_id': user.partner_id.telegram_chat_id,
                    'partner_id': user.partner_id.id,
                    'body': text,
                    'mail_message_id': message.id,
                })
        self.env['telegram.message'].sudo().create(vals_list)
