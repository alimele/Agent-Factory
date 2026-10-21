"""
Dynamic Foundry project-connection provisioning for knowledge bases.

Why this exists
----------------
A Foundry `RemoteTool` project connection isn't just an auth label — its
`target` property, fixed at creation time, is the actual MCP endpoint the
project's managed identity is authorized to call. `MCPTool.server_url` on
the agent is *supposed* to match that target; it does not override it. One
connection therefore belongs to exactly one knowledge base.

Before this module existed, `projectConnectionName` was a free-text field
typed by hand into each Azure App Configuration knowledge-source entry
(see knowledge_registry.py). Reusing a connection name across two different
knowledge bases — which happened for real (`credo-kb-mcp-connection` ended
up referenced by more than one knowledge source) — silently routes every
agent built from the affected entries to whichever knowledge base the
shared connection's `target` actually points at, regardless of what
`server_url` says. The agent's tool config looks correct; retrieval is not.

This module makes the connection name a *derived* value
(`connection_name_for`) and the connection itself a side effect of
registering a knowledge source (see knowledge_registry.register_knowledge_source),
so a human never has the opportunity to mistype or reuse one again.

Required app settings
----------------------
PROJECT_RESOURCE_ID
    The ARM resource ID of the Foundry project, e.g.
    /subscriptions/<sub>/resourceGroups/<rg>/providers/
    Microsoft.CognitiveServices/accounts/<account>/projects/<project>
    (NOT the same thing as FOUNDRY_ACTUAL_PROJECT_ENDPOINT, which is the
    data-plane endpoint used by AIProjectClient elsewhere in this codebase.)

Required role
--------------
Whatever identity calls ensure_project_connection (this Function App's
managed identity, if wired into an admin endpoint) needs the **Foundry
Project Manager** role on the parent Foundry resource. That's a real,
meaningful permission — see api/admin/routes.py for why this is gated to
an admin-only HTTP route rather than exposed to every signed-in user.
"""
from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

logger = logging.getLogger(__name__)

_ARM_BASE = "https://management.azure.com"
_ARM_CONNECTIONS_API_VERSION = "2025-10-01-preview"
_SEARCH_MCP_API_VERSION_DEFAULT = "2026-08-01-preview"
_SEARCH_AUDIENCE = "https://search.azure.com/"

_PROJECT_RESOURCE_ID = os.environ.get("PROJECT_RESOURCE_ID", "")

_MAX_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 1.5

_credential: Optional[DefaultAzureCredential] = None
_token_provider = None


class ConnectionProvisioningError(Exception):
    """Raised for any failure creating/reading/deleting a project connection."""


class ConnectionPermissionError(ConnectionProvisioningError):
    """
    Raised specifically for 401/403 from Azure Resource Manager — almost
    always means the calling identity is missing the Foundry Project
    Manager role on the project's parent resource, per Microsoft's own
    troubleshooting guidance for this exact connection type. Kept distinct
    from ConnectionProvisioningError so callers (e.g. the admin route) can
    return a clear, actionable 403 instead of a generic 502.
    """


def _get_token_provider():
    global _credential, _token_provider
    if _token_provider is None:
        _credential = DefaultAzureCredential()
        _token_provider = get_bearer_token_provider(
            _credential, "https://management.azure.com/.default"
        )
    return _token_provider


def _require_project_resource_id() -> str:
    if not _PROJECT_RESOURCE_ID:
        raise ConnectionProvisioningError(
            "PROJECT_RESOURCE_ID app setting is required to manage Foundry "
            "project connections (ARM resource ID of the Foundry project)."
        )
    return _PROJECT_RESOURCE_ID


def connection_name_for(source_id: str) -> str:
    """
    Deterministic, Azure-safe connection name derived from the knowledge
    source's own registry id. Because this is a pure function of source_id
    (never hand-typed, never copy-pasted from an unrelated entry), two
    different knowledge sources can never end up silently sharing a
    connection unless they explicitly share the same source_id — which
    would be a registry-key collision, not a connection-naming mistake.
    """
    cleaned = re.sub(r"[^A-Za-z0-9-]+", "-", source_id.strip()).strip("-").lower()
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    if not cleaned:
        raise ValueError("source_id must contain at least one letter or number")
    # Leave room for the fixed prefix; Azure connection names commonly cap
    # around 64 chars.
    return f"kb-mcp-{cleaned}"[:64].rstrip("-")


def build_mcp_target(
    search_service_endpoint: str,
    knowledge_base_name: str,
    api_version: str = _SEARCH_MCP_API_VERSION_DEFAULT,
) -> str:
    endpoint = search_service_endpoint.rstrip("/")
    return f"{endpoint}/knowledgebases/{knowledge_base_name}/mcp?api-version={api_version}"


