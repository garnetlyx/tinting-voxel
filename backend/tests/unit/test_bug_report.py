"""Report diagnostics and mocked notification delivery."""
import base64
import io
import json
import logging
import time

import httpx
import pytest
from PIL import Image
from pydantic import SecretStr

from config.settings import settings
from services import bug_report


def test_diagnostics_are_bounded_and_redacted():
    handler = bug_report.RecentReportLogs()
    for index in range(120):
        handler.emit(logging.LogRecord('api.routes.image', logging.ERROR, '', 0,
            f'failure {index} Authorization: Bearer private-token password="private value" https://app.test/path?secret=private data:image/png;base64,private', (), None))
    handler.emit(logging.LogRecord('unrelated', logging.ERROR, '', 0, 'ignored', (), None))
    assert len(handler.entries) == 100
    assert len(handler.recent()) == 50
    assert 'private' not in '\n'.join(handler.recent())
    assert 'ignored' not in '\n'.join(handler.recent())
    handler.entries.clear()
    handler.entries.append((time.time() - 301, 'expired'))
    assert handler.recent() == []
    assert len(bug_report.sanitize_diagnostic('x' * 3000)) == 1000


def test_existing_report_is_never_overwritten_or_removed(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'bug_report_storage_dir', str(tmp_path))
    monkeypatch.setattr(bug_report, 'uuid4', lambda: 'existing')
    path = tmp_path / 'existing.json'
    path.write_text('existing report')
    with pytest.raises(FileExistsError):
        bug_report.save_bug_report({})
    assert path.read_text() == 'existing report'


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [200, 403, 500, 'timeout'])
async def test_email_escapes_content_and_attaches_screenshot_without_real_network(tmp_path, monkeypatch, status):
    monkeypatch.setattr(settings, 'bug_report_storage_dir', str(tmp_path))
    monkeypatch.setattr(settings, 'resend_api_key', SecretStr('fake-test-key'))
    monkeypatch.setattr(settings, 'bug_report_email_to', 'test@example.invalid')
    monkeypatch.setattr(settings, 'resend_from', 'sender@example.invalid')
    buffer = io.BytesIO()
    Image.new('RGB', (2, 2), 'red').save(buffer, format='JPEG')
    image = base64.b64encode(buffer.getvalue()).decode()
    report = bug_report.save_bug_report({'description': '<script>alert(1)</script>\nPreview failed', 'screenshot': 'data:image/jpeg;base64,' + image})
    requests = []

    def respond(request):
        requests.append(request)
        if status == 'timeout':
            raise httpx.ReadTimeout('simulated timeout', request=request)
        return httpx.Response(status, json={'id': 'mock-email'})

    original_client = httpx.AsyncClient
    monkeypatch.setattr(bug_report.httpx, 'AsyncClient', lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs))
    assert await bug_report.send_bug_report_email(report) is (status == 200)
    assert len(requests) == 1
    request = requests[0]
    body = json.loads(request.content)
    assert body['to'] == ['test@example.invalid']
    assert '<script>' not in body['html'] and '&lt;script&gt;' in body['html']
    assert '\n' not in body['subject']
    assert body['attachments'] == [{'filename': 'screenshot.jpeg', 'content': image}]
    assert request.headers['Idempotency-Key'] == report['reportId']
    assert (tmp_path / f"{report['reportId']}.json").exists()
