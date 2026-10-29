"""FastAPI dependencies for authentication, scope checks, and rate limiting."""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request

from ..api.dependencies import ContainerDep
from .audit import AuditEvent
from .principal import AuthenticationError, AuthorizationError, Principal
from .rate_limit import RateLimitedError


async def get_principal(request: Request, container: ContainerDep) -> Principal:
    """Authenticate the caller once per request."""
    try:
        return await container.authenticator.authenticate(request)
    except AuthenticationError as error:
        await container.audit.record(
            AuditEvent(action="authenticate", outcome="denied", subject=None, detail=error.message)
        )
        raise


PrincipalDep = Annotated[Principal, Depends(get_principal)]


def require_scopes(*scopes: str) -> Callable[..., Awaitable[Principal]]:
    """Return a dependency that admits only principals holding every scope in `scopes`."""
    required = frozenset(scopes)

    async def dependency(
        request: Request, principal: PrincipalDep, container: ContainerDep
    ) -> Principal:
        action = f"{request.method} {request.url.path}"
        missing = principal.missing(required)
        if missing:
            detail = f"missing scopes: {', '.join(sorted(missing))}"
            denied = AuditEvent(action, "denied", principal.subject, detail)
            await container.audit.record(denied)
            needed = ", ".join(sorted(required))
            raise AuthorizationError(f"This request needs the scopes: {needed}.")
        await container.audit.record(
            AuditEvent(action=action, outcome="allowed", subject=principal.subject)
        )
        return principal

    return dependency


async def rate_limit(request: Request, container: ContainerDep) -> None:
    """Reject the request when the configured limiter says so."""
    key = request.client.host if request.client else "unknown"
    if not await container.rate_limiter.allow(key):
        raise RateLimitedError("Too many requests; retry later.", headers={"Retry-After": "60"})
