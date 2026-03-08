import colorsys
import itertools

import numpy as np
import pandas as pd

from core.color_materials import Color


def combined_permutation_matrix(items, count):
    if not items:
        raise ValueError("items list cannot be empty for combined_permutation_matrix")
    if count < 1:
        raise ValueError(f"count must be at least 1, got {count}")

    matrix = []
    for first in items:
        row = [first]
        for length in range(2, count + 1):
            combos = [first + "".join(p) for p in itertools.product(items, repeat=length - 1)]
            row.extend(combos)
        matrix.append(row)
    max_len = max(len(r) for r in matrix)

    for r in matrix:
        while len(r) < max_len:
            r.append("[]")

    cols = [l for l in range(max_len)]
    rows = [r for r in range(len(items))]
    return pd.DataFrame(matrix, index=rows, columns=cols)


def permutation_matrix(items, count):
    if not items:
        raise ValueError("items list cannot be empty for permutation_matrix")
    if count <= 0:
        raise ValueError(f"count must be positive, got {count}")
    perms = list(itertools.product(items, repeat=count))
    joined = ["".join(p) for p in perms]
    row = len(items)
    col = len(joined) // row
    matrix = [joined[i * col:(i + 1) * col] for i in range(row)]
    return pd.DataFrame(matrix)


def reshape_matrix(df, grid_length, grid_width, length_total, reshape, verbose=False, logger=None):
    split_num_x = df.shape[0] * df.shape[1] * grid_length // length_total
    if split_num_x == 0:
        return df, grid_length, grid_width
    split_num_y = df.shape[0] * df.shape[1] // split_num_x

    if split_num_x > 0 and reshape:
        df = pd.DataFrame(np.reshape(df, (split_num_y, split_num_x)))

    if verbose and logger is not None:
        logger.debug(
            "Length per cell: %.2f, Width per cell: %s",
            grid_length,
            grid_width,
        )
    return df, grid_length, grid_width


def set_code_rgb_df(df, code_to_rgb, sort_color=True):
    records = []
    n_rows, n_cols = df.shape

    for r in range(n_rows):
        for c in range(n_cols):
            code = df.iloc[r, c]
            rgb = code_to_rgb(code)
            h, l, s = colorsys.rgb_to_hls(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
            tone = 2
            if Color.is_neutral(rgb, 15.5):
                tone = 0
            if Color.is_brown(rgb):
                tone = 1
            records.append(
                {
                    "old_row": r,
                    "old_col": c,
                    "rgb": rgb,
                    "code": code,
                    "hue": h,
                    "light": l,
                    "saturation": s,
                    "tone": tone,
                }
            )

    if not sort_color:
        df_rgb = pd.DataFrame(index=range(n_rows), columns=range(n_cols), dtype=object)
        df_code = pd.DataFrame(index=range(n_rows), columns=range(n_cols), dtype=object)
        for record in records:
            df_rgb.iloc[record["old_row"], record["old_col"]] = record["rgb"]
            df_code.iloc[record["old_row"], record["old_col"]] = record["code"]
        return df_rgb, df_code

    sorted_records = pd.DataFrame(records).sort_values(
        by=["tone", "hue"], ascending=[False, True]
    ).reset_index(drop=True)
    df_rgb = pd.DataFrame(index=range(n_rows), columns=range(n_cols), dtype=object)
    df_code = pd.DataFrame(index=range(n_rows), columns=range(n_cols), dtype=object)

    indices = np.array_split(range(len(sorted_records)), n_cols)
    for new_c, idx_group in enumerate(indices):
        col_group = sorted_records.iloc[idx_group]
        col_sorted = col_group.sort_values(
            by=["tone", "light", "code"], ascending=[False, False, True]
        ).reset_index(drop=True)
        for new_r in range(min(n_rows, len(col_sorted))):
            df_rgb.iloc[new_r, new_c] = col_sorted.loc[new_r]["rgb"]
            df_code.loc[new_r, new_c] = col_sorted.loc[new_r]["code"]
    return df_rgb, df_code
