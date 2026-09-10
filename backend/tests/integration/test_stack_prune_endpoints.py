"""
Endpoint regression: an edited Clear palette (custom filamentColors carrying
measured td_rgb / td_neutral) must keep per-channel blending and the
translucent prune regime through the process-image request path.
"""
import io
import json

from PIL import Image

EDITED_CLEAR = [
        {"name": "Cyan", "hex": "#5489B4", "transmission_distance": 4.7,
         "alpha": 12.0, "k": 1.93, "td_rgb": [1.04, 4.66, 8.30], "td_neutral": 48.9,
         "td_scale": 1.0, "td_gamma": 1.0},
        {"name": "Magenta", "hex": "#DE5740", "transmission_distance": 6.3,
         "alpha": 12.0, "k": 1.44, "td_rgb": [12.87, 2.39, 3.70], "td_neutral": 100,
         "td_scale": 1.0, "td_gamma": 1.0},
        {"name": "Yellow", "hex": "#DDC465", "transmission_distance": 10.1,
         "alpha": 12.0, "k": 0.67, "td_rgb": [15.13, 12.29, 2.81], "td_neutral": 100,
         "td_scale": 1.0, "td_gamma": 1.0},
        {"name": "White", "hex": "#D9D6C5", "transmission_distance": 18.0,
         "alpha": 12.0, "k": 0.11, "td_rgb": [17.95, 18.90, 17.21], "td_neutral": 100,
         "td_scale": 1.0, "td_gamma": 1.0},
        {"name": "Grey", "hex": "#9A9D9C", "transmission_distance": 1.7,
         "alpha": 12.0, "k": 10.0, "td_rgb": [2.23, 1.69, 1.19], "td_neutral": 7.3,
         "td_scale": 1.0, "td_gamma": 1.0},
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
