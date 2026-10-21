"""
Admin-only HTTP surface for managing the knowledge-source catalog.

This is deliberately separate from anything a regular department user can
reach. Registering a knowledge source provisions a Foundry project
connection
"""
import json
import logging

import azure.functions as func
from pydantic import BaseModel, Field, ValidationError

from api.blueprint import connection_manager
from api.blueprint.catalog_mvp import DEPARTMENTS
from api.blueprint.knowledge_registry import (
    audit_connection_assignments,
    list_all_knowledge_sources,
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
    """Returns the built EvalContext, or an HttpResponse error. Callers check
    `isinstance(result, func.HttpResponse)`."""
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


@bp.route(route="admin/me", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def admin_me_route(req: func.HttpRequest) -> func.HttpResponse:
    """
    Tells the frontend whether the signed-in user should see admin UI at
    all. Deliberately does NOT 403 a non-admin — it's a status check, not a
    gated operation; every other route in this file still enforces
    is_admin() independently, so this endpoint being permissive teaches a
    caller nothing they couldn't already infer by being signed in.
    """
    try:
        context = build_context(req)
    except TokenError as exc:
        return _error_response(str(exc), 401)
    return _json_response({"isAdmin": is_admin(context.requester_groups)})


@bp.route(route="admin/knowledge-sources", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def list_knowledge_sources_route(req: func.HttpRequest) -> func.HttpResponse:
    """
    The full catalog, unfiltered by department, for the admin UI's list
    view. Deliberately cheap — reads only App Configuration, no live ARM
    calls — so it's safe to load whenever the admin page opens. Connection
    health (whether each entry's connection actually matches) is a
    separate, explicit action: see audit_knowledge_sources_route.
    """
    guard = _require_admin(req)
    if isinstance(guard, func.HttpResponse):
        return guard

    sources = list_all_knowledge_sources()
    items = [
        {
            "sourceId": source_id,
            "displayName": item.get("displayName", source_id),
            "departments": item.get("department", []),
            "dataClassification": item.get("dataClassification", "Internal"),
            "searchServiceEndpoint": item.get("searchServiceEndpoint"),
            "knowledgeBaseName": item.get("knowledgeBaseName"),
            "connectionName": item.get("projectConnectionName"),
            "agentFactoryReady": item.get("agentFactoryReady", False),
        }
        for source_id, item in sorted(sources.items())
    ]
    return _json_response({"knowledgeSources": items})


@bp.route(route="admin/knowledge-sources", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def register_knowledge_source_route(req: func.HttpRequest) -> func.HttpResponse:
    """
    Body: see RegisterKnowledgeSourceRequest. Creates or updates a
    knowledge-source catalog entry AND the Foundry project connection
    behind it — the connection is provisioned first, and only on success is
    the App Configuration entry written. There is no field for
    projectConnectionName: it is always derived from sourceId.
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
    connections. Makes a live ARM call per entry, so this is an explicit,
    admin-triggered action in the UI rather than something loaded
    automatically — see list_knowledge_sources_route for the cheap list.
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
