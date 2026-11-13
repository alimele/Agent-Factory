"""
Pydantic model for a persisted Agent record.

This is the piece that was missing before: every stage of the authoring
flow (Describe/Start, Configure, Review/Launch) previously lived only in
the browser's React state (BlueprintContext), so a reload — or just
closing the tab — silently threw the agent away with no way back. An
AgentRecord is the durable, Cosmos-backed version of that same state, keyed
by owner so "My Agents" and "Playground" can list and resume it.

Deliberately NOT a second source of truth for governance: `blueprint` and
`foundryPayload` here are just a cached copy of what /blueprint/compile
already returned after re-validating against the live catalogs. Nothing
reads governance decisions back out of this record — compile and
create-test-agent always re-validate from the real catalogs and policy
engine, exactly as before. This store only answers "what was I building"
and "what did I already create", never "was it allowed".
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    DRAFT = "draft"              # core draft exists; still being configured
    COMPILED = "compiled"        # blueprint compiled + policy-checked
    DEV_CREATED = "dev_created"  # a Foundry dev/test agent version exists
    PUBLISHED = "published"      # reserved for when publish/approval ships
    ARCHIVED = "archived"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    owner: str  # set from the authenticated requester's email; never trust a client-supplied value
    status: AgentStatus = AgentStatus.DRAFT

    # Stage 1 output (CoreBlueprintDraft), echoed back by the client and
    # re-validated server-side again at compile/create-test-agent time.
    coreDraft: dict[str, Any]

    # Stage 2 manual picks
    knowledgeSourceIds: list[str] = Field(default_factory=list)
    toolIds: list[str] = Field(default_factory=list)
    audienceIds: list[str] = Field(default_factory=list)
    behavior: dict[str, Any] = Field(default_factory=dict)

    # Cached Stage 3 outputs — set once /blueprint/compile and
    # /blueprint/create-test-agent have actually been called and succeeded.
    blueprint: Optional[dict[str, Any]] = None
    foundryPayload: Optional[dict[str, Any]] = None
    policyEvaluation: Optional[dict[str, Any]] = None
    foundryAgentName: Optional[str] = None
    foundryAgentVersion: Optional[str] = None

    templateId: Optional[str] = None

    createdAt: str = Field(default_factory=_now)
    updatedAt: str = Field(default_factory=_now)

    class Config:
        extra = "forbid"
