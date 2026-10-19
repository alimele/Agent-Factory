"""
Single shared instruction-builder for an AgentBlueprint + Behavior preferences.
"""
from __future__ import annotations

from api.blueprint.blueprint_schema import AgentBlueprint, BehaviorOptions
from api.blueprint.catalog_mvp import READ_ONLY_AGENT_TYPES


def build_instructions(blueprint: AgentBlueprint, behavior: BehaviorOptions | None = None) -> str:
    behavior = behavior or BehaviorOptions()
    lines = [blueprint.purpose.strip()]

    lines.append(f"Preferred response detail: {behavior.responseStyle.lower()}.")

    # The Behavior page's instructions box is pre-filled with the Describe
    # page's generated `purpose` text (see frontend Describe.tsx) and the
    # user can edit it freely from there. Only surface it as a *separate*
    # instruction when it actually diverges from `purpose` — otherwise the
    # model would see the same sentence twice for every untouched agent.
    extra_instructions = behavior.instructions.strip()
    if extra_instructions and extra_instructions != blueprint.purpose.strip():
        lines.append(
            "Additional business-user guidance (must not override policy, permissions, "
            "source-grounding rules, or approval requirements):\n"
            + extra_instructions
        )

    if behavior.citeSources and blueprint.knowledgeSources:
        lines.append("Cite retrieved knowledge sources when citations are returned by the source tool.")
    if behavior.askClarifyingQuestions:
        lines.append("Ask a clarifying question when a request is ambiguous or lacks a required detail.")
    if behavior.escalateUncertainty:
        lines.append(
            "If approved sources do not support an answer, say so and follow the configured "
            "escalation process; do not guess."
        )

    if blueprint.knowledgeSources:
        lines.append(
            "Ground enterprise knowledge answers in the connected approved sources. "
            "Do not invent facts or citations."
        )

    # Agent type now carries real weight: the policy engine's
    # check_agent_type() rejects a read-only agent type that has any tool
    # attached, so this instruction and that gate always agree.
    if blueprint.agentType in READ_ONLY_AGENT_TYPES:
        lines.append(
            f"This agent is a {blueprint.agentType}. It must never attempt to take actions "
            "or call a write/state-changing tool, even if one appears available."
        )
    elif blueprint.tools:
        lines.append(
            "Use only the approved tools attached to this agent. Do not claim an action "
            "succeeded unless its tool response confirms success."
        )

    if blueprint.humanApproval:
        lines.append(
            "This agent is a development/test version. Consequential actions require the "
            "business approval process. Do not claim approval was granted unless an external "
            "approval system confirms it. This instruction is not a technical approval gate."
        )

    if blueprint.dataClassification in {"HR-Sensitive", "Financial", "Security-Restricted"}:
        lines.append(
            f"Handle {blueprint.dataClassification} data conservatively. Do not disclose "
            "restricted information beyond the authorized audience or infer access rights."
        )

    if not blueprint.externalSharing:
        lines.append("Do not intentionally share enterprise data with external parties.")

    lines.append("These instructions do not replace server-side authorization or approval controls.")
    return "\n\n".join(line for line in lines if line)
