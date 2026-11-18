"""
Per-operation MCP tool discovery for the Tools (Actions) page.

This is the module function_app.py's new
GET /blueprint/catalog/{department}/tools/{toolId}/operations route calls.
It never hardcodes an operation name or schema — every operation returned
comes from a live MCP `tools/list` call (api/blueprint/mcp_client.py)
against the server API Center already has registered for this tool
(api/blueprint/api_center_catalog.py). The only two things an admin
declares ahead of time, matching conventions already used elsewhere in
this codebase, are:

  - `mcpallowedtools` (api_center_catalog.operations_allowlist): an
    optional governance CEILING — "no agent may ever use more than these
    operations on this server" — not a hardcoded operation list the user
    is stuck with. If unset, every operation the live server reports is
    selectable.
  - `operationrisk` (api_center_catalog.operation_risk_overrides): an
    optional per-operation risk override for the policy engine, falling
    back to the server's whole-tool `risk` property when absent.

Two different discovery paths, matching the two auth models in the task:

  - Shared ("organisation admin configures credentials once"): the server
    uses `foundryauthmode=functionkey` or `anonymous`, so this backend can
    call `tools/list` itself, with no per-user action required. See
    api_center_catalog.get_mcp_discovery_target().
  - Individual (OAuth / user-supplied credentials): discovery happens as a
    side effect of the user submitting the dynamic connection form —
    tool_connections.create_tool_connection() runs the live discovery call
    with those exact values and returns the operations directly. This
    module's discover_operations() reports NEEDS_CONNECTION for those
    servers so the frontend knows to show the connect form (which already
    returns operations on success) instead of calling this route again.
"""
from __future__ import annotations

import logging

from api.blueprint import api_center_catalog, mcp_client

logger = logging.getLogger(__name__)


class ToolDiscoveryError(Exception):
    pass


def apply_governance(tool_id: str, discovered: list[dict]) -> list[dict]:
    """
    Shared by both discovery paths (shared-auth, below, and
    tool_connections.discover_with_values' result): clamps the live
    tools/list result to the admin's operations_allowlist ceiling (if any)
    and attaches each operation's risk (operationrisk override, falling
    back to the server's own whole-tool risk).
    """
    allowlist = api_center_catalog.operations_allowlist(tool_id)
    risk_overrides = api_center_catalog.operation_risk_overrides(tool_id)
    fallback_risk = api_center_catalog.tool_risk(tool_id)

    operations = []
    for op in discovered:
        name = op.get("name")
        if not name:
            continue
        if allowlist is not None and name not in allowlist:
            continue
        operations.append({
            "name": name,
            "description": op.get("description", ""),
            "inputSchema": op.get("inputSchema", {}),
            "risk": risk_overrides.get(name, fallback_risk),
        })
    return operations


def discover_operations(tool_id: str) -> dict:
    """
    Returns:
      {"status": "discovered", "operations": [...]} — shared-auth server,
          live discovery succeeded.
      {"status": "needs_connection", "operations": []} — individually
          authenticated server; the Tools page should open the connect
          form (GET its schema, POST values) instead, which returns
          operations on success.
      {"status": "discovery_failed", "operations": [], "error": "..."} —
          shared-auth server configured but unreachable/misconfigured.
    """
    try:
        server_url, headers = api_center_catalog.get_mcp_discovery_target(tool_id)
    except ValueError:
        # "connection" auth mode (or any mode this backend can't resolve
        # alone) — not an error, just means discovery needs the user's own
        # connection step first (tool_connections.py).
        return {"status": "needs_connection", "operations": []}

    try:
        discovered = mcp_client.discover_tools(server_url, auth_headers=headers)
    except PermissionError as exc:
        return {"status": "needs_connection", "operations": [], "error": str(exc)}
    except mcp_client.MCPDiscoveryError as exc:
        logger.warning("Shared-auth discovery failed for tool=%s: %s", tool_id, exc)
        return {"status": "discovery_failed", "operations": [], "error": str(exc)}

    # apply_governance() already fills in each operation's risk (operationrisk
    # override, falling back to the server's own whole-tool risk) — nothing
    # further to do here.
    operations = apply_governance(tool_id, discovered)
    return {"status": "discovered", "operations": operations}
