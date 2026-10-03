"""
Shared error handling decorator for API route handlers.
"""
import functools
import logging

from fastapi import HTTPException

from api.concurrency import ServiceBusyError
from services.telemetry import emit

logger = logging.getLogger(__name__)


def handle_api_errors(operation: str):
    """
    Decorator that wraps route handlers with standard error handling.

    Re-raises HTTPException, converts ValueError to 422, and catches
    all other exceptions as 500 with logging.

    Args:
        operation: Short description for log messages (e.g., "generating STL")
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except HTTPException as e:
                emit("api_error", operation=operation, status=e.status_code, error="HTTPException",
                     detail=str(e.detail)[:200])
                raise
            except ServiceBusyError as e:
                emit("api_error", operation=operation, status=429, error="ServiceBusyError",
                     detail="heavy-job queue full")
                raise HTTPException(
                    status_code=429,
                    detail="Server is busy with other jobs. Please retry shortly.",
                    headers={"Retry-After": str(e.retry_after)},
                ) from e
            except ValueError as e:
                emit("api_error", operation=operation, status=422, error="ValueError", detail=str(e)[:200])
                raise HTTPException(status_code=422, detail=str(e))
            except Exception as e:
                logger.error("Error %s: %s", operation, str(e), exc_info=True)
                emit("api_error", operation=operation, status=500, error=type(e).__name__, detail=str(e)[:200])
                raise HTTPException(status_code=500, detail="An internal error occurred")
        return wrapper
    return decorator
