import json
import re
from datetime import timedelta

import requests

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

HINTS = {
    401: "The API key was rejected. Check Settings > Windows Access > API Key.",
    403: "The API key is not allowed to do this. Check its permissions (GET /v1/whoami).",
    404: "Not found on the server. Check the name/path/database spelling.",
    409: "It already exists or conflicts with an existing object.",
    422: "The API rejected the input. Check the fields named in the message.",
}


class ApiError(Exception):
    def __init__(self, msg, hint="", status=None):
        super().__init__(msg)
        self.msg, self.hint, self.status = msg, hint, status


def _missing(e):
    """SSAS/Windows answer 'not found' with a non-404 status, so check the message too."""
    return e.status == 404 or "not found" in e.msg.lower()


def _q(value):
    return requests.utils.quote(value, safe="")


def classify_ad_member(member, group_dns):
    """'user' | 'group' | 'other' for one entry of GET /ad/groups/{g}/members.

    The API returns nested groups and foreign security principals in the same shape as users,
    so a member is a group iff its DN is one of the DNs from GET /ad/groups."""
    dn = (member.get("dn") or "").lower()
    if dn in group_dns:
        return "group"
    if "cn=foreignsecurityprincipals" in dn or (member.get("sam_account_name") or "").endswith("$"):
        return "other"  # well-known SIDs (S-1-5-11 ...) and computer accounts
    return "user"


def derive_domain(dn):
    """'CN=x,DC=shaka,DC=local' -> ('shaka.local', 'SHAKA').
    ponytail: NetBIOS name assumed to be the first DC label; the Settings override covers renamed domains."""
    dcs = [p.split("=", 1)[1] for p in (dn or "").split(",") if p.strip().lower().startswith("dc=")]
    return (".".join(dcs), dcs[0].upper()) if dcs else ("", "")


def _message(data, text):
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
        if isinstance(err, str):
            return err
        d = data.get("detail")
        if isinstance(d, list):  # FastAPI validation errors
            return "; ".join("%s: %s" % (".".join(str(x) for x in i.get("loc", [])[1:]), i.get("msg"))
                             for i in d if isinstance(i, dict))
        if d:
            return str(d)
    return (text or "empty response")[:300]


def _cfg(env, key):
    return env["ir.config_parameter"].sudo().get_param("win_access." + key) or ""


def _call(env, method, path, body=None):
    url, key = _cfg(env, "url"), _cfg(env, "key")
    if not (url and key):
        raise ApiError("API URL / key not configured.", "Fill them in under Settings > Windows Access.")
    try:
        r = requests.request(method, url.rstrip("/") + "/v1" + path, json=body,
                             headers={"X-API-Key": key}, timeout=30)
    except requests.RequestException as e:
        raise ApiError("Cannot reach the API (%s)." % e,
                       "Check the API URL and that the BI host is reachable from Odoo.")
    try:
        data = r.json()
    except ValueError:
        data = None
    if r.status_code >= 400 or (isinstance(data, dict) and data.get("ok") is False):
        hint = HINTS.get(r.status_code) or ("Server error on the BI host; check its logs."
                                            if r.status_code >= 500 else "")
        raise ApiError(_message(data, r.text), hint, r.status_code)
    return data


def _ensure(env, get_path, post_path, body):
    """Create unless GET finds it. Only a 'not found' answer means missing; other errors propagate."""
    try:
        _call(env, "GET", get_path)
        return "Already exists"
    except ApiError as e:
        if not _missing(e):
            raise
    _call(env, "POST", post_path, body)
    return "Created"


class Runner:
    """Runs steps one by one, records each outcome, skips steps whose blocks failed."""

    def __init__(self):
        self.rows, self.failed, self.errors = [], set(), {}

    def step(self, label, fn, block, after=()):
        if self.failed & {block, *after}:
            self.rows.append((block, label, "skip", "Skipped because an earlier step failed.", ""))
            self.failed.add(block)
            return
        try:
            self.rows.append((block, label, "ok", fn() or "Done", ""))
        except ApiError as e:
            self.rows.append((block, label, "fail", e.msg, e.hint))
            self.failed.add(block)
            self.errors[block] = e.msg

    def data(self):
        def section(block):
            return "members" if re.fullmatch(r"m\d+", block) else block.split(":")[0]
        return [{"section": section(b), "label": l, "status": s, "message": m, "hint": h}
                for b, l, s, m, h in self.rows]


