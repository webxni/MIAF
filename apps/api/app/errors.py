"""Domain exceptions and FastAPI error handlers."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class MIAFError(Exception):
    """Base for all domain exceptions. status_code set by subclasses."""

    status_code: int = 400

    def __init__(self, message: str, *, code: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}


class NotFoundError(MIAFError):
    status_code = 404


class AuthError(MIAFError):
    status_code = 401


class ForbiddenError(MIAFError):
    status_code = 403


class ConflictError(MIAFError):
    status_code = 409


class UnbalancedEntryError(MIAFError):
    status_code = 422


class ImmutableEntryError(MIAFError):
    status_code = 409


class TenantIsolationError(ForbiddenError):
    """Raised when a query crosses tenant or entity scope. Always a bug."""


class RateLimitError(MIAFError):
    status_code = 429


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(MIAFError)
    async def _miaf_handler(_: Request, exc: MIAFError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )
