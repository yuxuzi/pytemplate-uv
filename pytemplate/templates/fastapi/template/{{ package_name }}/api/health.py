"""Liveness and readiness endpoints for orchestrators and load balancers."""

import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from .dependencies import ContainerDep

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])
CHECK_TIMEOUT_SECONDS = 2.0


class Liveness(BaseModel):
    """The process is up."""

    status: Literal["ok"] = "ok"
    version: str


class Readiness(BaseModel):
    """Whether every dependency the service needs is reachable."""

    status: Literal["ok", "unavailable"]
    checks: dict[str, Literal["ok", "failed"]]


@router.get("/live")
async def live(container: ContainerDep) -> Liveness:
    """Report that the process is running; never touches dependencies."""
    return Liveness(version=container.settings.APP_VERSION)


@router.get("/ready", responses={503: {"model": Readiness}})
async def ready(container: ContainerDep, response: Response) -> Readiness:
    """Run every registered readiness check; any failure makes the service unavailable."""
    checks: dict[str, Literal["ok", "failed"]] = {}
    for name, check in sorted(container.readiness_checks.items()):
        try:
            await asyncio.wait_for(check(), timeout=CHECK_TIMEOUT_SECONDS)
            checks[name] = "ok"
        except Exception:
            logger.warning("Readiness check '%s' failed", name, exc_info=True)
            checks[name] = "failed"
    healthy = all(result == "ok" for result in checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return Readiness(status="ok" if healthy else "unavailable", checks=checks)
