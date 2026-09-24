"""Browser usage events (see services/telemetry.py)."""
from fastapi import APIRouter, Request, Response

from api.client_ip import client_ip
from api.error_handlers import handle_api_errors
from api.models import ClientEventBatch
from api.rate_limiter import limiter
from services.telemetry import emit, visitor_id

router = APIRouter(prefix="/api", tags=["Telemetry"])


@router.post("/events", status_code=204)
@limiter.limit("60/minute")
@handle_api_errors("recording events")
async def api_events(request: Request, body: ClientEventBatch) -> Response:
    """Record a page load's batched usage events as ``client.<name>`` telemetry."""
    visitor = visitor_id(client_ip(request), request.headers.get("user-agent", ""))
    for event in body.events:
        emit(f"client.{event.name}", visitor=visitor, page=body.pageLoadId, at_ms=event.t, **event.props)
    return Response(status_code=204)
