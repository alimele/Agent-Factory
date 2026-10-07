"""
AgentBlueprint -> Foundry agent-creation payload.

Matches the Foundry Agent Service create-agent shape (per Microsoft's own
docs/SDK): name, model, instructions, tools (list, may be empty),
tool_resources (dict, may be {}), metadata (free-form dict — this is where
our governance fields ride along so they're visible on the agent record
itself, not just in our own database).

Both tools and knowledge sources are optional and independent:
- knowledgeSources=[] and tools=[] with a plain instructions-only agent
  is valid (a pure prompt agent, no grounding, no actions)
- only one of the two populated is the common case (Knowledge Assistant
  vs. Action/Process agent)
- "tools" in the OUTPUT Foundry payload can contain BOTH action tools and
  knowledge tools (file_search / azure_ai_search are themselves Foundry
  tools) — they are two different concepts in our blueprint, but merge
  into one Foundry "tools" array.
"""

from __future__ import annotations

from typing import Any, Dict, List

from api.blueprint.blueprint_schema import AgentBlueprint
from api.blueprint.catalog_mvp import KNOWLEDGE_CATALOG, TOOL_CATALOG, MODEL_POLICIES


def _render_instructions(blueprint: AgentBlueprint) -> str:
    lines = [blueprint.purpose.strip()]
    if blueprint.tools:
        lines.append(
            "You may take actions using your available tools when the user's "
            "request clearly calls for it. Confirm before any action with "
            "side effects unless the request is explicitly a direct instruction to do so."
        )
    if blueprint.knowledgeSources:
        lines.append(
            "Ground your answers in the knowledge sources available to you. "
            "If the answer isn't in them, say so rather than guessing."
        )
    if blueprint.dataClassification in {"HR-Sensitive", "Financial", "Security-Restricted"}:
        lines.append(
            f"This agent handles {blueprint.dataClassification} data. Do not disclose it "
            "to anyone outside the approved audience, and do not repeat it back in full "
            "unless the requester is clearly entitled to see it."
        )
    return "\n\n".join(lines)


def _resolve_knowledge_tools(knowledge_source_ids: List[str]) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Group knowledge sources by Foundry tool type and merge their tool_resources."""
    tools: List[Dict[str, Any]] = []
    resources: Dict[str, Any] = {}

    file_search_vector_store_ids: List[str] = []
    ai_search_indexes: List[Dict[str, Any]] = []

    for ks_id in knowledge_source_ids:
        entry = KNOWLEDGE_CATALOG[ks_id]  # KeyError here = blueprint referenced an unapproved id; let it raise
        tool_type = entry["foundry_tool_type"]
        if tool_type == "file_search":
            file_search_vector_store_ids += entry["tool_resource"]["file_search"]["vector_store_ids"]
        elif tool_type == "azure_ai_search":
            ai_search_indexes += entry["tool_resource"]["azure_ai_search"]["indexes"]
        else:
            raise ValueError(f"Unhandled knowledge tool type '{tool_type}' for {ks_id}")

    if file_search_vector_store_ids:
        tools.append({"type": "file_search"})
        resources["file_search"] = {"vector_store_ids": file_search_vector_store_ids}
    if ai_search_indexes:
        tools.append({"type": "azure_ai_search"})
        resources["azure_ai_search"] = {"indexes": ai_search_indexes}

    return tools, resources


def to_foundry_agent_payload(blueprint: AgentBlueprint) -> Dict[str, Any]:
    tools: List[Dict[str, Any]] = []
    tool_resources: Dict[str, Any] = {}

    # Action tools pass through from the catalog as-is (already Foundry-shaped)
    for tool_id in blueprint.tools:
        entry = TOOL_CATALOG[tool_id]
        tools.append(entry["foundry_tool"])

    # Knowledge sources resolve + merge into file_search / azure_ai_search tools
    if blueprint.knowledgeSources:
        k_tools, k_resources = _resolve_knowledge_tools(blueprint.knowledgeSources)
        tools += k_tools
        tool_resources.update(k_resources)

    payload = {
        "name": blueprint.name,
        "model": MODEL_POLICIES[blueprint.modelPolicy],
        "instructions": _render_instructions(blueprint),
        "tools": tools,                 # [] is valid — e.g. a pure Q&A agent with no file_search either
        "tool_resources": tool_resources,  # {} is valid when tools is []
        "metadata": {
            "aaf_department": blueprint.department,
            "aaf_agent_type": blueprint.agentType,
            "aaf_pattern": blueprint.pattern,
            "aaf_owner": blueprint.owner,
            "aaf_data_classification": blueprint.dataClassification,
            "aaf_human_approval_required": str(blueprint.humanApproval),
            "aaf_external_sharing": str(blueprint.externalSharing),
            "aaf_audience": ",".join(blueprint.audience),
            "aaf_review_period_days": str(blueprint.reviewPeriodDays),
            "aaf_blueprint_version": blueprint.blueprintVersion,
        },
    }
    return payload
