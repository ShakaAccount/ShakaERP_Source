import base64
import logging

from odoo import api, fields, models, modules
from odoo.exceptions import UserError
from odoo.tools import plaintext2html

from odoo.addons.telegram.tools import TelegramApi, TelegramError

_logger = logging.getLogger(__name__)


class TelegramBot(models.Model):
    _name = 'telegram.bot'
    _description = 'Telegram Bot'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    token = fields.Char(string="Bot Token", required=True, groups='telegram.group_telegram_admin',
                        help="Token given by @BotFather.")
    bot_username = fields.Char(string="Bot Username", readonly=True, copy=False,
                               help="Filled by 'Test Connection'. Needed for the connect links.")
    company_ids = fields.Many2many('res.company', string="Companies", default=lambda self: self.env.company)
    notify_user_ids = fields.Many2many(
        'res.users', string="Users to Notify", domain=[('share', '=', False)],
        default=lambda self: self.env.user,
        help="Users added to the Discuss channel when a contact writes to the bot.")
    update_offset = fields.Integer(string="Last Update ID", readonly=True, copy=False,
                                   groups='telegram.group_telegram_admin')

    def action_test_connection(self):
        self.ensure_one()
        try:
            me = TelegramApi(self).get_me()
        except TelegramError as e:
            raise UserError(self.env._("Telegram connection failed: %s", e)) from None
        self.bot_username = me.get('username')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': self.env._("Connected to @%s", self.bot_username),
            },
        }

    @api.model
    def _get_bot(self, company=None):
        """ Bot of ``company`` (current company by default), else any bot. """
        bots = self.sudo().search([], order='id')
        company = company or self.env.company
        return bots.filtered(lambda b: company in b.company_ids)[:1] or bots[:1]

    # ------------------------------------------------------------
    # INBOUND (getUpdates polling)
    # ------------------------------------------------------------

    @api.model
    def _cron_poll_updates(self):
        for bot in self.sudo().search([]):
            try:
                updates = TelegramApi(bot).get_updates(offset=bot.update_offset + 1)
            except TelegramError as e:
                _logger.warning("Telegram: polling %s failed: %s", bot.name, e)
                continue
            for update in updates:
                try:
                    with self.env.cr.savepoint():
                        bot._process_update(update)
                except Exception:
                    _logger.exception("Telegram: could not process update %s", update.get('update_id'))
                bot.update_offset = update['update_id']
            if not modules.module.current_test:
                self.env.cr.commit()

    def _process_update(self, update):
        self.ensure_one()
        msg = update.get('message')
        if not msg or msg.get('chat', {}).get('type') != 'private':
            return
        chat_id = str(msg['chat']['id'])
        text = msg.get('text') or msg.get('caption') or ''
        if text.startswith('/start'):
            self._process_start(chat_id, text.split()[1] if len(text.split()) > 1 else '')
            return

        channel = self.env['discuss.channel']._get_telegram_channel(self, chat_id, msg.get('from') or {})
        attachments = self._download_attachments(msg, channel)
        if not text and not attachments:
            return  # stickers, locations, ...: not supported
        message = channel.with_context(telegram_inbound=True).message_post(
            body=plaintext2html(text),
            author_id=channel.telegram_partner_id.id,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            attachment_ids=attachments.ids,
        )
        self.env['telegram.message'].create({
            'bot_id': self.id,
            'chat_id': chat_id,
            'partner_id': channel.telegram_partner_id.id,
            'body': text,
            'mail_message_id': message.id,
            'message_type': 'inbound',
            'state': 'received',
            'tg_message_id': str(msg.get('message_id', '')),
        })

    def _process_start(self, chat_id, token):
        api = TelegramApi(self)
        partner = token and self.env['res.partner'].sudo().search([('telegram_link_token', '=', token)], limit=1)
        if not partner:
            api.send_message(chat_id, self.env._("Hello! Send a message here and our team will answer you."))
            return
        # one Telegram chat belongs to one partner
        self.env['res.partner'].sudo().search([('telegram_chat_id', '=', chat_id)]).telegram_chat_id = False
        partner.write({'telegram_chat_id': chat_id, 'telegram_link_token': False})
        try:  # a failed confirmation must not undo the link
            api.send_message(chat_id, self.env._("Connected to %(company)s as %(name)s.",
                                                 company=self.env.company.name, name=partner.name))
        except TelegramError as e:
            _logger.warning("Telegram: could not confirm link to chat %s: %s", chat_id, e)

    def _download_attachments(self, msg, channel):
        """ Largest photo size, or the document, as an ir.attachment on ``channel``. """
        if msg.get('photo'):
            file_id, name, mimetype = msg['photo'][-1]['file_id'], 'photo.jpg', 'image/jpeg'
        elif msg.get('document'):
            doc = msg['document']
            file_id, name, mimetype = doc['file_id'], doc.get('file_name') or 'document', doc.get('mime_type')
        else:
            return self.env['ir.attachment']
        raw = TelegramApi(self).download_file(file_id)
        return self.env['ir.attachment'].sudo().create({
            'name': name,
            'datas': base64.b64encode(raw),
            'mimetype': mimetype,
            'res_model': 'discuss.channel',
            'res_id': channel.id,
        })
