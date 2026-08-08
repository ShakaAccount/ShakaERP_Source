from odoo.tests import users

from odoo.addons.helpdesk.tests.common import HelpdeskCommon


class TestVoipCall(HelpdeskCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.helpdesk_manager.write({"login": "user_helpdesk_manager"})
        cls.helpdesk_user.write({"login": "user_helpdesk_user"})
        cls.partner.write({"phone": "110"})
        cls.ticket_1 = cls.env["helpdesk.ticket"].create({
            "name": "Ticket 1",
            "user_id": cls.helpdesk_user.id,
            "partner_id": cls.partner.id,
            "stage_id": cls.stage_progress.id,
        })
        cls.ticket_2 = cls.env["helpdesk.ticket"].create({
            "name": "Ticket 2",
            "user_id": cls.helpdesk_manager.id,
            "partner_id": cls.partner.id,
            "stage_id": cls.stage_new.id,
        })
        cls.ticket_open_1 = cls.env["helpdesk.ticket"].create({
            "name": "Open Ticket 1",
            "user_id": cls.helpdesk_user.id,
            "partner_id": cls.partner.id,
            "stage_id": cls.stage_done.id,
        })
        cls.ticket_open_2 = cls.env["helpdesk.ticket"].create({
            "name": "Open Ticket 2",
            "user_id": cls.helpdesk_manager.id,
            "partner_id": cls.partner.id,
            "stage_id": cls.stage_cancel.id,
        })
        cls.call_1 = cls.env["voip.call"].create({
            "partner_id": cls.partner.id,
            "phone_number": "110",
            "user_id": cls.helpdesk_user.id,
        })
        cls.call_2 = cls.env["voip.call"].create({
            "partner_id": cls.partner.id,
            "phone_number": "110",
            "user_id": cls.helpdesk_manager.id,
        })

    @users("user_helpdesk_user")
    def test_voip_call_ticket_count_user(self):
        partner = self.partner.with_env(self.env)
        call = self.call_1.with_env(self.env)
        self.assertEqual([partner.ticket_count, partner.open_ticket_count], [call.ticket_count, call.open_ticket_count],
                         "The ticket counts on the call should match those on the partner.")

    @users("user_helpdesk_manager")
    def test_voip_call_ticket_count_manager(self):
        partner = self.partner.with_env(self.env)
        call = self.call_2.with_env(self.env)
        self.assertEqual([partner.ticket_count, partner.open_ticket_count], [call.ticket_count, call.open_ticket_count],
                         "The ticket counts on the call should match those on the partner.")
