"""
STL generation service with color mapping and mesh merging

Includes optimization via greedy meshing to reduce file sizes.
"""
import itertools
import logging
import threading
import zipfile
from io import BytesIO
from typing import Optional

import numpy as np
import pandas as pd

from core.blend_color import BlendTestGenerator, Color, Colors
from services.mesh_optimizer import generate_optimized_boxes

logger = logging.getLogger(__name__)


# Global reference matrices (initialized on app startup, used as fallback)
_reference_code_matrix = None
_reference_rgb_matrix = None
_blend_generator = None
_current_colors = None
_global_state_lock = threading.Lock()


def compute_reference_matrices(
    layer_count: int,
    layer_height: float,
    colors: Colors
) -> tuple:
    """
    Compute color reference matrices for Beer-Lambert mapping.

    Thread-safe: returns new matrices without modifying global state.

    Args:
        layer_count: Number of layers for color blending
        layer_height: Height of each layer in mm
        colors: Colors instance defining the filament configuration

    Returns:
        Tuple of (code_matrix, rgb_matrix) as DataFrames

    Raises:
        ValueError: If permutation count exceeds safety limit
    """
    if layer_count <= 0:
        raise ValueError(f"layer_count must be positive, got {layer_count}")
    generator = BlendTestGenerator(
        colors=colors,
        layer_height=layer_height,
        layer_count_max=layer_count
    )

    items = colors.get_labels()
    if not items:
        raise ValueError("Colors instance has no colors defined")
    max_permutations = 1_000_000
    permutation_count = len(items) ** layer_count
    if permutation_count > max_permutations:
        raise ValueError(
            f"Too many color permutations: {len(items)} colors x {layer_count} layers = "
            f"{permutation_count:,}. Maximum allowed is {max_permutations:,}. "
            f"Reduce the number of colors or layers."
        )
    perms = list(itertools.product(items, repeat=layer_count))
    code_list = [''.join(p) for p in perms]

    rgb_list = [generator.code_to_rgb(code) for code in code_list]

    n = len(code_list)
    rows = int(np.sqrt(n))
    cols = (n + rows - 1) // rows

    # Pad with last valid entry to avoid empty-string codes in nearest-color matching
    pad_count = rows * cols - n
    pad_code = code_list[-1] if code_list else ''
    pad_rgb = rgb_list[-1] if rgb_list else (255, 255, 255)
    code_list_padded = code_list + [pad_code] * pad_count
    rgb_list_padded = rgb_list + [pad_rgb] * pad_count

    code_matrix = [code_list_padded[i*cols:(i+1)*cols] for i in range(rows)]
    rgb_matrix = [rgb_list_padded[i*cols:(i+1)*cols] for i in range(rows)]

    code_df = pd.DataFrame(code_matrix)
    rgb_df = pd.DataFrame(rgb_matrix)

    logger.info("Computed reference matrices: %d colors, %d combinations", len(items), len(code_list))
    return code_df, rgb_df


def initialize_color_mapping(
    layer_count: int = 4,
    layer_height: float = 0.08,
    colors: Optional[Colors] = None
):
    """
    Initialize global color mapping reference matrices.

    Thread-safe: Uses lock to protect global state during initialization.

    Used for app startup caching. For request-scoped operations,
    prefer passing colors directly to generate_stl_zip() which
    computes matrices locally (thread-safe).

    Args:
        layer_count: Number of layers for color blending
        layer_height: Height of each layer in mm
        colors: Optional Colors instance. If None, uses default CMYK.
    """
    global _reference_code_matrix, _reference_rgb_matrix, _blend_generator, _current_colors

    if colors is None:
        colors = Colors()

    with _global_state_lock:
        _current_colors = colors
        _blend_generator = BlendTestGenerator(
            colors=colors,
            layer_height=layer_height,
            layer_count_max=layer_count
        )

        _reference_code_matrix, _reference_rgb_matrix = compute_reference_matrices(
            layer_count, layer_height, colors
        )


def generate_box(
    xrange: tuple[float, float],
    yrange: tuple[float, float],
    zrange: tuple[float, float]
) -> np.ndarray:
    """
    Generate a 3D box mesh for a single pixel

    Args:
        xrange: (x_min, x_max) in mm
        yrange: (y_min, y_max) in mm
        zrange: (z_min, z_max) in mm

    Returns:
        Numpy array of mesh vertices (12 triangles x 3 vertices x 3 coords)
    """
    x1, x2 = xrange
    y1, y2 = yrange
    z1, z2 = zrange

    # Validate non-negative coordinates (QA-167)
    if x1 < 0 or x2 < 0 or y1 < 0 or y2 < 0 or z1 < 0 or z2 < 0:
        raise ValueError(f"All coordinates must be non-negative, got xrange={xrange}, yrange={yrange}, zrange={zrange}")

    # Validate non-inverted ranges (QA-168)
    if x1 >= x2 or y1 >= y2 or z1 >= z2:
        raise ValueError(f"Range start must be less than end, got xrange={xrange}, yrange={yrange}, zrange={zrange}")

    # 8 vertices of the box
    vertices = np.array([
        [x1, y1, z1],
        [x2, y1, z1],
        [x2, y2, z1],
        [x1, y2, z1],
        [x1, y1, z2],
        [x2, y1, z2],
        [x2, y2, z2],
        [x1, y2, z2]
    ])

    # 12 triangular faces (2 per box face)
    faces = np.array([
        [0, 3, 1], [1, 3, 2],  # bottom
        [0, 4, 7], [0, 7, 3],  # left
        [4, 5, 6], [4, 6, 7],  # top
        [5, 1, 2], [5, 2, 6],  # right
        [2, 3, 6], [3, 7, 6],  # back
        [0, 1, 5], [0, 5, 4]   # front
    ])

    # Create mesh data (triangles with vertices)
    mesh_data = vertices[faces]

    return mesh_data