class WinAccessGroup(models.Model):
    _name = "win.access.group"
    _description = "Windows Access Group"

    name = fields.Char(required=True, help="Local Windows group name; also used as the SSAS role name.")
    description = fields.Char()
    ssas_instance_id = fields.Many2one(
        "win.access.option", "SSAS instance", domain=[("kind", "=", "ssas_instance")])
    ssas_database_id = fields.Many2one(
        "win.access.option", "SSAS database", domain=[("kind", "=", "ssas_db")],
        help="Blank = no SSAS role.")
    ssas_permission = fields.Selection(
        [("Read", "Read"), ("ReadWrite", "ReadWrite"), ("Administrator", "Administrator")],
        default="Read")
    pbirs_path_ids = fields.Many2many(
        "win.access.option", string="PBIRS items", domain=[("kind", "=", "pbirs")],
        help="Empty = no PBIRS policy. The group gets the role on each selected item.")
    options_error = fields.Char(compute="_compute_options_error")
    pbirs_role = fields.Char("PBIRS role", default="Browser")
    member_ids = fields.One2many("win.access.member", "group_id")
    state = fields.Selection([("draft", "Draft"), ("synced", "Synced"), ("error", "Errors")],
                             default="draft", readonly=True)
    sync_result = fields.Json(readonly=True)
    synced_at = fields.Datetime(readonly=True)

    @api.onchange("ssas_instance_id")
    def _onchange_ssas_instance(self):
        self.ssas_database_id = False

    def _compute_options_error(self):
        err = self.env["ir.config_parameter"].sudo().get_param("win_access.options_err")
        for g in self:
            g.options_error = err

    @api.model
    def default_get(self, fields_list):
        self.env["win.access.option"].autorefresh()
        return super().default_get(fields_list)

    def web_read(self, specification):
        self.env["win.access.option"].autorefresh()
        return super().web_read(specification)

    @api.constrains("name")
    def _check_name(self):
        for g in self:
            if not re.fullmatch(r"[\w][\w .\-]*[\w]|[\w]", g.name or "") or g.name.endswith("."):
                raise ValidationError(
                    "Group name '%s' is not valid. Use letters, digits, spaces, '-', '_' or '.' only "
                    "(no commas, slashes or other symbols), starting and ending with a letter or digit." % g.name)

    def _principal(self):
        return self.name

    def action_sync(self):
        env = self.env
        for g in self:
            run, n = Runner(), g.name
            run.step("Local group '%s'" % n, lambda: _ensure(
                env, "/local/groups/" + _q(n), "/local/groups",
                {"name": n, "comment": g.description or None}), "local")
            if g.ssas_database_id:
                g._sync_ssas(run)
            if g.pbirs_path_ids:
                g._sync_pbirs(run)
            g.member_ids._sync(run)
            g.write({"state": "error" if run.failed else "synced", "sync_result": run.data(),
                     "synced_at": fields.Datetime.now()})

    def _sync_ssas(self, run):
        env, n = self.env, self.name
        base = "/ssas/%s/databases/%s/roles" % (_q(self.ssas_instance_id.name), _q(self.ssas_database_id.name))
        run.step("SSAS role '%s' in %s" % (n, self.ssas_database_id.name), lambda: _ensure(
            env, "%s/%s" % (base, _q(n)), base,
            {"name": n, "description": self.description or None}), "ssas", ("local",))
        run.step("SSAS role permission = %s" % self.ssas_permission, lambda: _call(
            env, "PATCH", "%s/%s/permission" % (base, _q(n)),
            {"permission": self.ssas_permission}) and "Set", "ssas", ("local",))
        run.step("Add %s to SSAS role" % self._principal(), lambda: self._ssas_member(base), "ssas", ("local",))

    def _ssas_member(self, base):
        try:
            _call(self.env, "POST", "%s/%s/members" % (base, _q(self.name)),
                  {"principal": self._principal(), "principal_type": "group"})
        except ApiError as e:
            if e.status != 409:
                raise
            return "Already a member"

    def _sync_pbirs(self, run):
        for opt in self.pbirs_path_ids:
            self._sync_pbirs_item(run, opt.path)

    def _sync_pbirs_item(self, run, path):
        env, me = self.env, self._principal()
        role = self.pbirs_role or "Browser"

        def push():
            cur = _call(env, "GET", "/pbirs/items/policies?path=" + requests.utils.quote(path, safe="/"))
            # PBIRS returns principals as DOMAIN\\name (case varies), so match on the bare name.
            bare = lambda x: x.rsplit("\\", 1)[-1].lower()
            pol = [{"principal": p["principal"], "role": p["role"]} for p in cur.get("policies", [])]
            mine = [p for p in pol if bare(p["principal"]) == bare(me)]
            if any(p["role"] == role for p in mine):
                return "Already has %s" % role
            # The API folds several rows of one principal into one multi-role policy, so just add ours.
            me_name = mine[0]["principal"] if mine else me
            _call(env, "POST", "/pbirs/items/policies", {
                "path": path, "policies": pol + [{"principal": me_name, "role": role}],
                "inherit_parent": cur.get("inherit_parent", False)})
            return "Granted %s (existing roles kept)" % role

        run.step("PBIRS %s: give %s the %s role" % (path, me, role), push, "pbirs:" + path, ("local",))

    def action_test_connection(self):
        try:
            h = _call(self.env, "GET", "/health")
            ok, msg = True, json.dumps(h)[:300]
        except ApiError as e:
            ok, msg = False, "%s %s" % (e.msg, e.hint)
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {
            "title": "Windows Access API", "message": msg,
            "type": "success" if ok else "danger", "sticky": not ok}}


