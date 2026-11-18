"""
AgentBlueprint -> Foundry agent-creation payload.
"""

from __future__ import annotations

from typing import Any, Dict, List

from api.blueprint.blueprint_schema import AgentBlueprint, BehaviorOptions
from api.blueprint.catalog_mvp import MODEL_POLICIES
from api.blueprint.api_center_catalog import get_foundry_tool
from api.blueprint.knowledge_registry import get_foundry_tool as get_knowledge_mcp_tool
from api.blueprint.instructions import build_instructions


def _resolve_knowledge_tools(knowledge_source_ids: List[str]) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    tools: List[Dict[str, Any]] = []
    for ks_id in knowledge_source_ids:
        mcp_config = get_knowledge_mcp_tool(ks_id)
        tools.append({"type": "mcp", "mcp": mcp_config})
    return tools, {}  # knowledge MCP tools carry their own config, no tool_resources needed


def to_foundry_agent_payload(
    blueprint: AgentBlueprint, behavior: BehaviorOptions | None = None, tool_connections: Dict[str, str] | None = None
) -> Dict[str, Any]:
    """
    behavior is optional only so existing offline callers (test_phase2.py)
    that never cared about Behavior-page data keep working unchanged. Every
    real HTTP caller (function_app.py::blueprint_compile) now passes it, so
    this preview matches what create-test-agent will actually build.
    """
    tools: List[Dict[str, Any]] = []
    tool_resources: Dict[str, Any] = {}
    tool_connections = tool_connections or {}

    # Action tools pass through from the catalog as-is (already Foundry-shaped),
    # with the user's explicit per-operation selection applied to MCP servers
    # so this preview matches exactly what create-test-agent will build
    # (foundry_service.py::_build_tools) — never the admin's static
    # mcpallowedtools, and never a shared mutable dict (get_foundry_tool()
    # returns a cached object; copy before mutating so the Review page's
    # preview request can't corrupt the next caller's cached tool).
    for selection in blueprint.tools:
        tool = dict(get_foundry_tool(selection.serverId))
        conn_id = tool_connections.get(selection.serverId)
        if tool.get("type") == "mcp":
            mcp = dict(tool["mcp"])
            mcp["allowed_tools"] = selection.operations
            if conn_id:
                mcp["project_connection_id"] = conn_id
            tool["mcp"] = mcp
        tools.append(tool)

    # Knowledge sources resolve + merge into file_search / azure_ai_search tools
    if blueprint.knowledgeSources:
        k_tools, k_resources = _resolve_knowledge_tools(blueprint.knowledgeSources)
        tools += k_tools
        tool_resources.update(k_resources)

    payload = {
        "name": blueprint.name,
        "model": MODEL_POLICIES[blueprint.modelPolicy],
        "instructions": build_instructions(blueprint, behavior),
        "tools": tools,                 # [] is valid — e.g. a pure Q&A agent with no file_search either
        "tool_resources": tool_resources,  # {} is valid when tools is []
        "metadata": {
            "credo_department": blueprint.department,
            "credo_agent_type": blueprint.agentType,
            "credo_pattern": blueprint.pattern,
            "credo_owner": blueprint.owner,
            "credo_data_classification": blueprint.dataClassification,
            "credo_human_approval_required": str(blueprint.humanApproval),
            "credo_external_sharing": str(blueprint.externalSharing),
            "credo_audience": ",".join(blueprint.audience),
            "credo_review_period_days": str(blueprint.reviewPeriodDays),
            "credo_blueprint_version": blueprint.blueprintVersion,
        },
    }
    return payload
