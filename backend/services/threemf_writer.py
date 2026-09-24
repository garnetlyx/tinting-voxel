"""3MF packaging: one printable object whose parts are the filaments.

Slicers load the file as a single object with one part per filament, so the
color layers stay in register without a "multi-part object" prompt, and every
part carries its filament's color as a standard 3MF material color (Bambu
Studio and OrcaSlicer offer to map those colors to filament slots).
"""
import zipfile
from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO
from xml.sax.saxutils import quoteattr

import numpy as np

from services.mesh_optimizer import BoxRange

# Corners of a box as (x, y, z) picks from ((x1, x2), (y1, y2), (z1, z2)), and
# its 12 triangles wound counter-clockwise seen from outside.
_CORNERS = np.array([
    [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
    [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1],
])
_BOX_TRIANGLES = np.array([
    [0, 3, 1], [1, 3, 2],
    [0, 4, 7], [0, 7, 3],
    [4, 5, 6], [4, 6, 7],
    [5, 1, 2], [5, 2, 6],
    [2, 3, 6], [3, 7, 6],
    [0, 1, 5], [0, 5, 4],
])
# Coordinates are written to 1 nm; shared corners stay identical.
_DECIMALS = 6
_ROWS_PER_WRITE = 65_536

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
    '</Types>'
)
_RELS = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
    'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
    '</Relationships>'
)


@dataclass
class Part:
    """One filament's geometry: boxes in mm, and its display color."""
    name: str
    color: str  # "#RRGGBB"
    boxes: list[BoxRange]


def write_3mf(parts: list[Part], object_name: str) -> bytes:
    """A 3MF archive holding one object assembled from the given parts."""
    parts = [part for part in parts if part.boxes]
    if not parts:
        raise ValueError("No geometry to export")
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _RELS)
        with archive.open("3D/3dmodel.model", "w", force_zip64=True) as model:
            _write_model(model, parts, object_name)
    return buffer.getvalue()


def _write_model(out: BinaryIO, parts: list[Part], object_name: str) -> None:
    out.write(
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<model unit="millimeter" xml:lang="en-US" '
        b'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
        b'xmlns:m="http://schemas.microsoft.com/3dmanufacturing/material/2015/02">'
        b'<metadata name="Application">Tinting Voxel</metadata><resources>'
        b'<m:colorgroup id="1">'
    )
    out.write("".join(f'<m:color color="{part.color.upper()}"/>' for part in parts).encode())
    out.write(b"</m:colorgroup>")
    for index, part in enumerate(parts):
        out.write(f'<object id="{index + 2}" name={quoteattr(part.name)} type="model" pid="1" pindex="{index}">'.encode())
        _write_mesh(out, part.boxes)
        out.write(b"</object>")
    assembly_id = len(parts) + 2
    out.write(f'<object id="{assembly_id}" name={quoteattr(object_name)} type="model"><components>'.encode())
    out.write("".join(f'<component objectid="{index + 2}"/>' for index in range(len(parts))).encode())
    out.write(f'</components></object></resources><build><item objectid="{assembly_id}"/></build></model>'.encode())


def _write_mesh(out: BinaryIO, boxes: list[BoxRange]) -> None:
    """Shared-vertex mesh of boxes, written a chunk of rows at a time."""
    ranges = np.round(np.asarray(boxes, dtype=np.float64), _DECIMALS)  # (boxes, axis, lo/hi)
    # Corners lie on a lattice of each axis's distinct coordinates; a corner's
    # key is its lattice position, so shared corners get one vertex.
    axis_values = [np.unique(ranges[:, axis, :]) for axis in range(3)]
    bx, by, bz = (np.searchsorted(axis_values[axis], ranges[:, axis, :]) for axis in range(3))
    del ranges
    ny, nz = len(axis_values[1]), len(axis_values[2])
    keys = (bx[:, _CORNERS[:, 0]] * ny + by[:, _CORNERS[:, 1]]) * nz + bz[:, _CORNERS[:, 2]]  # (boxes, 8)
    del bx, by, bz
    vertex_keys, box_corners = np.unique(keys.ravel(), return_inverse=True)
    del keys
    box_corners = box_corners.reshape(-1, 8)
    labels = [np.array([np.format_float_positional(v, trim="-") for v in values]) for values in axis_values]

    out.write(b"<mesh><vertices>")
    for start in range(0, len(vertex_keys), _ROWS_PER_WRITE):
        chunk = vertex_keys[start:start + _ROWS_PER_WRITE]
        rows = zip(labels[0][chunk // (nz * ny)].tolist(), labels[1][chunk // nz % ny].tolist(), labels[2][chunk % nz].tolist())
        out.write("".join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in rows).encode())
    out.write(b"</vertices><triangles>")
    boxes_per_write = _ROWS_PER_WRITE // len(_BOX_TRIANGLES)
    for start in range(0, len(box_corners), boxes_per_write):
        rows = box_corners[start:start + boxes_per_write][:, _BOX_TRIANGLES].reshape(-1, 3).tolist()
        out.write("".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in rows).encode())
    out.write(b"</triangles></mesh>")
