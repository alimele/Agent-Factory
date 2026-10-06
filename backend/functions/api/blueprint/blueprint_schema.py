"""
AAF Agent Blueprint — the governance-rich object the NLP layer produces.

Design rule (ties to the Governance Gate in the project plan, section 6):
the NLP model NEVER emits a raw Foundry tool/connector definition. It only
ever picks catalog IDs (strings) from the approved catalog it was shown.
The *catalog* — not the model — holds the actual Foundry-shape fragments
(tool type, tool_resources, OpenAPI spec refs, connection ids). Resolution
from blueprint -> real Foundry payload happens in foundry_payload.py,
deterministically, in code. This is what makes "cannot invent connectors
or permissions" (plan section 5) actually true rather than aspirational.

knowledgeSources and tools are both optional and independently so:
- a pure Knowledge Assistant may have knowledgeSources but tools=[]
- a pure Process/Action agent may have tools but knowledgeSources=[]
- a template/boilerplate agent could technically have neither, though the
  Review page should flag that as unusual rather than block it.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class AgentBlueprint(BaseModel):
    """
    Mirrors the example in Project-Plan.docx section 5, with:
    - knowledgeSources / tools made explicitly optional (default [])
    - a few fields split into (NLP-generated) vs (server-set) — see
      blueprint_generator.py for which half of this the model actually fills in.
    """

    # --- Stage 1: LLM-generated from the Describe-page text (blueprint_generator.py).
    # Constrained to the catalog, but the catalog slice it sees here is ONLY
    # departments/agentTypes/patterns/modelPolicies/dataClassifications —
    # it is never shown knowledge/tool/audience catalogs, so it cannot guess them.
    name: str = Field(..., description="Short human-readable agent name")
    department: str
    agentType: str = Field(
        ..., description="Knowledge Assistant | Analyst | Process Agent | Action Agent | Monitoring Agent"
    )
    pattern: str = Field(
        ..., description="knowledge_only | knowledge_action | process | monitoring"
    )
    purpose: str = Field(..., description="1-3 sentence plain-language purpose, shown on the Review page")
    modelPolicy: str
    dataClassification: str
    humanApproval: bool
    externalSharing: bool = False

    # --- Stage 2: manual catalog selection on the Knowledge/Actions/Audience
    # pages (blueprint_compiler.py). No model involved — the user picks these
    # from catalog entries pre-filtered by `department` above.
    knowledgeSources: List[str] = Field(
        default_factory=list,
        description="Approved knowledge-catalog IDs. Empty if the agent needs no grounding.",
    )
    tools: List[str] = Field(
        default_factory=list,
        description="Approved tool-catalog IDs. Empty if the agent takes no actions.",
    )
    audience: List[str] = Field(..., description="Entra groups / named audiences, from the approved audience catalog")
    channels: List[str] = Field(default_factory=lambda: ["Teams"])

    # --- Stage 3: server-set, never produced by the model or the user form ---
    owner: Optional[str] = None          # filled from the Entra token of the requester
    reviewPeriodDays: int = 180          # default; business-sponsor can override on Submit
    riskClass: Optional[str] = None      # computed by the Phase 3 policy engine, not here
    blueprintVersion: str = "1.0"

    class Config:
        extra = "forbid"  # a blueprint with an unexpected field fails closed, not open


class CatalogSnapshot(BaseModel):
    """
    The subset of the approved catalogs a given requester is entitled to see,
    passed into build_constrained_model() to generate a per-request Pydantic
    model whose Literal fields can ONLY contain values from this snapshot.

    For Phase 2 (MVP), this can be the full static catalog. Audience/permission
    -aware filtering of *which* catalog entries a given user sees is a Phase 3
    concern (Knowledge/Actions pages are already permission-aware per the UX
    design — Phase 2 just needs to accept a pre-filtered snapshot, not build
    the filtering itself).
    """

    departments: List[str]
    agent_types: List[str]
    patterns: List[str]
    model_policies: List[str]
    knowledge_source_ids: List[str]
    tool_ids: List[str]
    audience_ids: List[str]
    data_classifications: List[str]
    channels: List[str]
