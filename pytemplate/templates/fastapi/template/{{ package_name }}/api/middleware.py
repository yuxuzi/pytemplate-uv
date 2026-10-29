"""Request context (correlation ID, access log, unexpected errors) and host and CORS policy."""

import logging
import re
import time
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..bootstrap.logging import request_id
from ..bootstrap.settings import Settings
from .errors import error_response

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
_INCOMING_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


class RequestContextMiddleware:
    """Give each request an ID, log it, add security headers, and contain unexpected errors."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle one ASGI call."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        current = incoming if _INCOMING_ID.fullmatch(incoming) else uuid.uuid4().hex
        token = request_id.set(current)
        started = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_context(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = current
                for name, value in SECURITY_HEADERS.items():
                    headers.setdefault(name, value)
            await send(message)

        try:
            await self.app(scope, receive, send_with_context)
        except Exception:
            logger.exception("Unhandled error in %s %s", scope["method"], scope["path"])
            if response_started:
                raise
            response = error_response(500, "INTERNAL_ERROR", "An unexpected error occurred.")
            await response(scope, receive, send_with_context)
        finally:
            logger.info(
                "%s %s -> %s",
                scope["method"],
                scope["path"],
                status_code,
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "status": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
            request_id.reset(token)


class TrustedHostMiddleware:
    """Reject requests for hosts outside ALLOWED_HOSTS, except `/health/` probes, which
    orchestrators send by IP address."""

    def __init__(self, app: ASGIApp, allowed_hosts: list[str]) -> None:
        self.app = app
        self.allowed = [host.lower() for host in allowed_hosts]

    def _allowed(self, host: str) -> bool:
        return any(
            pattern == "*"
            or host == pattern
            or (pattern.startswith("*.") and host.endswith(pattern[1:]))
            for pattern in self.allowed
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pass allowed requests through; answer the rest with a 400 error envelope."""
        if scope["type"] != "http" or scope["path"].startswith("/health/"):
            await self.app(scope, receive, send)
            return
        host = Headers(scope=scope).get("host", "").lower()
        host = host[1 : host.find("]")] if host.startswith("[") else host.split(":")[0]
        if self._allowed(host):
            await self.app(scope, receive, send)
            return
        response = error_response(400, "BAD_REQUEST", "Invalid host header.")
        await response(scope, receive, send)


def setup_middleware(app: FastAPI, settings: Settings) -> None:
    """Install middleware; the request context is outermost so every response carries an ID."""
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
    if settings.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "X-API-Key", REQUEST_ID_HEADER],
            expose_headers=[REQUEST_ID_HEADER],
        )
    app.add_middleware(RequestContextMiddleware)
