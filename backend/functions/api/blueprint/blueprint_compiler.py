"""
Blueprint compiler
"""

from __future__ import annotations

from typing import List
from pydantic import BaseModel

from api.blueprint.blueprint_schema import AgentBlueprint
from api.blueprint.catalog_mvp import KNOWLEDGE_CATALOG, AUDIENCES
from api.blueprint.api_center_catalog import tools_for_department


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
    _validate_ids(tool_ids, tools_for_department(core_draft.department), "tool")
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
