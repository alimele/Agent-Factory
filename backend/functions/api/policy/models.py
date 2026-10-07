"""
Pydantic models for the Credo Agent Factory policy engine.
"""
from __future__ import annotations
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    FLAGGED = "flagged"
    SKIPPED = "skipped"  # not applicable at this stage


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    RESTRICTED = "restricted"


class Stage(str, Enum):
    PRE_DEPLOY = "pre_deploy"    # Submit step, gates creation of the Foundry dev/test agent
    PRE_PUBLISH = "pre_publish"  # after Test/red-team, before approval-for-publish


class CheckResult(BaseModel):
    id: str
    name: str
    status: CheckStatus
    reason: str = ""


class EvalContext(BaseModel):
    """Everything the engine needs that isn't inside the blueprint itself."""
    requester_id: str
    requester_department: Optional[str] = None
    requester_groups: list[str] = Field(default_factory=list)
    test_results: Optional[dict] = None  # only populated for PRE_PUBLISH


class PolicyEvaluation(BaseModel):
    blueprint_id: Optional[str] = None
    stage: Stage
    overall_status: CheckStatus       # PASS / FAIL / FLAGGED, rolled up
    risk_tier: RiskTier
    required_approvers: list[str]
    checks: list[CheckResult]
