"""
Dynamic tool catalog backed by Azure API Center.
"""
from __future__ import annotations

import json
import os
import time
import logging
from dataclasses import dataclass
from typing import Any, Optional

from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.mgmt.apicenter import ApiCenterMgmtClient

logger = logging.getLogger(__name__)

_SUBSCRIPTION_ID = os.environ["AZURE_SUBSCRIPTION_ID"]
_RESOURCE_GROUP = os.environ["RESOURCE_GROUP"]
_SERVICE_NAME = os.environ["APICENTER_SERVICE_NAME"]
_WORKSPACE_NAME = os.environ.get("APICENTER_WORKSPACE_NAME", "default")

_CATALOG_CACHE_TTL_SECONDS = int(os.environ.get("APICENTER_CATALOG_CACHE_TTL", "120"))
_SPEC_CACHE_TTL_SECONDS = int(os.environ.get("APICENTER_SPEC_CACHE_TTL", "600"))

# See the module docstring CAVEAT — confirm against a real registered asset.
_MCP_KINDS = {"mcp", "mcpserver", "mcp_server", "modelcontextprotocol"}

_client: Optional[ApiCenterMgmtClient] = None


def _get_client() -> ApiCenterMgmtClient:
    global _client
    if _client is None:
        _client = ApiCenterMgmtClient(
            credential=DefaultAzureCredential(),
            subscription_id=_SUBSCRIPTION_ID,
        )
    return _client


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


_tool_cache: dict[str, _CacheEntry] = {}
_spec_cache: dict[str, _CacheEntry] = {}


def _cache_get(cache: dict[str, _CacheEntry], key: str):
    entry = cache.get(key)
    if entry and entry.expires_at > time.time():
        return entry.value
    return None


def _cache_set(cache: dict[str, _CacheEntry], key: str, value: Any, ttl: int):
    cache[key] = _CacheEntry(value=value, expires_at=time.time() + ttl)


def _properties(entity) -> dict:
    return entity.as_dict().get("properties", {}) or {}


def _custom_props(entity) -> dict:
    return _properties(entity).get("custom_properties", {}) or {}


def _is_mcp(api) -> bool:
    kind = (_properties(api).get("kind") or "").strip().lower()
    return kind in _MCP_KINDS


def tools_for_department(department: str) -> dict[str, dict]:
    cached = _cache_get(_tool_cache, department)
    if cached is not None:
        return cached

    client = _get_client()
    result: dict[str, dict] = {}
    try:
        apis = client.apis.list(
            resource_group_name=_RESOURCE_GROUP,
            service_name=_SERVICE_NAME,
            workspace_name=_WORKSPACE_NAME,
        )
        for api in apis:
            props = _custom_props(api)
            depts = props.get("department") or []
            ready = props.get("agentfactoryready") is True
            if department in depts and ready:
                result[api.name] = {
                    "display_name": _properties(api).get("title", api.name),
                    "description": (
                        props.get("tooldescription")
                        or _properties(api).get("summary")
                        or _properties(api).get("description")
                        or "No description provided."
                    ),
                    "capabilities": [
                        item.strip()
                        for item in str(props.get("toolcapabilities", "")).split(";")
                        if item.strip()
                    ],
                    "access_mode": (
                        props.get("toolaccessmode") or "read_write"
                    ).strip().lower(),
                    "department": depts,
                    "risk": props.get("risk", "medium"),
                    "kind": "mcp" if _is_mcp(api) else "openapi",
                    "requires_connection": bool(props.get("connectionschema")),
                }
    except HttpResponseError:
        logger.exception("API Center list failed for department=%s", department)
        raise

    _cache_set(_tool_cache, department, result, _CATALOG_CACHE_TTL_SECONDS)
    return result

# tool_connections.py needs the raw asset, not just get_foundry_tool()'s slimmed output
def get_api_asset(api_name: str):
    client = _get_client()
    try:
        return client.apis.get(
            resource_group_name=_RESOURCE_GROUP,
            service_name=_SERVICE_NAME,
            workspace_name=_WORKSPACE_NAME,
            api_name=api_name,
        )
    except ResourceNotFoundError:
        raise ValueError(f"API Center asset '{api_name}' not found")

