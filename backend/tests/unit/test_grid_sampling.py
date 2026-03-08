import numpy as np
import pandas as pd
import pytest
from PIL import Image

from core.grid_sampling import (
    color_variance,
    image_to_rgb_matrix,
    matrix_to_code_color_map,
    parse_cell,
)


class TestParseCell:
    def test_parse_nan(self):
        result = parse_cell(float("nan"))
        assert pd.isna(result)

    def test_parse_tuple_string(self):
        result = parse_cell("('CCCC', (0, 255, 255))")
        assert result == ("CCCC", (0, 255, 255))

    def test_parse_numpy_float_wrapper(self):
        result = parse_cell("np.float64(3.14)")
        assert result == pytest.approx(3.14)

    def test_parse_plain_string(self):
        assert parse_cell("hello") == "hello"

    def test_parse_non_string(self):
        assert parse_cell(42) == 42


class TestMatrixToCodeColorMap:
    def test_map_contains_all_codes(self):
        df_code = pd.DataFrame([["CC", "CM"], ["MC", "MM"]])
        df_rgb = pd.DataFrame(
            [[(1, 2, 3), (4, 5, 6)], [(7, 8, 9), (10, 11, 12)]]
        )

        result = matrix_to_code_color_map(df_rgb, df_code)

        assert result == {
            "CC": (1, 2, 3),
            "CM": (4, 5, 6),
            "MC": (7, 8, 9),
            "MM": (10, 11, 12),
        }

    def test_duplicate_codes_keep_last_value(self):
        df_code = pd.DataFrame([["CC", "CC"]])
        df_rgb = pd.DataFrame([[(1, 2, 3), (9, 8, 7)]])

        result = matrix_to_code_color_map(df_rgb, df_code)

        assert result["CC"] == (9, 8, 7)


class TestImageToRgbMatrix:
    def test_mean_sampling_returns_expected_quadrants(self, tmp_path):
        arr = np.zeros((20, 20, 3), dtype=np.uint8)
        arr[:10, :10] = (255, 0, 0)
        arr[:10, 10:] = (0, 255, 0)
        arr[10:, :10] = (0, 0, 255)
        arr[10:, 10:] = (255, 255, 255)

        image_path = tmp_path / "quadrants.png"
        Image.fromarray(arr).save(image_path)

        result = image_to_rgb_matrix(str(image_path), grid_size=2, sample_fraction=1.0, method="mean")

        assert result.shape == (2, 2)
        assert result.iat[0, 0] == (255, 0, 0)
        assert result.iat[0, 1] == (0, 255, 0)
        assert result.iat[1, 0] == (0, 0, 255)
        assert result.iat[1, 1] == (255, 255, 255)

    def test_median_sampling_rejects_single_outlier(self, tmp_path):
        arr = np.full((3, 3, 3), (255, 0, 0), dtype=np.uint8)
        arr[1, 1] = (0, 0, 255)

        image_path = tmp_path / "outlier.png"
        Image.fromarray(arr).save(image_path)

        result = image_to_rgb_matrix(str(image_path), grid_size=1, sample_fraction=1.0, method="median")

        assert result.iat[0, 0] == (255, 0, 0)

    def test_save_samples_writes_tiles(self, tmp_path):
        arr = np.zeros((20, 20, 3), dtype=np.uint8)
        image_path = tmp_path / "tiles.png"
        Image.fromarray(arr).save(image_path)

        sample_dir = tmp_path / "samples"
        result = image_to_rgb_matrix(
            str(image_path),
            grid_size=2,
            sample_fraction=1.0,
            save_samples=True,
            sample_directory=str(sample_dir),
        )

        assert result.shape == (2, 2)
        assert (sample_dir / "tile0_0.png").exists()
        assert (sample_dir / "tile0_1.png").exists()
        assert (sample_dir / "tile1_0.png").exists()
        assert (sample_dir / "tile1_1.png").exists()


class TestColorVariance:
    def test_shape_mismatch_returns_none(self):
        df_ref = pd.DataFrame([[("CC", (0, 0, 0))]])
        df_photo = pd.DataFrame([[(0, 0, 0)], [(255, 255, 255)]])
        new_df_code = pd.DataFrame([["CC"]])
        new_df_rgb = pd.DataFrame([[(0, 0, 0)]])

        assert color_variance(df_ref, df_photo, new_df_rgb, new_df_code, labels=["C"]) is None

    def test_returns_numeric_variance(self):
        df_ref = pd.DataFrame(
            [[("CC", (0, 0, 0)), ("CM", (0, 0, 0))]]
        )
        df_photo = pd.DataFrame(
            [[(10, 10, 10), (20, 20, 20)]]
        )
        new_df_code = pd.DataFrame([["CC", "CM"]])
        new_df_rgb = pd.DataFrame([[(12, 12, 12), (18, 18, 18)]])

        result = color_variance(df_ref, df_photo, new_df_rgb, new_df_code, labels=["C", "M"])

        assert isinstance(result, (float, np.floating))
        assert result >= 0
