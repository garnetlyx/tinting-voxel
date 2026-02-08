"""
Integration test fixtures for FastAPI TestClient.
"""
import io
import struct

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from api.rate_limiter import limiter
from main import app


@pytest.fixture(scope="module")
def client():
    """Module-scoped TestClient with lifespan events."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset rate limiter state before each test to avoid cross-test interference."""
    limiter.reset()
    yield


@pytest.fixture
def tiny_png_bytes():
    """Generate a minimal 4x4 PNG with 4 color quadrants."""
    img = Image.new('RGB', (4, 4))
    pixels = img.load()
    # Top-left: red, Top-right: green, Bottom-left: blue, Bottom-right: white
    for y in range(4):
        for x in range(4):
            if x < 2 and y < 2:
                pixels[x, y] = (255, 0, 0)
            elif x >= 2 and y < 2:
                pixels[x, y] = (0, 255, 0)
            elif x < 2 and y >= 2:
                pixels[x, y] = (0, 0, 255)
            else:
                pixels[x, y] = (255, 255, 255)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


@pytest.fixture
def tiny_jpeg_bytes():
    """Generate a minimal 4x4 JPEG."""
    img = Image.new('RGB', (4, 4), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    return buf.getvalue()


@pytest.fixture
def sample_color_blocks_with_hex():
    """Sample color blocks with hex field for API requests."""
    return [
        {
            'r': 255, 'g': 0, 'b': 0,
            'count': 4,
            'pixels': [{'x': 0, 'y': 0}, {'x': 1, 'y': 0}, {'x': 0, 'y': 1}, {'x': 1, 'y': 1}],
            'hex': '#FF0000'
        },
        {
            'r': 0, 'g': 255, 'b': 0,
            'count': 4,
            'pixels': [{'x': 2, 'y': 0}, {'x': 3, 'y': 0}, {'x': 2, 'y': 1}, {'x': 3, 'y': 1}],
            'hex': '#00FF00'
        },
        {
            'r': 0, 'g': 0, 'b': 255,
            'count': 4,
            'pixels': [{'x': 0, 'y': 2}, {'x': 1, 'y': 2}, {'x': 0, 'y': 3}, {'x': 1, 'y': 3}],
            'hex': '#0000FF'
        },
        {
            'r': 255, 'g': 255, 'b': 255,
            'count': 4,
            'pixels': [{'x': 2, 'y': 2}, {'x': 3, 'y': 2}, {'x': 2, 'y': 3}, {'x': 3, 'y': 3}],
            'hex': '#FFFFFF'
        },
    ]
