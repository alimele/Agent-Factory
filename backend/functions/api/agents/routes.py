"""
HTTP surface for the Agent record store.

Used by:
- Start: save a draft the moment a core blueprint draft exists (template or
  description-generated), so it survives a reload immediately.
- Configure: autosave selections as the user picks knowledge/tools/behavior.
- Review & Launch: save the compiled blueprint + policy result + created
  Foundry agent name/version once each step succeeds.
- My Agents: list everything the signed-in user owns.
- Playground: list the owner's dev_created/published agents to chat with.

Ownership is always taken from the authenticated requester (get_requester),
never from the request body — this is a convenience/continuity layer, not
a governance boundary. Nothing here grants access to knowledge, tools, or
Foundry creation that /blueprint/compile and /blueprint/create-test-agent
wouldn't independently re-validate anyway.
"""
import json
import logging
from datetime import datetime, timezone

import azure.functions as func
from pydantic import ValidationError

from api.agents import store
from api.agents.models import AgentRecord, AgentStatus
from api.blueprint.auth import get_requester, UnauthenticatedError

bp = func.Blueprint()


def _json(body, status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(json.dumps(body), status_code=status_code, mimetype="application/json")


def _error(message: str, status_code: int) -> func.HttpResponse:
    return _json({"error": message}, status_code)


@bp.route(route="agents", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def list_agents(req: func.HttpRequest) -> func.HttpResponse:
    try:
        requester = get_requester(req)
    except UnauthenticatedError as e:
        return _error(str(e), 401)

    status_param = req.params.get("status")
    try:
        status = AgentStatus(status_param) if status_param else None
    except ValueError:
        return _error(f"Invalid status '{status_param}'", 400)

    try:
        records = store.list_for_owner(requester.email, status)
    except Exception:
        logging.exception("Failed to list agents for %s", requester.email)
        return _error("Failed to load agents", 502)

    return _json([r.model_dump() for r in records])


@bp.route(route="agents", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def upsert_agent(req: func.HttpRequest) -> func.HttpResponse:
    """
    Body: a partial or full AgentRecord (id omitted => create new). When an
    id is supplied and already belongs to this owner, the new fields are
    merged onto the existing record so a partial update (e.g. just a status
    change after create-test-agent succeeds) doesn't clobber fields the
    caller didn't send.
    """
    try:
        requester = get_requester(req)
    except UnauthenticatedError as e:
        return _error(str(e), 401)

    try:
        body = dict(req.get_json() or {})
    except ValueError:
        return _error("Invalid JSON body", 400)

    body["owner"] = requester.email  # never trust a client-supplied owner

    existing = store.get(requester.email, body.get("id", "")) if body.get("id") else None
    merged = {**existing.model_dump(), **body} if existing else body
    merged["updatedAt"] = datetime.now(timezone.utc).isoformat()

    try:
        record = AgentRecord(**merged)
    except ValidationError as e:
        return _error(f"Invalid agent record: {e}", 400)

    try:
        store.save(record)
    except Exception:
        logging.exception("Failed to save agent record for %s", requester.email)
        return _error("Failed to save agent", 502)

    return _json(record.model_dump())


@bp.route(route="agents/{id}", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_agent(req: func.HttpRequest) -> func.HttpResponse:
    try:
        requester = get_requester(req)
    except UnauthenticatedError as e:
        return _error(str(e), 401)

    record = store.get(requester.email, req.route_params.get("id"))
    if not record:
        return _error("Not found", 404)
    return _json(record.model_dump())
