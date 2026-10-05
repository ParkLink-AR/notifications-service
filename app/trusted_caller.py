"""Rejects any request that didn't come through the ParkLink gateway or from another
ParkLink service.

Routes here trust X-User-Id (and, for admins, the caller id the gateway forwards) as
already verified -- true only for requests the gateway forwarded, since it strips whatever
the client sent. If this service is reachable directly (e.g. its own public URL on a PaaS),
anyone could send those headers themselves; this closes that hole.
"""

from __future__ import annotations

import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings

# Health probes are hit by the platform itself, never with either secret.
_OPEN_PATHS = {"/livez", "/readyz", "/health"}


def _matches(provided: str | None, expected: str) -> bool:
    return bool(expected) and provided is not None and hmac.compare_digest(provided, expected)


class TrustedCallerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        gateway_secret = settings.GATEWAY_INTERNAL_SECRET
        internal_key = settings.INTERNAL_SERVICE_KEY
        if (
            (not gateway_secret and not internal_key)
            or request.url.path in _OPEN_PATHS
            or _matches(request.headers.get("x-gateway-secret"), gateway_secret)
            or _matches(request.headers.get("x-internal-key"), internal_key)
        ):
            return await call_next(request)
        return JSONResponse(
            status_code=401,
            content={"code": "UNTRUSTED_CALLER", "error": "requests must go through the gateway"},
        )