def approved_tool_ids(department: str) -> set[str]:
    """Used by policy/catalogs.py's approved_tool_ids() — same contract."""
    return set(tools_for_department(department).keys())


def _runtime_uri(client: ApiCenterMgmtClient, api_name: str) -> str:
    """
    The deployment mechanism is shared by every API kind — this is API
    Center's own "where does this actually run" record, not something we
    invented for MCP. Picks the first active deployment with a runtime_uri.
    """
    deployments = list(
        client.deployments.list(
            resource_group_name=_RESOURCE_GROUP,
            service_name=_SERVICE_NAME,
            workspace_name=_WORKSPACE_NAME,
            api_name=api_name,
        )
    )
    for d in deployments:
        props = _properties(d)
        if props.get("state", "active") != "active":
            continue
        server = props.get("server") or {}
        uris = server.get("runtime_uri") or server.get("runtimeUri") or []
        if uris:
            return uris[0]
    raise ValueError(f"API Center asset '{api_name}' has no active deployment with a runtime_uri set")


def _get_foundry_mcp_tool(client: ApiCenterMgmtClient, api_name: str, api) -> dict:
    props = _custom_props(api)
    server_url = _runtime_uri(client, api_name)

    allowed_tools_raw = props.get("mcpallowedtools")
    allowed_tools = (
        [t.strip() for t in allowed_tools_raw.split(",") if t.strip()]
        if isinstance(allowed_tools_raw, str) and allowed_tools_raw.strip()
        else None
    )

    mcp_config: dict[str, Any] = {
        "server_label": api_name,
        "server_url": server_url,
        # Deliberately defaulting to "never": real human-in-the-loop for
        # action tools isn't wired up end-to-end yet (no approve/deny UI,
        # no resume call) — see Review.tsx/Test.tsx. Flipping this to
        # "always" today would make the agent call hang with no way for a
        # user to ever approve it. Set mcprequireapproval=always once that
        # UI exists.
        "require_approval": props.get("mcprequireapproval", "never"),
    }
    if allowed_tools:
        mcp_config["allowed_tools"] = allowed_tools

    # Three auth modes, matching how Microsoft's own "build your own MCP
    # server on Azure Functions" guide maps auth to Foundry:
    #  - "connection": project_connection_id, Entra/managed-identity-based.
    #    Set up once in the Foundry project; nothing sensitive stored here.
    #  - "functionkey": the Function App's x-functions-key header. The key
    #    itself is NEVER stored as an API Center custom property (that
    #    would be a plaintext secret sitting in catalog metadata) — only
    #    the *name* of an app setting is stored, and the real value is read
    #    from this Function App's own environment at request time. Put the
    #    target server's key in this app's settings (ideally sourced from
    #    Key Vault via an @Microsoft.KeyVault(...) app setting reference).
    #  - anything else (default "anonymous"): no auth, for a server you've
    #    deliberately left open.
    auth_mode = (props.get("foundryauthmode") or "anonymous").strip()
    if auth_mode == "connection":
        mcp_config["project_connection_id"] = props.get("foundryconnectionid", "")
    elif auth_mode == "functionkey":
        env_var_name = props.get("foundryfunctionkeyenvvar")
        key_value = os.environ.get(env_var_name, "") if env_var_name else ""
        if not key_value:
            raise ValueError(
                f"MCP tool uses auth mode 'functionkey' but its key env var "
                f"'{env_var_name}' is unset on this Function App"
            )
        mcp_config["headers"] = {"x-functions-key": key_value}

    return {"type": "mcp", "mcp": mcp_config}


