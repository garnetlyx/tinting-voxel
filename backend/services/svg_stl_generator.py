"""Generate SVG-mode STL files from the printable pixel partition."""
from config.print_defaults import DEFAULT_BACKING_LAYERS
import logging
import zipfile
from io import BytesIO
from typing import Optional

from core.blend_color import Colors
from config.settings import settings
from services.mesh_optimizer import boxes_from_rectangles, greedy_mesh_2d
from services import stl_generator
from services.print_stack import (
    PRINT_BACKGROUND_RGB,
    backing_suffix,
    build_print_stack,
    normalize_backing_layers,
    resolve_backing_label,
    strip_backing_suffix,
)
from services.stl_generator import (
    generate_box,
    generate_boxes_batch,
    get_filename_prefix,
    layer_runs,
    merge_stl_meshes,
    _log_blend_code_distribution,
    _log_input_color_brightness,
)
from services.vector_processor import finalize_vector_partition

logger = logging.getLogger(__name__)


def generate_svg_stl_zip(
    vector_results: list[dict],
    layer_height: float,
    pixel_size: float,
    layer_count: int,
    image_dimensions: dict,
    colors: Colors,
    white_backing_layers: int = DEFAULT_BACKING_LAYERS,
    backing_mode: str = 'white',
    detail_size: Optional[float] = None,
) -> bytes:
    """
    Generate ZIP file containing STL files from vector contours.

    Uses Beer-Lambert color mapping (same as pixel mode).

    Args:
        vector_results: List of dicts with 'color' and 'regions' keys
            - color: RGB tuple (r, g, b)
            - regions: exterior rings with optional holes
        layer_height: Height of each layer in mm
        pixel_size: Physical size of each pixel in mm
        layer_count: Total number of layers
        image_dimensions: Dict with 'width' and 'height' keys
        colors: Active filament configuration.
        detail_size: Minimum printable feature width in mm.

    Returns:
        ZIP file binary content
    """
    if not vector_results:
        raise ValueError('No vector results provided')

    active_colors = colors

    # Compute reference matrices locally (thread-safe, backing-aware)
    ref_code_matrix, ref_rgb_matrix = stl_generator.compute_reference_matrices(
        layer_count, layer_height, active_colors, n_targets=len(vector_results),
        backing_layers=white_backing_layers, backing_mode=backing_mode,
    )

    # Initialize mesh map for each primary color dynamically
    code_mesh_map = {label: [] for label in active_colors.get_labels()}

    # Extract colors from vector results
    input_colors = [result['color'] for result in vector_results]

    # Map to blend codes using Beer-Lambert model (with order refinement
    # for composition-pruned translucent sets); codes carry the backing suffix.
    from services.image_processor import _map_and_refine
    _b_label = resolve_backing_label(active_colors, white_backing_layers, backing_mode)
    _b_suffix = backing_suffix(_b_label, white_backing_layers)
    _b_boundary = PRINT_BACKGROUND_RGB if _b_suffix else None
    result_codes, _ = _map_and_refine(
        input_colors, ref_code_matrix, ref_rgb_matrix,
        active_colors, layer_count, layer_height,
        backing_suffix=_b_suffix, background_rgb=_b_boundary,
    )

    _log_input_color_brightness(input_colors, "SVG-STL")
    _log_blend_code_distribution(result_codes, active_colors.get_labels(), "SVG-STL")

    width = image_dimensions['width']
    height = image_dimensions['height']
    total_regions = 0
    total_boxes = 0

    z_offset = 0.0

    n_white = normalize_backing_layers(white_backing_layers)
    w_label = resolve_backing_label(active_colors, n_white, backing_mode)
    if n_white > 0:
        logger.info("SVG-STL: printed backing mode='%s', label='%s', layers=%d", backing_mode, w_label, n_white)

    partition = finalize_vector_partition(
        vector_results, image_dimensions, pixel_size, detail_size,
    )

    # Process each color group
    for idx, result in enumerate(vector_results):
        region_grid = partition == idx
        if not region_grid.any():
            continue
        total_regions += len(result['regions'])
        blend_code = strip_backing_suffix(result_codes[idx], w_label, n_white)

        # The region is meshed once; each vertical run extrudes it.
        runs = layer_runs(blend_code, z_offset, layer_height)
        rectangles = greedy_mesh_2d(
            region_grid,
            max_rectangles=max(0, settings.stl_max_boxes - total_boxes) // max(len(runs), 1),
        )
        for code_char, z_min, z_max in runs:
            boxes = boxes_from_rectangles(rectangles, pixel_size, z_min, z_max)
            if boxes:
                total_boxes += len(boxes)
                code_mesh_map[code_char].append(generate_boxes_batch(boxes))

    logger.info(
        "SVG STL generation: %d regions -> %d boxes",
        total_regions, total_boxes
    )

    # Add white backing above optical layers (reflector behind colors)
    if n_white > 0:
        optical_top = z_offset + layer_count * layer_height
        # Merge all backing layers into a single large block to eliminate internal faces
        backing_mesh = generate_box(
            xrange=(0, width * pixel_size),
            yrange=(0, height * pixel_size),
            zrange=(optical_top,
                    optical_top + n_white * layer_height)
        )
        code_mesh_map[w_label].append(backing_mesh)
        logger.info("SVG-STL: added 1 merged white backing block thickness=%.2f mm at z=%.2f-%.2f mm",
                     n_white * layer_height, optical_top, optical_top + n_white * layer_height)

    # Merge meshes by primary color and create STL files
    stl_files = {}
    print_stack = build_print_stack(
        layer_count=layer_count,
        layer_height=layer_height,
        backing_layers=n_white,
        backing_mode=backing_mode,
    )
    physical_height = print_stack["totalHeightMm"]
    prefix = get_filename_prefix(active_colors)

    for code, meshes in code_mesh_map.items():
        if len(meshes) > 0:
            merged_stl = merge_stl_meshes(meshes)
            filename = f"{prefix}_{width}x{height}x{physical_height:.2f}_{code}.stl"
            stl_files[filename] = merged_stl

    # Create ZIP archive
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, stl_content in stl_files.items():
            zip_file.writestr(filename, stl_content)

    return zip_buffer.getvalue()
