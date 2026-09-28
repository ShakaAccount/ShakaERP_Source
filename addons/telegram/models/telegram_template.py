from odoo import api, fields, models


class TelegramTemplate(models.Model):
    """ Same shape as sms.template: a body rendered per record by mail.render.mixin. """
    _name = 'telegram.template'
    _inherit = ['mail.render.mixin']
    _description = 'Telegram Template'

    _unrestricted_rendering = True

    name = fields.Char(required=True, translate=True)
    model_id = fields.Many2one('ir.model', string="Applies to", required=True, ondelete='cascade',
                               domain=[('transient', '=', False)])
    model = fields.Char(related='model_id.model', index=True, store=True, readonly=True)
    body = fields.Text(required=True, translate=True,
                       help="Placeholders like {{ object.name }} are replaced for each record.")
    report_id = fields.Many2one('ir.actions.report', string="Attach Report",
                                domain="[('model', '=', model)]", ondelete='set null')
    company_id = fields.Many2one('res.company', string="Company")
    sidebar_action_id = fields.Many2one('ir.actions.act_window', readonly=True, copy=False)

    @api.depends('model')
    def _compute_render_model(self):
        for template in self:
            template.render_model = template.model

    def unlink(self):
        self.sudo().sidebar_action_id.unlink()
        return super().unlink()

    def action_create_sidebar_action(self):
        view = self.env.ref('telegram.telegram_composer_view_form')
        for template in self:
            template.sidebar_action_id = self.env['ir.actions.act_window'].create({
                'name': self.env._("Send Telegram (%s)", template.name),
                'res_model': 'telegram.composer',
                'context': "{'default_template_id': %d, 'default_res_model': active_model, "
                           "'default_res_ids': active_ids}" % template.id,
                'view_mode': 'form',
                'view_id': view.id,
                'target': 'new',
                'binding_model_id': template.model_id.id,
            })

    def action_unlink_sidebar_action(self):
        self.sidebar_action_id.unlink()
