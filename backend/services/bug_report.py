"""Bounded diagnostics, local report storage, and optional Resend delivery."""
import base64
import binascii
import html
import io
import json
import logging
import os
import re
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
from uuid import uuid4

import httpx
from PIL import Image, UnidentifiedImageError

from config.settings import settings

logger = logging.getLogger(__name__)
MAX_SCREENSHOT_LENGTH = 5 * 1024 * 1024


def sanitize_diagnostic(message: str) -> str:
    """Remove common credential strings and URL queries from diagnostic text."""
    message = re.sub(r'data:[^\s]+', '[image data]', message, flags=re.I)
    message = re.sub(r'(https?://[^\s?#]+)[?#][^\s]*', r'\1', message, flags=re.I)
    message = re.sub(r'Bearer\s+\S+', 'Bearer [redacted]', message, flags=re.I)
    message = re.sub(
        r'''(authorization|api[_-]?key|token|password|secret)["']?\s*[:=]\s*(?:"[^"]*"|'[^']*'|[^\s,;]+)''',
        r'\1=[redacted]', message, flags=re.I,
    )
    return message[:1000]


class RecentReportLogs(logging.Handler):
    """Keep recent application diagnostics without logging report contents."""

    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.entries = deque(maxlen=100)
        self.buffer_lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        if record.name == __name__ or not (
            record.name == 'main' or record.name.startswith(('api.', 'services.'))
        ):
            return
        message = sanitize_diagnostic(f'{record.levelname} {record.name}: {record.getMessage()}')
        with self.buffer_lock:
            self.entries.append((record.created, message))

    def recent(self) -> List[str]:
        cutoff = time.time() - 300
        with self.buffer_lock:
            return [message for timestamp, message in self.entries if timestamp >= cutoff][-50:]


recent_logs = RecentReportLogs()


def install_bug_report_logging() -> None:
    """Install the application log buffer once."""
    root = logging.getLogger()
    if recent_logs not in root.handlers:
        root.addHandler(recent_logs)


def decode_report_screenshot(screenshot: str) -> Tuple[str, str]:
    """Accept only bounded, valid PNG/JPEG screenshots with matching MIME types."""
    if len(screenshot) > MAX_SCREENSHOT_LENGTH:
        raise ValueError('Screenshot exceeds the 5 MB limit')
    match = re.fullmatch(r'data:image/(png|jpeg);base64,([A-Za-z0-9+/=]+)', screenshot)
    if not match:
        raise ValueError('Screenshot must be a base64 PNG or JPEG image')
    extension, content = match.groups()
    try:
        raw = base64.b64decode(content, validate=True)
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != {'png': 'PNG', 'jpeg': 'JPEG'}[extension]:
                raise ValueError('Screenshot content does not match its image type')
            if image.width * image.height > 16_000_000:
                raise ValueError('Screenshot dimensions are too large')
            image.verify()
    except (binascii.Error, OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValueError('Screenshot is not a valid image') from exc
    return extension, content


def _sanitize_context(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_diagnostic(value)
    if isinstance(value, list):
        return [_sanitize_context(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_context(item) for key, item in value.items()}
    return value


def save_bug_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Persist the complete report before acknowledging it or sending email."""
    report = {
        'reportId': str(uuid4()),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'description': payload.get('description', ''),
        'frontendContext': _sanitize_context(payload.get('frontendContext', {})),
        'serverLogs': recent_logs.recent(),
    }
    if payload.get('screenshot'):
        report['screenshot'] = payload['screenshot']
    directory = Path(settings.bug_report_storage_dir)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / f"{report['reportId']}.json"
    created = False
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            json.dump(report, output, ensure_ascii=False)
            output.flush()
            os.fsync(output.fileno())
    except OSError:
        if created:
            path.unlink(missing_ok=True)
        raise
    logger.info('Bug report saved: %s (screenshot=%s)', report['reportId'], 'screenshot' in report)
    return report


async def send_bug_report_email(report: Dict[str, Any]) -> bool:
    """Use server-only configuration; retain the saved report if delivery fails."""
    api_key = settings.resend_api_key.get_secret_value()
    recipient = settings.bug_report_email_to.strip()
    if not api_key or not recipient:
        return False
    context = html.escape(json.dumps(report['frontendContext'], indent=2, ensure_ascii=False))
    logs = html.escape('\n'.join(report['serverLogs']) or 'No recent server logs')
    description = report['description'] or '(no description provided)'
    body: Dict[str, Any] = {
        'from': settings.resend_from,
        'to': [recipient],
        'subject': '[Tinting Voxel Bug Report] ' + ' '.join(description.split())[:60],
        'html': (
            '<h2>Bug Report — Tinting Voxel</h2>'
            f"<p>Report ID: {html.escape(report['reportId'])}</p>"
            f"<p>Received: {html.escape(report['timestamp'])}</p>"
            f'<h3>Description</h3><pre>{html.escape(description)}</pre>'
            f'<h3>Browser and converter details</h3><pre>{context}</pre>'
            f'<h3>Recent server logs</h3><pre>{logs}</pre>'
        ),
    }
    if report.get('screenshot'):
        extension, content = decode_report_screenshot(report['screenshot'])
        body['attachments'] = [{'filename': f'screenshot.{extension}', 'content': content}]
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                'https://api.resend.com/emails', json=body,
                headers={'Authorization': f'Bearer {api_key}', 'Idempotency-Key': report['reportId']},
            )
            if response.is_success:
                logger.info('Bug report email delivered: %s', report['reportId'])
                return True
            logger.warning('Bug report email failed: %s (HTTP %s)', report['reportId'], response.status_code)
    except httpx.HTTPError:
        logger.warning('Bug report email unavailable: %s; local copy retained', report['reportId'])
    return False
