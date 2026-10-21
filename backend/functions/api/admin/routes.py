"""
Admin-only HTTP surface for managing the knowledge-source catalog.

This is deliberately separate from anything a regular department user can
reach. Registering a knowledge source provisions a Foundry project
connection (api/blueprint/connection_manager.py) — the identity that does
this needs the Foundry Project Manager role on the project's parent
resource, which is a materially bigger permission than "can create agents
for my own department". Gate accordingly: being approved for a department
in GROUP_DEPARTMENT_MAP says nothing about being trusted to manage the
catalog and the Foundry connections behind it.
"""
import json
import logging

import azure.functions as func
from pydantic import BaseModel, Field, ValidationError

from api.blueprint import connection_manager
from api.blueprint.catalog_mvp import DEPARTMENTS
from api.blueprint.knowledge_registry import (
    audit_connection_assignments,
    register_knowledge_source,
)
from api.policy.identity import TokenError, build_context, is_admin

logger = logging.getLogger(__name__)

bp = func.Blueprint()


class RegisterKnowledgeSourceRequest(BaseModel):
    sourceId: str = Field(min_length=1, max_length=100)
    displayName: str = Field(min_length=1, max_length=200)
    departments: list[str] = Field(min_length=1)
    dataClassification: str
    searchServiceEndpoint: str = Field(min_length=1)
    knowledgeBaseName: str = Field(min_length=1)
    agentFactoryReady: bool = True

    class Config:
        extra = "forbid"


def _json_response(body: dict, status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(json.dumps(body), status_code=status_code, mimetype="application/json")


def _error_response(message: str, status_code: int) -> func.HttpResponse:
    return _json_response({"error": message}, status_code)


def _require_admin(req: func.HttpRequest):
    """Returns the built EvalContext, or raises by returning an HttpResponse-shaped error.
    Callers check `isinstance(result, func.HttpResponse)`."""
    try:
        context = build_context(req)
    except TokenError as exc:
        return _error_response(str(exc), 401)
    if not is_admin(context.requester_groups):
        return _error_response(
            "This operation requires catalog-admin access. Contact your platform administrator.",
            403,
        )
    return context


@bp.route(route="admin/knowledge-sources", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def register_knowledge_source_route(req: func.HttpRequest) -> func.HttpResponse:
    """
    Body: see RegisterKnowledgeSourceRequest. Creates or updates a
    knowledge-source catalog entry AND the Foundry project connection
    behind it, atomically from the caller's point of view — the connection
    is provisioned first, and only on success is the App Configuration
    entry written (knowledge_registry.register_knowledge_source). There is
    no field for projectConnectionName: it is always derived from
    sourceId, so it can never be mistyped or copy-pasted from an unrelated
    entry.
    """
    guard = _require_admin(req)
    if isinstance(guard, func.HttpResponse):
        return guard

    try:
        body = req.get_json()
    except ValueError:
        return _error_response("Request body must be JSON", 400)

    try:
        payload = RegisterKnowledgeSourceRequest(**(body or {}))
    except ValidationError as exc:
        return _error_response(f"Request failed validation: {exc}", 400)

    unknown_departments = [d for d in payload.departments if d not in DEPARTMENTS]
    if unknown_departments:
        return _error_response(f"Unknown department(s): {unknown_departments}", 400)

    try:
        result = register_knowledge_source(
            source_id=payload.sourceId,
            display_name=payload.displayName,
            departments=payload.departments,
            data_classification=payload.dataClassification,
            search_service_endpoint=payload.searchServiceEndpoint,
            knowledge_base_name=payload.knowledgeBaseName,
            agent_factory_ready=payload.agentFactoryReady,
        )
    except connection_manager.ConnectionPermissionError as exc:
        return _error_response(
            f"Could not provision the Foundry project connection: {exc}", 403
        )
    except connection_manager.ConnectionProvisioningError as exc:
        logger.exception("Connection provisioning failed for source_id=%s", payload.sourceId)
        return _error_response(f"Could not provision the Foundry project connection: {exc}", 502)
    except ValueError as exc:
        return _error_response(str(exc), 400)

    return _json_response(result, 201)


@bp.route(route="admin/knowledge-sources/audit", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def audit_knowledge_sources_route(req: func.HttpRequest) -> func.HttpResponse:
    """
    Cross-checks every registered knowledge source against the live Foundry
    connections and flags anything that looks like the Alpha Bank /
    knowledgebase107 bug class: a shared connection across two different
    knowledge bases, a connection whose live target doesn't match what the
    registry entry expects, or a missing/unreadable connection.
    """
    guard = _require_admin(req)
    if isinstance(guard, func.HttpResponse):
        return guard

    try:
        findings = audit_connection_assignments()
    except connection_manager.ConnectionPermissionError as exc:
        return _error_response(f"Could not read Foundry connections: {exc}", 403)
    except connection_manager.ConnectionProvisioningError as exc:
        logger.exception("Audit failed")
        return _error_response(f"Could not read Foundry connections: {exc}", 502)

    return _json_response({"findings": findings, "clean": len(findings) == 0})
