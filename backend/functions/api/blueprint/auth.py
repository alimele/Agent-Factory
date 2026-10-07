"""
Requester identity for Function endpoints.

Relies on Azure Static Web Apps' linked-API auth (or Function App Easy Auth,
same mechanism) injecting the `x-ms-client-principal` header — base64-encoded
JSON containing the Entra ID claims — into every request that reaches this
Function once the user is logged in via the Phase 1 MSAL flow. We do NOT
validate a JWT here ourselves; SWA/Easy Auth already did that in front of us.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass


@dataclass
class Requester:
    email: str
    name: str | None = None
    roles: list[str] | None = None


class UnauthenticatedError(Exception):
    pass


def get_requester(req) -> Requester:
    header = req.headers.get("x-ms-client-principal")
    if header:
        try:
            claims = json.loads(base64.b64decode(header))
        except Exception as e:
            raise UnauthenticatedError(f"Malformed x-ms-client-principal: {e}")

        email = None
        for c in claims.get("claims", []):
            if c.get("typ") in ("preferred_username", "emails", "upn", "email"):
                email = c.get("val")
                break
        if not email:
            email = claims.get("userDetails")  # SWA's own convenience field
        if not email:
            raise UnauthenticatedError("No email/upn claim found in principal")

        return Requester(email=email, name=claims.get("userDetails"))

    # Local dev only — must be explicitly opted into, never a silent default.
    if os.environ.get("LOCAL_DEV_MODE") == "true":
        dev_email = req.headers.get("x-debug-email", "dev-local@example.com")
        return Requester(email=dev_email, name="Local Dev User")

    raise UnauthenticatedError(
        "No x-ms-client-principal header present and LOCAL_DEV_MODE is not set."
    )
