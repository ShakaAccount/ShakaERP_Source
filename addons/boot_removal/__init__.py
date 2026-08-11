from odoo import api, SUPERUSER_ID


def disable_odoobot_completely(env):
    """
    Rebrands OdooBot to ShakaBot across Users, Partners, and suppresses onboarding.
    """
    if not isinstance(env, api.Environment):
        cr = env
        env = api.Environment(cr, SUPERUSER_ID, {})

    # 1. Update the User record
    odoobot_user = env.ref('base.user_odoobot', raise_if_not_found=False)
    if odoobot_user:
        odoobot_user.sudo().write({
            'name': 'ShakaBot',
            'odoobot_state': 'disabled',
            'notification_type': 'inbox',
        })

    # 2. Update the Root Partner Record (This controls what is displayed in Discuss/Chatter)
    partner_root = env.ref('base.partner_root', raise_if_not_found=False)
    if partner_root:
        partner_root.sudo().write({
            'name': 'ShakaBot',
            'email': 'shakabot@example.com',
        })

    # Also update the user's explicit partner if it differs from base.partner_root
    if odoobot_user and odoobot_user.partner_id:
        odoobot_user.partner_id.sudo().write({
            'name': 'ShakaBot',
        })

    # 3. Clean up default welcome posts in #general
    general_channel = env['discuss.channel'].search([('name', '=', 'general')], limit=1)
    if general_channel and partner_root:
        welcome_msgs = env['mail.message'].search([
            ('model', '=', 'discuss.channel'),
            ('res_id', '=', general_channel.id),
            ('author_id', '=', partner_root.id),
        ])
        if welcome_msgs:
            welcome_msgs.unlink()
