"""
Dynamic agent-template catalog — the pre-built, department-aligned starting
points shown on the Start page (IT Service Desk, Employee Onboarding,
Invoice Processing, SOC Investigation, ...). Backed by the same Azure App
Configuration store as knowledge_registry.py, under its own key prefix, so
a catalog admin can add, edit, or retire a template with no code deploy —
see api/admin/routes.py's catalog-admin/agent-templates routes and the
matching AdminAgentTemplates.tsx page.

A template only pre-fills the Stage 1 fields a human would otherwise type
on the Describe/Start page (name, department, agentType, pattern, purpose,
modelPolicy, dataClassification, humanApproval, externalSharing) — exactly
the same fields blueprint_generator.py's LLM call produces and nothing
more. It deliberately never pre-selects knowledgeSources/tools/audience:
those are still picked by the user from the real, live, department-scoped
catalog on Configure, for the same reason blueprint_generator.py never
guesses them — only the actual catalog pages know what's approved right
now, and a template that went stale (a knowledge source renamed or
retired) must never be able to silently attach an unapproved id.

register_agent_template() is the only supported way to add or update a
template, mirroring knowledge_registry.register_knowledge_source()'s
"no hand-edited App Configuration keys" rule.
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

logger = logging.getLogger(__name__)

_APPCONFIG_ENDPOINT = os.environ["APPCONFIG_ENDPOINT"]
_KEY_PREFIX = os.environ.get("TEMPLATE_KEY_PREFIX", "agent-templates/")
_CACHE_TTL_SECONDS = int(os.environ.get("TEMPLATE_CACHE_TTL_SECONDS", "120"))

_client: Optional[AzureAppConfigurationClient] = None


def _get_client() -> AzureAppConfigurationClient:
    global _client
    if _client is None:
        _client = AzureAppConfigurationClient(base_url=_APPCONFIG_ENDPOINT, credential=DefaultAzureCredential())
    return _client


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


_cache: Optional[_CacheEntry] = None


def _invalidate_cache() -> None:
    global _cache
    _cache = None


def _all_templates() -> dict[str, dict]:
    global _cache
    if _cache and _cache.expires_at > time.time():
        return _cache.value

    client = _get_client()
    result: dict[str, dict] = {}
    try:
        for setting in client.list_configuration_settings(key_filter=f"{_KEY_PREFIX}*"):
            template_id = setting.key[len(_KEY_PREFIX):]
            try:
                result[template_id] = json.loads(setting.value)
            except (TypeError, json.JSONDecodeError):
                logger.exception("Bad JSON in App Configuration key %s", setting.key)
    except HttpResponseError:
        logger.exception("App Configuration list failed for agent templates")
        raise

    _cache = _CacheEntry(value=result, expires_at=time.time() + _CACHE_TTL_SECONDS)
    return result


def list_all_templates() -> dict[str, dict]:
    """Unfiltered registry contents, for the admin UI."""
    return _all_templates()


def list_templates(departments: Optional[list[str]] = None) -> list[dict]:
    """
    Templates visible to a requester approved for `departments`
    (None means unfiltered — used only by trusted/internal callers; the
    public /api/templates route always passes the requester's real list).
    """
    items = []
    for template_id, item in sorted(_all_templates().items()):
        if departments is not None and item.get("department") not in departments:
            continue
        items.append({"id": template_id, **item})
    return items


def get_template(template_id: str) -> dict:
    item = _all_templates().get(template_id)
    if item is None:
        raise ResourceNotFoundError(f"Agent template '{template_id}' not found in registry")
    return {"id": template_id, **item}


def register_agent_template(
    template_id: str,
    display_name: str,
    department: str,
    agent_type: str,
    pattern: str,
    purpose: str,
    model_policy: str,
    data_classification: str,
    human_approval: bool,
    external_sharing: bool = False,
    icon: str = "",
    description: str = "",
) -> dict:
    item = {
        "displayName": display_name,
        "department": department,
        "agentType": agent_type,
        "pattern": pattern,
        "purpose": purpose,
        "modelPolicy": model_policy,
        "dataClassification": data_classification,
        "humanApproval": human_approval,
        "externalSharing": external_sharing,
        "icon": icon,
        "description": description,
    }
    client = _get_client()
    client.set_configuration_setting(
        ConfigurationSetting(key=f"{_KEY_PREFIX}{template_id}", value=json.dumps(item))
    )
    _invalidate_cache()
    logger.info("Registered agent template '%s' for department '%s'", template_id, department)
    return {"id": template_id, **item}


def delete_agent_template(template_id: str) -> None:
    client = _get_client()
    client.delete_configuration_setting(key=f"{_KEY_PREFIX}{template_id}")
    _invalidate_cache()