class WinAccessOption(models.Model):
    """Cache of server-side lists (SSAS instances/databases, PBIRS items, users) for the pickers."""
    _name = "win.access.option"
    _description = "Windows Access Dropdown Option"
    _order = "kind, name"

    kind = fields.Selection([("ssas_instance", "SSAS instance"), ("ssas_db", "SSAS database"),
                             ("pbirs", "PBIRS item"), ("user", "User"),
                             ("ssas_table", "SSAS table"), ("ssas_column", "SSAS column"),
                             ("dw_member", "Warehouse row")], required=True)
    name = fields.Char(required=True)
    path = fields.Char()
    item_type = fields.Char()
    parent_id = fields.Many2one("win.access.option", ondelete="cascade")
    source = fields.Selection([("ad", "AD"), ("local", "Local"), ("odoo", "Odoo")])
    display_name = fields.Char()
    upn = fields.Char()

    def _names(self, data, key, fields=("name", "id")):
        # Response shape is not documented: accept a list, or a dict wrapping one.
        if isinstance(data, dict):
            data = data.get(key) or next((v for v in data.values() if isinstance(v, list)), [])
        out = []
        for x in data or []:
            x = x if isinstance(x, str) else next((x[f] for f in fields if x.get(f)), None)
            if x:
                out.append(x)
        return out

    def autorefresh(self):
        """Refresh the picker cache at most every 5 minutes; never blocks opening a form."""
        icp = self.env["ir.config_parameter"].sudo()
        last = icp.get_param("win_access.options_at")
        if last and fields.Datetime.now() - fields.Datetime.to_datetime(last) < timedelta(minutes=5):
            return
        errors = self.refresh()
        icp.set_param("win_access.options_err",
                      "Could not load some lists from the API: %s" % "; ".join(errors) if errors else "")
        icp.set_param("win_access.options_at", str(fields.Datetime.now()))

    def _ad_users(self):
        """No user-list endpoint exists, so collect the members of every AD group, real users only."""
        env, users = self.env, {}
        data = _call(env, "GET", "/ad/groups")
        groups = (data.get("groups") if isinstance(data, dict) else data) or []
        group_dns = {g["dn"].lower() for g in groups if g.get("dn")}
        for g in groups:
            name = g.get("sam_account_name") or g.get("name")
            try:
                data = _call(env, "GET", "/ad/groups/%s/members" % _q(name))
            except ApiError:
                continue  # one unreadable group must not hide the rest
            for m in (data.get("members") if isinstance(data, dict) else data) or []:
                if m.get("sam_account_name") and classify_ad_member(m, group_dns) == "user":
                    users.setdefault(m["sam_account_name"], m)
        return users, derive_domain(groups[0].get("dn") if groups else "")

    def refresh(self):
        """Fetch each source on its own: a failing source (SSAS, PBIRS, AD, local) keeps its old
        cache rows and is reported, the others still refresh. Returns the list of error messages."""
        env, errors, failed = self.env, [], set()

        def fetch(tag, fn):
            try:
                return fn()
            except ApiError as e:
                failed.add(tag)
                errors.append("%s: %s %s" % (tag.upper(), e.msg, e.hint))

        inst = fetch("ssas", lambda: {
            i: self._names(_call(env, "GET", "/ssas/%s/databases" % _q(i)), "databases")
            for i in self._names(_call(env, "GET", "/ssas/instances"), "instances")}) or {}
        items = fetch("pbirs", lambda: _call(env, "GET", "/pbirs/items?path=%2F&recursive=true").get("items", [])) or []
        ad = fetch("ad", self._ad_users)
        ad_users = ad[0] if ad else {}
        local = fetch("local", lambda: self._names(_call(env, "GET", "/local/users"), "users")) or []
        odoo_logins = env["res.users"].search([("share", "=", False)]).mapped("login")
        if ad:
            icp = env["ir.config_parameter"].sudo()
            icp.set_param("win_access.domain_dns", ad[1][0])
            icp.set_param("win_access.domain_netbios", ad[1][1])

        # Upsert (not wipe) so groups keep their selected values across refreshes.
        keep = self.browse()

        def upsert(kind, name, parent=None, **vals):
            nonlocal keep
            dom = [("kind", "=", kind), ("name", "=", name), ("parent_id", "=", parent.id if parent else False)]
            if "source" in vals:
                dom.append(("source", "=", vals["source"]))
            rec = self.search(dom, limit=1)
            if rec:
                rec.write({k: v for k, v in vals.items() if (rec[k] or False) != (v or False)})
            else:
                rec = self.create({"kind": kind, "name": name, "parent_id": parent.id if parent else False, **vals})
            keep |= rec
            return rec

        for i, dbs in inst.items():
            parent = upsert("ssas_instance", i)
            for d in dbs:
                db = upsert("ssas_db", d, parent)
                tables = fetch("ssas", lambda: self._names(
                    _call(env, "GET", "/ssas/%s/databases/%s/tables" % (_q(i), _q(d))), "tables")) or []
                for t in tables:
                    upsert("ssas_table", t, db)
        for x in items:
            if x.get("path"):
                upsert("pbirs", "%s  (%s)" % (x["path"], x.get("type", "")), path=x["path"],
                       item_type=x.get("type", ""))
        for sam, m in ad_users.items():
            upsert("user", sam, source="ad", display_name=m.get("display_name"),
                   upn=m.get("user_principal_name"))
        for u in local:
            upsert("user", u, source="local")
        if ad:  # without the AD list we can't tell which Odoo logins are AD users
            for u in set(odoo_logins) - set(ad_users):
                upsert("user", u, source="odoo")
        # keep options that members still point at (typed-in names) or whose source failed,
        # drop other stale ones
        used = self.env["win.access.member"].search([]).user_option_id

        def failed_source(o):
            tag = o.source if o.kind == "user" else o.kind.split("_")[0]
            return tag in failed or (tag == "odoo" and "ad" in failed)

        (self.search([("kind", "!=", "ssas_column")]) - keep - used).filtered(
            lambda o: not failed_source(o)).unlink()
        return errors

    def load_columns(self):
        """Fetch the columns of this SSAS table option (kind='ssas_table') on demand.
        Hidden columns are kept on purpose: RLS keys such as BranchID are hidden in the model.
        Only the internal RowNumber-<guid> column is left out."""
        self.ensure_one()
        db, inst = self.parent_id, self.parent_id.parent_id
        data = _call(self.env, "GET", "/ssas/%s/databases/%s/tables/%s/columns" % (
            _q(inst.name), _q(db.name), _q(self.name)))
        names = [c["name"] for c in (data.get("columns") if isinstance(data, dict) else data) or []
                 if not c["name"].startswith("RowNumber-")]
        have = {c.name: c for c in self.search([("kind", "=", "ssas_column"), ("parent_id", "=", self.id)])}
        for n in names:
            if n not in have:
                self.create({"kind": "ssas_column", "name": n, "parent_id": self.id})
        self.search([("kind", "=", "ssas_column"), ("parent_id", "=", self.id), ("name", "not in", names)]).unlink()


