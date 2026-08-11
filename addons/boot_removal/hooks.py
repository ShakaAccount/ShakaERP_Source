from .hooks import disable_odoobot_completely
from . import models  # If you have a models directory
from odoo import api, SUPERUSER_ID

def disable_odoobot_completely(env):
    if not isinstance(env, api.Environment):
        cr = env
        env = api.Environment(cr, SUPERUSER_ID, {})

    odoobot_user = env.ref('base.user_odoobot', raise_if_not_found=False)
    if odoobot_user:
        odoobot_user.sudo().write({
            'name': 'ShakaBot',
            'odoobot_state': 'disabled',
        })
        if odoobot_user.partner_id:
            odoobot_user.partner_id.sudo().write({
                'name': 'ShakaBot',
            })
