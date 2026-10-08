"""
HTTP surface for the policy engine.
"""
import logging

import azure.functions as func
from pydantic import ValidationError

from api.policy.engine import evaluate
from api.policy.models import Stage
from api.policy.identity import build_context, TokenError

bp = func.Blueprint()


@bp.route(route="policy/evaluate", methods=["POST"],auth_level=func.AuthLevel.ANONYMOUS)
def evaluate_policy(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON body", status_code=400)

    blueprint = body.get("blueprint")
    if not blueprint:
        return func.HttpResponse("Missing 'blueprint'", status_code=400)

    try:
        stage = Stage(body.get("stage", "pre_deploy"))
    except ValueError:
        return func.HttpResponse("Invalid 'stage' — use 'pre_deploy' or 'pre_publish'", status_code=400)

    try:
        ctx = build_context(req, test_results=body.get("testResults"))
    except TokenError as e:
        return func.HttpResponse(str(e), status_code=401)

    try:
        result = evaluate(blueprint, ctx, stage, blueprint_id=body.get("blueprintId"))
    except (KeyError, ValidationError) as e:
        logging.exception("Policy evaluation failed")
        return func.HttpResponse(f"Evaluation error: {e}", status_code=400)

    return func.HttpResponse(
        result.model_dump_json(),
        status_code=200,
        mimetype="application/json",
    )
    
