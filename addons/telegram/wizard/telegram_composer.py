import base64

from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class TelegramComposer(models.TransientModel):
    _name = 'telegram.composer'
    _description = 'Send Telegram Message'

    res_model = fields.Char(required=True)
    res_ids = fields.Json(required=True)
    template_id = fields.Many2one('telegram.template', string="Template", domain="[('model', '=', res_model)]")
    body = fields.Text(compute='_compute_body', store=True, readonly=False,
                       help="With several records, the template is rendered for each record instead.")
    partner_ids = fields.Many2many('res.partner', string="Recipients",
                                   compute='_compute_partner_ids', store=True, readonly=False)
    unlinked_partner_ids = fields.Many2many('res.partner', compute='_compute_unlinked_partner_ids',
                                            string="Not connected to Telegram")
    is_single = fields.Boolean(compute='_compute_is_single')

    def _get_records(self):
        return self.env[self.res_model].browse(self.res_ids or [])

    @api.depends('res_ids')
    def _compute_is_single(self):
        for composer in self:
            composer.is_single = len(composer.res_ids or []) == 1

    @api.depends('template_id', 'res_model', 'res_ids')
    def _compute_body(self):
        for composer in self:
            if composer.template_id and composer.is_single:
                res_id = composer.res_ids[0]
                composer.body = composer.template_id._render_field('body', [res_id], compute_lang=True)[res_id]
            elif composer.template_id:
                composer.body = composer.template_id.body

    @api.depends('res_model', 'res_ids')
    def _compute_partner_ids(self):
        for composer in self:
            composer.partner_ids = composer._get_record_partners(composer._get_records())

    @api.depends('partner_ids')
    def _compute_unlinked_partner_ids(self):
        for composer in self:
            composer.unlinked_partner_ids = composer.partner_ids.sudo().filtered(lambda p: not p.telegram_chat_id)

    def _get_record_partners(self, records):
        if records._name == 'res.partner':
            return records
        return self.env['res.partner'].union(*records._mail_get_partners().values())

    def action_send(self):
        self._send_messages(raise_if_empty=True)
        return {'type': 'ir.actions.act_window_close'}

    def _send_messages(self, raise_if_empty=False):
        """ ``raise_if_empty=False`` for automations: never break their transaction. """
        self.ensure_one()
        bot = self.env['telegram.bot']._get_bot()
        if not bot:
            if raise_if_empty:
                raise UserError(self.env._("No Telegram bot is configured."))
            return
        records = self._get_records()
        if self.is_single or not self.template_id:
            bodies = dict.fromkeys(records.ids, self.body or '')
        else:
            bodies = self.template_id._render_field('body', records.ids, compute_lang=True)

        vals_list = []
        for record in records:
            # one record: the recipients edited in the wizard; several: each record's own contacts
            partners = self.partner_ids if self.is_single else self._get_record_partners(record)
            partners = partners.sudo().filtered('telegram_chat_id')
            if not partners:
                continue
            attachments = self._render_report(record)
            for partner in partners:
                vals_list.append({
                    'bot_id': bot.id,
                    'chat_id': partner.telegram_chat_id,
                    'partner_id': partner.id,
                    'body': bodies[record.id],
                    'attachment_ids': [Command.set(attachments.ids)],
                })
            if hasattr(record, 'message_post'):
                record.message_post(
                    body=Markup('<p>%s</p>%s') % (
                        self.env._("Telegram sent to %s:", ', '.join(partners.mapped('name'))),
                        Markup('<br/>').join((bodies[record.id] or '').splitlines()),
                    ),
                    attachment_ids=attachments.ids,
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
        if not vals_list and raise_if_empty:
            raise UserError(self.env._("None of the recipients is connected to Telegram."))
        self.env['telegram.message'].sudo().create(vals_list)

    def _render_report(self, record):
        report = self.template_id.report_id
        if not report:
            return self.env['ir.attachment']
        pdf, _ = self.env['ir.actions.report']._render_qweb_pdf(report, [record.id])
        return self.env['ir.attachment'].create({
            'name': f"{report.name} - {record.display_name}.pdf",
            'datas': base64.b64encode(pdf),
            'mimetype': 'application/pdf',
            'res_model': record._name,
            'res_id': record.id,
        })
