"""
Per-user Foundry project connections for tools that need user-supplied
connection details (e.g. a customer's own Postgres database), as opposed
to tools with one fixed, shared deployment.

Two different things, easy to conflate:
  - The MCP server's own hosting endpoint (API Center's deployment/
    runtime_uri) is an admin-registered, one-time concern — the same
    server URL for every customer using that tool type.
  - The CREDENTIALS a specific user's agent needs to reach *their* data
    through that server (host/db/user/password) are per-user and belong
    in a project connection — never in API Center custom properties or
    our own Table Storage.

This module handles the second half: reading a tool's declared
`connectionschema`, validating user input against it, and creating a
connection scoped to (tool, requester) carrying those values as
connection credentials.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from api.blueprint import api_center_catalog, connection_manager as cm

logger = logging.getLogger(__name__)


class SchemaValidationError(Exception):
    """Raised when a tool's declared schema is malformed, or submitted
    values don't satisfy it."""


def get_connection_schema(tool_id: str) -> list[dict]:
    """[] means the tool is pre-wired (e.g. SharePoint via managed
    identity) — nothing for the user to fill in."""
    api = api_center_catalog.get_api_asset(tool_id)
    raw = api_center_catalog._custom_props(api).get("connectionschema")
    if not raw:
        return []
    try:
        schema = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError) as exc:
        raise SchemaValidationError(f"Tool '{tool_id}' has an invalid connectionschema: {exc}") from exc
    if not isinstance(schema, list):
        raise SchemaValidationError(f"Tool '{tool_id}' connectionschema must be a JSON array")
    return schema


def validate_values(schema: list[dict], values: dict[str, Any]) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    missing = []
    for field in schema:
        key = field["key"]
        value = values.get(key)
        if value in (None, "") and field.get("required", True):
            missing.append(key)
            continue
        if value not in (None, ""):
            cleaned[key] = str(value)
    if missing:
        raise SchemaValidationError(f"Missing required field(s): {', '.join(missing)}")
    return cleaned


def connection_name_for(tool_id: str, owner_email: str) -> str:
    """Deterministic per-(tool, user) name — two users picking the same
    tool never share a connection; the same user resubmitting updates it."""
    owner_hash = hashlib.sha256(owner_email.lower().encode()).hexdigest()[:12]
    cleaned_tool = "".join(c if c.isalnum() else "-" for c in tool_id.lower()).strip("-")
    return f"tool-{cleaned_tool}-{owner_hash}"[:64].rstrip("-")


def create_tool_connection(tool_id: str, owner_email: str, values: dict[str, Any]) -> str:
    schema = get_connection_schema(tool_id)
    if not schema:
        raise SchemaValidationError(f"Tool '{tool_id}' takes no user-supplied connection values")
    cleaned = validate_values(schema, values)

    # The MCP server's own address — admin-registered once, shared by
    # everyone. Raises the same ValueError you saw originally if nobody's
    # registered a deployment for this tool type yet.
    server_url = api_center_catalog.get_foundry_tool(tool_id)["mcp"]["server_url"]

    connection_name = connection_name_for(tool_id, owner_email)
    project_resource_id = cm._require_project_resource_id()
    url = (
        f"{cm._ARM_BASE}{project_resource_id}/connections/{connection_name}"
        f"?api-version={cm._ARM_CONNECTIONS_API_VERSION}"
    )
    body = {
        "name": connection_name,
        "type": "Microsoft.MachineLearningServices/workspaces/connections",
        "properties": {
            "authType": "CustomKeys",
            "category": "RemoteTool",
            "target": server_url,
            "isSharedToAll": False,  # scoped to this one user's agents only
            "credentials": {"keys": cleaned},
            "metadata": {"toolId": tool_id, "owner": owner_email},
        },
    }
    response = cm._request_with_retry("PUT", url, headers=cm._headers(), json=body)
    if not response.ok:
        raise cm.ConnectionProvisioningError(
            f"Failed to create tool connection '{connection_name}': "
            f"{response.status_code} {response.text[:500]}"
        )
    logger.info("Tool connection '%s' created for %s (tool=%s)", connection_name, owner_email, tool_id)
    return connection_name