"""
Filament preview service for generating color matrix previews.

Generates a visual preview showing all achievable colors from a given
filament configuration using Beer-Lambert optical blending.
"""
import base64
import colorsys
import itertools
import logging
from io import BytesIO
from typing import List

import numpy as np
from PIL import Image, ImageDraw
from skimage.color import rgb2lab

from core.blend_color import BlendTestGenerator, Colors
from config.print_defaults import DEFAULT_BACKING_LAYERS
from services.print_stack import resolve_backing_label, backing_suffix, PRINT_BACKGROUND_RGB

logger = logging.getLogger(__name__)

# Gamut preview render bounds: cells shrink for large grids so the decoded
# image stays browser-safe; the combination data itself is never capped.
BASE_CELL_SIZE_PX = 12
MAX_PREVIEW_EDGE_PX = 2048


class FilamentPreviewService:
    """
    Generate preview images and color analysis for filament configurations.

    Given a set of filament colors, generates a matrix of all possible
    color combinations and renders them as a grid image.
    """

    def __init__(self, colors: Colors, layer_count: int = 4, layer_height: float = 0.08,
                 backing_layers: int = DEFAULT_BACKING_LAYERS, backing_mode: str = "white"):
        self.colors = colors
        self.layer_count = layer_count
        self.layer_height = layer_height
        label = resolve_backing_label(colors, backing_layers, backing_mode)
        suffix = backing_suffix(label, backing_layers)
        self.generator = BlendTestGenerator(
            colors=colors,
            layer_height=layer_height,
            layer_count_max=layer_count,
            verbose=False,
            backing_suffix=suffix,
            background_rgb=PRINT_BACKGROUND_RGB if suffix else None,
        )

    def generate_preview(self, page: int = None, page_size: int = None) -> dict:
        """
        Generate a color matrix preview for the current filament configuration.

        Args:
            page: 1-based page number for paginated results. None for all results.
            page_size: Number of entries per page. Required when page is set.

        Returns:
            dict with keys:
                - image: base64-encoded PNG of the color grid
                - colorMatrix: list of {code, rgb} entries
                - stats: {colorCount, combinationCount}
                - imageDimensions: {width, height}
                - pagination: (only when page is set) {page, pageSize, totalCombinations, totalPages}
        """
        labels = self.colors.get_labels()
        num_colors = len(labels)

        # Time-budget guard (same policy as compute_reference_matrices):
        # the probe-extrapolated blend cost decides affordability; pagination
        # is the caller's escape hatch for very large grids.
        permutation_count = num_colors ** self.layer_count
        from config.settings import settings
        from services.stl_generator import _estimate_full_enumeration_seconds
        estimated = _estimate_full_enumeration_seconds(permutation_count, 1)
        if estimated > settings.full_enumeration_budget_seconds and page is None:
            raise ValueError(
                f"Preview grid for {num_colors} colors x {self.layer_count} layers "
                f"({permutation_count:,} cells) is estimated at {estimated:.0f}s, over "
                f"the {settings.full_enumeration_budget_seconds:.0f}s budget. "
                f"Request a page (page/page_size) or reduce colors/layers."
            )

        # Generate the requested slice of codes (paginated requests decode
        # flat indices without materializing the full product).
        if page is not None and page_size is not None:
            total_pages = max(1, int(np.ceil(permutation_count / page_size)))
            if page > total_pages:
                raise ValueError(
                    f"Page {page} is out of range. Total pages: {total_pages} "
                    f"({permutation_count} combinations, page_size={page_size})."
                )
            start_idx = (page - 1) * page_size
            end_idx = min(start_idx + page_size, permutation_count)
            codes = []
            for idx in range(start_idx, end_idx):
                rem = idx
                chars = [''] * self.layer_count
                for pos in range(self.layer_count - 1, -1, -1):
                    chars[pos] = labels[rem % num_colors]
                    rem //= num_colors
                codes.append(''.join(chars))
        else:
            codes = [''.join(p) for p in itertools.product(labels, repeat=self.layer_count)]
        num_combos = permutation_count

        # Vectorized batch blend (the only production blend path)
        rgbs = self.generator.codes_to_rgb(codes)
        color_matrix = []
        for code, rgb in zip(codes, rgbs):
            rgb_int = (
                max(0, min(255, int(round(rgb[0])))),
                max(0, min(255, int(round(rgb[1])))),
                max(0, min(255, int(round(rgb[2])))),
            )
            color_matrix.append({"code": code, "rgb": list(rgb_int)})

        # Sort by hue then lightness for visual arrangement
        for entry in color_matrix:
            r, g, b = [v / 255.0 for v in entry["rgb"]]
            h, l, s = colorsys.rgb_to_hls(r, g, b)
            entry["_hue"] = h
            entry["_light"] = l

        color_matrix.sort(key=lambda e: (e["_hue"], e["_light"]))

        # Pagination was applied when generating the code slice above.
        is_paginated = page is not None and page_size is not None
        page_matrix = color_matrix

        # Render grid image for the current page's entries. Swatches are viewed
        # at display resolution, so shrink cells instead of emitting
        # multi-megapixel images — a 390k-combination grid at 12px cells is
        # 7500x7500 and freezes the browser tab decoding ~225MB of pixels.
        page_count = len(page_matrix)
        if page_count > 0:
            cols = int(np.ceil(np.sqrt(page_count)))
            rows = int(np.ceil(page_count / cols))
        else:
            cols = 0
            rows = 0
        cell_size = max(1, min(BASE_CELL_SIZE_PX, MAX_PREVIEW_EDGE_PX // max(cols, rows, 1)))
        img_width = max(1, cols * cell_size)
        img_height = max(1, rows * cell_size)

        img = Image.new('RGB', (img_width, img_height), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        for idx, entry in enumerate(page_matrix):
            col = idx % cols if cols > 0 else 0
            row = idx // cols if cols > 0 else 0
            x0 = col * cell_size
            y0 = row * cell_size
            rgb_tuple = tuple(entry["rgb"])
            draw.rectangle([x0, y0, x0 + cell_size - 1, y0 + cell_size - 1], fill=rgb_tuple)

        # Encode as base64 PNG
        buf = BytesIO()
        img.save(buf, format='PNG')
        image_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

        # Clean up sort keys
        clean_matrix = [{"code": e["code"], "rgb": e["rgb"]} for e in page_matrix]

        logger.info(
            "Generated filament preview: %d colors, %d combinations, %dx%d image",
            num_colors, num_combos, img_width, img_height
        )

        result = {
            "image": image_b64,
            "colorMatrix": clean_matrix,
            "stats": {
                "colorCount": num_colors,
                "combinationCount": num_combos,
            },
            "imageDimensions": {
                "width": img_width,
                "height": img_height,
            },
        }

        if is_paginated:
            result["pagination"] = {
                "page": page,
                "pageSize": page_size,
                "totalCombinations": num_combos,
                "totalPages": total_pages,
            }

        return result

    def check_similar_colors(self, threshold: float = 10.0) -> List[str]:
        """
        Check for similar filament colors that may produce indistinguishable results.

        Uses CIELAB color space for perceptual distance measurement.

        Args:
            threshold: Minimum CIELAB distance between colors. Pairs closer
                than this are flagged.

        Returns:
            List of warning strings for similar color pairs.
        """
        labels = self.colors.get_labels()
        warnings = []

        if len(labels) < 2:
            return warnings

        # Collect RGB values for each color
        color_rgbs = []
        color_names = []
        for label in labels:
            color = self.colors[label]
            color_rgbs.append(list(color.rgb))
            color_names.append(color.name)

        # Convert to LAB
        rgb_array = np.array(color_rgbs) / 255.0
        lab_array = rgb2lab(rgb_array.reshape(-1, 1, 3)).reshape(-1, 3)

        # Check pairwise distances
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                dist = np.linalg.norm(lab_array[i] - lab_array[j])
                if dist < threshold:
                    warnings.append(
                        f"{color_names[i]} and {color_names[j]} are very similar "
                        f"(distance: {dist:.1f})"
                    )

        return warnings
