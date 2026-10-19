"""
MVP catalogs — 5-10 tools, a handful of knowledge sources, matching the
"5-8 agent templates / 5-10 tools" MVP scope in the project plan (section 9).
"""

import json
import os

from api.blueprint.blueprint_schema import CatalogSnapshot
from api.blueprint.api_center_catalog import tools_for_department
from api.blueprint.knowledge_registry import knowledge_sources_for_department  # re-export

DEPARTMENTS = ["HR", "Finance", "DevSecOps", "IT Support", "Admin", "Sales"]

AGENT_TYPES = [
    "Knowledge Assistant", "Analyst", "Process Agent", "Action Agent", "Monitoring Agent",
]

PATTERNS = ["knowledge_only", "knowledge_action", "process", "monitoring"]

# Agent types that must never carry a write-capable tool. Enforced by
# api/policy/rules.py::check_agent_type() and reflected in the instructions
# sent to the real Foundry agent (api/blueprint/instructions.py), so both the
# policy gate and the model's own behavior agree on what these types may do.
READ_ONLY_AGENT_TYPES = {"Knowledge Assistant", "Monitoring Agent"}

MODEL_POLICIES = {
    # internal policy name -> your Azure OpenAI DEPLOYMENT name in Foundry
    # (not a bare model id — Azure OpenAI routes by deployment name, and
    # you choose that name yourself when you deploy in the portal). These
    # are placeholders: confirm what you actually deploy and rename to match.
    "approved-general-enterprise": "gpt-5",
    "approved-high-accuracy": "gpt-5.2",
    "approved-fast-lowcost": "gpt-5-mini",
}

DATA_CLASSIFICATIONS = [
    "Public", "Internal", "Confidential", "HR-Sensitive", "Financial", "Security-Restricted",
]

CHANNELS = ["Teams", "M365Copilot"]


def _build_audiences(group_department_map: dict[str, str]) -> dict[str, dict[str, str]]:
    audiences = {}
    for group_id, department in group_department_map.items():
        if department not in DEPARTMENTS:
            continue

        audience_id = f"{department.replace(' ', '-')}-Team"
        if audience_id in audiences:
            raise ValueError(f"Multiple Entra groups configured for audience '{audience_id}'")
        audiences[audience_id] = {"entra_group_id": group_id}
    return audiences


AUDIENCES = _build_audiences(json.loads(os.environ.get("GROUP_DEPARTMENT_MAP", "{}")))

def mvp_catalog_snapshot(departments: list[str] | None = None) -> CatalogSnapshot:
    """
    departments: restrict the Stage 1 (Describe page) LLM to this subset
    instead of the full DEPARTMENTS list — used to constrain a requester to
    their own department (function_app.py::blueprint_core()) now that the
    Knowledge/Actions catalog endpoint is department-gated, so Stage 1 can
    no longer hand back a department the requester isn't allowed to browse.
    """
    return CatalogSnapshot(
        departments=departments if departments else DEPARTMENTS,
        agent_types=AGENT_TYPES,
        patterns=PATTERNS,
        model_policies=list(MODEL_POLICIES.keys()),
        knowledge_source_ids=[],
        tool_ids=[],
        audience_ids=list(AUDIENCES.keys()),
        data_classifications=DATA_CLASSIFICATIONS,
        channels=CHANNELS,
    )
