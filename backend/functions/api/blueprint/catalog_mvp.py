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

def mvp_catalog_snapshot() -> CatalogSnapshot:
    return CatalogSnapshot(
        departments=DEPARTMENTS,
        agent_types=AGENT_TYPES,
        patterns=PATTERNS,
        model_policies=list(MODEL_POLICIES.keys()),
        knowledge_source_ids=[],
        tool_ids=[],
        audience_ids=list(AUDIENCES.keys()),
        data_classifications=DATA_CLASSIFICATIONS,
        channels=CHANNELS,
    )
