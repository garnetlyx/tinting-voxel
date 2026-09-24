"""Browser usage events endpoint."""
import logging

import pytest

PAGE = "0f3c2b8e-7d41-4a6e-9c55-1b2d3e4f5a6b"


def test_valid_events_are_recorded(client, caplog):
    with caplog.at_level(logging.INFO, logger="telemetry"):
        response = client.post("/api/events", json={
            "pageLoadId": PAGE,
            "events": [
                {"name": "page_view", "props": {"locale": "en", "width": 1280}, "t": 12},
                {"name": "image_selected", "props": {"megapixels": 12.2, "editable": True}},
            ],
        })
    assert response.status_code == 204
    records = [r for r in caplog.records if getattr(r, "event", "").startswith("client.")]
    assert [r.event for r in records] == ["client.page_view", "client.image_selected"]
    assert records[0].locale == "en" and records[0].width == 1280 and records[0].at_ms == 12
    assert records[0].page == PAGE and len(records[0].visitor) == 16
    assert records[0].visitor == records[1].visitor


@pytest.mark.parametrize("payload", [
    {"pageLoadId": PAGE, "events": [{"name": "Page View"}]},
    {"pageLoadId": PAGE, "events": [{"name": "page_view", "props": {"message": "x"}}]},
    {"pageLoadId": PAGE, "events": [{"name": "page_view", "props": {"visitor": "x"}}]},
    {"pageLoadId": PAGE, "events": [{"name": "page_view", "props": {"level": "error"}}]},
    {"pageLoadId": PAGE, "events": [{"name": "page_view", "props": {"nested": {"a": 1}}}]},
    {"pageLoadId": PAGE, "events": [{"name": "page_view", "props": {"long": "x" * 201}}]},
    {"pageLoadId": PAGE, "events": [{"name": "page_view"}] * 51},
    {"pageLoadId": "short", "events": [{"name": "page_view"}]},
    {"pageLoadId": PAGE, "events": []},
])
def test_invalid_events_are_rejected(client, payload):
    assert client.post("/api/events", json=payload).status_code == 422
