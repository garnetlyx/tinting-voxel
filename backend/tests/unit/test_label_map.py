"""Label-map requests: the model grid as one byte per cell (services/label_map.py)."""
import base64

import numpy as np
import pytest
from pydantic import ValidationError

from api.models import DownloadSTLRequestV2
from config.settings import settings
from services.label_map import EMPTY, block_cell_counts, block_pixels, decode_label_map


def _encode(labels: np.ndarray) -> str:
    return base64.b64encode(labels.astype(np.uint8).tobytes()).decode()


def test_decodes_row_major_cells():
    labels = np.array([[0, 1, EMPTY], [1, 1, 0]], dtype=np.uint8)
    decoded = decode_label_map(_encode(labels), 3, 2, 2)
    assert np.array_equal(decoded, labels)
    assert block_cell_counts(decoded, 2).tolist() == [2, 3]
    assert block_pixels(decoded, 2) == [
        [{'x': 0, 'y': 0}, {'x': 2, 'y': 1}],
        [{'x': 1, 'y': 0}, {'x': 0, 'y': 1}, {'x': 1, 'y': 1}],
    ]


@pytest.mark.parametrize("encoded,width,height,blocks,message", [
    ("not base64!", 2, 2, 1, "not valid base64"),
    (_encode(np.zeros(3)), 2, 2, 1, "has 3 cells; a 2x2 model has 4"),
    (_encode(np.full(4, EMPTY)), 2, 2, 1, "covers no cells"),
    (_encode(np.array([0, 0, 2, 0])), 2, 2, 2, "refers to block 2; there are 2 blocks"),
])
def test_rejects_malformed_maps(encoded, width, height, blocks, message):
    with pytest.raises(ValueError, match=message):
        decode_label_map(encoded, width, height, blocks)


def _request(width: int, height: int, labels: np.ndarray) -> dict:
    return {
        "colorBlocks": [{"r": 255, "g": 0, "b": 0, "hex": "#ff0000"}],
        "labelMap": _encode(labels),
        "imageDimensions": {"width": width, "height": height},
        "layerHeight": 0.08, "pixelSize": 0.1, "layerCount": 4,
    }


def test_request_exposes_the_decoded_labels():
    request = DownloadSTLRequestV2(**_request(2, 2, np.zeros((2, 2))))
    assert request.labels.shape == (2, 2) and int(request.labels.sum()) == 0


def test_request_over_the_model_grid_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "max_model_cells", 3)
    with pytest.raises(ValidationError, match="exceeds the 3-cell model grid"):
        DownloadSTLRequestV2(**_request(2, 2, np.zeros((2, 2))))
