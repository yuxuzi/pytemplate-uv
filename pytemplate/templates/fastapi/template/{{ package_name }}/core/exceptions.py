"""Application errors and their consistent JSON representation."""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Body returned for every application error."""

    code: str
    message: str
    details: dict[str, Any] | None = None


class AppError(Exception):
    """Base class for errors that map to a specific HTTP response."""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "BAD_REQUEST"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def to_response(self) -> ErrorResponse:
        """Return the serializable error body."""
        return ErrorResponse(code=self.code, message=self.message, details=self.details)


class NotFoundError(AppError):
    """A requested resource does not exist."""

    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"

    def __init__(self, resource: str, resource_id: object) -> None:
        super().__init__(
            f"{resource} {resource_id} was not found",
            {"resource": resource, "id": str(resource_id)},
        )


async def _handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):
        raise exc
    return JSONResponse(status_code=exc.status_code, content=exc.to_response().model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    """Render every `AppError` as an `ErrorResponse`."""
    app.add_exception_handler(AppError, _handle_app_error)