def _headers() -> dict[str, str]:
    token = _get_token_provider()()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _request_with_retry(method: str, url: str, **kwargs) -> requests.Response:
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = requests.request(method, url, timeout=30, **kwargs)
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning("ARM %s %s failed (attempt %d/%d): %s", method, url, attempt, _MAX_RETRIES, exc)
            time.sleep(_RETRY_BACKOFF_SECONDS * attempt)
            continue

        if response.status_code in (401, 403):
            raise ConnectionPermissionError(
                f"ARM {method} {url} returned {response.status_code}. The calling identity "
                "is almost certainly missing the 'Foundry Project Manager' role on the "
                "project's parent resource (required to create/read/delete project "
                f"connections). Response: {response.text[:500]}"
            )
        if response.status_code >= 500 and attempt < _MAX_RETRIES:
            logger.warning(
                "ARM %s %s returned %d (attempt %d/%d), retrying",
                method, url, response.status_code, attempt, _MAX_RETRIES,
            )
            time.sleep(_RETRY_BACKOFF_SECONDS * attempt)
            continue
        return response

    raise ConnectionProvisioningError(f"ARM {method} {url} failed after {_MAX_RETRIES} attempts: {last_exc}")


def ensure_project_connection(
    connection_name: str,
    search_service_endpoint: str,
    knowledge_base_name: str,
    api_version: str = _SEARCH_MCP_API_VERSION_DEFAULT,
) -> str:
    """
    Idempotent create-or-update of a RemoteTool project connection pointed
    at exactly one knowledge base's MCP endpoint. Safe to call every time a
    knowledge source is registered or re-synced (e.g. when the search MCP
    api-version is bumped) — ARM PUT on this resource type is an upsert.

    Returns the mcp_endpoint the connection now targets, so callers can log
    or assert it matches what they expect.
    """
    project_resource_id = _require_project_resource_id()
    mcp_endpoint = build_mcp_target(search_service_endpoint, knowledge_base_name, api_version)

    url = (
        f"{_ARM_BASE}{project_resource_id}/connections/{connection_name}"
        f"?api-version={_ARM_CONNECTIONS_API_VERSION}"
    )
    body = {
        "name": connection_name,
        "type": "Microsoft.MachineLearningServices/workspaces/connections",
        "properties": {
            "authType": "ProjectManagedIdentity",
            "category": "RemoteTool",
            "target": mcp_endpoint,
            "isSharedToAll": True,
            "audience": _SEARCH_AUDIENCE,
            "metadata": {"ApiType": "Azure"},
        },
    }

    response = _request_with_retry("PUT", url, headers=_headers(), json=body)
    if not response.ok:
        raise ConnectionProvisioningError(
            f"Failed to create/update connection '{connection_name}': "
            f"{response.status_code} {response.text[:500]}"
        )

    logger.info(
        "Project connection '%s' now targets %s (knowledge_base=%s)",
        connection_name, mcp_endpoint, knowledge_base_name,
    )
    return mcp_endpoint


def get_project_connection_target(connection_name: str) -> Optional[str]:
    """Returns the connection's current `target`, or None if it doesn't exist."""
    project_resource_id = _require_project_resource_id()
    url = (
        f"{_ARM_BASE}{project_resource_id}/connections/{connection_name}"
        f"?api-version={_ARM_CONNECTIONS_API_VERSION}"
    )
    response = _request_with_retry("GET", url, headers=_headers())
    if response.status_code == 404:
        return None
    if not response.ok:
        raise ConnectionProvisioningError(
            f"Failed to read connection '{connection_name}': {response.status_code} {response.text[:500]}"
        )
    return (response.json().get("properties") or {}).get("target")


def list_project_connections() -> list[dict[str, Any]]:
    """
    All RemoteTool connections on the project, each as
    {"name": ..., "target": ..., "category": ...}. Used by the audit script
    to find connections that are shared across knowledge bases that
    shouldn't share one, and connections that are now orphaned.
    """
    project_resource_id = _require_project_resource_id()
    url = f"{_ARM_BASE}{project_resource_id}/connections?api-version={_ARM_CONNECTIONS_API_VERSION}"
    response = _request_with_retry("GET", url, headers=_headers())
    if not response.ok:
        raise ConnectionProvisioningError(
            f"Failed to list project connections: {response.status_code} {response.text[:500]}"
        )
    items = response.json().get("value", [])
    result = []
    for item in items:
        props = item.get("properties") or {}
        result.append({
            "name": item.get("name"),
            "target": props.get("target"),
            "category": props.get("category"),
        })
    return result


def delete_project_connection(connection_name: str) -> None:
    project_resource_id = _require_project_resource_id()
    url = (
        f"{_ARM_BASE}{project_resource_id}/connections/{connection_name}"
        f"?api-version={_ARM_CONNECTIONS_API_VERSION}"
    )
    response = _request_with_retry("DELETE", url, headers=_headers())
    if not response.ok and response.status_code != 404:
        raise ConnectionProvisioningError(
            f"Failed to delete connection '{connection_name}': {response.status_code} {response.text[:500]}"
        )
