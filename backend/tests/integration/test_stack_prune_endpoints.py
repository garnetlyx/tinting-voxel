"""
Endpoint regression: an edited Clear palette (custom filamentColors carrying
hex + td + k) must keep the translucent prune regime through the
process-image request path, and removed schema fields (td_rgb, td_neutral,
alpha, td_scale, td_gamma) are rejected instead of silently discarded.
"""
import io
import json

from PIL import Image

EDITED_CLEAR = [
        {"name": "Cyan", "hex": "#4C72A0", "transmission_distance": 4.7, "k": 0.0},
        {"name": "Magenta", "hex": "#CE5E53", "transmission_distance": 6.3, "k": 0.0},
        {"name": "Yellow", "hex": "#D8B695", "transmission_distance": 10.1, "k": 0.0},
        {"name": "White", "hex": "#D9D6C5", "transmission_distance": 18.0, "k": 0.0},
    ]


REMOVED_FIELDS = [
    {"name": "Cyan", "hex": "#4C72A0", "transmission_distance": 4.7, "td_rgb": [1.0, 2.0, 3.0]},
    {"name": "Cyan", "hex": "#4C72A0", "transmission_distance": 4.7, "td_neutral": 48.9},
    {"name": "Cyan", "hex": "#4C72A0", "transmission_distance": 4.7, "alpha": 12.0},
    {"name": "Cyan", "hex": "#4C72A0", "transmission_distance": 4.7, "td_scale": 1.48},
    {"name": "Cyan", "hex": "#4C72A0", "transmission_distance": 4.7, "td_gamma": 0.2},
]


def test_process_image_endpoint_accepts_edited_clear_palette(client):
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (200, 60, 60)).save(buf, format="PNG")
    resp = client.post(
        "/api/process-image",
        data={
            "mode": "pixel",
            "filamentColors": json.dumps(EDITED_CLEAR),
            "layerCount": "4",
            "layerHeight": "0.84",
            "pixelSize": "0.42",
            "maxColors": "8",
        },
        files={"image": ("t.png", buf.getvalue(), "image/png")},
    )
    assert resp.status_code == 200, resp.text


def test_removed_schema_fields_are_rejected(client):
    """Obsolete clients sending deleted fields must fail loudly, not get
    silently changed optical behavior."""
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (200, 60, 60)).save(buf, format="PNG")
    for colors in REMOVED_FIELDS:
        resp = client.post(
            "/api/process-image",
            data={
                "mode": "pixel",
                "filamentColors": json.dumps(colors),
                "layerCount": "4",
                "layerHeight": "0.08",
                "pixelSize": "0.42",
            },
            files={"image": ("t.png", buf.getvalue(), "image/png")},
        )
        assert resp.status_code == 400, (
            f"removed field should be rejected: {colors} -> {resp.status_code} {resp.text[:200]}"
        )