def _get_foundry_openapi_tool(client: ApiCenterMgmtClient, api_name: str, api) -> dict:
    versions = list(
        client.api_versions.list(
            resource_group_name=_RESOURCE_GROUP,
            service_name=_SERVICE_NAME,
            workspace_name=_WORKSPACE_NAME,
            api_name=api_name,
        )
    )
    if not versions:
        raise ValueError(f"API '{api_name}' has no versions registered in API Center")
    version = next(
        (v for v in versions if _properties(v).get("lifecycle_stage") == "production"),
        versions[0],
    )

    definitions = list(
        client.api_definitions.list(
            resource_group_name=_RESOURCE_GROUP,
            service_name=_SERVICE_NAME,
            workspace_name=_WORKSPACE_NAME,
            api_name=api_name,
            version_name=version.name,
        )
    )
    if not definitions:
        raise ValueError(f"API '{api_name}' version '{version.name}' has no definitions")
    definition = definitions[0]

    poller = client.api_definitions.begin_export_specification(
        resource_group_name=_RESOURCE_GROUP,
        service_name=_SERVICE_NAME,
        workspace_name=_WORKSPACE_NAME,
        api_name=api_name,
        version_name=version.name,
        definition_name=definition.name,
    )
    export_result = poller.result()
    # Confirmed against the real SDK (ApiSpecExportResult): `format` is
    # "inline" or "link". We only handle "inline" — if API Center ever
    # exports a spec by link instead of inline, `value` is a URL, not the
    # spec itself, and this intentionally raises rather than silently
    # trying to JSON/YAML-parse a bare URL.
    if getattr(export_result, "format", "inline") != "inline":
        raise ValueError(
            f"API '{api_name}' exported its spec as format='{export_result.format}', "
            "not 'inline' — fetching a linked spec isn't implemented yet"
        )
    spec_value = export_result.value

    props = _custom_props(api)
    auth_mode = (props.get("foundryauthmode") or "anonymous").strip()

    if auth_mode == "connection":
        auth = {"type": "connection", "connection_id": props.get("foundryconnectionid", "")}
    elif auth_mode == "managed":
        # Agent's own managed identity authenticates to the target API via
        # Entra — best option for internal company APIs that support it,
        # avoids storing any secret at all. Needs an `audience` too; add a
        # matching "foundryAudience" custom property if you use this.
        auth = {"type": "managed_identity", "audience": props.get("foundryaudience", "")}
    else:
        auth = {"type": "anonymous"}

    return {
        "type": "openapi",
        "openapi": {
            "name": api_name,
            "description": _properties(api).get("summary") or _properties(api).get("title") or api_name,
            "spec": spec_value,
            "auth": auth,
        },
    }


def tool_risk(tool_id: str) -> str:
    """The server's own `risk` custom property, independent of department —
    used as the fallback risk for any operation without an `operationrisk`
    override (tool_discovery.py, tool_connections.py)."""
    api = get_api_asset(tool_id)
    return (_custom_props(api).get("risk") or "medium")


def operations_allowlist(tool_id: str) -> Optional[list[str]]:
    """
    Admin-declared governance CEILING on which MCP operations may ever be
    selected for this server — reusing the existing `mcpallowedtools`
    custom property, now interpreted as "at most these" rather than "always
    exactly these". None means no admin-declared ceiling: every operation
    discovery.discover_operations() actually finds on the live server is
    selectable (still subject to the Agent-type / risk policy checks in
    api/policy/rules.py). An empty discovered intersection is NOT the same
    as "no tool" — callers should surface it as a configuration problem,
    not silently drop the server.
    """
    api = get_api_asset(tool_id)
    props = _custom_props(api)
    raw = props.get("mcpallowedtools")
    if not isinstance(raw, str) or not raw.strip():
        return None
    return [t.strip() for t in raw.split(",") if t.strip()]