def merge_stl_meshes(meshes: list[np.ndarray]) -> bytes:
    """
    Merge multiple mesh arrays into a single STL binary format

    Args:
        meshes: List of mesh arrays (each is Nx3x3 array of triangles)

    Returns:
        Binary STL file content
    """
    if not meshes:
        # Return valid empty STL: 80-byte header + uint32(0) triangle count
        return b' ' * 80 + np.uint32(0).tobytes()

    # Concatenate all meshes
    all_triangles = np.concatenate(meshes, axis=0)
    num_triangles = len(all_triangles)

    # STL binary format:
    # - 80 bytes header
    # - 4 bytes: number of triangles (uint32)
    # - For each triangle (50 bytes):
    #   - 12 bytes: normal vector (3 floats)
    #   - 36 bytes: 3 vertices (9 floats)
    #   - 2 bytes: attribute byte count (uint16)

    buffer = BytesIO()

    # Write header (80 bytes)
    buffer.write(b' ' * 80)

    # Write number of triangles
    buffer.write(np.uint32(num_triangles).tobytes())

    # Write each triangle
    for triangle in all_triangles:
        # Calculate normal vector
        v1, v2, v3 = triangle
        edge1 = v2 - v1
        edge2 = v3 - v1
        normal = np.cross(edge1, edge2)
        norm_length = np.linalg.norm(normal)
        if norm_length > 0:
            normal = normal / norm_length
        else:
            normal = np.array([0, 0, 1])

        # Write normal (3 float32)
        buffer.write(normal.astype(np.float32).tobytes())

        # Write 3 vertices (9 float32)
        buffer.write(v1.astype(np.float32).tobytes())
        buffer.write(v2.astype(np.float32).tobytes())
        buffer.write(v3.astype(np.float32).tobytes())

        # Write attribute byte count (uint16, always 0)
        buffer.write(np.uint16(0).tobytes())

    return buffer.getvalue()


def get_filename_prefix(colors: Colors) -> str:
    """
    Generate filename prefix from color labels.

    Maintains backward compatibility: CMYW produces "CMYW" prefix.

    Args:
        colors: Colors instance

    Returns:
        String prefix for filenames
    """
    labels = colors.get_labels()
    # Backward compatibility: if labels are exactly C, M, Y, W in any order,
    # and we have exactly 4 colors, use CMYW for consistency
    if set(labels) == {'C', 'M', 'Y', 'W'} and len(labels) == 4:
        return "CMYW"
    return ''.join(labels)


