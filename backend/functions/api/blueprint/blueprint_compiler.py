"""
Blueprint compiler
"""

from __future__ import annotations

import logging
from typing import Any, List
from pydantic import BaseModel

from api.blueprint.blueprint_schema import AgentBlueprint, ToolOperationSelection
from api.blueprint.catalog_mvp import AUDIENCES
from api.blueprint.api_center_catalog import tools_for_department
from api.blueprint.knowledge_registry import knowledge_sources_for_department
from api.blueprint import tool_discovery

logger = logging.getLogger(__name__)


class CatalogValidationError(ValueError):
    """Raised when a Stage 2 selection references an id that isn't (or is no
    longer) in the approved catalog — e.g. a stale page, tampered request,
    or a catalog entry that was deprecated between page-load and submit."""


def _validate_ids(ids: List[str], catalog: dict, label: str) -> None:
    unknown = [i for i in ids if i not in catalog]
    if unknown:
        raise CatalogValidationError(f"Unapproved {label} id(s): {unknown}")


def _validate_tool_selections(
    raw_selections: List[dict], department: str
) -> List[ToolOperationSelection]:
    """
    Re-derives the approved operation set for every selected server from
    LIVE sources (never trusts what the client echoes back for either the
    server id or the operation names):
      1. serverId must be an approved tool for this department
         (api_center_catalog.tools_for_department — unchanged gate).
      2. each requested operation must appear in that server's current,
         governance-filtered discovery result (tool_discovery.discover_operations
         for a shared-auth server, or the server's declared operations_allowlist
         alone when live discovery needs a per-user connection this request
         doesn't carry — see the fallback below).
    A selection with zero operations surviving validation is dropped
    entirely rather than kept as an empty-operations entry, since
    ToolOperationSelection requires at least one operation.
    """
    approved_servers = tools_for_department(department)
    seen_servers: set[str] = set()
    result: List[ToolOperationSelection] = []

    for raw in raw_selections:
        server_id = raw.get("serverId")
        requested_ops = raw.get("operations") or []
        if not server_id or server_id not in approved_servers:
            raise CatalogValidationError(f"Unapproved tool id: {server_id!r}")
        if server_id in seen_servers:
            raise CatalogValidationError(f"Tool '{server_id}' was selected more than once")
        seen_servers.add(server_id)

        allowed_ops = _resolve_allowed_operations(server_id)
        if allowed_ops is not None:
            bad = [op for op in requested_ops if op not in allowed_ops]
            if bad:
                raise CatalogValidationError(
                    f"Tool '{server_id}': operation(s) not currently discoverable or approved: {bad}"
                )

        valid_ops = [op for op in requested_ops if isinstance(op, str) and op.strip()]
        if not valid_ops:
            raise CatalogValidationError(f"Tool '{server_id}' was selected with no valid operations")

        result.append(ToolOperationSelection(serverId=server_id, operations=valid_ops))

    return result


def _resolve_allowed_operations(server_id: str) -> List[str] | None:
    """
    Best-effort live re-check of what this server currently exposes, for
    shared-auth servers this backend can reach directly. For a server that
    needs a per-user connection (discover_operations -> "needs_connection"),
    compile-time re-validation falls back to the admin's operations_allowlist
    alone (None = no admin ceiling declared, so any non-empty operation
    name the user selected is accepted) — it already went through a real
    tools/list call at connect time (tool_connections.create_tool_connection),
    this call just can't repeat that without the user's credentials in hand.
    """
    from api.blueprint import api_center_catalog

    discovery = tool_discovery.discover_operations(server_id)
    if discovery["status"] == "discovered":
        return [op["name"] for op in discovery["operations"]]
    # needs_connection / discovery_failed: fall back to the declared ceiling only.
    return api_center_catalog.operations_allowlist(server_id)


def compile_blueprint(
    core_draft: BaseModel,
    knowledge_source_ids: List[str],
    tool_selections: List[dict[str, Any]],
    audience_ids: List[str],
    requester_email: str,
    channels: List[str] | None = None,
    review_period_days: int = 180,
) -> AgentBlueprint:
    _validate_ids(knowledge_source_ids, knowledge_sources_for_department(core_draft.department), "knowledge source")
    _validate_ids(audience_ids, AUDIENCES, "audience")
    tools = _validate_tool_selections(tool_selections, core_draft.department)

    return AgentBlueprint(
        **core_draft.model_dump(),
        knowledgeSources=knowledge_source_ids,
        tools=tools,
        audience=audience_ids,
        channels=channels or ["Teams"],
        owner=requester_email,
        reviewPeriodDays=review_period_days,
    )
