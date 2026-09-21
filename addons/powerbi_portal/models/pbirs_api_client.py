"""Minimal client for the Windows Access Management API (FastAPI on the PBIRS
host, e.g. http://192.168.2.12:8443). This is the *replacement* channel for the
direct SQL (PBIRS Discovery) and SOAP (PBIRS Access Push) connections: the API
runs on the BI host itself with the correct Windows/AD service identity, so Odoo
no longer needs Kerberos/SSPI/NTLM libraries or a working ODBC driver to reach
PBIRS, SSAS, AD or local Windows groups.

Only the operations the portal actually uses are implemented: health/whoami,
PBIRS catalog discovery (list items + policies), PBIRS access push (set
policies / provision / deprovision), plus the SSAS and AD helpers made available
for the broader access-management use cases.
"""
import logging

import requests

_logger = logging.getLogger(__name__)


class PbirsApiError(Exception):
    pass


class PbirsApiClient:
    """session-authenticated caller. Every request uses the X-API-Key header.
    Errors surface as PbirsApiError with the API's own error message."""

    def __init__(self, base_url, api_key, timeout=30):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.timeout = timeout
        self.session = requests.Session()
        if self.api_key:
            self.session.headers["X-API-Key"] = self.api_key
        self.session.headers["Content-Type"] = "application/json"

    # ------------------------------------------------------------------ base
    def _request(self, method, path, params=None, body=None):
        url = self.base_url + path
        try:
            resp = self.session.request(
                method, url, params=params, json=body, timeout=self.timeout
            )
        except requests.RequestException as e:
            raise PbirsApiError("Could not reach API (%s %s): %s" % (method, url, e))

        try:
            data = resp.json()
        except ValueError:
            data = None

        # The API wraps failures in {"ok": false, "error": {...}} but may also
        # use plain 4xx/5xx, so check both.
        http_err = resp.status_code >= 400
        api_err = (
            isinstance(data, dict)
            and data.get("ok") is False
            and "error" in data
        )
        if http_err or api_err:
            detail = None
            if isinstance(data, dict):
                err = data.get("error")
                if isinstance(err, dict):
                    detail = err.get("message")
                elif isinstance(err, str):
                    detail = err
            if not detail and http_err:
                detail = "HTTP %s %s (%s)" % (method, url, resp.status_code)
            raise PbirsApiError(
                "API %s %s failed: %s" % (method, url, detail or "unknown error")
            )
        return data

    # --------------------------------------------------------------- health
    def health(self):
        """GET /v1/health - server + AD/SSAS/PBIRS component status."""
        return self._request("GET", "/v1/health")

    def whoami(self):
        """GET /v1/whoami - the API key's identity and granted permissions."""
        return self._request("GET", "/v1/whoami")

    # ------------------------------------------------------------ PBIRS read
    # Item types that are NOT reports (mirror the _NON_REPORT_TYPES SQL codes,
    # but by name since the API exposes a human-readable `type` per item).
    NON_REPORT_TYPES = ("Folder", "Resource", "DataSource", "SharedDataset", "Model", "Cube")

    def list_items(self, path="/", recursive=True):
        """GET /v1/pbirs/items?path=...&recursive=... - walk the catalog.
        Returns the API payload: {"items": [{name,path,type,id,...}], "count": N}."""
        return self._request("GET", "/v1/pbirs/items", params={
            "path": path, "recursive": recursive,
        })

    def get_item_type(self, item_path):
        """GET /v1/pbirs/items/{item_path}/type - type string of a single item."""
        return self._request("GET", "/v1/pbirs/items/%s/type" % item_path)

    def get_policies(self, item_path):
        """GET /v1/pbirs/items/policies?path=...
        Returns {"path":..., "policies":[{"principal","principal_type","role"}],
        "inherit_parent": bool}."""
        return self._request("GET", "/v1/pbirs/items/policies", params={
            "path": item_path,
        })

    # ----------------------------------------------------------- PBIRS write
    def set_policies(self, item_path, principal_roles, inherit_parent=False):
        """POST /v1/pbirs/items/policies - set the item's explicit policy list.
        principal_roles: iterable of (principal, role) pairs, e.g.
        [("shaka\\\\svc-pbi", "Browser")]. REPLACES the item's explicit policy
        list (items not passed here lose explicit access) - matches the
        full-overwrite 'source of truth' pattern the portal already uses."""
        policies = [{"principal": p, "role": r} for p, r in principal_roles]
        return self._request("POST", "/v1/pbirs/items/policies", body={
            "path": item_path,
            "policies": policies,
            "inherit_parent": inherit_parent,
        })

    def provision(self, principal, principal_type, targets, dry_run=False, atomic=True):
        """POST /v1/provision - one-shot grant of a user/group across PBIRS,
        SSAS, AD and/or local groups in a single call. targets is a dict of
        ProvisionTargets, e.g.
        {"pbirs": {"path": "/Sales", "role": "Browser", "recursive": True},
         "ssas":  {"database": "Sales", "role": "SalesViewer", "permission": "Read"},
         "ad_group": {"group": "PowerBI-Viewers"},
         "local_group": {"group": "BI-Viewers"}}"""
        return self._request("POST", "/v1/provision", body={
            "user_or_group": principal,
            "principal_type": principal_type,
            "targets": targets,
            "dry_run": dry_run,
            "atomic": atomic,
        })

    def deprovision(self, principal, principal_type, targets, dry_run=False, atomic=False):
        """POST /v1/deprovision - reverse of provision."""
        return self._request("POST", "/v1/deprovision", body={
            "user_or_group": principal,
            "principal_type": principal_type,
            "targets": targets,
            "dry_run": dry_run,
            "atomic": atomic,
        })

    # ----------------------------------------------------------------- AD
    def list_ad_groups(self):
        return self._request("GET", "/v1/ad/groups")

    def create_ad_group(self, name, sam_account_name, ou=None, description=None):
        body = {"name": name, "sam_account_name": sam_account_name}
        if ou:
            body["ou"] = ou
        if description:
            body["description"] = description
        return self._request("POST", "/v1/ad/groups", body=body)

    # ---------------------------------------------------------------- SSAS
    def ssas_instances(self):
        return self._request("GET", "/v1/ssas/instances")

    def ssas_databases(self, instance="default"):
        return self._request("GET", "/v1/ssas/%s/databases" % instance)

    def ssas_add_role_member(self, instance, database, role_name, principal,
                             principal_type="user"):
        return self._request(
            "POST",
            "/v1/ssas/%s/databases/%s/roles/%s/members" % (instance, database, role_name),
            body={"principal": principal, "principal_type": principal_type},
        )

    def ssas_set_role_permission(self, instance, database, role_name, permission):
        return self._request(
            "PATCH",
            "/v1/ssas/%s/databases/%s/roles/%s/permission" % (instance, database, role_name),
            body={"permission": permission},
        )