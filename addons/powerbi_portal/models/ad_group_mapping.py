import logging

from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AdGroupMapping(models.Model):
    _name = "ad.group.mapping"
    _description = "AD Group -> Odoo Group Mapping"

    name = fields.Char(compute="_compute_name", store=True)
    ad_group_dn = fields.Char(
        required=True,
        string="AD Group DN",
        help="Full Distinguished Name of the AD group, e.g. "
             "CN=Finance,OU=Groups,DC=company,DC=local",
    )
    odoo_group_id = fields.Many2one(
        "res.groups", required=True, string="Odoo Group",
        help="For AD-owned mappings, this module keeps this group's "
             "membership matching the AD group above - do not also manage "
             "membership by hand, it will be overwritten on each sync. For "
             "Odoo-owned mappings, the reverse is true: manage membership "
             "in Odoo and save the related powerbi.report record - access "
             "push to AD/PBIRS happens automatically on save - since this "
             "mapping's pull sync is skipped.",
    )
    owner = fields.Selection(
        [
            ("ad", "AD-owned (pull AD -> Odoo, the normal direction)"),
            ("odoo", "Odoo-owned (pull is skipped - this AD group only "
                     "exists to mirror an Odoo group for PBIRS access)"),
        ],
        default="ad", required=True,
        help="AD-owned: this AD group is managed externally (by an AD "
             "admin, or discovered by PBIRS Discovery) - AD is the source "
             "of truth, so the pull sync/cron keeps Odoo's group matching "
             "it. Odoo-owned: this AD group was auto-created by PBIRS "
             "Portal's automatic access-push (triggered on saving a "
             "report's Visible To Groups/Users) purely so PBIRS has a real "
             "AD principal to grant access to - Odoo's group is the source "
             "of truth here, so the pull sync deliberately skips it (pulling "
             "would silently revert membership edits made in Odoo back to "
             "whatever AD still has from the last push).",
    )
    active = fields.Boolean(default=True)
    last_sync_date = fields.Datetime(readonly=True)
    last_sync_summary = fields.Text(readonly=True)

    @api.depends("ad_group_dn", "odoo_group_id")
    def _compute_name(self):
        for rec in self:
            rec.name = "%s -> %s" % (rec.ad_group_dn or "?", rec.odoo_group_id.display_name or "?")

    def action_sync_now(self):
        odoo_owned = self.filtered(lambda m: m.owner == "odoo")
        self._run_sync(self - odoo_owned)
        message = "Sync finished. See each mappings log for details."
        if odoo_owned:
            message += (
                " Skipped %s Odoo-owned mapping(s) (%s) - pulling AD into "
                "Odoo for those would overwrite membership edits made in "
                "Odoo. Save the related report instead (Visible To Groups/"
                "Users push happens automatically) to go the other "
                "direction." % (len(odoo_owned), ", ".join(odoo_owned.mapped("name")))
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "AD Group Sync",
                "message": message,
                "type": "warning" if odoo_owned else "success",
                "sticky": bool(odoo_owned),
            },
        }

    @api.model
    def _cron_sync_all(self):
        # Odoo-owned mappings (auto-created by PBIRS Portal's push feature)
        # are deliberately excluded here - see the `owner` field help text.
        mappings = self.search([("active", "=", True), ("owner", "=", "ad")])
        self._run_sync(mappings)


    def _run_sync(self, mappings):
        """Sync AD group membership into Odoo groups for the given mapping records.
        Only ever adds/removes the *specific* odoo_group_id on each mapping -
        never touches any other group a user may have."""
        config = self.env["ad.group.sync.config"].search([("active", "=", True)], limit=1)
        if not config:
            raise UserError("No active AD connection configured (AD Group Sync > Connection Settings).")

        conn = config._get_connection()
        try:
            for mapping in mappings:
                self._sync_one_mapping(conn, config, mapping)
        finally:
            conn.unbind()

    def _sync_one_mapping(self, conn, config, mapping):
        from ldap3 import SUBTREE
        from ldap3.core.exceptions import LDAPException
        from ldap3.utils.conv import escape_filter_chars

        try:
            filter_str = "(&(objectClass=user)(memberOf=%s))" % escape_filter_chars(mapping.ad_group_dn)
            conn.search(
                search_base=config.base_dn,
                search_filter=filter_str,
                search_scope=SUBTREE,
                attributes=["sAMAccountName"],
            )
            results = conn.entries
        except LDAPException as e:
            mapping.write({
                "last_sync_date": fields.Datetime.now(),
                "last_sync_summary": "ERROR querying AD: %s" % e,
            })
            _logger.error("AD Group Sync: error querying %s: %s", mapping.ad_group_dn, e)
            return

        ad_logins = set()
        for entry in results:
            if "sAMAccountName" not in entry:
                continue
            login = str(entry.sAMAccountName.value or "")
            if login:
                ad_logins.add(login.lower())

        if not ad_logins:
            # Empty group or DN typo - don't blindly wipe the Odoo group, just log it.
            mapping.write({
                "last_sync_date": fields.Datetime.now(),
                "last_sync_summary": "AD query returned 0 members. Check the Group DN is correct. "
                                      "No changes were made to the Odoo group for safety.",
            })
            return

        Users = self.env["res.users"]
        group = mapping.odoo_group_id

        # Users that ARE in AD with this login (case-insensitive match on login).
        all_users = Users.search([("active", "=", True)])
        ad_matched_users = all_users.filtered(lambda u: u.login.lower() in ad_logins)

        current_members = group.user_ids
        to_add = ad_matched_users - current_members
        # Only remove membership from users who are known to be AD-backed
        # (i.e. their login matches SOME account we can see in AD's user
        # base at all - approximated here by: they are a current member of
        # this specific mapped group already). We never touch users we
        # didn't find in the AD query for this group AND that aren't
        # currently members of the mapped group.
        to_remove = current_members - ad_matched_users

        commands = [(4, u.id) for u in to_add] + [(3, u.id) for u in to_remove]
        if commands:
            group.write({"user_ids": commands})

        summary = "Added: %s | Removed: %s | AD group size: %s" % (
            ", ".join(to_add.mapped("login")) or "-",
            ", ".join(to_remove.mapped("login")) or "-",
            len(ad_logins),
        )
        mapping.write({
            "last_sync_date": fields.Datetime.now(),
            "last_sync_summary": summary,
        })
        _logger.info("AD Group Sync [%s]: %s", mapping.ad_group_dn, summary)