def generate_stl_zip(
    color_blocks: list[dict],
    layer_height: float,
    pixel_size: float,
    layer_count: int,
    image_dimensions: dict,
    use_greedy_meshing: bool = True,
    colors: Optional[Colors] = None,
    base_plate_thickness: float = 0.0,
    double_sided: bool = False,
) -> bytes:
    """
    Generate ZIP file containing merged STL files by primary color

    Args:
        color_blocks: List of color blocks with RGB and pixels
        layer_height: Height of each layer in mm
        pixel_size: Physical size of each pixel in mm
        layer_count: Total number of layers
        image_dimensions: Dict with 'width' and 'height' keys
        use_greedy_meshing: If True, merge adjacent pixels to reduce file size
        colors: Optional Colors instance. If None, uses current global colors.
        base_plate_thickness: Thickness of solid base plate in mm (0 = no base plate)
        double_sided: If True, generate mirrored back side layers on top

    Returns:
        ZIP file binary content
    """
    if not color_blocks:
        raise ValueError("No color blocks provided")

    # Use provided colors or fall back to global state (thread-safe read)
    if colors is not None:
        active_colors = colors
    else:
        with _global_state_lock:
            active_colors = _current_colors

    if active_colors is None:
        raise RuntimeError("No colors provided and no global colors initialized.")

    # Compute reference matrices locally (thread-safe)
    ref_code_matrix, ref_rgb_matrix = compute_reference_matrices(
        layer_count, layer_height, active_colors
    )

    # Step 1: Initialize primary color mesh map dynamically
    code_mesh_map = {label: [] for label in active_colors.get_labels()}

    # Step 2: Extract all input colors
    input_colors = [(block['r'], block['g'], block['b']) for block in color_blocks]

    # Step 3: Map to blend codes using map_to_nearest_color
    result_codes, result_rgbs = Color.map_to_nearest_color(
        input_colors,
        ref_code_matrix,
        ref_rgb_matrix
    )

    width, height = image_dimensions['width'], image_dimensions['height']
    total_original_boxes = 0
    total_optimized_boxes = 0

    # Z offset: color layers sit on top of base plate
    z_offset = base_plate_thickness if base_plate_thickness > 0 else 0.0

    # Step 4: Generate meshes for each color block
    for idx, color_block in enumerate(color_blocks):
        pixels = color_block['pixels']
        blend_code = result_codes[idx]  # e.g., "CCCM"

        # Generate mesh for each layer
        for z_idx, code_char in enumerate(blend_code):
            z_min = z_offset + z_idx * layer_height
            z_max = z_offset + (z_idx + 1) * layer_height

            if use_greedy_meshing and len(pixels) > 1:
                # Use greedy meshing to merge adjacent pixels
                optimized_boxes = generate_optimized_boxes(
                    pixels=pixels,
                    width=width,
                    height=height,
                    pixel_size=pixel_size,
                    z_min=z_min,
                    z_max=z_max
                )
                total_original_boxes += len(pixels)
                total_optimized_boxes += len(optimized_boxes)

                for xrange, yrange, zrange in optimized_boxes:
                    mesh = generate_box(xrange, yrange, zrange)
                    code_mesh_map[code_char].append(mesh)
            else:
                # Original per-pixel box generation
                total_original_boxes += len(pixels)
                total_optimized_boxes += len(pixels)
                for pixel in pixels:
                    x, y = pixel['x'], pixel['y']
                    mesh = generate_box(
                        xrange=(x * pixel_size, (x + 1) * pixel_size),
                        yrange=(y * pixel_size, (y + 1) * pixel_size),
                        zrange=(z_min, z_max)
                    )
                    code_mesh_map[code_char].append(mesh)

    # Step 4b: Generate back-side (mirrored) layers if double-sided
    if double_sided:
        front_top = z_offset + layer_count * layer_height
        for idx, color_block in enumerate(color_blocks):
            pixels = color_block['pixels']
            blend_code = result_codes[idx]

            # Mirror pixels horizontally: x -> (width - 1 - x)
            mirrored_pixels = [
                {'x': width - 1 - p['x'], 'y': p['y']}
                for p in pixels
            ]

            # Back layers are stacked on top of front, in reverse order
            for z_idx, code_char in enumerate(reversed(blend_code)):
                z_min = front_top + z_idx * layer_height
                z_max = front_top + (z_idx + 1) * layer_height

                if use_greedy_meshing and len(mirrored_pixels) > 1:
                    optimized_boxes = generate_optimized_boxes(
                        pixels=mirrored_pixels,
                        width=width,
                        height=height,
                        pixel_size=pixel_size,
                        z_min=z_min,
                        z_max=z_max
                    )
                    for xrange, yrange, zrange in optimized_boxes:
                        mesh = generate_box(xrange, yrange, zrange)
                        code_mesh_map[code_char].append(mesh)
                else:
                    for pixel in mirrored_pixels:
                        x, y = pixel['x'], pixel['y']
                        mesh = generate_box(
                            xrange=(x * pixel_size, (x + 1) * pixel_size),
                            yrange=(y * pixel_size, (y + 1) * pixel_size),
                            zrange=(z_min, z_max)
                        )
                        code_mesh_map[code_char].append(mesh)

        logger.info("Generated double-sided print: front + mirrored back")

    if use_greedy_meshing and total_original_boxes > 0:
        reduction = (1 - total_optimized_boxes / total_original_boxes) * 100
        logger.info(
            "Greedy meshing: %d -> %d boxes (%.1f%% reduction)",
            total_original_boxes, total_optimized_boxes, reduction
        )

    # Step 5: Merge meshes by primary color and create STL files
    stl_files = {}
    effective_layer_count = layer_count * 2 if double_sided else layer_count
    physical_height = effective_layer_count * layer_height + z_offset
    prefix = get_filename_prefix(active_colors)

    for code, meshes in code_mesh_map.items():
        if len(meshes) > 0:
            # Merge all meshes for this primary color
            merged_stl = merge_stl_meshes(meshes)

            # Generate filename: PREFIX_208x208x3.36_C.stl
            filename = f"{prefix}_{width}x{height}x{physical_height:.2f}_{code}.stl"

            stl_files[filename] = merged_stl

    # Step 5b: Generate base plate if thickness > 0
    if base_plate_thickness > 0:
        base_mesh = generate_box(
            xrange=(0, width * pixel_size),
            yrange=(0, height * pixel_size),
            zrange=(0, base_plate_thickness)
        )
        base_stl = merge_stl_meshes([base_mesh])
        base_filename = f"{prefix}_{width}x{height}x{physical_height:.2f}_base.stl"
        stl_files[base_filename] = base_stl
        logger.info("Generated base plate: %.2f x %.2f x %.2f mm",
                     width * pixel_size, height * pixel_size, base_plate_thickness)

    # Step 6: Create ZIP archive
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, stl_content in stl_files.items():
            zip_file.writestr(filename, stl_content)

    return zip_buffer.getvalue()
