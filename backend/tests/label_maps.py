"""Label-map inputs (services/label_map.py) built from pixel-list color blocks."""
import base64

import numpy as np

from services.label_map import EMPTY


def _as_dicts(color_blocks: list) -> list[dict]:
    return [block.model_dump() if hasattr(block, 'model_dump') else block for block in color_blocks]


def labels_from_blocks(color_blocks: list, width: int, height: int) -> np.ndarray:
    """The label map of blocks given as pixel lists (dicts or ColorBlock models)."""
    labels = np.full((height, width), EMPTY, dtype=np.uint8)
    for index, block in enumerate(_as_dicts(color_blocks)):
        for pixel in block['pixels']:
            labels[pixel['y'], pixel['x']] = index
    return labels


def label_map_request(color_blocks: list, width: int, height: int) -> dict:
    """The colorBlocks, labelMap and imageDimensions fields of an export or preview request."""
    color_blocks = _as_dicts(color_blocks)
    return {
        'colorBlocks': [
            {'r': b['r'], 'g': b['g'], 'b': b['b'], 'hex': b.get('hex', f"#{b['r']:02x}{b['g']:02x}{b['b']:02x}")}
            for b in color_blocks
        ],
        'labelMap': base64.b64encode(labels_from_blocks(color_blocks, width, height).tobytes()).decode(),
        'imageDimensions': {'width': width, 'height': height},
    }
