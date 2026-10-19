"""
Dynamic tool catalog backed by Azure API Center.
"""
from __future__ import annotations

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
                    "department": depts,
                    "risk": props.get("risk", "medium"),
                    "kind": "mcp" if _is_mcp(api) else "openapi",
                }
    except HttpResponseError:
        logger.exception("API Center list failed for department=%s", department)
        raise

    _cache_set(_tool_cache, department, result, _CATALOG_CACHE_TTL_SECONDS)
    return result


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
