from odoo import models, fields, api
from odoo.exceptions import UserError


class AdGroupSyncConfig(models.Model):
    _name = "ad.group.sync.config"
    _description = "AD Group Sync - Connection Settings"

    name = fields.Char(default="AD Connection", required=True)
    server = fields.Char(required=True, help="Hostname or IP of the AD/LDAP server, e.g. dc01.company.local")
    port = fields.Integer(default=389)
    use_tls = fields.Boolean(default=True, string="Use StartTLS")
    base_dn = fields.Char(required=True, help="e.g. DC=company,DC=local")
    binddn = fields.Char(
        string="Service Account DN",
        required=True,
        help="AD service account used for LDAP queries (and, once the "
             "Group Creation OU below is configured, for auto-creating AD "
             "groups too - so despite the name this isn't purely read-only "
             "anymore). e.g. CN=svc-odoo-pbi,OU=Service Accounts,"
             "DC=company,DC=local (a plain 'DOMAIN\\\\username' or UPN "
             "'user@domain.local' also works with AD).\n"
             "Recommended: use ONE dedicated account everywhere - also run "
             "the Odoo Windows service as this same account, and it "
             "automatically covers the PBIRS Discovery SQL connection and "
             "PBIRS Access Push SOAP calls too (via Windows Integrated "
             "auth), with no extra passwords stored in Odoo for those. "
             "LDAP itself still needs the explicit DN + password below "
             "regardless, since it can't reuse the Windows process "
             "identity the way the SQL/SOAP calls can.",
    )
    bind_password = fields.Char(string="Service Account Password")
    netbios_domain = fields.Char(
        string="NetBIOS Domain",
        help="Short-form Windows domain name used to build 'DOMAIN\\\\name' "
             "principal strings for systems (like PBIRS) that expect that "
             "format rather than a DN, e.g. SHAKA for shaka.local. Leave "
             "blank to auto-derive from the first component of Base DN "
             "(e.g. DC=shaka,DC=local -> SHAKA) - set this explicitly if "
             "your AD's real NetBIOS name differs from that guess.",
    )
    group_creation_base_dn = fields.Char(
        string="Group Creation OU",
        help="DN of the OU where Odoo is allowed to CREATE new AD security "
             "groups, e.g. OU=PowerBI Groups,OU=Groups,DC=shaka,DC=local - "
             "required for the automatic access-push (on saving a report) "
             "to auto-create a missing "
             "AD group. Use a dedicated OU with rights delegated only over "
             "that OU for the Service Account below (not domain-wide "
             "Create/Delete Group rights) - same recommendation as for the "
             ".NET app's own group provisioning.",
    )
    group_creation_prefix = fields.Char(
        string="Created Group Name Prefix", default="Odoo-",
        help="Prefix used when naming AD groups Odoo creates automatically, "
             "e.g. an Odoo group 'Finance Viewers' becomes AD group "
             "'Odoo-Finance Viewers'.",
    )
    active = fields.Boolean(default=True)

    def _get_netbios_domain(self):
        self.ensure_one()
        if self.netbios_domain:
            return self.netbios_domain
        first_dc = (self.base_dn or "").split(",")[0]
        return first_dc.split("=")[-1].upper() if "=" in first_dc else first_dc.upper()

    def _get_connection(self):
        """Open and bind an LDAP connection using the service account, via ldap3
        (pure Python, no compiler/OpenLDAP headers needed - works on Windows).
        Raises UserError with a readable message on failure."""
        try:
            from ldap3 import Server, Connection, ALL
            from ldap3.core.exceptions import LDAPException
        except ImportError:
            raise UserError(
                "The 'ldap3' package is required. Install it on the Odoo "
                "server with: pip install ldap3 --break-system-packages"
            )

        self.ensure_one()
        server = Server(self.server, port=self.port, use_ssl=False, get_info=ALL)
        conn = Connection(server, user=self.binddn, password=self.bind_password or "", auto_bind=False)
        try:
            conn.open()
            if self.use_tls:
                conn.start_tls()
            if not conn.bind():
                raise UserError(
                    "Could not bind to AD with the service account: %s" % conn.result
                )
        except LDAPException as e:
            raise UserError("Could not connect/bind to AD: %s" % e)
        return conn

    def action_test_connection(self):
        self.ensure_one()
        conn = self._get_connection()
        conn.unbind()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Success",
                "message": "Connected and bound to AD successfully.",
                "type": "success",
                "sticky": False,
            },
        }

    def action_import_from_odoo_ldap(self):
        """Copy connection settings from Odoo's own 'auth_ldap' module
        (Settings > Technical > LDAP Configuration) into this record, so you
        only have to enter the AD connection details once."""
        self.ensure_one()
        LdapConfig = self.env.get("res.company.ldap")
        if LdapConfig is None:
            raise UserError(
                "The 'LDAP Authentication' (auth_ldap) module doesn't seem "
                "to be installed - install it first, or keep filling this "
                "form in manually."
            )
        ldap_rec = self.env["res.company.ldap"].search([], limit=1)
        if not ldap_rec:
            raise UserError(
                "No LDAP configuration found under Settings > Technical > "
                "LDAP Configuration. Set that up first, then try this again."
            )

        # ldap_tls's exact field name has varied a bit across Odoo versions -
        # try the common one, fall back gracefully instead of hard failing.
        use_tls = getattr(ldap_rec, "ldap_tls", None)
        if use_tls is None:
            use_tls = getattr(ldap_rec, "use_tls", self.use_tls)

        self.write({
            "server": ldap_rec.ldap_server,
            "port": ldap_rec.ldap_server_port,
            "use_tls": bool(use_tls),
            "base_dn": ldap_rec.ldap_base,
            "binddn": ldap_rec.ldap_binddn,
            "bind_password": ldap_rec.ldap_password,
        })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Imported",
                "message": "Connection settings copied from Odoo LDAP "
                           "Configuration. Click Test Connection to confirm.",
                "type": "success",
                "sticky": False,
            },
        }

    def _resolve_principal(self, principal_name, conn=None):
        """Given a principal name as stored by the Report Server (usually
        'DOMAIN\\name' or 'name@domain'), look it up in AD and report back
        its DN and whether it is a group or a user.
        Returns a dict {'dn':..., 'is_group': bool, 'sam': ...} or None if
        not found in AD at all.
        Pass an already-open `conn` (from _get_connection()) when resolving
        many principals in a row, to avoid reconnecting for each one."""
        self.ensure_one()
        from ldap3 import SUBTREE
        from ldap3.utils.conv import escape_filter_chars

        sam = principal_name.split("\\")[-1].split("@")[0].strip()
        if not sam:
            return None

        own_conn = conn is None
        if own_conn:
            conn = self._get_connection()
        try:
            filter_str = "(sAMAccountName=%s)" % escape_filter_chars(sam)
            conn.search(
                search_base=self.base_dn,
                search_filter=filter_str,
                search_scope=SUBTREE,
                attributes=["objectClass", "distinguishedName"],
            )
            if not conn.entries:
                return None
            entry = conn.entries[0]
            object_classes = [str(v).lower() for v in entry.objectClass.values]
            is_group = "group" in object_classes
            return {
                "dn": str(entry.entry_dn),
                "is_group": is_group,
                "sam": sam,
            }
        finally:
            if own_conn:
                conn.unbind()

    def _resolve_dn_to_sam(self, dn, conn=None):
        """Given a DN (as stored on an ad.group.mapping), confirm it still
        exists in AD and return its current sAMAccountName. Returns None if
        the DN no longer resolves (group deleted/renamed since it was
        mapped) - callers should treat that as unmappable, same as a
        principal never found in AD.
        Pass an already-open `conn` when resolving many DNs in a row."""
        self.ensure_one()
        from ldap3 import BASE
        from ldap3.core.exceptions import LDAPException

        own_conn = conn is None
        if own_conn:
            conn = self._get_connection()
        try:
            try:
                conn.search(
                    search_base=dn,
                    search_filter="(objectClass=*)",
                    search_scope=BASE,
                    attributes=["sAMAccountName"],
                )
            except LDAPException:
                return None
            if not conn.entries or "sAMAccountName" not in conn.entries[0]:
                return None
            sam = str(conn.entries[0].sAMAccountName.value or "")
            return sam or None
        finally:
            if own_conn:
                conn.unbind()

    def _create_ad_group(self, odoo_group_name, member_dns, conn=None):
        """Create a new AD security group under Group Creation OU, named
        '<prefix><odoo_group_name>', and add member_dns to it immediately
        (seeding it with the Odoo group's CURRENT members) so the next
        AD Group Sync pull-cron sees a matching membership instead of an
        empty group that would wipe the Odoo group out.
        Returns {'dn':..., 'sam':...}. Raises UserError on any failure
        (missing OU config, insufficient rights, name collision, etc) -
        callers should catch this per-group so one failure doesn't block
        other groups in the same push."""
        self.ensure_one()
        if not self.group_creation_base_dn:
            raise UserError(
                "No Group Creation OU configured (AD Group Sync > "
                "Connection Settings > Group Creation OU) - required before "
                "Odoo can auto-create AD groups."
            )
        from ldap3 import MODIFY_ADD
        from ldap3.core.exceptions import LDAPException
        from ldap3.utils.conv import escape_filter_chars

        # AD sAMAccountName has a 20-char hard limit; CN is more forgiving
        # but keep both sane and collision-checkable.
        raw_name = "%s%s" % (self.group_creation_prefix or "", odoo_group_name)
        cn = "".join(c for c in raw_name if c not in '"/\\[]:;|=,+*?<>').strip() or "Odoo-Group"
        sam = cn[:20]
        dn = "CN=%s,%s" % (cn, self.group_creation_base_dn)

        own_conn = conn is None
        if own_conn:
            conn = self._get_connection()
        try:
            # A colliding sAMAccountName under OUR OWN Group Creation OU is
            # almost certainly a leftover from an earlier push that created
            # the AD group successfully but then failed on a later step
            # (e.g. SetPolicies), rolling back Odoo's own bookkeeping of it
            # while the external AD write stood. Adopt it rather than
            # hard-failing every retry - but only if it's actually a group
            # object; anything else is a genuine conflict a human should see.
            conn.search(
                search_base=self.group_creation_base_dn,
                search_filter="(sAMAccountName=%s)" % escape_filter_chars(sam),
                search_scope="LEVEL",
                attributes=["distinguishedName", "objectClass"],
            )
            if conn.entries:
                existing = conn.entries[0]
                existing_dn = str(existing.entry_dn)
                object_classes = [str(v).lower() for v in existing.objectClass.values]
                if "group" not in object_classes:
                    raise UserError(
                        "Cannot create AD group '%s' - a NON-group object "
                        "with sAMAccountName '%s' already exists at %s under "
                        "the Group Creation OU. Rename the Odoo group or the "
                        "existing AD object to resolve the collision." % (cn, sam, existing_dn)
                    )
                if member_dns:
                    conn.modify(existing_dn, {"member": [(MODIFY_ADD, member_dns)]})
                return {"dn": existing_dn, "sam": sam, "adopted": True}

            ok = conn.add(
                dn,
                attributes={
                    "objectClass": ["top", "group"],
                    "sAMAccountName": sam,
                    # -2147483646 = ADS_GROUP_TYPE_GLOBAL_GROUP | ADS_GROUP_TYPE_SECURITY_ENABLED
                    "groupType": "-2147483646",
                },
            )
            if not ok:
                raise UserError(
                    "Failed to create AD group '%s' at %s: %s\n\n"
                    "Most likely cause: the Service Account doesn't have "
                    "Create Child (group) rights delegated on the Group "
                    "Creation OU." % (cn, dn, conn.result)
                )

            if member_dns:
                mod_ok = conn.modify(dn, {"member": [(MODIFY_ADD, member_dns)]})
                if not mod_ok:
                    raise UserError(
                        "Created AD group '%s' but failed to add initial "
                        "members: %s" % (cn, conn.result)
                    )

            return {"dn": dn, "sam": sam, "adopted": False}
        except LDAPException as e:
            raise UserError("Error creating AD group '%s': %s" % (cn, e))
        finally:
            if own_conn:
                conn.unbind()
