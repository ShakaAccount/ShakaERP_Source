from odoo.tests import BaseCase, tagged

from odoo.addons.win_access.models.bi_user_access import match_ssas_tables
from odoo.addons.win_access.models.group import classify_ad_member, derive_domain

GROUP_DNS = {"cn=domain guests,cn=users,dc=shaka,dc=local", "cn=domain users,cn=users,dc=shaka,dc=local"}


@tagged("post_install", "-at_install")
class TestPureHelpers(BaseCase):
    def test_nested_group_is_not_a_user(self):
        # the 'Domain Guests' bug: a group comes back in the same shape as a user
        m = {"dn": "CN=Domain Guests,CN=Users,DC=shaka,DC=local", "sam_account_name": "Domain Guests"}
        self.assertEqual(classify_ad_member(m, GROUP_DNS), "group")

    def test_real_user(self):
        m = {"dn": "CN=معین فیض شمس,OU=Shaka,DC=shaka,DC=local", "sam_account_name": "m.feiz"}
        self.assertEqual(classify_ad_member(m, GROUP_DNS), "user")

    def test_sid_and_computer_are_not_users(self):
        fsp = {"dn": "CN=S-1-5-11,CN=ForeignSecurityPrincipals,DC=shaka,DC=local", "sam_account_name": "S-1-5-11"}
        pc = {"dn": "CN=DCB,OU=Domain Controllers,DC=shaka,DC=local", "sam_account_name": "DCB$"}
        self.assertEqual(classify_ad_member(fsp, GROUP_DNS), "other")
        self.assertEqual(classify_ad_member(pc, GROUP_DNS), "other")

    def test_derive_domain(self):
        self.assertEqual(derive_domain("CN=x,CN=Builtin,DC=shaka,DC=local"), ("shaka.local", "SHAKA"))
        self.assertEqual(derive_domain(""), ("", ""))

    def test_match_ssas_tables(self):
        tables = ["DimParty", "DimParty 1", "DimParty 2", "DimPartyType", "DimDate", "DimDate1", "DimDetailedLedger4"]
        self.assertEqual(match_ssas_tables("DimParty", tables), ["DimParty", "DimParty 1", "DimParty 2"])
        self.assertEqual(match_ssas_tables("DimDate", tables), ["DimDate", "DimDate1"])
        self.assertEqual(match_ssas_tables("DimDetailedLedger", tables), ["DimDetailedLedger4"])
        self.assertNotIn("DimPartyType", match_ssas_tables("DimParty", tables))  # never a longer name
        self.assertEqual(match_ssas_tables("DimNothing", tables), [])
