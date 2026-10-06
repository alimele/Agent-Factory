"""
Stage 3 of 3 — Review page.

No model call here at all — by the time the user reaches Review, every
field already has a value (Stage 1 generated the core fields, Stage 2 was
the user manually picking from catalog pages). This module's only job is to
assemble those into the final AgentBlueprint and reject anything that
doesn't check out against the real catalog — this is the important part,
since knowledgeSources/tools/audience are no longer constrained by a
schema the model was forced into; they came from a web form, so they get
validated here instead, server-side, before anything is trusted.
"""

from __future__ import annotations

from typing import List
from pydantic import BaseModel

from blueprint_schema import AgentBlueprint
from catalog_mvp import KNOWLEDGE_CATALOG, TOOL_CATALOG, AUDIENCES


class CatalogValidationError(ValueError):
    """Raised when a Stage 2 selection references an id that isn't (or is no
    longer) in the approved catalog — e.g. a stale page, tampered request,
    or a catalog entry that was deprecated between page-load and submit."""


def _validate_ids(ids: List[str], catalog: dict, label: str) -> None:
    unknown = [i for i in ids if i not in catalog]
    if unknown:
        raise CatalogValidationError(f"Unapproved {label} id(s): {unknown}")


def compile_blueprint(
    core_draft: BaseModel,
    knowledge_source_ids: List[str],
    tool_ids: List[str],
    audience_ids: List[str],
    requester_email: str,
    channels: List[str] | None = None,
    review_period_days: int = 180,
) -> AgentBlueprint:
    _validate_ids(knowledge_source_ids, KNOWLEDGE_CATALOG, "knowledge source")
    _validate_ids(tool_ids, TOOL_CATALOG, "tool")
    _validate_ids(audience_ids, AUDIENCES, "audience")

    return AgentBlueprint(
        **core_draft.model_dump(),
        knowledgeSources=knowledge_source_ids,
        tools=tool_ids,
        audience=audience_ids,
        channels=channels or ["Teams"],
        owner=requester_email,
        reviewPeriodDays=review_period_days,
    )
