"""
CREDO Agent Blueprint — the governance-rich object the NLP layer produces.
"""

from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class ToolOperationSelection(BaseModel):
    """
    One MCP server (an approved tool-catalog entry / API Center asset) plus
    the individual operations the requester selected on it, e.g.
    {"serverId": "github", "operations": ["create_issue", "list_issues"]}.

    Replaces the old flat `tools: List[str]` (whole-integration selection).
    `operations` is always a *subset* of what mcp_client.discover_tools()
    actually returned for this server, re-validated server-side in
    blueprint_compiler.compile_blueprint() — never trust what the client
    echoes back. An empty `operations` list is rejected at compile time
    (a server with nothing selected on it shouldn't be in `tools` at all).
    """

    serverId: str = Field(..., description="Tool-catalog id (API Center asset name) of the MCP server")
    operations: List[str] = Field(
        ..., min_length=1, description="MCP operation names selected on this server, from live tools/list discovery"
    )

    class Config:
        extra = "forbid"


class AgentBlueprint(BaseModel):
    """
    Mirrors the example in Project-Plan.docx section 5, with:
    - knowledgeSources / tools made explicitly optional (default [])
    - a few fields split into (NLP-generated) vs (server-set) — see
      blueprint_generator.py for which half of this the model actually fills in.
    - tools is a list of ToolOperationSelection (per-server, per-operation),
      not a flat list of tool-catalog ids — see that model's docstring.
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
    tools: List[ToolOperationSelection] = Field(
        default_factory=list,
        description="Approved tool-catalog servers with the individual operations selected on each. Empty if the agent takes no actions.",
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


class BehaviorOptions(BaseModel):
    """
    Bounded, user-configured behavior preferences from the Behavior page.

    Lives here (not in foundry_service.py) because both the real agent
    creation path (foundry_service.py) and the Review-page preview path
    (foundry_payload.py) need it — via the shared instructions.py builder —
    and putting it in either of those would create a circular import.
    """
    instructions: str = Field(default="", max_length=4000)
    responseStyle: Literal["Concise", "Balanced", "Detailed"] = "Balanced"
    citeSources: bool = True
    askClarifyingQuestions: bool = True
    escalateUncertainty: bool = True

    class Config:
        extra = "forbid"


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
