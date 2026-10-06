"""
Place this file at the ROOT of your Functions project (same level as
host.json/requirements.txt) — Python v2 Functions looks for function_app.py
there by default. Your existing modules stay where they are, at
api/blueprint/*.py; this file just imports them.

If you used the older function.json-based model in Phase 0 instead of the
v2 decorator model, say so and I'll restructure this into that shape
instead — the three handlers' bodies stay the same either way.

Routes:
  POST /api/blueprint/core                -> Stage 1 (Describe page)
  GET  /api/blueprint/catalog/{department} -> Stage 2 (Knowledge/Actions pages)
  POST /api/blueprint/compile              -> Stage 3 (Review page)
"""

import json
import logging

import azure.functions as func
from pydantic import ValidationError

from api.blueprint.blueprint_generator import generate_core_blueprint, build_core_draft_model
from api.blueprint.blueprint_compiler import compile_blueprint, CatalogValidationError
from api.blueprint.foundry_payload import to_foundry_agent_payload
from api.blueprint.catalog_mvp import (
    mvp_catalog_snapshot,
    knowledge_sources_for_department,
    tools_for_department,
    DEPARTMENTS,
    AUDIENCES,
)
from api.blueprint.auth import get_requester, UnauthenticatedError

app = func.FunctionApp()


def _json_response(body: dict, status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(json.dumps(body), status_code=status_code, mimetype="application/json")


def _error_response(message: str, status_code: int) -> func.HttpResponse:
    return _json_response({"error": message}, status_code)


# ---------------------------------------------------------------------------
# Stage 1 — Describe page
# ---------------------------------------------------------------------------
@app.route(route="blueprint/core", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def blueprint_core(req: func.HttpRequest) -> func.HttpResponse:
    """
    Body: { "description": "<the user's plain-language text>" }
    Returns the Stage 1 CoreBlueprintDraft fields only — no knowledge/tool/
    audience fields exist on this response at all.
    """
    try:
        requester = get_requester(req)
    except UnauthenticatedError as e:
        return _error_response(str(e), 401)

    try:
        body = req.get_json()
    except ValueError:
        return _error_response("Request body must be JSON", 400)

    description = (body or {}).get("description", "").strip()
    if not description:
        return _error_response("'description' is required", 400)

    catalog = mvp_catalog_snapshot()  # TODO Phase 3: filter by requester's Entra groups/department

    try:
        core_draft = generate_core_blueprint(description, catalog)
    except Exception as e:
        logging.exception("Stage 1 generation failed")
        return _error_response(f"Blueprint generation failed: {e}", 502)

    result = core_draft.model_dump()
    result["requestedBy"] = requester.email  # echoed for the frontend to carry through, not trusted at compile time
    return _json_response(result)


# ---------------------------------------------------------------------------
# Stage 2 — Knowledge / Actions pages
# ---------------------------------------------------------------------------
@app.route(route="blueprint/catalog/{department}", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def blueprint_catalog(req: func.HttpRequest) -> func.HttpResponse:
    """
    Returns the knowledge sources and tools approved for the given
    department, for the Knowledge/Actions pages to render as pickable
    options. No model call — a pure catalog lookup.
    """
    try:
        get_requester(req)  # still gated; result not otherwise used here
    except UnauthenticatedError as e:
        return _error_response(str(e), 401)

    department = req.route_params.get("department")
    if department not in DEPARTMENTS:
        return _error_response(f"Unknown department '{department}'", 404)

    knowledge = knowledge_sources_for_department(department)
    tools = tools_for_department(department)

    # Only hand the frontend what it needs to render a picker — not the
    # internal Foundry-shape fragments (tool_resource/foundry_tool), which
    # stay server-side until compile time.
    return _json_response({
        "department": department,
        "knowledgeSources": [
            {"id": k, "displayName": v["display_name"]} for k, v in knowledge.items()
        ],
        "tools": [
            {"id": k, "displayName": v["display_name"], "risk": v.get("risk")} for k, v in tools.items()
        ],
        # Not yet department-filtered (MVP: audiences aren't tagged to a
        # department in catalog_mvp.py) — every requester sees the full
        # audience list. Worth revisiting in Phase 3 alongside real
        # permission-aware filtering.
        "audiences": [{"id": k} for k in AUDIENCES.keys()],
    })


# ---------------------------------------------------------------------------
# Stage 3 — Review page
# ---------------------------------------------------------------------------
@app.route(route="blueprint/compile", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def blueprint_compile(req: func.HttpRequest) -> func.HttpResponse:
    """
    Body:
    {
      "coreDraft": { ...the Stage 1 response fields, echoed back... },
      "knowledgeSourceIds": ["..."],
      "toolIds": ["..."],
      "audienceIds": ["..."],
      "channels": ["Teams"]            # optional
    }

    No model call. Re-validates coreDraft against the catalog (don't trust
    whatever the client echoes back between pages) and validates every
    picked id, then returns both the governance blueprint and the
    Foundry-ready agent-creation payload.
    """
    try:
        requester = get_requester(req)
    except UnauthenticatedError as e:
        return _error_response(str(e), 401)

    try:
        body = req.get_json()
    except ValueError:
        return _error_response("Request body must be JSON", 400)

    body = body or {}
    core_draft_raw = body.get("coreDraft")
    if not core_draft_raw:
        return _error_response("'coreDraft' is required", 400)

    catalog = mvp_catalog_snapshot()
    CoreDraftModel = build_core_draft_model(catalog)

    # Re-validate the core fields server-side — this is what stops a client
    # that tampered with department/modelPolicy/etc. between the Describe
    # and Review pages from ever reaching compile_blueprint.
    try:
        core_draft = CoreDraftModel(**core_draft_raw)
    except ValidationError as e:
        return _error_response(f"coreDraft failed validation: {e}", 400)

    try:
        blueprint = compile_blueprint(
            core_draft=core_draft,
            knowledge_source_ids=body.get("knowledgeSourceIds", []),
            tool_ids=body.get("toolIds", []),
            audience_ids=body.get("audienceIds", []),
            requester_email=requester.email,
            channels=body.get("channels"),
        )
    except CatalogValidationError as e:
        return _error_response(str(e), 400)

    foundry_payload = to_foundry_agent_payload(blueprint)

    return _json_response({
        "blueprint": blueprint.model_dump(),
        "foundryPayload": foundry_payload,
    })
