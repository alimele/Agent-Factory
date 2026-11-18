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
    Real risk level per selected tool (server), straight from the live API
    Center catalog (the same `risk` property the Tools page shows as a
    pill) — never guessed from the tool's name/id. A tool id that isn't in
    the catalog (stale selection, deprecated/removed tool) comes back as
    "unknown" rather than being silently dropped, so callers can decide
    to treat an unresolvable tool as risky by default.
    """
    catalog = tools_for_department(department)
    return {
        tool_id: catalog.get(tool_id, {}).get("risk", "unknown") for tool_id in tool_ids
    }


def operation_risk_levels(department: str, tool_selections: Iterable[dict]) -> dict[tuple[str, str], str]:
    """
    Per-(server, operation) risk, keyed finer than tool_risk_levels() above.
    Prefers the live, governance-filtered discovery result (which already
    carries each operation's resolved risk — operationrisk override, or the
    server's own risk as fallback; see tool_discovery.apply_governance) and
    falls back to the whole-server risk for an operation that didn't come
    back from discovery (e.g. a needs_connection server at policy-eval
    time) — never silently "unknown" for a real selection, since an
    unresolvable operation is exactly the case policy must not treat as
    automatically low-risk.
    """
    from api.blueprint import tool_discovery  # local import: policy must not import blueprint at module load time

    server_fallback = tool_risk_levels(department, [s.get("serverId") for s in tool_selections])
    result: dict[tuple[str, str], str] = {}
    for selection in tool_selections:
        server_id = selection.get("serverId")
        discovery = tool_discovery.discover_operations(server_id)
        by_name = {op["name"]: op.get("risk") for op in discovery.get("operations", [])}
        for op_name in selection.get("operations") or []:
            result[(server_id, op_name)] = by_name.get(op_name) or server_fallback.get(server_id, "unknown")
    return result
