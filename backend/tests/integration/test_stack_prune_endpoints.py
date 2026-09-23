"""Single TD payloads reach processing; obsolete optical fields are rejected."""
import io
import json

from PIL import Image

EDITED_CLEAR = [
        {"name": "Cyan", "hex": "#5489B4", "transmission_distance": 4.7},
        {"name": "Magenta", "hex": "#DE5740", "transmission_distance": 6.3},
        {"name": "Yellow", "hex": "#DDC465", "transmission_distance": 10.1},
        {"name": "White", "hex": "#D9D6C5", "transmission_distance": 18.0},
    ]


ACCEPTED_FIELD_VARIANTS = [
    {"name": "Cyan", "hex": "#5489B4", "transmission_distance": 4.7},
    {"name": "Cyan", "hex": "#5489B4", "transmission_distance": [1.0, 2.0, 3.0]},
]

REMOVED_FIELDS = [
    {"name": "Cyan", "hex": "#5489B4", "transmission_distance": 4.7, field: value}
    for field, value in {
        "td_rgb": [1., 2., 3.], "td_neutral": 48.9, "alpha": 12., "k": 0.,
        "k_rgb": [1., 2., 3.], "alpha_s": 2.2292, "td_scale": 1.48, "td_gamma": .2,
    }.items()
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


def test_current_schema_fields_are_accepted(client):
    """Both TD input shapes use the current production model."""
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (200, 60, 60)).save(buf, format="PNG")
    for variant in ACCEPTED_FIELD_VARIANTS:
        siblings = [
            {"name": "Magenta", "hex": "#DE5740", "transmission_distance": 6.3},
            {"name": "Yellow", "hex": "#DDC465", "transmission_distance": 10.1},
            {"name": "White", "hex": "#D9D6C5", "transmission_distance": 18.0},
        ]
        resp = client.post(
            "/api/process-image",
            data={
                "mode": "pixel",
                "filamentColors": json.dumps([variant] + siblings),
                "layerCount": "4",
                "layerHeight": "0.84",
                "pixelSize": "0.42",
                "maxColors": "8",
            },
            files={"image": ("t.png", buf.getvalue(), "image/png")},
        )
        assert resp.status_code == 200, (
            f"live field variant should be accepted: {variant} -> {resp.status_code} {resp.text[:200]}"
        )


def test_removed_schema_fields_are_rejected(client):
    """Obsolete clients sending deleted fields must fail loudly, not get
    silently changed optical behavior."""
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (200, 60, 60)).save(buf, format="PNG")
    siblings = [
        {"name": "Magenta", "hex": "#DE5740", "transmission_distance": 6.3},
        {"name": "Yellow", "hex": "#DDC465", "transmission_distance": 10.1},
        {"name": "White", "hex": "#D9D6C5", "transmission_distance": 18.0},
    ]
    for colors in REMOVED_FIELDS:
        removed_field = next(k for k in colors if k not in siblings[0])
        resp = client.post(
            "/api/process-image",
            data={
                "mode": "pixel",
                "filamentColors": json.dumps([colors] + siblings),
                "layerCount": "4",
                "layerHeight": "0.08",
                "pixelSize": "0.42",
            },
            files={"image": ("t.png", buf.getvalue(), "image/png")},
        )
        assert resp.status_code == 400, (
            f"removed field should be rejected: {colors} -> {resp.status_code} {resp.text[:200]}"
        )
        assert removed_field in resp.text, (
            f"rejection should name the removed field {removed_field}: {resp.text[:200]}"
        )
