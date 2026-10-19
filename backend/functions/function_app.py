"""
This is the Azure Functions entrypoint for the Blueprint API.
"""

import json
import logging

import azure.functions as func
from pydantic import ValidationError

from api.blueprint.blueprint_generator import generate_core_blueprint, build_core_draft_model
from api.blueprint.blueprint_compiler import compile_blueprint, CatalogValidationError
from api.blueprint.blueprint_schema import BehaviorOptions
from api.blueprint.foundry_payload import to_foundry_agent_payload
from api.blueprint.foundry_service import TestAgentRequest, create_test_agent, run_test_query
from api.policy.engine import evaluate
from api.policy.identity import build_context, TokenError
from api.policy.models import Stage
from api.blueprint.catalog_mvp import (
    mvp_catalog_snapshot,
    knowledge_sources_for_department,
    tools_for_department,
    DEPARTMENTS,
    AUDIENCES,
)
from api.blueprint.auth import get_requester, UnauthenticatedError
from api.policy.routes import bp as policy_bp

app = func.FunctionApp()

app.register_functions(policy_bp)

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

    # Constrain Stage 1 to the requester's own department (via their Entra
    # groups / GROUP_DEPARTMENT_MAP) so it can never hand back a department
    # the requester isn't allowed to browse the Knowledge/Actions catalog
    # for. Best-effort: if department mapping fails for any reason, fall
    # back to the unconstrained list rather than blocking Describe outright
    # — get_requester() above already gated this endpoint on real auth.
    try:
        requester_department = build_context(req).requester_department
    except TokenError:
        requester_department = None
    catalog = mvp_catalog_snapshot([requester_department] if requester_department else None)

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

    Gated to the requester's own department: build_context() reads their
    Entra groups via GROUP_DEPARTMENT_MAP (api/policy/identity.py), the
    same mapping the PRE_DEPLOY policy gate's check_department() already
    relies on. Browsing another department's catalog is a 403, not just a
    policy flag caught later at Submit — previously any authenticated user
    could GET any department's knowledge/tool catalog.
    """
    try:
        context = build_context(req)
    except TokenError as e:
        return _error_response(str(e), 401)

    department = req.route_params.get("department")
    if department not in DEPARTMENTS:
        return _error_response(f"Unknown department '{department}'", 404)

    if context.requester_department != department:
        return _error_response(
            f"You are not authorized to view the '{department}' catalog.", 403
        )

    knowledge = knowledge_sources_for_department(department)
    tools = tools_for_department(department)

    # One audience per department, named "<Department>-Team" and carrying
    # its real Entra group id (catalog_mvp.py::_build_audiences(), driven by
    # GROUP_DEPARTMENT_MAP) — only expose this department's own entry.
    own_audience_id = f"{department.replace(' ', '-')}-Team"

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
        "audiences": [{"id": k} for k in AUDIENCES.keys() if k == own_audience_id],
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
      "channels": ["Teams"],           # optional
      "behavior": { ... }              # optional — Behavior page's BehaviorOptions shape
    }

    No model call. Re-validates coreDraft against the catalog (don't trust
    whatever the client echoes back between pages) and validates every
    picked id, then returns both the governance blueprint and the
    Foundry-ready agent-creation payload. `behavior` is included so the
    returned foundryPayload.instructions is the *same* text
    /blueprint/create-test-agent would actually send to Foundry, not a
    simplified stand-in — see api/blueprint/instructions.py.
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

    behavior_raw = body.get("behavior") or {}
    if not isinstance(behavior_raw, dict):
        return _error_response("'behavior' must be a JSON object", 400)
    try:
        behavior = BehaviorOptions(**behavior_raw)
    except ValidationError as e:
        return _error_response(f"'behavior' failed validation: {e}", 400)

    foundry_payload = to_foundry_agent_payload(blueprint, behavior)

    return _json_response({
        "blueprint": blueprint.model_dump(),
        "foundryPayload": foundry_payload,
    })

# ---------------------------------------------------------------------------
# Phase 4 — Create a real, unpublished Foundry development/test agent
# ---------------------------------------------------------------------------
def _validated_blueprint_for_foundry(body: dict, requester_email: str):
    """Rebuild the blueprint from catalog IDs; never trust a frontend payload."""
    core_draft_raw = body.get("coreDraft")
    if not isinstance(core_draft_raw, dict):
        raise ValueError("'coreDraft' is required and must be an object")

    catalog = mvp_catalog_snapshot()
    CoreDraftModel = build_core_draft_model(catalog)
    try:
        core_draft = CoreDraftModel(**core_draft_raw)
    except ValidationError as exc:
        raise ValueError(f"coreDraft failed validation: {exc}") from exc

    try:
        return compile_blueprint(
            core_draft=core_draft,
            knowledge_source_ids=body.get("knowledgeSourceIds", []),
            tool_ids=body.get("toolIds", []),
            audience_ids=body.get("audienceIds", []),
            requester_email=requester_email,
            channels=body.get("channels"),
        )
    except CatalogValidationError as exc:
        raise ValueError(str(exc)) from exc


@app.route(route="blueprint/create-test-agent", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def blueprint_create_test_agent(req: func.HttpRequest) -> func.HttpResponse:
    """Revalidate selections and pre-deploy policy, then create an unpublished test version."""
    try:
        requester = get_requester(req)
    except UnauthenticatedError as exc:
        return _error_response(str(exc), 401)

    try:
        body = req.get_json()
    except ValueError:
        return _error_response("Request body must be JSON", 400)
    if not isinstance(body, dict):
        return _error_response("Request body must be a JSON object", 400)

    try:
        blueprint = _validated_blueprint_for_foundry(body, requester.email)
        behavior_raw = body.get("behavior") or {}
        if not isinstance(behavior_raw, dict):
            return _error_response("'behavior' must be a JSON object", 400)
        behavior = BehaviorOptions(**behavior_raw)
    except (ValueError, ValidationError) as exc:
        return _error_response(str(exc), 400)

    try:
        context = build_context(req)
    except TokenError as exc:
        return _error_response(str(exc), 401)

    try:
        policy_result = evaluate(blueprint.model_dump(), context, Stage.PRE_DEPLOY)
    except Exception as exc:
        logging.exception("Pre-deploy policy evaluation failed before Foundry creation")
        return _error_response("Pre-deploy policy evaluation failed; no Foundry agent was created", 502)

    policy_json = policy_result.model_dump(mode="json")
    if policy_result.overall_status.value == "fail":
        return _json_response({
            "error": "The pre-deploy policy gate blocked Foundry creation.",
            "policyEvaluation": policy_json,
        }, 403)

    try:
        agent = create_test_agent(blueprint, behavior)
    except Exception:
        logging.exception("Foundry development agent creation failed")
        return _error_response(
            "Foundry could not create the development agent. Check Function App logs, model deployment names, project permissions, and tool definitions.",
            502,
        )

    return _json_response({"agent": agent, "policyEvaluation": policy_json}, 201)


@app.route(route="blueprint/test-agent", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def blueprint_test_agent(req: func.HttpRequest) -> func.HttpResponse:
    """Run a prompt only against a development agent owned by the signed-in requester."""
    try:
        requester = get_requester(req)
    except UnauthenticatedError as exc:
        return _error_response(str(exc), 401)

    try:
        body = req.get_json()
    except ValueError:
        return _error_response("Request body must be JSON", 400)
    if not isinstance(body, dict):
        return _error_response("Request body must be a JSON object", 400)
    try:
        test_request = TestAgentRequest(**body)
    except ValidationError as exc:
        return _error_response(f"Test request failed validation: {exc}", 400)

    try:
        result = run_test_query(test_request, requester.email)
    except PermissionError as exc:
        return _error_response(str(exc), 403)
    except ValueError as exc:
        return _error_response(str(exc), 400)
    except Exception:
        logging.exception("Foundry test query failed")
        return _error_response("The Foundry test query failed. Check Function App logs and the agent's connected tools.", 502)
    return _json_response(result)
