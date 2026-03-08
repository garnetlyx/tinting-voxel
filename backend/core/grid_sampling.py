import ast
import math
import os.path
import re

import numpy as np
import pandas as pd
from PIL import Image


def image_to_rgb_matrix(image_path, grid_size=16, sample_fraction=0.4, method="mean", save_samples=False, sample_directory=None):
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    cell_w, cell_h = w / grid_size, h / grid_size
    arr = np.array(img)

    rgb_matrix = []
    for row in range(grid_size):
        row_colors = []
        for col in range(grid_size):
            x0 = int(col * cell_w)
            x1 = int((col + 1) * cell_w)
            y0 = int(row * cell_h)
            y1 = int((row + 1) * cell_h)

            margin_x = int((1 - sample_fraction) * (x1 - x0) / 2)
            margin_y = int((1 - sample_fraction) * (y1 - y0) / 2)
            xs, xe = x0 + margin_x, x1 - margin_x
            ys, ye = y0 + margin_y, y1 - margin_y

            patch = arr[ys:ye, xs:xe, :]
            if method == "median":
                color = tuple(np.median(patch.reshape(-1, 3), axis=0).astype(int))
            else:
                color = tuple(np.mean(patch.reshape(-1, 3), axis=0).astype(int))
            row_colors.append(color)

            if save_samples and sample_directory is not None:
                filename = f"tile{row}_{col}.png"
                file_path = os.path.join(sample_directory, filename)
                os.makedirs(sample_directory, exist_ok=True)
                cell = img.crop((xs, ys, xe, ye))
                cell.save(file_path)
        rgb_matrix.append(row_colors)

    return pd.DataFrame(rgb_matrix)


def matrix_to_code_color_map(df_rgb, df_code):
    mapping = {}
    n_rows, n_cols = df_rgb.shape

    for r in range(n_rows):
        for c in range(n_cols):
            code = df_code.iloc[r, c]
            rgb = df_rgb.iloc[r, c]
            mapping[code] = rgb
    return mapping


def color_variance(df_ref, df_photo, new_df_rgb, new_df_code, labels):
    rows, cols = df_ref.shape
    if df_ref.shape != df_photo.shape:
        return None

    code_color_map = matrix_to_code_color_map(new_df_rgb, new_df_code)
    diffs = np.zeros((rows, cols))
    max_diff = math.sqrt(255**2 * 3)

    for y_idx in range(df_ref.shape[0]):
        for x_idx in range(df_ref.shape[1]):
            photo_code = df_ref.iat[y_idx, x_idx][0]
            photo_rgb = df_photo.iat[y_idx, x_idx]
            new_rgb = code_color_map[photo_code]
            diff = math.sqrt(
                (new_rgb[0] - photo_rgb[0]) ** 2
                + (new_rgb[1] - photo_rgb[1]) ** 2
                + (new_rgb[2] - photo_rgb[2]) ** 2
            ) / max_diff
            diffs[y_idx, x_idx] = round(diff, 2)

    avg = np.average(pd.DataFrame(diffs))
    wrong_color_count = dict.fromkeys(labels, 0)
    for y_idx in range(df_ref.shape[0]):
        for x_idx in range(df_ref.shape[1]):
            if diffs[y_idx, x_idx] > avg:
                code, _ = df_ref.iloc[y_idx][x_idx]
                for c in code:
                    wrong_color_count[c] = wrong_color_count[c] + diffs[y_idx, x_idx]
    return avg


def parse_cell(s):
    if pd.isna(s):
        return s
    if not isinstance(s, str):
        return s
    s2 = re.sub(r"np\.float64\(([^)]+)\)", r"\1", s)
    try:
        return ast.literal_eval(s2)
    except Exception:
        return s2
