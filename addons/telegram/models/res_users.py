from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    telegram_notify = fields.Boolean(string="Telegram Notifications", default=True,
                                     help="Also send my Odoo notifications to my Telegram.")
    telegram_chat_id = fields.Char(related='partner_id.telegram_chat_id', string="Telegram Chat ID")

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['telegram_notify', 'telegram_chat_id']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['telegram_notify']

    @api.model
    def _cron_telegram_activity_digest(self):
        """ Morning message per user: activities overdue and due today. """
        users = self.sudo().search([
            ('share', '=', False), ('telegram_notify', '=', True), ('partner_id.telegram_chat_id', '!=', False),
        ])
        base_url = self.get_base_url()
        vals_list = []
        for user in users:
            today = fields.Date.context_today(user.with_context(tz=user.tz))
            activities = self.env['mail.activity'].sudo().search(
                [('user_id', '=', user.id), ('date_deadline', '<=', today), ('res_model', '!=', False)],
                order='date_deadline, id')
            bot = self.env['telegram.bot']._get_bot(user.company_id)
            if not activities or not bot:
                continue
            user_self = self.with_context(lang=user.lang)

            def line(act):
                title = act.summary or act.activity_type_id.name or user_self.env._('To-Do')
                return f"• {title} — {act.res_name}\n  {base_url}/mail/view?model={act.res_model}&res_id={act.res_id}"

            parts = []
            overdue = activities.filtered(lambda a: a.date_deadline < today)
            if overdue:
                parts.append(user_self.env._("Overdue (%s):", len(overdue)) + '\n' + '\n'.join(map(line, overdue)))
            due = activities - overdue
            if due:
                parts.append(user_self.env._("Due today (%s):", len(due)) + '\n' + '\n'.join(map(line, due)))
            vals_list.append({
                'bot_id': bot.id,
                'chat_id': user.partner_id.telegram_chat_id,
                'partner_id': user.partner_id.id,
                'body': user_self.env._("Your activities") + '\n\n' + '\n\n'.join(parts),
            })
        self.env['telegram.message'].create(vals_list)

    # partner methods check that the partner is the current user's own
    def action_telegram_connect(self):
        self.ensure_one()
        return self.partner_id.action_telegram_connect()

    def action_telegram_disconnect(self):
        self.partner_id.action_telegram_disconnect()
