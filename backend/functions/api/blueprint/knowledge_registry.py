"""
Dynamic knowledge-source catalog backed by Azure App Configuration.

NOTE for whoever builds Phase 4 (actual Foundry agent creation — not built
yet as of this writing): creating a real agent goes through
`azure-ai-projects`'s AIProjectClient.agents.create_version(...) with
typed PromptAgentDefinition/MCPTool objects (or an equivalent dict), not
a generic REST payload assembled independently — see
scripts/test_foundry_iq_agent.py for the confirmed working call shape.
foundry_payload.py's to_foundry_agent_payload() may need to change shape
once Phase 4 is actually built against this, since its current
`type`/`openapi`-nested-dict convention doesn't obviously match how
MCPTool is constructed — worth checking against the real SDK then, not
assuming today's shape carries over.

Config key naming (`knowledge-sources/<id>`) is this module's own choice,
not an Azure constraint — fine to rename before you seed data, just keep
KEY_PREFIX in sync.
"""
from __future__ import annotations

import os
import json
import time
import logging
from dataclasses import dataclass
from typing import Any, Optional

from azure.appconfiguration import AzureAppConfigurationClient
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

_APPCONFIG_ENDPOINT = os.environ["APPCONFIG_ENDPOINT"]  # e.g. https://<store>.azconfig.io
_KEY_PREFIX = os.environ.get("KNOWLEDGE_KEY_PREFIX", "knowledge-sources/")

_CACHE_TTL_SECONDS = int(os.environ.get("KNOWLEDGE_CACHE_TTL_SECONDS", "120"))

_client: Optional[AzureAppConfigurationClient] = None


def _get_client() -> AzureAppConfigurationClient:
    global _client
    if _client is None:
        _client = AzureAppConfigurationClient(
            base_url=_APPCONFIG_ENDPOINT, credential=DefaultAzureCredential()
        )
    return _client


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


_cache: dict[str, _CacheEntry] = {}


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and entry.expires_at > time.time():
        return entry.value
    return None


def _cache_set(key: str, value: Any, ttl: int = _CACHE_TTL_SECONDS):
    _cache[key] = _CacheEntry(value=value, expires_at=time.time() + ttl)


def _all_sources() -> dict[str, dict]:
    """All knowledge-source settings, id -> parsed JSON value. Not cached at
    this level — tools_for_department() below caches per-department."""
    client = _get_client()
    result: dict[str, dict] = {}
    try:
        settings = client.list_configuration_settings(key_filter=f"{_KEY_PREFIX}*")
        for setting in settings:
            source_id = setting.key[len(_KEY_PREFIX):]
            try:
                result[source_id] = json.loads(setting.value)
            except (TypeError, json.JSONDecodeError):
                logger.exception("Bad JSON in App Configuration key %s", setting.key)
    except HttpResponseError:
        logger.exception("App Configuration list failed")
        raise
    return result


def knowledge_sources_for_department(department: str) -> dict[str, dict]:
    """
    Stage 2 (Knowledge page) replacement for the old static
    catalog_mvp.knowledge_sources_for_department(). Same return shape as
    before: {source_id: {"display_name":..., "department": [...], ...}}
    """
    cached = _cache_get(department)
    if cached is not None:
        return cached

    result: dict[str, dict] = {}
    for source_id, item in _all_sources().items():
        depts = item.get("department") or []
        if department in depts and item.get("agentFactoryReady") is True:
            result[source_id] = {
                "display_name": item.get("displayName", source_id),
                "department": depts,
                "data_classification": item.get("dataClassification", "Internal"),
                "search_service_endpoint": item.get("searchServiceEndpoint"),
                "knowledge_base_name": item.get("knowledgeBaseName"),
                "project_connection_name": item.get("projectConnectionName"),
            }

    _cache_set(department, result)
    return result


def get_foundry_tool(source_id: str) -> dict:
    """
    Resolve one knowledge source -> the MCP tool config for Foundry Agent
    Service. Field set confirmed by an actual end-to-end test (real agent,
    real grounded + cited answer) — not guessed. Phase 4's agent-creation
    code will likely want to pass these same fields into an azure-ai-projects
    MCPTool(...) object rather than consume this as a raw dict — check the
    real SDK call shape at that point (see scripts/test_foundry_iq_agent.py)
    rather than assuming this dict can be handed to it unchanged.
    """
    sources = _all_sources()
    item = sources.get(source_id)
    if item is None:
        raise ResourceNotFoundError(f"Knowledge source '{source_id}' not found in registry")

    endpoint = item.get("searchServiceEndpoint")
    kb_name = item.get("knowledgeBaseName")
    connection_name = item.get("projectConnectionName")
    if not endpoint or not kb_name or not connection_name:
        raise ValueError(
            f"Knowledge source '{source_id}' is missing searchServiceEndpoint/"
            f"knowledgeBaseName/projectConnectionName"
        )

    mcp_endpoint = f"{endpoint}/knowledgebases/{kb_name}/mcp?api-version=2026-08-01-preview"

    return {
        "server_label": "knowledge-base",
        "server_url": mcp_endpoint,
        "require_approval": "never",
        "allowed_tools": ["knowledge_base_retrieve"],
        "project_connection_id": connection_name,
    }


if __name__ == "__main__":
    dept = "IT Support"  # change to whatever your seeded setting is tagged with
    print(f"Knowledge sources for '{dept}':")
    print(json.dumps(knowledge_sources_for_department(dept), indent=2))
