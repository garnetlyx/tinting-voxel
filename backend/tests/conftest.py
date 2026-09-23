"""
Pytest configuration and fixtures
"""
import os
import sys
from pathlib import Path

import pytest

# Add backend directory to path for imports
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# The app lifespan must not fetch Cloudflare's edge ranges during tests.
os.environ["CLOUDFLARE_IPS_URL"] = ""


@pytest.fixture
def sample_color_blocks():
    """Sample color blocks for testing"""
    return [
        {
            'r': 255, 'g': 0, 'b': 0,
            'count': 100,
            'pixels': [{'x': i % 10, 'y': i // 10} for i in range(100)]
        },
        {
            'r': 0, 'g': 255, 'b': 0,
            'count': 50,
            'pixels': [{'x': i % 10 + 10, 'y': i // 10} for i in range(50)]
        }
    ]


@pytest.fixture
def sample_image_dimensions():
    """Sample image dimensions for testing"""
    return {'width': 20, 'height': 10}


@pytest.fixture
def sample_pixel_map():
    """Sample pixel map for testing greedy meshing"""
    # 5x5 grid with some pixels set
    # X X X . .
    # X X X . .
    # X X X . .
    # . . . X X
    # . . . X X
    return {
        (0, 0): True, (1, 0): True, (2, 0): True,
        (0, 1): True, (1, 1): True, (2, 1): True,
        (0, 2): True, (1, 2): True, (2, 2): True,
        (3, 3): True, (4, 3): True,
        (3, 4): True, (4, 4): True,
    }
