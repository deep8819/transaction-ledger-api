"""Named errors raised by services, and the one place that turns every error
into the standard shape:

    {"error": {"code": "...", "message": "...", "details": []}}
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.error import ErrorResponse

logger = logging.getLogger(__name__)


class DomainError(Exception):
    """Base for errors raised by the service layer. They know nothing about HTTP."""

    message = "Request could not be completed"

    def __init__(self, message: str | None = None):
        self.message = message or self.message
        super().__init__(self.message)


class AccountNotFound(DomainError):
    message = "Account not found"


class InsufficientFunds(DomainError):
    message = "Insufficient funds: debit exceeds balance"


class DuplicateTransaction(DomainError):
    message = "Transaction with this reference_id already exists for this account"


# How each named error is presented to the client.
_DOMAIN_ERRORS: dict[type[DomainError], tuple[int, str]] = {
    AccountNotFound: (404, "ACCOUNT_NOT_FOUND"),
    InsufficientFunds: (409, "INSUFFICIENT_FUNDS"),
    DuplicateTransaction: (409, "DUPLICATE_TRANSACTION"),
}

_RESPONSE_DESCRIPTIONS = {
    404: "Not found (ACCOUNT_NOT_FOUND)",
    409: "Conflict (INSUFFICIENT_FUNDS or DUPLICATE_TRANSACTION)",
    422: "Validation error (VALIDATION_ERROR)",
}


def error_responses(*status_codes: int) -> dict:
    """The `responses=` entry that makes /docs list these errors."""
    return {
        code: {"model": ErrorResponse, "description": _RESPONSE_DESCRIPTIONS[code]}
        for code in status_codes
    }


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: list | None = None,
    headers: dict | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details or []}},
        headers=headers,
    )


def _domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    status_code, code = _DOMAIN_ERRORS[type(exc)]
    return _error_response(status_code, code, exc.message)


def _validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        {
            "field": "body"
            if err["type"] == "json_invalid"
            else ".".join(str(part) for part in err["loc"]),
            "message": err["msg"],
        }
        for err in exc.errors()
    ]
    return _error_response(422, "VALIDATION_ERROR", "Request validation failed", details)


def _http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Framework-level errors such as an unknown URL or a wrong HTTP method.
    code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
    message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
    return _error_response(exc.status_code, code, message, headers=exc.headers)


def _unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # The real error goes to the server log only; the client gets a generic message.
    logger.error(
        "Unhandled error on %s %s", request.method, request.url.path, exc_info=exc
    )
    return _error_response(500, "INTERNAL_ERROR", "An unexpected error occurred")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(Exception, _unexpected_error_handler)
