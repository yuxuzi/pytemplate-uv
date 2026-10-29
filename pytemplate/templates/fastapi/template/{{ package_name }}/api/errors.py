"""One error envelope for application, domain, validation, and HTTP errors."""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..bootstrap.logging import request_id
from ..domain.errors import DomainError, InvalidValueError, NotFoundError

_HTTP_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "TOO_MANY_REQUESTS",
}
_DOMAIN_STATUS: dict[type[DomainError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    InvalidValueError: 422,
}


class ErrorBody(BaseModel):
    """What went wrong, in a stable shape."""

    code: str
    message: str
    details: dict[str, Any] | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    """The body of every error response."""

    error: ErrorBody


class ApiError(Exception):
    """An error raised by the HTTP layer that maps to one status code."""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "BAD_REQUEST"

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        self.headers = headers


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build an `ErrorResponse` carrying the current request ID."""
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, details=details, request_id=request_id.get())
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(), headers=headers)


async def _api_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ApiError):
        raise exc
    return error_response(exc.status_code, exc.code, exc.message, exc.details, exc.headers)


async def _domain_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, DomainError):
        raise exc
    status_code = next(
        (code for kind, code in _DOMAIN_STATUS.items() if isinstance(exc, kind)),
        status.HTTP_400_BAD_REQUEST,
    )
    return error_response(status_code, exc.code, str(exc), exc.details)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    # Report where and why only; echoing input values could leak secrets into responses.
    errors = [
        {"loc": [str(part) for part in error["loc"]], "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return error_response(
        422,
        "VALIDATION_ERROR",
        "The request is invalid.",
        {"errors": errors},
    )


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    return error_response(
        exc.status_code,
        _HTTP_CODES.get(exc.status_code, "HTTP_ERROR"),
        str(exc.detail),
        headers=dict(exc.headers) if exc.headers else None,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Render every expected error as an `ErrorResponse`; unexpected ones are handled in
    `RequestContextMiddleware` so they still carry the request ID."""
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(DomainError, _domain_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
