"""Bug reports must be saved before success and never send real email in tests."""
import base64
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from api.routes import bug_report as route
from config.settings import settings
from main import app


@pytest.fixture(scope='module')
def client():
    # Report submission does not use the expensive optical-matrix cache.
    with patch('services.matrix_cache.warmup_cache', return_value=0), TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def isolated_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'bug_report_storage_dir', str(tmp_path / 'reports'))
    monkeypatch.setattr(settings, 'resend_api_key', SecretStr(''))
    monkeypatch.setattr(settings, 'bug_report_email_to', '')
    return tmp_path / 'reports'


def test_report_is_saved_without_email(client, isolated_reports):
    response = client.post('/api/bug-report', json={
        'description': '3D preview turned gray',
        'frontendContext': {
            'url': 'https://example.test/convert?token=private#hash',
            'localStorage': {'secret': 'must not be stored'},
            'converter': {'layerCount': 4, 'imageWidth': 1000, 'sourceImage': 'private pixels'},
            'debugLogs': [{'level': 'error', 'message': 'Authorization: Bearer private-key', 'timestamp': 'now'}],
        },
    })
    assert response.status_code == 200
    result = response.json()
    assert result['success'] is True and result['delivery'] == 'stored'
    path = isolated_reports / f"{result['reportId']}.json"
    report = json.loads(path.read_text())
    assert report['description'] == '3D preview turned gray'
    assert report['frontendContext']['converter']['layerCount'] == 4
    assert report['frontendContext']['url'] == 'https://example.test/convert'
    assert 'private' not in json.dumps(report)
    assert 'screenshot' not in report
    assert path.stat().st_mode & 0o777 == 0o600
    assert isolated_reports.stat().st_mode & 0o777 == 0o700


def test_empty_description_is_allowed(client):
    assert client.post('/api/bug-report', json={}).status_code == 200


@pytest.mark.parametrize('format_name', ['png', 'jpeg'])
def test_valid_screenshot_is_preserved(client, isolated_reports, tiny_png_bytes, tiny_jpeg_bytes, format_name):
    image = tiny_png_bytes if format_name == 'png' else tiny_jpeg_bytes
    screenshot = f'data:image/{format_name};base64,' + base64.b64encode(image).decode()
    response = client.post('/api/bug-report', json={'screenshot': screenshot})
    assert response.status_code == 200
    report = json.loads(next(isolated_reports.glob('*.json')).read_text())
    assert report['screenshot'] == screenshot


@pytest.mark.parametrize('payload', [
    {'description': 'x' * 1001},
    {'screenshot': 'data:text/html;base64,PHNjcmlwdD4='},
    {'screenshot': 'data:image/png;base64,bm90IGFuIGltYWdl'},
    {'screenshot': 'x' * (5 * 1024 * 1024 + 1)},
    {'frontendContext': {'debugLogs': [{}] * 101}},
    {'frontendContext': {'converter': {'imageWidth': -1}}},
    [],
])
def test_invalid_reports_are_not_saved(client, isolated_reports, payload):
    response = client.post('/api/bug-report', json=payload)
    assert response.status_code == 422
    assert len(response.content) < 300
    assert not list(isolated_reports.glob('*.json'))


def test_image_mime_must_match_contents(client, tiny_png_bytes):
    screenshot = 'data:image/jpeg;base64,' + base64.b64encode(tiny_png_bytes).decode()
    assert client.post('/api/bug-report', json={'screenshot': screenshot}).status_code == 422


def test_malformed_json_and_wrong_content_type(client):
    assert client.post('/api/bug-report', content='{', headers={'content-type': 'application/json'}).status_code == 422
    assert client.post('/api/bug-report', content='{}').status_code == 415


def test_body_limit_includes_chunked_requests(client, isolated_reports):
    response = client.post('/api/bug-report', content=iter([b' ' * (3 * 1024 * 1024)] * 3), headers={'content-type': 'application/json'})
    assert response.status_code == 413
    assert not list(isolated_reports.glob('*.json'))


def test_rate_limit_is_three_per_hour(client):
    assert [client.post('/api/bug-report', json={}).status_code for _ in range(4)] == [200, 200, 200, 429]


def test_storage_failure_never_acknowledges_success(client, monkeypatch):
    def unavailable(_payload):
        raise OSError('Disk unavailable')
    monkeypatch.setattr(route, 'save_bug_report', unavailable)
    email = AsyncMock()
    monkeypatch.setattr(route, 'send_bug_report_email', email)
    response = client.post('/api/bug-report', json={})
    assert response.status_code == 503
    email.assert_not_called()


def test_email_is_attempted_only_after_persistence(client, isolated_reports, monkeypatch):
    async def deliver(report):
        assert (isolated_reports / f"{report['reportId']}.json").exists()
        return True
    monkeypatch.setattr(route, 'send_bug_report_email', deliver)
    assert client.post('/api/bug-report', json={}).json()['delivery'] == 'email'
