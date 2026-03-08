import logging
import math
import os.path
from typing import Optional

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

from core.blend_models import (
    _blend_hybrid,
    _blend_hybrid_per_color,
    _blend_kromacut,
    _blend_per_channel,
    _code_to_rgb_cached,
    clear_rgb_cache,
    rgb_cache_info,
)
from core.code_grid import (
    combined_permutation_matrix,
    permutation_matrix,
    reshape_matrix as reshape_code_matrix,
    set_code_rgb_df as build_code_rgb_df,
)
from core.color_materials import Color, Colors
from core.grid_sampling import (
    color_variance as compute_color_variance,
    image_to_rgb_matrix as sample_image_to_rgb_matrix,
    matrix_to_code_color_map,
    parse_cell,
)
from core.plate_geometry import generate_box, merge_stl_meshes

logger = logging.getLogger(__name__)


class BlendTestGenerator:
    def __init__(
        self,
        plate_length=13 * 16,
        plate_width=13 * 16,
        grid_length=13,
        grid_width=13,
        layer_height=0.08,
        layer_count_max=4,
        same_height=False,
        rearrange_by_size=True,
        sort_color=True,
        verbose=True,
        directory="output",
        colors=None,
        alpha: float = 12.0,
        blend_mode: str = "original",
        custom_code_grid=None,
        grid_origin_x: float = 0.0,
        grid_origin_y: float = 0.0,
        extra_regions=None,
        filename_prefix: Optional[str] = None,
    ):
        if layer_count_max <= 0:
            raise ValueError(f"layer_count_max must be positive, got {layer_count_max}")
        self.length_total = plate_length
        self.width_total = plate_width
        self.grid_length = grid_length
        self.grid_width = grid_width
        self.layer_height = layer_height
        self.layer_count_max = layer_count_max
        self.colors = colors if colors is not None else Colors()
        self.alpha = alpha
        self.blend_mode = blend_mode
        self.reshape = rearrange_by_size
        self.same_height = same_height
        self.sort_color = sort_color
        self.verbose = verbose
        self.custom_code_grid = custom_code_grid
        self.grid_origin_x = float(grid_origin_x)
        self.grid_origin_y = float(grid_origin_y)
        self.extra_regions = extra_regions or []
        color_labels = "".join(self.colors.get_labels())
        height = self.layer_height * self.layer_count_max
        self.filename = filename_prefix or f"{color_labels}_{self.length_total}x{self.width_total}x{height:.2f}"
        self.directory = os.path.join(directory, self.filename) + "/"
        self.df_code = pd.DataFrame()
        self.df_rgb = pd.DataFrame()

    def permutation_matrix(self, items, count):
        return permutation_matrix(items, count)

    def combined_permutation_matrix(self, items, count):
        return combined_permutation_matrix(items, count)

    def reshape_matrix(self, df):
        return reshape_code_matrix(
            df=df,
            grid_length=self.grid_length,
            grid_width=self.grid_width,
            length_total=self.length_total,
            reshape=self.reshape,
            verbose=self.verbose,
            logger=logger,
        )

    def _build_code_df(self):
        if self.custom_code_grid is not None:
            return pd.DataFrame(self.custom_code_grid)
        if self.same_height:
            return self.permutation_matrix(self.colors.get_labels(), self.layer_count_max)
        return self.combined_permutation_matrix(self.colors.get_labels(), self.layer_count_max)

    def _append_code_meshes(self, meshes, code, x_range, y_range):
        for color_idx in range(len(code)):
            color = code[color_idx]
            z_range = [self.layer_height * color_idx, self.layer_height * (color_idx + 1)]
            meshes[color].append(generate_box(x_range, y_range, z_range))

    def generate_box(self, xrange, yrange, zrange):
        return generate_box(xrange, yrange, zrange)

    def merge_stl_meshes(self, mesh_list):
        return merge_stl_meshes(mesh_list)

    def merge_meshes_by_color(self, meshes):
        color_labels = "".join(self.colors.get_labels())
        for color in meshes:
            filename = f"{color_labels}_{color}_{self.length_total}x{self.width_total}x{self.layer_height * self.layer_count_max:.2f}.stl"
            self.save_stl_mesh(merge_stl_meshes(meshes[color]), filename)

    def generate(self):
        df = self._build_code_df()
        df, grid_length, grid_width = self.reshape_matrix(df)
        df_rgb, df_code = self.set_code_rgb_df(df)

        meshes = {color: [] for color in self.colors.get_labels()}
        for y in range(df_code.shape[0]):
            for x in range(df_code.shape[1]):
                if not pd.isna(df_code.iat[y, x]):
                    code = df_code.iat[y, x]
                    x_range = [
                        self.grid_origin_x + grid_length * x,
                        self.grid_origin_x + grid_length * (x + 1),
                    ]
                    y_range = [
                        self.grid_origin_y + grid_width * y,
                        self.grid_origin_y + grid_width * (y + 1),
                    ]
                    self._append_code_meshes(meshes, code, x_range, y_range)

        for region in self.extra_regions:
            code = region["code"]
            x_range = [region["x"], region["x"] + region["width"]]
            y_range = [region["y"], region["y"] + region["height"]]
            self._append_code_meshes(meshes, code, x_range, y_range)

        self.merge_meshes_by_color(meshes)
        self.save_matrix_csv()
        self.save_matrix_image()
        return df_rgb, df_code

    def save_stl_mesh(self, mesh_obj, filename):
        file_path = os.path.join(self.directory, filename)
        os.makedirs(self.directory, exist_ok=True)
        mesh_obj.save(file_path)
        return mesh_obj

    def save_matrix_csv(self):
        file_path = os.path.join(self.directory, self.filename)
        os.makedirs(self.directory, exist_ok=True)
        self.df_rgb.to_csv(file_path + "_rgb.csv", index=False)
        self.df_code.to_csv(file_path + "_code.csv", index=False)

    def read_matrix_csv(self, filename):
        df_raw = pd.read_csv(os.path.join(self.directory, filename), header=0, dtype=str)
        return df_raw.map(parse_cell)

    def matrix_to_code_color_map(self, df_rgb, df_code):
        return matrix_to_code_color_map(df_rgb, df_code)

    def set_code_rgb_df(self, df):
        df_rgb, df_code = build_code_rgb_df(df, self.code_to_rgb, sort_color=self.sort_color)
        self.df_code = df_code
        self.df_rgb = df_rgb
        return df_rgb, df_code

    def _color_key(self) -> tuple:
        return tuple(
            (label, self.colors[label].td, self.colors[label].hex)
            for label in self.colors.get_labels()
        )

    def code_to_rgb(self, code: str):
        if not code or not code.strip():
            return (255, 255, 255)
        code = code.strip().upper()
        return _code_to_rgb_cached(
            code,
            self.layer_height,
            self._color_key(),
            self.alpha,
            self.blend_mode,
        )

    def save_matrix_image(self, save_blank=True):
        rows, cols = self.df_code.shape
        cell_size = 50
        rgb_array = np.zeros((rows * cell_size, cols * cell_size, 3), dtype=np.uint8)
        for y in range(rows):
            for x in range(cols):
                rgb = self.df_rgb.iat[y, x]
                if rgb is None:
                    rgb_array[y * cell_size:(y + 1) * cell_size, x * cell_size:(x + 1) * cell_size] = (255, 255, 255)
                else:
                    rgb_array[y * cell_size:(y + 1) * cell_size, x * cell_size:(x + 1) * cell_size] = rgb

        file_path = os.path.join(self.directory, self.filename + ".png")
        os.makedirs(self.directory, exist_ok=True)
        img = Image.fromarray(rgb_array)
        draw = ImageDraw.Draw(img)
        img_blank = Image.fromarray(rgb_array)
        draw_blank = ImageDraw.Draw(img_blank)
        for y in range(rows):
            for x in range(cols):
                if self.df_code.iat[y, x] is None or pd.isna(self.df_code.iat[y, x]):
                    continue
                code = self.df_code.iat[y, x]
                rgb = tuple(rgb_array[y * cell_size, x * cell_size])
                x0, y0 = x * cell_size, y * cell_size
                x1, y1 = x0 + cell_size, y0 + cell_size
                draw.rectangle([x0, y0, x1, y1], fill=rgb)
                draw_blank.rectangle([x0, y0, x1, y1], fill=(255, 255, 255), outline=(0, 0, 0))
                brightness = (rgb[0] * 0.299 + rgb[1] * 0.587 + rgb[2] * 0.114) / 255
                text_color = (0, 0, 0) if brightness > 0.5 else (255, 255, 255)
                draw.text((x0, y0), code, fill=text_color)
                draw_blank.text((x0, y0), code, fill=(0, 0, 0))
        img.save(file_path)
        if save_blank:
            img_blank.save(f"{file_path[:-4]}_blank.png")

    def save_plate_layout_image(self, save_blank=True, pixels_per_mm=8):
        if self.df_code.empty:
            raise ValueError("No code matrix available. Call generate() before save_plate_layout_image().")

        width_px = max(1, int(math.ceil(self.length_total * pixels_per_mm)))
        height_px = max(1, int(math.ceil(self.width_total * pixels_per_mm)))
        img = Image.new("RGB", (width_px, height_px), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        img_blank = Image.new("RGB", (width_px, height_px), (255, 255, 255))
        draw_blank = ImageDraw.Draw(img_blank)

        def mm_to_px(value):
            return int(round(value * pixels_per_mm))

        rows, cols = self.df_code.shape
        for y in range(rows):
            for x in range(cols):
                code = self.df_code.iat[y, x]
                if pd.isna(code):
                    continue
                rgb = tuple(int(round(c)) for c in self.df_rgb.iat[y, x])
                x0 = mm_to_px(self.grid_origin_x + self.grid_length * x)
                x1 = mm_to_px(self.grid_origin_x + self.grid_length * (x + 1))
                y0 = mm_to_px(self.grid_origin_y + self.grid_width * y)
                y1 = mm_to_px(self.grid_origin_y + self.grid_width * (y + 1))
                draw.rectangle([x0, y0, x1, y1], fill=rgb, outline=(0, 0, 0))
                draw_blank.rectangle([x0, y0, x1, y1], fill=(255, 255, 255), outline=(0, 0, 0))

        for region in self.extra_regions:
            rgb = tuple(int(round(c)) for c in self.code_to_rgb(region["code"]))
            x0 = mm_to_px(region["x"])
            x1 = mm_to_px(region["x"] + region["width"])
            y0 = mm_to_px(region["y"])
            y1 = mm_to_px(region["y"] + region["height"])
            draw.rectangle([x0, y0, x1, y1], fill=rgb, outline=(0, 0, 0))
            draw_blank.rectangle([x0, y0, x1, y1], fill=(255, 255, 255), outline=(0, 0, 0))
            label = region.get("label")
            if label:
                draw_blank.text((x0 + 2, y0 + 2), label, fill=(0, 0, 0))

        file_path = os.path.join(self.directory, self.filename + "_plate.png")
        os.makedirs(self.directory, exist_ok=True)
        img.save(file_path)
        if save_blank:
            img_blank.save(f"{file_path[:-4]}_blank.png")

    def image_to_rgb_matrix(self, image_path, grid_size=16, sample_fraction=0.4, method="mean", save_samples=False):
        sample_directory = None
        if save_samples:
            sample_directory = os.path.join(self.directory, "samples")
        return sample_image_to_rgb_matrix(
            image_path=image_path,
            grid_size=grid_size,
            sample_fraction=sample_fraction,
            method=method,
            save_samples=save_samples,
            sample_directory=sample_directory,
        )

    def color_variance(self, df_ref, df_photo, new_df_rgb, new_df_code, save_comp_img=False):
        return compute_color_variance(
            df_ref=df_ref,
            df_photo=df_photo,
            new_df_rgb=new_df_rgb,
            new_df_code=new_df_code,
            labels=self.colors.get_labels(),
        )

    def parse_cell(self, s):
        return parse_cell(s)