def operation_risk_overrides(tool_id: str) -> dict[str, str]:
    """
    Optional admin-declared per-operation risk, for finer-grained policy
    than the whole-server `risk` custom property (requirement: "apply
    security policies to individual operations, not just entire
    integrations"). Custom property `operationrisk` is a JSON object
    {"operationName": "low|medium|high|critical", ...}. Never guessed —
    an operation missing from this map falls back to the server's own
    `risk` property in api/policy/catalogs.py::operation_risk_levels().
    """
    api = get_api_asset(tool_id)
    raw = _custom_props(api).get("operationrisk")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        logger.warning("Tool '%s' has an unparsable operationrisk custom property", tool_id)
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _shared_mcp_auth_headers(api) -> Optional[dict[str, str]]:
    """
    Headers this Function App can itself attach to a direct MCP request for
    an admin-configured ("shared authentication") server — i.e. only the
    `functionkey` auth mode, where the real secret lives in Key Vault via an
    `@Microsoft.KeyVault(...)` app-setting reference and only the setting's
    *name* is stored in API Center (see _get_foundry_mcp_tool's docstring).
    `anonymous` needs no headers (returns {}). `connection`
    (ProjectManagedIdentity) auth is resolved by Foundry's own managed
    identity at agent-runtime, which this backend does not hold — callers
    must treat that case as "not discoverable from here" rather than guess.
    """
    props = _custom_props(api)
    auth_mode = (props.get("foundryauthmode") or "anonymous").strip()
    if auth_mode == "anonymous":
        return {}
    if auth_mode == "functionkey":
        env_var_name = props.get("foundryfunctionkeyenvvar")
        key_value = os.environ.get(env_var_name, "") if env_var_name else ""
        if not key_value:
            raise ValueError(
                f"MCP tool uses auth mode 'functionkey' but its key env var "
                f"'{env_var_name}' is unset on this Function App"
            )
        return {"x-functions-key": key_value}
    return None  # "connection", or anything else — not resolvable here


def get_mcp_discovery_target(tool_id: str) -> tuple[str, dict[str, str]]:
    """
    (server_url, headers) this backend can use right now to call the live
    MCP server's `tools/list` for an admin ("shared authentication") tool —
    i.e. without needing a per-user connection first. Raises ValueError if
    the tool isn't an MCP server, or uses an auth mode (`connection`) this
    backend cannot resolve on its own; callers should treat that as
    "discovery requires the user to connect first" (tool_connections.py) or
    "discovery requires elevated admin access", not a bug.
    """
    client = _get_client()
    api = get_api_asset(tool_id)
    if not _is_mcp(api):
        raise ValueError(f"Tool '{tool_id}' is not an MCP server (kind='{_properties(api).get('kind')}')")
    headers = _shared_mcp_auth_headers(api)
    if headers is None:
        raise ValueError(
            f"Tool '{tool_id}' uses the 'connection' auth mode, which this backend cannot "
            "use for live discovery on its own (it relies on the Foundry project's own "
            "managed identity at agent-runtime). Use per-user discovery via "
            "tool_connections.discover_with_values() instead, or register this server with "
            "foundryauthmode='functionkey' if an admin-shared secret is appropriate."
        )
    server_url = _runtime_uri(client, tool_id)
    return server_url, headers


def get_foundry_tool(api_name: str) -> dict:
    """
    Returns either {"type": "openapi", "openapi": {...}} or
    {"type": "mcp", "mcp": {...}} — foundry_service.py::_build_tools()
    branches on "type" to build the matching SDK tool object.
    """
    cached = _cache_get(_spec_cache, api_name)
    if cached is not None:
        return cached

    client = _get_client()
    try:
        api = client.apis.get(
            resource_group_name=_RESOURCE_GROUP,
            service_name=_SERVICE_NAME,
            workspace_name=_WORKSPACE_NAME,
            api_name=api_name,
        )
    except ResourceNotFoundError:
        raise ValueError(f"API Center asset '{api_name}' not found")

    if _is_mcp(api):
        foundry_tool = _get_foundry_mcp_tool(client, api_name, api)
    else:
        foundry_tool = _get_foundry_openapi_tool(client, api_name, api)

    _cache_set(_spec_cache, api_name, foundry_tool, _SPEC_CACHE_TTL_SECONDS)
    return foundry_tool
