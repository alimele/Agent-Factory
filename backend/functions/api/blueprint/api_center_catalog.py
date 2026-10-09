"""
Dynamic tool catalog backed by Azure API Center.
"""
from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass
from typing import Any, Optional

from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential
from azure.mgmt.apicenter import ApiCenterMgmtClient

logger = logging.getLogger(__name__)

_SUBSCRIPTION_ID = os.environ["AZURE_SUBSCRIPTION_ID"]
_RESOURCE_GROUP = os.environ["RESOURCE_GROUP"]
_SERVICE_NAME = os.environ["APICENTER_SERVICE_NAME"]
_WORKSPACE_NAME = os.environ.get("APICENTER_WORKSPACE_NAME", "default")

_CATALOG_CACHE_TTL_SECONDS = int(os.environ.get("APICENTER_CATALOG_CACHE_TTL", "120"))
_SPEC_CACHE_TTL_SECONDS = int(os.environ.get("APICENTER_SPEC_CACHE_TTL", "600"))

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
            print(api.name, "props:", props)  # DEBUG
            depts = props.get("department") or []
            ready = props.get("agentfactoryready") is True
            if department in depts and ready:
                result[api.name] = {
                    "display_name": _properties(api).get("title", api.name),
                    "department": depts,
                    "risk": props.get("risk", "medium"),
                }
    except HttpResponseError:
        logger.exception("API Center list failed for department=%s", department)
        raise

    _cache_set(_tool_cache, department, result, _CATALOG_CACHE_TTL_SECONDS)
    return result


def approved_tool_ids(department: str) -> set[str]:
    """Used by policy/catalogs.py's approved_tool_ids() — same contract."""
    return set(tools_for_department(department).keys())


def get_foundry_tool(api_name: str) -> dict:
    cached = _cache_get(_spec_cache, api_name)
    if cached is not None:
        return cached

    client = _get_client()

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
    # export_result.value / .format — confirm exact attribute (VERIFY #1)
    spec_value = export_result.value

    api = client.apis.get(
        resource_group_name=_RESOURCE_GROUP,
        service_name=_SERVICE_NAME,
        workspace_name=_WORKSPACE_NAME,
        api_name=api_name,
    )
    props = _custom_props(api)
    auth_mode = props.get("foundryauthmode", "anonymous").strip()

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

    foundry_tool = {
        "type": "openapi",
        "openapi": {
            "name": api_name,
            "description": _properties(api).get("summary") or _properties(api).get("title") or api_name,
            "spec": spec_value,
            "auth": auth,
        },
    }
    _cache_set(_spec_cache, api_name, foundry_tool, _SPEC_CACHE_TTL_SECONDS)
    return foundry_tool
