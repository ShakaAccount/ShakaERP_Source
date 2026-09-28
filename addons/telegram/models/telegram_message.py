import logging

from odoo import api, fields, models, modules

from odoo.addons.telegram.tools import TelegramApi, TelegramError

_logger = logging.getLogger(__name__)


class TelegramMessage(models.Model):
    """ Outbound queue (sent by ``_send_cron``) and log of inbound messages. """
    _name = 'telegram.message'
    _description = 'Telegram Message'
    _order = 'id desc'
    _rec_name = 'chat_id'

    bot_id = fields.Many2one('telegram.bot', string="Bot", required=True, ondelete='cascade', index=True)
    chat_id = fields.Char(string="Chat ID", required=True)
    partner_id = fields.Many2one('res.partner', string="Contact", index='btree_not_null', ondelete='set null')
    body = fields.Text()
    attachment_ids = fields.Many2many('ir.attachment', string="Attachments")
    mail_message_id = fields.Many2one('mail.message', index='btree_not_null', ondelete='set null')
    message_type = fields.Selection([('outbound', 'Outbound'), ('inbound', 'Inbound')],
                                    default='outbound', required=True, readonly=True)
    state = fields.Selection([
        ('outgoing', 'In Queue'),
        ('sent', 'Sent'),
        ('received', 'Received'),
        ('error', 'Failed'),
    ], default='outgoing', required=True, index=True)
    failure_reason = fields.Char(readonly=True)
    tg_message_id = fields.Char(string="Telegram Message ID", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        messages = super().create(vals_list)
        if any(m.state == 'outgoing' for m in messages):
            self.env.ref('telegram.ir_cron_send_queue')._trigger()
        return messages

    def action_retry(self):
        self.filtered(lambda m: m.state == 'error').write({'state': 'outgoing', 'failure_reason': False})
        self.env.ref('telegram.ir_cron_send_queue')._trigger()

    @api.model
    def _send_cron(self):
        messages = self.search([('state', '=', 'outgoing')], order='id', limit=500)
        messages._send(with_commit=not modules.module.current_test)
        if len(messages) == 500:
            self.env.ref('telegram.ir_cron_send_queue')._trigger()

    def _send(self, with_commit=False):
        apis = {}
        for message in self:
            api = apis.setdefault(message.bot_id, TelegramApi(message.bot_id))
            try:
                result = api.send_message(message.chat_id, message.body) if message.body else {}
                for attachment in message.attachment_ids.sudo():
                    result = api.send_document(message.chat_id, attachment)
                message.write({'state': 'sent', 'failure_reason': False,
                               'tg_message_id': str(result.get('message_id', ''))})
            except TelegramError as e:
                # ponytail: 429/network errors retry on every cron run with no backoff or max tries
                message.write({'state': 'outgoing' if e.retry else 'error', 'failure_reason': str(e)})
                if e.code == 403:  # the user blocked the bot: stop sending to this chat
                    self.env['res.partner'].sudo().search([('telegram_chat_id', '=', message.chat_id)]).telegram_chat_id = False
            if with_commit:
                self.env.cr.commit()
