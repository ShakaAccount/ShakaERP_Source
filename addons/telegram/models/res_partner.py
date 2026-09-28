import secrets

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

TELEGRAM_PROTECTED_FIELDS = {'telegram_chat_id', 'telegram_link_token'}


class ResPartner(models.Model):
    _inherit = 'res.partner'

    telegram_chat_id = fields.Char(string="Telegram Chat ID", copy=False, index='btree_not_null',
                                   groups='base.group_user')
    telegram_link_token = fields.Char(copy=False, index='btree_not_null', groups='base.group_user')
    telegram_connect_url = fields.Char(string="Telegram Connect Link", compute='_compute_telegram_connect_url',
                                       groups='base.group_user')

    @api.depends('telegram_link_token')
    def _compute_telegram_connect_url(self):
        username = self.env['telegram.bot']._get_bot().bot_username
        for partner in self:
            partner.telegram_connect_url = (
                f'https://t.me/{username}?start={partner.telegram_link_token}'
                if username and partner.telegram_link_token else False
            )

    def write(self, vals):
        # whoever sets the chat id receives this partner's messages: only through the link flow
        if TELEGRAM_PROTECTED_FIELDS & vals.keys() and not self.env.su:
            self._telegram_check_can_link()
        return super().write(vals)

    def _telegram_check_can_link(self):
        """ A user's own partner is linked by that user only (or a Telegram admin),
        otherwise a colleague could receive their notifications. """
        if self.env.user.has_group('telegram.group_telegram_admin'):
            return
        others = self - self.env.user.partner_id
        if any(p.user_ids for p in others):
            raise AccessError(self.env._("You can only connect your own Telegram account."))
        if others:  # check_access checks the model ACL even on an empty recordset
            others.check_access('write')

    def action_telegram_generate_link(self):
        """ Deep link: the bot sees ``/start <token>`` and saves the chat id. """
        self._telegram_check_can_link()
        if not self.env['telegram.bot']._get_bot().bot_username:
            raise UserError(self.env._("Configure a Telegram bot and click 'Test Connection' first."))
        for partner in self.sudo():
            partner.telegram_link_token = secrets.token_urlsafe(16)

    def action_telegram_connect(self):
        self.ensure_one()
        self.action_telegram_generate_link()
        return {'type': 'ir.actions.act_url', 'url': self.sudo().telegram_connect_url, 'target': 'new'}

    def action_telegram_disconnect(self):
        self._telegram_check_can_link()
        self.sudo().write({'telegram_chat_id': False, 'telegram_link_token': False})

    def action_telegram_send(self):
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Send Telegram"),
            'res_model': 'telegram.composer',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_res_model': 'res.partner', 'default_res_ids': self.ids},
        }
