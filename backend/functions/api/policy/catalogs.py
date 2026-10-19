"""
Thin wrapper the policy engine uses to re-validate a blueprint's
knowledge sources and tools against the approved, department-scoped
catalog, never trust what the frontend sent, only what's actually
in the catalog.

"""
from typing import Iterable

from api.blueprint.catalog_mvp import knowledge_sources_for_department, tools_for_department  # adjust to match your module


def approved_tool_ids(department: str) -> set[str]:
    return set(tools_for_department(department).keys())


def approved_knowledge_ids(department: str) -> set[str]:
    return set(knowledge_sources_for_department(department).keys())


def unapproved(selected, approved: set[str]) -> list[str]:
    return [item for item in selected if item not in approved]


def tool_risk_levels(department: str, tool_ids) -> dict[str, str]:
    """
    Real risk level per selected tool, straight from the live API Center
    catalog (the same `risk` property the Tools page shows as a pill) —
    never guessed from the tool's name/id. A tool id that isn't in the
    catalog (stale selection, deprecated/removed tool) comes back as
    "unknown" rather than being silently dropped, so callers can decide
    to treat an unresolvable tool as risky by default.
    """
    catalog = tools_for_department(department)
    return {
        tool_id: catalog.get(tool_id, {}).get("risk", "unknown") for tool_id in tool_ids
    }
