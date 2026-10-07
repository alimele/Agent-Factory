"""
Thin wrapper the policy engine uses to re-validate a blueprint's
knowledge sources and tools against the approved, department-scoped
catalog, never trust what the frontend sent, only what's actually
in the catalog.

"""
from typing import Iterable

from api.blueprint.catalog_mvp import knowledge_sources_for_department, tools_for_department  # adjust to match your module


def approved_tool_ids(department: str) -> set[str]:
    return set(tools_for_department(department).keys())


def approved_knowledge_ids(department: str) -> set[str]:
    return set(knowledge_sources_for_department(department).keys())


def unapproved(selected, approved: set[str]) -> list[str]:
    return [item for item in selected if item not in approved]
