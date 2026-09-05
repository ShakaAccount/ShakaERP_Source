import logging

from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PBIRS_ROLE = "Browser"


def _windows_principal(dn, sam, netbios_domain):
    """Objects under AD's special 'Builtin' container (mirroring Windows'
    built-in local groups, e.g. Administrators, Users) use the literal
    'BUILTIN' authority, not the domain's NetBIOS name - PBIRS/Windows
    rejects 'DOMAIN\\Administrators' as an unknown principal even though
    the object legitimately resolves in AD under that domain."""
    if ",cn=builtin," in (dn or "").lower():
        return "BUILTIN\\%s" % sam
    return "%s\\%s" % (netbios_domain, sam)


class PowerBIReport(models.Model):
    _name = "powerbi.report"
    _description = "Power BI Report (Portal Entry)"
    _order = "sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    url = fields.Char(
        string="Report URL",
        required=True,
        help="Full URL of the report on the Power BI Report Server, e.g. "
             "https://pbirs.company.local/reports/powerbi/Finance/Sales%20Dashboard"
             "?rs:embed=true\n\n"
             "The report server authenticates the browser's own Windows/AD "
             "session directly when this URL loads in the iframe - Odoo "
             "never stores or forwards any report-server credentials.",
    )
    folder = fields.Char(help="Optional grouping label shown as a section header in the sidebar.")
    active = fields.Boolean(default=True)
    description = fields.Text()
    allowed_group_ids = fields.Many2many(
        "res.groups",
        string="Visible To Groups",
        help="Only users in at least one of these Odoo groups will see this "
             "report in the sidebar. Leave empty (with no Visible To Users "
             "either) to show it to everyone. "
             "Pair with the 'AD Group Sync' module to drive these groups "
             "from real Active Directory group membership.\n\n"
             "Note: this only controls what's *listed* in Odoo's sidebar. "
             "The actual report data access and row-level security is "
             "enforced independently by the Report Server itself, based on "
             "the user's real Windows identity in the browser.",
    )
    allowed_user_ids = fields.Many2many(
        "res.users",
        string="Visible To Users",
        help="Individual users who can see this report, in addition to "
             "anyone matched by Visible To Groups. Used for PBIRS access "
             "granted directly to a person rather than through an AD "
             "group. Note: PBIRS Discovery can only match an individual "
             "principal here if that person has already logged into Odoo "
             "at least once (so their Odoo user record exists).",
    )
    managed_by_discovery = fields.Boolean(
        default=False, readonly=True,
        help="If set, this record's URL and Visible To Groups are "
             "overwritten automatically by PBIRS Discovery sync to always "
             "match the Report Server's own permissions. Do not hand-edit "
             "Visible To Groups on discovery-managed reports - it will be "
             "overwritten on the next sync.",
    )
    catalog_path = fields.Char(
        readonly=True,
        help="Full catalog path on the Report Server, used internally by "
             "PBIRS Discovery to match this record to the server's own item "
             "on each sync. Not set for manually-created reports.",
    )
    last_push_date = fields.Datetime(readonly=True)
    last_push_summary = fields.Text(readonly=True)

    def _resolve_push_principals(self):
        """Reverse-map this report's allowed_group_ids/allowed_user_ids to
        AD principal strings PBIRS understands ('DOMAIN\\name').

        If an Odoo group has no AD mapping (or its mapped AD group DN no
        longer resolves), a new AD security group is CREATED under the AD
        connection's Group Creation OU, seeded with the Odoo group's
        current members, and mapped - rather than being skipped. Only
        individual users with no matching AD account, and groups where
        creation itself fails (e.g. no Group Creation OU configured, or
        insufficient AD rights), are skipped.

        Returns (principals: [str], notes: [str], failures: [str]) -
        `notes` are informational (e.g. "created AD group X"), `failures`
        are genuine problems that mean something could NOT be pushed."""
        self.ensure_one()
        ad_config = self.env["ad.group.sync.config"].search([("active", "=", True)], limit=1)
        if not ad_config:
            raise UserError(
                "No active AD connection configured (AD Group Sync > "
                "Connection Settings) - needed to translate Odoo groups/"
                "users into AD principals PBIRS understands."
            )

        principals = []
        notes = []
        failures = []
        domain = ad_config._get_netbios_domain()
        conn = ad_config._get_connection()
        try:
            Mapping = self.env["ad.group.mapping"]
            for group in self.allowed_group_ids:
                mapping = Mapping.search([("odoo_group_id", "=", group.id)], limit=1)
                sam = None
                resolved_dn = mapping.ad_group_dn if mapping else None
                if mapping:
                    sam = ad_config._resolve_dn_to_sam(mapping.ad_group_dn, conn=conn)
                    if not sam:
                        _logger.warning(
                            "PowerBI Portal: mapped AD group %s for '%s' no "
                            "longer resolves - will (re)create.",
                            mapping.ad_group_dn, group.name,
                        )

                if not sam:
                    # No mapping, or the mapped DN is stale - create the AD
                    # group now rather than skipping the report's access.
                    member_dns = []
                    unresolved_members = []
                    for user in group.user_ids:
                        resolved = ad_config._resolve_principal(user.login, conn=conn)
                        if resolved:
                            member_dns.append(resolved["dn"])
                        else:
                            unresolved_members.append(user.login)

                    try:
                        created = ad_config._create_ad_group(group.display_name, member_dns, conn=conn)
                    except UserError as e:
                        failures.append("Group '%s' - could not auto-create AD group: %s" % (group.name, e))
                        continue

                    if mapping:
                        mapping.write({"ad_group_dn": created["dn"], "owner": "odoo"})
                    else:
                        Mapping.create({
                            "ad_group_dn": created["dn"],
                            "odoo_group_id": group.id,
                            "owner": "odoo",
                        })
                    # The AD group creation above is an external side effect
                    # that Odoo can't roll back. Commit this bookkeeping now
                    # so a later failure in this same push (e.g. SetPolicies)
                    # can't roll it back and silently orphan the AD group -
                    # that's exactly what caused repeat "already exists"
                    # collisions on retry before this fix.
                    self.env.cr.commit()
                    sam = created["sam"]
                    resolved_dn = created["dn"]
                    if created.get("adopted"):
                        note = (
                            "Group '%s' - reused existing AD group %s "
                            "(found already present under the Group "
                            "Creation OU, likely from an earlier attempt) "
                            "and added %s member(s)." % (group.name, created["dn"], len(member_dns))
                        )
                    else:
                        note = "Group '%s' - auto-created AD group %s with %s member(s)." % (
                            group.name, created["dn"], len(member_dns)
                        )
                    if unresolved_members:
                        note += (
                            " Could not add as members (no matching AD account): %s"
                            % ", ".join(unresolved_members)
                        )
                    notes.append(note)

                principals.append(_windows_principal(resolved_dn, sam, domain))

            for user in self.allowed_user_ids:
                resolved = ad_config._resolve_principal(user.login, conn=conn)
                if not resolved:
                    failures.append(
                        "User '%s' (login: %s) - no matching account found "
                        "in AD, so PBIRS wouldn't recognize the principal "
                        "either." % (user.name, user.login)
                    )
                    continue
                principals.append(_windows_principal(resolved["dn"], resolved["sam"], domain))
        finally:
            conn.unbind()

        return principals, notes, failures

    def _auto_push_access_to_pbirs(self):
        """Push this report's current Visible To Groups/Users to PBIRS.
        Called automatically by write() whenever those fields change and
        the record is saved (covers both a manual Save click and Odoo's
        autosave, since both go through write()) - there is no button for
        this anymore, it's fully automatic.

        Deliberately NEVER raises: a push failure (AD/PBIRS unreachable,
        access denied, etc) must not block saving the Odoo record itself.
        The outcome is always recorded in last_push_date/last_push_summary
        instead - check there if access doesn't seem to be taking effect."""
        self.ensure_one()
        if not self.catalog_path:
            return

        config = self.env["pbirs.discovery.config"].search([("active", "=", True)], limit=1)
        if not config:
            _logger.warning(
                "PowerBI Portal: skipped auto-push for '%s' - no active "
                "PBIRS connection configured (PBIRS Discovery > Connection "
                "Settings).", self.name,
            )
            return

        try:
            principals, notes, failures = self._resolve_push_principals()
        except UserError as e:
            summary = "ERROR resolving AD principals: %s" % e
            self.write({"last_push_date": fields.Datetime.now(), "last_push_summary": summary})
            _logger.warning("PowerBI Portal: auto-push for '%s' failed: %s", self.name, summary)
            return

        had_source = bool(self.allowed_group_ids or self.allowed_user_ids)
        if not principals and failures and had_source:
            # There WERE groups/users configured on this report, but none of
            # them could be translated to a real AD principal - record it as
            # a problem, but still don't block the save.
            summary = (
                "Nothing pushed - none of this report's groups/users could "
                "be resolved to a real AD principal.\n"
                + "\n".join(notes + failures)
            )
            self.write({"last_push_date": fields.Datetime.now(), "last_push_summary": summary})
            _logger.warning("PowerBI Portal: auto-push for '%s': %s", self.name, summary)
            return
        # Otherwise: either everything resolved, or Visible To Groups/Users
        # was deliberately left empty - proceed and push an empty policy
        # list in that case, which revokes all of this item's EXPLICIT
        # PBIRS access (matches removing all groups/users in Odoo).

        # PBIRS rejects the whole SetPolicies call if the same principal
        # appears twice (InvalidPolicyDefinitionException) - dedupe defensively,
        # since distinct Odoo groups/users can still resolve to the same AD
        # principal (e.g. a user in allowed_user_ids who's also a member of
        # one of allowed_group_ids's AD-side group, or two mappings pointing
        # at the same AD group).
        deduped_principals = list(dict.fromkeys(principals))
        if len(deduped_principals) != len(principals):
            notes.append(
                "Note: %s duplicate principal(s) collapsed before pushing "
                "(same AD account reached via more than one group/user "
                "entry)." % (len(principals) - len(deduped_principals))
            )
        principals = deduped_principals

        try:
            client = config._get_soap_client()
            client.set_policies(self.catalog_path, [(p, PBIRS_ROLE) for p in principals])
        except Exception as e:
            summary = "ERROR pushing to PBIRS: %s" % e
            self.write({"last_push_date": fields.Datetime.now(), "last_push_summary": summary})
            _logger.warning("PowerBI Portal: auto-push for '%s' failed: %s", self.name, summary)
            return

        if principals:
            summary_lines = ["Pushed %s access to: %s" % (PBIRS_ROLE, ", ".join(principals))]
        else:
            summary_lines = ["Pushed an empty policy list - revoked ALL explicit access on this PBIRS item "
                              "(Visible To Groups/Users is empty on this report)."]
        if notes:
            summary_lines.append("Notes:")
            summary_lines.extend("  - %s" % n for n in notes)
        if failures:
            summary_lines.append("Not pushed:")
            summary_lines.extend("  - %s" % f for f in failures)
        summary = "\n".join(summary_lines)
        self.write({"last_push_date": fields.Datetime.now(), "last_push_summary": summary})
        _logger.info("PowerBI Portal: auto-pushed access for '%s': %s", self.name, summary)

    _AUTO_PUSH_TRIGGER_FIELDS = {"allowed_group_ids", "allowed_user_ids"}

    def write(self, vals):
        res = super().write(vals)
        # skip_auto_push guards two things: (1) recursion, since this method
        # itself calls self.write() to record the push outcome, and (2) the
        # PBIRS Discovery sync's own writes to these same fields, which are
        # the opposite (pull) direction and must NOT immediately trigger a
        # push right back - among other problems, our push always sends
        # role 'Browser', which would silently downgrade any other role
        # (e.g. Content Manager) discovery just found.
        if self.env.context.get("skip_auto_push"):
            return res
        if self._AUTO_PUSH_TRIGGER_FIELDS & set(vals.keys()):
            for report in self:
                if report.catalog_path:
                    report.with_context(skip_auto_push=True)._auto_push_access_to_pbirs()
        return res

    @api.model
    def get_sidebar_reports(self):
        """Returns the reports visible to the current user, already filtered
        by Odoo's normal record rules (see security/security.xml), with a
        full folder path for each - used by the sidebar to build a tree."""
        reports = self.search([])
        result = []
        for r in reports:
            if r.catalog_path:
                path = r.catalog_path
            elif r.folder:
                path = "/%s/%s" % (r.folder, r.name)
            else:
                path = "/%s" % r.name
            result.append({
                "id": r.id,
                "name": r.name,
                "url": r.url,
                "path": path,
                "description": r.description or "",
            })
        return result
