import json
import logging

import azure.functions as func

# Phase 0: anonymous auth so the frontend can call it with no key.
# Phase 3 (policy engine) should move real auth to APIM / Entra token
# validation rather than relying on function-level auth levels.
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """Hello-world endpoint: proves Function App deploys and responds."""
    logging.info("GET /api/health called")

    payload = {
        "status": "ok",
        "service": "aaf-factory-api",
        "phase": "0-foundations",
    }

    return func.HttpResponse(
        json.dumps(payload),
        status_code=200,
        mimetype="application/json",
        headers={"Access-Control-Allow-Origin": "*"},
    )
