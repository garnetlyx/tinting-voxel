import numpy as np
from stl import mesh


def generate_box(xrange, yrange, zrange):
    x1, x2 = xrange
    y1, y2 = yrange
    z1, z2 = zrange

    if x1 < 0 or x2 < 0:
        raise ValueError(f"X coordinates must be non-negative, got ({x1}, {x2})")
    if y1 < 0 or y2 < 0:
        raise ValueError(f"Y coordinates must be non-negative, got ({y1}, {y2})")
    if z1 < 0 or z2 < 0:
        raise ValueError(f"Z coordinates must be non-negative, got ({z1}, {z2})")

    if x1 >= x2:
        raise ValueError(f"X range start must be less than end, got ({x1}, {x2})")
    if y1 >= y2:
        raise ValueError(f"Y range start must be less than end, got ({y1}, {y2})")
    if z1 >= z2:
        raise ValueError(f"Z range start must be less than end, got ({z1}, {z2})")

    vertices = np.array(
        [
            [x1, y1, z1],
            [x2, y1, z1],
            [x2, y2, z1],
            [x1, y2, z1],
            [x1, y1, z2],
            [x2, y1, z2],
            [x2, y2, z2],
            [x1, y2, z2],
        ]
    )

    faces = np.array(
        [
            [0, 3, 1],
            [1, 3, 2],
            [0, 4, 7],
            [0, 7, 3],
            [4, 5, 6],
            [4, 6, 7],
            [5, 1, 2],
            [5, 2, 6],
            [2, 3, 6],
            [3, 7, 6],
            [0, 1, 5],
            [0, 5, 4],
        ]
    )

    box = mesh.Mesh(np.zeros(faces.shape[0], dtype=mesh.Mesh.dtype))
    for i, f in enumerate(faces):
        for j in range(3):
            box.vectors[i][j] = vertices[f[j], :]

    return box


def merge_stl_meshes(mesh_list):
    total_faces = sum(m.data.shape[0] for m in mesh_list)
    combined = mesh.Mesh(np.zeros(total_faces, dtype=mesh.Mesh.dtype))

    current_index = 0
    for m in mesh_list:
        n = m.data.shape[0]
        combined.data[current_index:current_index + n] = m.data
        current_index += n

    return combined
