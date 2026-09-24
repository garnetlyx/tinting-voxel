"""Response helpers for handlers that build large payloads in worker threads."""
from fastapi import Response
from pydantic import BaseModel


def json_response(model: BaseModel) -> Response:
    """Serialize a response model to JSON bytes.

    Call it inside the worker thread that built the model, so a large
    payload is never encoded on the event loop.
    """
    return Response(content=model.model_dump_json(), media_type="application/json")
