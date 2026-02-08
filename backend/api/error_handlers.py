"""
Shared error handling decorator for API route handlers.
"""
import functools
import logging

from fastapi import HTTPException

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
            except HTTPException:
                raise
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))
            except Exception as e:
                logger.error("Error %s: %s", operation, str(e), exc_info=True)
                raise HTTPException(status_code=500, detail="An internal error occurred")
        return wrapper
    return decorator
