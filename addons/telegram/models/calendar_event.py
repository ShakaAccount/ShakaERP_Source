from odoo import models


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    def _do_telegram_reminder(self, alarm):
        """ Queue a Telegram reminder for attendees that haven't declined the event. """
        bot = self.env['telegram.bot']._get_bot()
        if not bot:
            return
        vals_list = []
        for event in self:
            declined = event.attendee_ids.filtered_domain([('state', '=', 'declined')]).partner_id
            partners = event._mail_get_partners()[event.id].sudo().filtered(
                lambda p: p.telegram_chat_id and p not in declined)
            if event.user_id and not alarm.notify_responsible:
                partners -= event.user_id.partner_id
            link = event._notify_get_action_link('view')
            for partner in partners:
                user = partner.user_ids[:1]
                if user and not user.telegram_notify:
                    continue
                event_l = event.with_context(tz=user.tz or partner.tz or 'UTC', lang=user.lang or partner.lang)
                when = event_l._get_display_time(event.start, event.stop, event.duration, event.allday)
                lines = [event_l.env._("Reminder: %(name)s, %(time)s", name=event.name, time=when)]
                if event.location:
                    lines.append(event.location)
                lines.append(link)
                vals_list.append({
                    'bot_id': bot.id,
                    'chat_id': partner.telegram_chat_id,
                    'partner_id': partner.id,
                    'body': '\n'.join(lines),
                })
        self.env['telegram.message'].create(vals_list)
