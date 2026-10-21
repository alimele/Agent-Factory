"""
Reads identity off Easy Auth's x-ms-client-principal header. App Service
Authentication (Easy Auth), enabled directly on credo-factory-api, validates
the bearer token itself before the request reaches this code and injects
this header — no token validation happens in this module.

MVP limitation: the groups claim Easy Auth surfaces is subject to the
same 200-group overage limit as a manually validated token — if a user
belongs to 200+ groups, the claim is omitted. Fine for MVP.
"""
import base64
import json
import os

from api.blueprint.catalog_mvp import DEPARTMENTS
from api.policy.models import EvalContext

_GROUP_DEPARTMENT_MAP: dict[str, str] = json.loads(os.environ.get("GROUP_DEPARTMENT_MAP", "{}"))
_OID_CLAIM = "http://schemas.microsoft.com/identity/claims/objectidentifier"

_ALL_DEPARTMENTS_SENTINEL = "*"

# Deliberately a separate app setting from GROUP_DEPARTMENT_MAP — department
# access (what agents you can build) and catalog-admin access (what
# knowledge sources/connections exist for everyone) are different
# privileges, and conflating them was part of how the shared-connection bug
# happened unnoticed. Comma-separated Entra group object ids.
_ADMIN_GROUP_IDS: set[str] = {
    g.strip() for g in os.environ.get("ADMIN_GROUP_IDS", "").split(",") if g.strip()
}


class TokenError(Exception):
    pass


def _departments_for_groups(groups: list[str]) -> list[str]:
    matched: set[str] = set()
    for group_id in groups:
        mapped = _GROUP_DEPARTMENT_MAP.get(group_id)
        if not mapped:
            continue
        if mapped == _ALL_DEPARTMENTS_SENTINEL:
            return list(DEPARTMENTS)
        if mapped in DEPARTMENTS:
            matched.add(mapped)
    return sorted(matched)


def is_admin(groups: list[str]) -> bool:
    """True if the requester belongs to one of the groups in ADMIN_GROUP_IDS."""
    return any(g in _ADMIN_GROUP_IDS for g in groups)


def build_context(req, test_results: dict | None = None) -> EvalContext:
    """req: azure.functions.HttpRequest"""
    header = req.headers.get("x-ms-client-principal")
    if not header:
        raise TokenError("Missing x-ms-client-principal — Easy Auth did not authenticate this request")

    try:
        principal = json.loads(base64.b64decode(header))
    except (ValueError, json.JSONDecodeError) as e:
        raise TokenError(f"Malformed x-ms-client-principal: {e}") from e

    claims = principal.get("claims", [])
    requester_id = next((c["val"] for c in claims if c.get("typ") == _OID_CLAIM), None)
    groups = [c["val"] for c in claims if c.get("typ") == "groups"]

    if not requester_id:
        raise TokenError("No object id claim on principal")

    return EvalContext(
        requester_id=requester_id,
        requester_departments=_departments_for_groups(groups),
        requester_groups=groups,
        test_results=test_results,
    )
