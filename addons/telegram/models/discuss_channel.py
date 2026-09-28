from odoo import Command, api, fields, models, tools
from odoo.tools import html2plaintext

from odoo.addons.mail.tools.discuss import Store


def is_telegram_channel(channel):
    return channel.channel_type == 'telegram'


class DiscussChannel(models.Model):
    """ One channel per (bot, Telegram chat): replies posted here go to Telegram. """
    _inherit = 'discuss.channel'

    channel_type = fields.Selection(selection_add=[('telegram', 'Telegram Chat')], ondelete={'telegram': 'cascade'})
    telegram_chat_id = fields.Char(string="Telegram Chat ID", index='btree_not_null')
    telegram_bot_id = fields.Many2one('telegram.bot', string="Telegram Bot", ondelete='cascade')
    telegram_partner_id = fields.Many2one('res.partner', string="Telegram Contact", index='btree_not_null')

    @api.model
    def _get_telegram_channel(self, bot, chat_id, sender):
        """ Find or create the channel of ``chat_id``; ``sender`` is Telegram's ``from`` dict. """
        channel = self.sudo().search([
            ('channel_type', '=', 'telegram'),
            ('telegram_chat_id', '=', chat_id),
            ('telegram_bot_id', '=', bot.id),
        ], limit=1)
        if channel:
            return channel
        Partner = self.env['res.partner'].sudo()
        partner = Partner.search([('telegram_chat_id', '=', chat_id)], limit=1)
        if not partner:
            name = ' '.join(filter(None, [sender.get('first_name'), sender.get('last_name')])) \
                or sender.get('username') or chat_id
            partner = Partner.create({'name': name, 'telegram_chat_id': chat_id})
        members = partner | bot.notify_user_ids.partner_id
        channel = self.sudo().with_context(tools.clean_context(self.env.context)).create({
            'name': partner.name,
            'channel_type': 'telegram',
            'telegram_chat_id': chat_id,
            'telegram_bot_id': bot.id,
            'telegram_partner_id': partner.id,
            'channel_member_ids': [Command.create({'partner_id': p.id}) for p in members],
        })
        channel._broadcast(members.ids)
        return channel

    def message_post(self, **kwargs):
        message = super().message_post(**kwargs)
        if (
            self.channel_type == 'telegram'
            and not self.env.context.get('telegram_inbound')
            and message.message_type == 'comment'
            and message.author_id != self.telegram_partner_id
        ):
            self.env['telegram.message'].sudo().create({
                'bot_id': self.telegram_bot_id.id,
                'chat_id': self.telegram_chat_id,
                'partner_id': self.telegram_partner_id.id,
                'body': html2plaintext(message.body or ''),
                'attachment_ids': [Command.set(message.attachment_ids.ids)],
                'mail_message_id': message.id,
            })
        return message

    def _to_store_defaults(self, target):
        return super()._to_store_defaults(target) + [
            Store.One('telegram_partner_id', [], predicate=is_telegram_channel),
        ]

    def _types_allowing_seen_infos(self):
        return super()._types_allowing_seen_infos() + ['telegram']
