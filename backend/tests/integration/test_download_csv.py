"""
Integration tests for the /api/download-csv endpoint.
"""


def test_csv_success(client, sample_color_blocks_with_hex):
    """POST /api/download-csv returns a CSV file."""
    response = client.post(
        "/api/download-csv",
        json={"colorBlocks": sample_color_blocks_with_hex},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment" in response.headers.get("content-disposition", "")


def test_csv_content_format(client, sample_color_blocks_with_hex):
    """CSV contains header row plus data rows."""
    response = client.post(
        "/api/download-csv",
        json={"colorBlocks": sample_color_blocks_with_hex},
    )
    assert response.status_code == 200
    lines = response.text.strip().split("\n")
    # At least a header + 1 data row
    assert len(lines) >= 2


def test_csv_empty_blocks(client):
    """Empty color blocks returns 422 (min_items=1 validation)."""
    response = client.post(
        "/api/download-csv",
        json={"colorBlocks": []},
    )
    assert response.status_code == 422


def test_csv_invalid_body_returns_422(client):
    """Invalid request body returns 422."""
    response = client.post(
        "/api/download-csv",
        json={"wrong_field": []},
    )
    assert response.status_code == 422
