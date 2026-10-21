"""
Dynamic knowledge-source catalog backed by Azure App Configuration.

Config key naming (`knowledge-sources/<id>`) is this module's own choice,
not an Azure constraint — fine to rename before you seed data, just keep
KEY_PREFIX in sync.

Registration (register_knowledge_source) is the only supported way to add
or update a knowledge source. It derives and provisions the Foundry
project connection itself (see connection_manager.py) rather than letting
a human type `projectConnectionName` into App Configuration by hand — that
manual path is exactly how one knowledge source ended up silently sharing
another's connection (and therefore another's retrieval results) in
production. Hand-editing a `knowledge-sources/*` key directly in App
Configuration is no longer supported; use register_knowledge_source or the
POST /api/admin/knowledge-sources route instead.
"""
from __future__ import annotations

import os
import json
import time
import logging
from dataclasses import dataclass
from typing import Any, Optional

from azure.appconfiguration import AzureAppConfigurationClient, ConfigurationSetting
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential

from api.blueprint import connection_manager

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


def _invalidate_cache() -> None:
    """Called after register_knowledge_source() writes a new/changed entry
    so a subsequent read in the same process doesn't serve a stale
    per-department cache for up to KNOWLEDGE_CACHE_TTL_SECONDS."""
    _cache.clear()


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


def list_all_knowledge_sources() -> dict[str, dict]:
    """Public alias of _all_sources() for admin/audit tooling (scripts/
    audit_and_fix_kb_connections.py, the admin audit route) — the raw,
    un-department-filtered registry contents."""
    return _all_sources()


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
    Service.
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

    mcp_endpoint = connection_manager.build_mcp_target(endpoint, kb_name)

    return {
        "server_label": "knowledge-base",
        "server_url": mcp_endpoint,
        "require_approval": "never",
        "allowed_tools": ["knowledge_base_retrieve"],
        "project_connection_id": connection_name,
    }


def register_knowledge_source(
    source_id: str,
    display_name: str,
    departments: list[str],
    data_classification: str,
    search_service_endpoint: str,
    knowledge_base_name: str,
    agent_factory_ready: bool = True,
) -> dict:
    """
    The only supported way to add or update a knowledge source. Derives the
    connection name from source_id (connection_manager.connection_name_for),
    provisions (creates or updates) the matching Foundry project connection
    so its `target` actually points at this knowledge base, and only then
    writes the App Configuration entry — with the derived name, never a
    caller-supplied one. A caller cannot set projectConnectionName directly;
    there is deliberately no parameter for it.

    Re-running this for an existing source_id is safe and is the supported
    way to repoint a knowledge source at a different search service/index,
    or to re-sync its connection after the knowledge-base MCP api-version
    changes (connection_manager.ensure_project_connection is an upsert).
    """
    if not departments:
        raise ValueError("departments must contain at least one department")
    if not search_service_endpoint or not knowledge_base_name:
        raise ValueError("search_service_endpoint and knowledge_base_name are required")

    connection_name = connection_manager.connection_name_for(source_id)
    mcp_target = connection_manager.ensure_project_connection(
        connection_name=connection_name,
        search_service_endpoint=search_service_endpoint,
        knowledge_base_name=knowledge_base_name,
    )

    item = {
        "displayName": display_name,
        "department": departments,
        "dataClassification": data_classification,
        "searchServiceEndpoint": search_service_endpoint,
        "knowledgeBaseName": knowledge_base_name,
        "projectConnectionName": connection_name,
        "agentFactoryReady": agent_factory_ready,
    }

    client = _get_client()
    client.set_configuration_setting(
        ConfigurationSetting(key=f"{_KEY_PREFIX}{source_id}", value=json.dumps(item))
    )
    _invalidate_cache()

    logger.info(
        "Registered knowledge source '%s' -> connection '%s' -> %s",
        source_id, connection_name, mcp_target,
    )
    return {"sourceId": source_id, "connectionName": connection_name, "mcpTarget": mcp_target, **item}


def audit_connection_assignments() -> list[dict]:
    """
    Cross-checks every knowledge-source entry against the live Foundry
    connections. Flags two distinct problems — either one means an agent
    built from the affected entry is retrieving from the wrong knowledge
    base, exactly like the Alpha Bank / knowledgebase107 incident:

    - "shared_connection": this entry's projectConnectionName is also used
      by a different entry whose searchServiceEndpoint/knowledgeBaseName
      differ — i.e. two knowledge bases are sharing one connection.
    - "target_mismatch": the connection exists, but its live `target` does
      not match what this entry's own endpoint/knowledge base would
      produce — i.e. the connection was repointed (or never matched) after
      the registry entry was written.

    Used by both the GET /api/admin/knowledge-sources/audit route and
    scripts/audit_and_fix_kb_connections.py so there is exactly one
    definition of "correctly wired".
    """
    sources = _all_sources()

    by_connection: dict[str, list[tuple[str, str, str]]] = {}
    for source_id, item in sources.items():
        conn = item.get("projectConnectionName")
        if not conn:
            continue
        by_connection.setdefault(conn, []).append(
            (source_id, item.get("searchServiceEndpoint", ""), item.get("knowledgeBaseName", ""))
        )

    findings: list[dict] = []
    for source_id, item in sources.items():
        conn = item.get("projectConnectionName")
        endpoint = item.get("searchServiceEndpoint")
        kb_name = item.get("knowledgeBaseName")
        if not conn or not endpoint or not kb_name:
            findings.append({
                "sourceId": source_id,
                "issue": "incomplete_entry",
                "detail": "Missing projectConnectionName/searchServiceEndpoint/knowledgeBaseName",
            })
            continue

        siblings = [s for s in by_connection.get(conn, []) if s[0] != source_id]
        conflicting = [s for s in siblings if (s[1], s[2]) != (endpoint, kb_name)]
        if conflicting:
            findings.append({
                "sourceId": source_id,
                "issue": "shared_connection",
                "connectionName": conn,
                "detail": f"Shared with: {[s[0] for s in conflicting]}",
            })

        try:
            live_target = connection_manager.get_project_connection_target(conn)
        except connection_manager.ConnectionProvisioningError as exc:
            findings.append({
                "sourceId": source_id,
                "issue": "connection_unreadable",
                "connectionName": conn,
                "detail": str(exc),
            })
            continue

        expected_target = connection_manager.build_mcp_target(endpoint, kb_name)
        if live_target is None:
            findings.append({
                "sourceId": source_id,
                "issue": "connection_missing",
                "connectionName": conn,
                "detail": "No such connection exists on the Foundry project",
            })
        elif live_target != expected_target:
            findings.append({
                "sourceId": source_id,
                "issue": "target_mismatch",
                "connectionName": conn,
                "detail": f"Connection targets {live_target!r}, entry expects {expected_target!r}",
            })

    return findings


if __name__ == "__main__":
    dept = "IT Support"  # change to whatever your seeded setting is tagged with
    print(f"Knowledge sources for '{dept}':")
    print(json.dumps(knowledge_sources_for_department(dept), indent=2))
