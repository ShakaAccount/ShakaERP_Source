from odoo import api, fields, models


class IrActionsServer(models.Model):
    """ Add a 'Send Telegram' option to server actions (copied from whatsapp). """
    _inherit = 'ir.actions.server'

    state = fields.Selection(selection_add=[
        ('telegram', 'Send Telegram'), ('followers',),
    ], ondelete={'telegram': 'cascade'})
    telegram_template_id = fields.Many2one(
        'telegram.template', 'Telegram Template',
        compute='_compute_telegram_template_id',
        ondelete='restrict', readonly=False, store=True,
        domain="[('model_id', '=', model_id)]",
    )

    def _name_depends(self):
        return [*super()._name_depends(), 'telegram_template_id']

    def _generate_action_name(self):
        self.ensure_one()
        if self.state == 'telegram' and self.telegram_template_id:
            return self.env._('Send %(template_name)s', template_name=self.telegram_template_id.name)
        return super()._generate_action_name()

    @api.depends('model_id', 'state')
    def _compute_telegram_template_id(self):
        to_reset = self.filtered(
            lambda act: act.state != 'telegram' or act.model_id != act.telegram_template_id.model_id
        )
        if to_reset:
            to_reset.telegram_template_id = False

    def _run_action_telegram_multi(self, eval_context=None):
        if not self.telegram_template_id or self._is_recompute():
            return False
        records = eval_context.get('records') or eval_context.get('record')
        if not records:
            return False
        self.env['telegram.composer'].create({
            'res_model': records._name,
            'res_ids': records.ids,
            'template_id': self.telegram_template_id.id,
        })._send_messages()
        return False