class WinAccessMember(models.Model):
    _name = "win.access.member"
    _description = "Windows Access Group Member"

    group_id = fields.Many2one("win.access.group", required=True, ondelete="cascade")
    user_option_id = fields.Many2one("win.access.option", "User", domain=[("kind", "=", "user")])
    name = fields.Char("Username", compute="_compute_name", store=True, readonly=False,
                       help="AD users are picked from the list; local users are picked or typed.")
    kind = fields.Selection([("ad", "AD user"), ("local", "Local user")], default="ad", required=True)
    account_created = fields.Boolean(readonly=True, help="Set once the account is known to exist; sync then skips the check.")
    full_name = fields.Char()
    password = fields.Char()
    state = fields.Selection([("draft", "Pending"), ("added", "Member"), ("error", "Error")],
                             default="draft", readonly=True)
    log = fields.Char("Last error", readonly=True)

    @api.depends("user_option_id")
    def _compute_name(self):
        for m in self:
            if m.user_option_id:
                m.name = m.user_option_id.name

    def _sync(self, run):
        for m in self:
            blk, k = "m%s" % m.id, m.kind
            if not m.account_created:
                run.step("Check %s user '%s'" % (k, m.name), m._ensure_account, blk, ("local",))
            run.step("Add '%s' to local group" % m.principal, m._add, blk, ("local",))
            ok = blk not in run.failed
            done = ok and not m.account_created
            m.write({"state": "added" if ok else "error", "log": run.errors.get(blk, False),
                     **({"password": False, "account_created": True} if done else {})})

    @api.constrains("name")
    def _check_name_set(self):
        if any(not (m.name or "").strip() for m in self):
            raise ValidationError("Every member needs a username.")

    @property
    def principal(self):
        """AD users join the local group as DOMAIN\\name: Settings override, else derived from the AD."""
        d = _cfg(self.env, "domain") or _cfg(self.env, "domain_netbios")
        if self.kind == "ad" and d and "\\" not in self.name and "@" not in self.name:
            return "%s\\%s" % (d, self.name)
        return self.name

    def _ensure_account(self):
        """AD accounts are never created here, only verified. Local accounts are created if missing."""
        self.ensure_one()
        env = self.env
        if self.kind == "ad":
            try:
                _call(env, "GET", "/ad/users/" + _q(self.name))
            except ApiError as e:
                if _missing(e):
                    raise ApiError("No AD user '%s'." % self.name,
                                   "Pick an existing user from the list. This addon never creates AD accounts.")
                raise
            return "Exists in AD"
        try:
            _call(env, "GET", "/local/users/" + _q(self.name))
            return "Already exists"
        except ApiError as e:
            if not _missing(e):
                raise
        if not self.password:
            raise ApiError("The local account does not exist yet and no password was given.",
                           "Fill the password so the account can be created, or check the username.")
        _call(env, "POST", "/local/users", {
            "username": self.name, "password": self.password,
            "full_name": self.full_name or None, "active": True})
        return "Created"

    def _add(self):
        self.ensure_one()
        try:
            _call(self.env, "POST", "/local/groups/%s/members" % _q(self.group_id.name),
                  {"user": self.principal})
        except ApiError as e:
            # Windows reports "already a member" (error 1378) with a non-409 status.
            if e.status == 409 or "already a member" in e.msg.lower() or "1378" in e.msg:
                return "Already a member"
            raise

    def _remove_remote(self):
        """Take the account out of the local group; a missing membership counts as done."""
        self.ensure_one()
        try:
            _call(self.env, "DELETE", "/local/groups/%s/members/%s" % (_q(self.group_id.name), _q(self.principal)))
        except ApiError as e:
            gone = e.status == 404 or "not a member" in e.msg.lower() or "1377" in e.msg
            if not gone:
                raise UserError("Could not remove %s from group %s, so nothing was changed: %s %s"
                                % (self.principal, self.group_id.name, e.msg, e.hint))

    def write(self, vals):
        # Changing who/what the row is: first remove the OLD account from the Windows group.
        if {"kind", "name", "user_option_id"} & vals.keys():
            added = self.filtered(lambda m: m.state == "added")
            added._remove_remote_all()
            res = super().write(vals)
            super(WinAccessMember, added).write({"state": "draft", "account_created": False, "log": False})
            return res
        return super().write(vals)

    def _remove_remote_all(self):
        for m in self:
            m._remove_remote()

    def unlink(self):
        self.filtered(lambda m: m.state == "added")._remove_remote_all()
        return super().unlink()
