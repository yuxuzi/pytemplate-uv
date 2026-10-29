"""Who am I: the authenticated principal, for clients and smoke checks."""

from fastapi import APIRouter
from pydantic import BaseModel

from ...security.dependencies import PrincipalDep

router = APIRouter(tags=["auth"])


class PrincipalRead(BaseModel):
    """The caller as the service sees it."""

    subject: str
    scopes: list[str]


@router.get("/me")
async def me(principal: PrincipalDep) -> PrincipalRead:
    """Return the authenticated caller."""
    return PrincipalRead(subject=principal.subject, scopes=sorted(principal.scopes))
