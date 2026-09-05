"""Minimal SOAP client for the PBIRS/SSRS ReportService2010 endpoint
(GetPolicies / SetPolicies only - just enough to push report access from
Odoo). Deliberately built on plain `requests` + string templates instead of
a SOAP library like `zeep`, to avoid another compiled/heavy dependency on
top of pyodbc and ldap3 (matches the ldap3-over-python-ldap choice made
elsewhere in this project for the same reason).
"""
import logging
import xml.etree.ElementTree as ET

_logger = logging.getLogger(__name__)

_SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"

_ENVELOPE = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
{body}
  </soap:Body>
</soap:Envelope>"""

_GET_POLICIES_BODY = """    <GetPolicies xmlns="{ns}">
      <ItemPath>{path}</ItemPath>
    </GetPolicies>"""

_SET_POLICIES_BODY = """    <SetPolicies xmlns="{ns}">
      <ItemPath>{path}</ItemPath>
      <Policies>
{policies}
      </Policies>
    </SetPolicies>"""

_POLICY_TEMPLATE = """        <Policy>
          <GroupUserName>{principal}</GroupUserName>
          <Roles>
            <Role><Name>{role}</Name></Role>
          </Roles>
        </Policy>"""


def _xml_escape(value):
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _local(tag):
    """Strip any namespace off an ElementTree tag, e.g. '{ns}Foo' -> 'Foo'.
    Used to parse response elements regardless of whether the server
    qualifies them or not - not something worth assuming either way after
    getting the request-side qualification wrong once already."""
    return tag.rsplit("}", 1)[-1]


class PbirsSoapError(Exception):
    pass


class PbirsSoapClient:
    """session: a requests.Session already configured with the right auth
    (Windows Integrated via requests-negotiate-sspi, or NTLM via
    requests-ntlm - see pbirs_discovery.py's _get_soap_client())."""

    def __init__(self, soap_url, session):
        self.soap_url = soap_url
        self.session = session
        self._action_cache = {}

    def _get_soap_action(self, operation):
        """Look up the exact SOAPAction string for `operation` from the
        service's own WSDL, rather than assuming the classic SSRS
        '{namespace}/{operation}' convention - confirmed on this project
        that assumption doesn't hold for this PBIRS build (server rejected
        it as unrecognized regardless of http/https). The WSDL is the only
        reliable source for this, same reasoning as not hardcoding the
        ODBC driver name or the Catalog.Type codes elsewhere in this
        module."""
        if operation in self._action_cache:
            return self._action_cache[operation]

        wsdl_url = self.soap_url + ("&" if "?" in self.soap_url else "?") + "wsdl"
        try:
            resp = self.session.get(wsdl_url, timeout=20)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except Exception as e:
            raise PbirsSoapError(
                "Could not fetch/parse the service WSDL (%s) to determine "
                "the correct SOAPAction for '%s': %s" % (wsdl_url, operation, e)
            )

        action = None
        for binding in root.iter():
            if _local(binding.tag) != "binding":
                continue
            for op_el in binding:
                if _local(op_el.tag) != "operation" or op_el.get("name") != operation:
                    continue
                for soap_op in op_el:
                    if _local(soap_op.tag) == "operation" and soap_op.get("soapAction"):
                        action = soap_op.get("soapAction")
                        break
                if action:
                    break
            if action:
                break

        if not action:
            raise PbirsSoapError(
                "Could not find a SOAPAction for operation '%s' in the "
                "service WSDL (%s). Double check the SOAP Endpoint URL "
                "points at ReportService2010.asmx." % (operation, wsdl_url)
            )
        self._action_cache[operation] = action
        return action

    def _get_operation_ns(self, operation):
        """Derive the operation's target namespace from its own discovered
        SOAPAction (conventionally '{namespace}/{operationName}'), instead
        of a second hardcoded guess that could silently diverge from the
        namespace that's actually confirmed to route correctly."""
        action = self._get_soap_action(operation)
        suffix = "/" + operation
        if action.endswith(suffix):
            return action[: -len(suffix)]
        return action.rsplit("/", 1)[0]

    def _call(self, action, body):
        envelope = _ENVELOPE.format(body=body)
        soap_action = self._get_soap_action(action)
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": '"%s"' % soap_action,
        }
        _logger.info("PBIRS SOAP '%s': SOAPAction=%s", action, soap_action)
        _logger.info("PBIRS SOAP '%s': outgoing envelope:\n%s", action, envelope)
        try:
            resp = self.session.post(self.soap_url, data=envelope.encode("utf-8"), headers=headers, timeout=30)
        except Exception as e:
            raise PbirsSoapError("Could not reach PBIRS SOAP endpoint (%s): %s" % (self.soap_url, e))

        _logger.info(
            "PBIRS SOAP '%s': HTTP %s, actually-sent body was %s bytes",
            action, resp.status_code, len(resp.request.body or b""),
        )

        if resp.status_code != 200:
            raise PbirsSoapError(
                "PBIRS SOAP call '%s' failed with HTTP %s: %s"
                % (action, resp.status_code, resp.text[:1000])
            )
        try:
            return ET.fromstring(resp.content)
        except ET.ParseError as e:
            raise PbirsSoapError("Could not parse PBIRS SOAP response for '%s': %s" % (action, e))

    def get_policies(self, item_path):
        """Returns (inherit_parent: bool, policies: [(principal, [role_names])])."""
        ns = self._get_operation_ns("GetPolicies")
        body = _GET_POLICIES_BODY.format(ns=ns, path=_xml_escape(item_path))
        root = self._call("GetPolicies", body)

        policies = []
        for policy_el in root.iter():
            if _local(policy_el.tag) != "Policy":
                continue
            principal = None
            roles = []
            for child in policy_el.iter():
                if _local(child.tag) == "GroupUserName":
                    principal = child.text
                elif _local(child.tag) == "Name" and child.text:
                    roles.append(child.text)
            if principal:
                policies.append((principal, roles))

        inherit = False
        for el in root.iter():
            if _local(el.tag) == "InheritParent":
                inherit = (el.text or "").lower() == "true"
                break
        return inherit, policies

    def set_policies(self, item_path, principal_roles):
        """principal_roles: list of (principal, role_name) tuples. Does a
        full replace of the item's *explicit* policy list (matches the
        'source of truth' full-overwrite pattern already used by PBIRS
        Discovery in the other direction) - anything not in this list will
        no longer have explicit access after this call."""
        policies_xml = "\n".join(
            _POLICY_TEMPLATE.format(principal=_xml_escape(p), role=_xml_escape(r))
            for p, r in principal_roles
        )
        ns = self._get_operation_ns("SetPolicies")
        body = _SET_POLICIES_BODY.format(ns=ns, path=_xml_escape(item_path), policies=policies_xml)
        self._call("SetPolicies", body)
