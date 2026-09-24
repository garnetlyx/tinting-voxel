"""User bug reports with bounded request bodies and optional email delivery."""
import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from api.error_handlers import handle_api_errors
from api.models import BugReportRequest
from api.rate_limiter import limiter
from services.bug_report import decode_report_screenshot, save_bug_report, send_bug_report_email
from services.telemetry import emit

router = APIRouter(tags=['Bug reports'])
logger = logging.getLogger(__name__)
MAX_REPORT_BODY_BYTES = 6 * 1024 * 1024


@router.post('/api/bug-report')
@limiter.limit('3/hour')
@handle_api_errors('submitting bug report')
async def api_bug_report(request: Request) -> Dict[str, Any]:
    """Save feedback, its diagnostics, and an optional screenshot."""
    if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
        raise HTTPException(status_code=415, detail='Bug reports must use application/json')
    # Bound streamed/chunked requests before parsing JSON or allocating images.
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_REPORT_BODY_BYTES:
            raise HTTPException(status_code=413, detail='Bug report exceeds the 6 MB limit')
        chunks.append(chunk)
    try:
        body = BugReportRequest.model_validate(json.loads(b''.join(chunks)))
    except (ValueError, ValidationError) as exc:
        # Do not echo large screenshots or untrusted payloads in validation errors.
        raise HTTPException(status_code=422, detail='Invalid bug report. Check the description, screenshot, and browser details.') from exc
    if body.screenshot:
        decode_report_screenshot(body.screenshot)
    try:
        report = await run_in_threadpool(save_bug_report, body.model_dump(mode='json', exclude_none=True))
    except OSError as exc:
        logger.error('Could not save bug report: %s', type(exc).__name__)
        raise HTTPException(status_code=503, detail='Could not save your report. Please try again later.') from exc
    emailed = await send_bug_report_email(report)
    delivery = 'email' if emailed else 'stored'
    emit('bug_report_submitted', delivery=delivery, screenshot=bool(body.screenshot))
    return {'success': True, 'reportId': report['reportId'], 'delivery': delivery}
