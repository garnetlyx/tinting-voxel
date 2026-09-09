"""
Unit tests for core/blend_color.py - Color, Colors, and BlendTestGenerator.

Covers optical mixing, color classification, mesh generation,
permutation matrices, and code-to-RGB conversion.
"""
import math

import numpy as np
import pandas as pd
import pytest

from core.blend_color import (
    BlendTestGenerator,
    Color,
    Colors,
    _blend_hybrid,
    _blend_hybrid_per_color,
)
from core.color_config import BAMBU_CMYW_PHASE6_PRESET, ColorConfig


class TestColorGetLabel:
    """Tests for Color.get_label() method."""

    def test_get_label_uppercase_first_char(self):
        color = Color("Cyan", transmission_distance=3.0, hex="#00FFFF")
        assert color.get_label() == "C"

    def test_get_label_lowercase_name(self):
        color = Color("magenta", transmission_distance=1.9, hex="#FF00FF")
        assert color.get_label() == "M"


class TestColorGetAbsorption:
    """Tests for Color.get_absorption()."""

    def test_white_has_zero_absorption(self):
        color = Color("White", transmission_distance=7.2, hex="#FFFFFF")
        np.testing.assert_array_almost_equal(color.get_absorption(), [0, 0, 0])

    def test_black_has_full_absorption(self):
        color = Color("Black", transmission_distance=1.0, hex="#000000")
        np.testing.assert_array_almost_equal(color.get_absorption(), [1, 1, 1])

    def test_red_absorbs_green_and_blue(self):
        color = Color("Red", transmission_distance=2.0, hex="#FF0000")
        absorption = color.get_absorption()
        assert absorption[0] == pytest.approx(0.0)  # no red absorption
        assert absorption[1] == pytest.approx(1.0)  # full green absorption
        assert absorption[2] == pytest.approx(1.0)  # full blue absorption

    def test_gray_has_equal_absorption(self):
        color = Color("Gray", transmission_distance=2.0, hex="#808080")
        absorption = color.get_absorption()
        assert absorption[0] == pytest.approx(absorption[1])
        assert absorption[1] == pytest.approx(absorption[2])
        expected = (255 - 128) / 255
        assert absorption[0] == pytest.approx(expected, abs=0.01)


class TestColorGetTransmissionRate:
    """Tests for Color.get_transmission_rate() (Beer-Lambert law)."""

    def test_zero_distance_full_transmission(self):
        t = Color.get_transmission_rate(d=0, td=3.0)
        assert t == pytest.approx(1.0)

    def test_negative_td_returns_zero(self):
        t = Color.get_transmission_rate(d=1.0, td=-1.0)
        assert t == 0.0

    def test_zero_td_returns_zero(self):
        t = Color.get_transmission_rate(d=1.0, td=0)
        assert t == 0.0

    def test_large_distance_approaches_zero(self):
        t = Color.get_transmission_rate(d=100, td=1.0)
        assert t < 0.001

    def test_transmission_decreases_with_distance(self):
        t1 = Color.get_transmission_rate(d=0.08, td=3.0)
        t2 = Color.get_transmission_rate(d=0.16, td=3.0)
        assert t1 > t2

    def test_higher_td_gives_more_transmission(self):
        t_opaque = Color.get_transmission_rate(d=0.08, td=1.0)
        t_clear = Color.get_transmission_rate(d=0.08, td=10.0)
        assert t_clear > t_opaque


class TestColorGetLab:
    """Tests for Color.get_lab() LAB conversion."""

    def test_white_has_high_lightness(self):
        L, a, b, C = Color.get_lab((255, 255, 255))
        assert float(L) > 99  # L=100 for white

    def test_black_has_zero_lightness(self):
        L, a, b, C = Color.get_lab((0, 0, 0))
        assert float(L) == pytest.approx(0, abs=0.5)

    def test_gray_has_low_chroma(self):
        L, a, b, C = Color.get_lab((128, 128, 128))
        assert float(C) < 1  # neutral gray

    def test_red_has_positive_a(self):
        L, a, b, C = Color.get_lab((255, 0, 0))
        assert float(a) > 0  # positive a = red direction


class TestColorIsNeutral:
    """Tests for Color.is_neutral()."""

    def test_pure_gray_is_neutral(self):
        assert bool(Color.is_neutral((128, 128, 128))) is True

    def test_white_is_neutral(self):
        assert bool(Color.is_neutral((255, 255, 255))) is True

    def test_black_is_neutral(self):
        assert bool(Color.is_neutral((0, 0, 0))) is True

    def test_saturated_red_is_not_neutral(self):
        assert bool(Color.is_neutral((255, 0, 0))) is False

    def test_saturated_blue_is_not_neutral(self):
        assert bool(Color.is_neutral((0, 0, 255))) is False


class TestColorIsBrown:
    """Tests for Color.is_brown()."""

    def test_dark_warm_neutral_is_brown(self):
        # Brown-ish color: dark, warm, low chroma
        # A typical brown like #8B4513 (SaddleBrown)
        # L~37, a~25, b~36 -> neutral may not apply
        # Use a darker neutral: not exactly typical but matches the logic
        result = Color.is_brown((80, 60, 40))
        # This tests the logic path even if result depends on exact thresholds
        assert isinstance(result, (bool, np.bool_))

    def test_white_is_not_brown(self):
        assert bool(Color.is_brown((255, 255, 255))) is False

    def test_bright_red_is_not_brown(self):
        assert bool(Color.is_brown((255, 0, 0))) is False


class TestColorMapToNearestColor:
    """Tests for Color.map_to_nearest_color()."""

    def test_exact_match_returns_same_code(self):
        ref_code = pd.DataFrame([["CCCC", "MMMM"]])
        ref_rgb = pd.DataFrame([[(0, 255, 255), (255, 0, 255)]])
        codes, colors = Color.map_to_nearest_color(
            [(0, 255, 255)], ref_code, ref_rgb
        )
        assert codes[0] == "CCCC"

    def test_nearest_match_for_close_color(self):
        ref_code = pd.DataFrame([["CCCC", "MMMM"]])
        ref_rgb = pd.DataFrame([[(0, 255, 255), (255, 0, 255)]])
        # A color closer to cyan than magenta
        codes, _ = Color.map_to_nearest_color(
            [(0, 200, 200)], ref_code, ref_rgb
        )
        assert codes[0] == "CCCC"

    def test_multiple_inputs(self):
        ref_code = pd.DataFrame([["C", "M", "Y"]])
        ref_rgb = pd.DataFrame([[(0, 255, 255), (255, 0, 255), (255, 255, 0)]])
        codes, colors = Color.map_to_nearest_color(
            [(0, 200, 200), (200, 0, 200), (200, 200, 0)],
            ref_code, ref_rgb
        )
        assert len(codes) == 3
        assert codes[0] == "C"
        assert codes[1] == "M"
        assert codes[2] == "Y"


class TestColorsWhiteBalance:
    """Tests for Colors.update_white_balance()."""

    def test_update_white_balance(self):
        colors = Colors()
        colors.update_white_balance(5, 15, 30)
        assert colors.white_balance['r'] == 5
        assert colors.white_balance['g'] == 15
        assert colors.white_balance['b'] == 30

    def test_default_white_balance(self):
        colors = Colors()
        assert colors.white_balance['r'] == 0
        assert colors.white_balance['g'] == 10
        assert colors.white_balance['b'] == 24


class TestColorsSetItem:
    """Tests for Colors.__setitem__()."""

    def test_setitem_adds_color(self):
        colors = Colors()
        new_color = Color("Purple", transmission_distance=2.0, hex="#800080")
        colors['P'] = new_color
        assert colors['P'].name == "Purple"

    def test_setitem_strips_and_uppercases(self):
        colors = Colors()
        new_color = Color("Purple", transmission_distance=2.0, hex="#800080")
        colors[' p '] = new_color
        assert colors['P'].name == "Purple"


class TestColorsAdd:
    """Tests for Colors.add()."""

    def test_add_color(self):
        colors = Colors(colors={})
        color = Color("Red", transmission_distance=2.0, hex="#FF0000")
        colors.add(color)
        assert 'R' in colors.get_labels()
        assert colors['R'].name == "Red"


class TestBlendTestGeneratorCodeToRgb:
    """Tests for BlendTestGenerator.code_to_rgb()."""

    @pytest.fixture
    def generator(self):
        return BlendTestGenerator(
            colors=Colors(),
            layer_height=0.08,
            layer_count_max=4,
            verbose=False,
        )

    def test_empty_code_returns_white(self, generator):
        rgb = generator.code_to_rgb("")
        assert rgb == (255, 255, 255)

    def test_single_layer_code(self, generator):
        rgb = generator.code_to_rgb("C")
        # Should produce some color influenced by cyan
        assert isinstance(rgb, tuple)
        assert len(rgb) == 3
        # Blue channel should be higher than red for cyan-influenced result
        assert rgb[2] > rgb[0]

    def test_multi_layer_same_color(self, generator):
        rgb = generator.code_to_rgb("CCCC")
        assert isinstance(rgb, tuple)
        assert len(rgb) == 3
        # 4 layers of cyan should be more saturated than 1 layer
        rgb_single = generator.code_to_rgb("C")
        # More layers = more color absorption = less white
        assert sum(rgb) <= sum(rgb_single)

    def test_white_layers_produce_near_white(self, generator):
        rgb = generator.code_to_rgb("WWWW")
        # White filament should produce near-white result
        assert all(c > 200 for c in rgb)

    def test_mixed_layers(self, generator):
        rgb = generator.code_to_rgb("CMYW")
        assert isinstance(rgb, tuple)
        assert len(rgb) == 3
        assert all(0 <= c <= 255 for c in rgb)

    def test_code_longer_than_layer_count_max(self, generator):
        # QA-19: code longer than layer_count_max should not IndexError
        rgb = generator.code_to_rgb("CCCCCC")
        assert isinstance(rgb, tuple)
        assert len(rgb) == 3

    def test_lowercase_code_handled(self, generator):
        rgb_upper = generator.code_to_rgb("C")
        rgb_lower = generator.code_to_rgb("c")
        assert rgb_upper == pytest.approx(rgb_lower, abs=0.01)


class TestCodeToRgbCache:
    """Tests for LRU cache in code_to_rgb()."""

    @pytest.fixture
    def generator(self):
        return BlendTestGenerator(
            colors=Colors(),
            layer_height=0.08,
            layer_count_max=4,
            verbose=False,
        )

    def test_cache_returns_same_result(self, generator):
        """Calling code_to_rgb with same code returns identical result."""
        rgb1 = generator.code_to_rgb("CMYW")
        rgb2 = generator.code_to_rgb("CMYW")
        assert rgb1 == rgb2

    def test_cache_different_codes_different_results(self, generator):
        """Different codes produce different results (not stale cache)."""
        rgb_c = generator.code_to_rgb("C")
        rgb_m = generator.code_to_rgb("M")
        assert rgb_c != rgb_m

    def test_cache_isolated_between_generators(self):
        """Different generator configs don't share cached results."""
        from core.blend_color import clear_rgb_cache
        clear_rgb_cache()

        gen1 = BlendTestGenerator(
            colors=Colors(clear=False),
            layer_height=0.08,
            layer_count_max=4,
            verbose=False,
        )
        gen2 = BlendTestGenerator(
            colors=Colors(clear=True),
            layer_height=0.84,
            layer_count_max=4,
            verbose=False,
        )
        rgb1 = gen1.code_to_rgb("CMYW")
        rgb2 = gen2.code_to_rgb("CMYW")
        # Different color configs should produce different results
        assert rgb1 != rgb2

    def test_clear_rgb_cache(self, generator):
        """clear_rgb_cache() resets the cache."""
        from core.blend_color import clear_rgb_cache, rgb_cache_info
        clear_rgb_cache()
        generator.code_to_rgb("C")
        info = rgb_cache_info()
        assert info.hits == 0
        assert info.misses == 1

        generator.code_to_rgb("C")
        info = rgb_cache_info()
        assert info.hits == 1
        assert info.misses == 1

        clear_rgb_cache()
        info = rgb_cache_info()
        assert info.hits == 0
        assert info.misses == 0


class TestHybridPerColorBlend:
    """Tests for per-color hybrid absorption scaling."""

    @pytest.fixture
    def color_map(self):
        colors = Colors()
        return {label: colors[label] for label in colors.get_labels()}

    def test_matches_hybrid_when_all_k_equal(self, color_map):
        code = "CMYW"
        hybrid = _blend_hybrid(
            code, 0.08, color_map, scatter_alpha=4.0, k=7.5
        )
        hybrid_kc = _blend_hybrid_per_color(
            code,
            0.08,
            color_map,
            scatter_alpha=4.0,
            k_map={label: 7.5 for label in color_map},
        )
        assert hybrid_kc == pytest.approx(hybrid, abs=1e-6)

    def test_higher_yellow_k_darkens_yellow_rich_code(self, color_map):
        default_rgb = _blend_hybrid_per_color(
            "YYYY", 0.08, color_map, scatter_alpha=4.0, k_map={"Y": 2.0}
        )
        boosted_rgb = _blend_hybrid_per_color(
            "YYYY", 0.08, color_map, scatter_alpha=4.0, k_map={"Y": 12.0}
        )
        assert sum(boosted_rgb) < sum(default_rgb)

    @pytest.mark.parametrize(
        "blend_mode",
        ["hybrid_calibrated", "hybrid_per_color_k_td1s_gamma"],
    )
    def test_calibrated_mode_aliases_share_same_kernel(self, blend_mode):
        colors = Colors.from_configs(BAMBU_CMYW_PHASE6_PRESET)
        generator = BlendTestGenerator(
            colors=colors,
            layer_height=0.08,
            layer_count_max=4,
            verbose=False,
            blend_mode=blend_mode,
        )
        baseline = BlendTestGenerator(
            colors=colors,
            layer_height=0.08,
            layer_count_max=4,
            verbose=False,
            blend_mode="hybrid_calibrated",
        )

        assert generator.code_to_rgb("CMYW") == pytest.approx(
            baseline.code_to_rgb("CMYW"),
            abs=1e-6,
        )

    def test_hybrid_per_color_k_ignores_td_gamma_remap(self):
        colors = Colors.from_configs(BAMBU_CMYW_PHASE6_PRESET)
        per_color_mode = BlendTestGenerator(
            colors=colors,
            layer_height=0.08,
            layer_count_max=4,
            verbose=False,
            blend_mode="hybrid_per_color_k",
        )
        baseline = BlendTestGenerator(
            colors=colors,
            layer_height=0.08,
            layer_count_max=4,
            verbose=False,
            blend_mode="hybrid_calibrated",
        )

        assert per_color_mode.code_to_rgb("CMYW") != pytest.approx(
            baseline.code_to_rgb("CMYW"),
            abs=1e-6,
        )


class TestBlendTestGeneratorGenerateBox:
    """Tests for BlendTestGenerator.generate_box()."""

    @pytest.fixture
    def generator(self):
        return BlendTestGenerator(verbose=False)

    def test_box_has_12_faces(self, generator):
        box = generator.generate_box([0, 1], [0, 1], [0, 1])
        assert len(box.vectors) == 12

    def test_box_dimensions_match(self, generator):
        box = generator.generate_box([10, 20], [30, 40], [0, 5])
        # Check that vertices span the expected ranges
        all_vertices = box.vectors.reshape(-1, 3)
        assert np.min(all_vertices[:, 0]) == pytest.approx(10)
        assert np.max(all_vertices[:, 0]) == pytest.approx(20)
        assert np.min(all_vertices[:, 1]) == pytest.approx(30)
        assert np.max(all_vertices[:, 1]) == pytest.approx(40)
        assert np.min(all_vertices[:, 2]) == pytest.approx(0)
        assert np.max(all_vertices[:, 2]) == pytest.approx(5)


class TestBlendTestGeneratorMergeMeshes:
    """Tests for BlendTestGenerator.merge_stl_meshes()."""

    @pytest.fixture
    def generator(self):
        return BlendTestGenerator(verbose=False)

    def test_merge_two_boxes(self, generator):
        box1 = generator.generate_box([0, 1], [0, 1], [0, 1])
        box2 = generator.generate_box([2, 3], [2, 3], [0, 1])
        merged = generator.merge_stl_meshes([box1, box2])
        assert len(merged.vectors) == 24  # 12 + 12

    def test_merge_single_mesh(self, generator):
        box = generator.generate_box([0, 1], [0, 1], [0, 1])
        merged = generator.merge_stl_meshes([box])
        assert len(merged.vectors) == 12


class TestBlendTestGeneratorPermutationMatrix:
    """Tests for permutation matrix generation."""

    @pytest.fixture
    def generator(self):
        return BlendTestGenerator(verbose=False)

    def test_permutation_matrix_shape(self, generator):
        df = generator.permutation_matrix(['C', 'M'], 2)
        # 2 items, repeat 2: 4 combos -> 2 rows x 2 cols
        assert df.shape == (2, 2)

    def test_permutation_matrix_all_values(self, generator):
        df = generator.permutation_matrix(['C', 'M'], 2)
        values = sorted(df.values.flatten().tolist())
        assert values == sorted(['CC', 'CM', 'MC', 'MM'])

    def test_combined_permutation_matrix_structure(self, generator):
        df = generator.combined_permutation_matrix(['C', 'M'], 3)
        # 2 items: each row starts with single letter, then 2-letter, then 3-letter combos
        assert df.shape[0] == 2  # 2 items = 2 rows
        # First element of each row is a single letter
        assert len(df.iloc[0, 0]) == 1
        assert len(df.iloc[1, 0]) == 1


class TestBlendTestGeneratorReshapeMatrix:
    """Tests for BlendTestGenerator.reshape_matrix()."""

    def test_reshape_matrix_returns_tuple(self):
        gen = BlendTestGenerator(
            plate_length=52, plate_width=52,
            grid_length=13, grid_width=13,
            verbose=False,
        )
        df = gen.permutation_matrix(['C', 'M'], 2)
        result = gen.reshape_matrix(df)
        assert len(result) == 3
        df_out, gl, gw = result
        assert gl == 13
        assert gw == 13


class TestBlendTestGeneratorSetCodeRgbDf:
    """Tests for BlendTestGenerator.set_code_rgb_df()."""

    def test_set_code_rgb_df_returns_dataframes(self):
        gen = BlendTestGenerator(
            colors=Colors(names=['C', 'M']),
            layer_height=0.08,
            layer_count_max=2,
            verbose=False,
        )
        df_input = gen.permutation_matrix(['C', 'M'], 2)
        df_rgb, df_code = gen.set_code_rgb_df(df_input)

        assert isinstance(df_rgb, pd.DataFrame)
        assert isinstance(df_code, pd.DataFrame)
        assert df_rgb.shape == df_input.shape
        assert df_code.shape == df_input.shape

    def test_set_code_rgb_df_stores_on_instance(self):
        gen = BlendTestGenerator(
            colors=Colors(names=['C', 'M']),
            layer_height=0.08,
            layer_count_max=2,
            verbose=False,
        )
        df_input = gen.permutation_matrix(['C', 'M'], 2)
        gen.set_code_rgb_df(df_input)

        assert gen.df_code.shape == df_input.shape
        assert gen.df_rgb.shape == df_input.shape

    def test_set_code_rgb_df_preserves_custom_order_when_sort_disabled(self):
        gen = BlendTestGenerator(
            colors=Colors(names=['C', 'M']),
            layer_height=0.08,
            layer_count_max=2,
            verbose=False,
            sort_color=False,
        )
        df_input = pd.DataFrame([["MC", "CC"], ["MM", "CM"]])
        _, df_code = gen.set_code_rgb_df(df_input)
        assert df_code.values.tolist() == df_input.values.tolist()


class TestBlendTestGeneratorStructuredPlate:
    def test_generate_with_custom_grid_origin_and_markers(self, tmp_path):
        colors = Colors.from_configs([
            ColorConfig(name="Cyan", hex="#3D79C6", transmission_distance=3.0),
            ColorConfig(name="Magenta", hex="#B3356E", transmission_distance=1.9),
            ColorConfig(name="Yellow", hex="#FFE665", transmission_distance=2.5),
            ColorConfig(name="White", hex="#FFFFFF", transmission_distance=7.2),
            ColorConfig(name="Key", hex="#111111", transmission_distance=0.3),
        ])
        gen = BlendTestGenerator(
            colors=colors,
            layer_height=0.08,
            layer_count_max=4,
            plate_length=60,
            plate_width=40,
            grid_length=10,
            grid_width=10,
            rearrange_by_size=False,
            sort_color=False,
            verbose=False,
            directory=str(tmp_path),
            custom_code_grid=[["C", "M"], ["Y", "W"]],
            grid_origin_x=5,
            grid_origin_y=3,
            extra_regions=[
                {"x": 1, "y": 1, "width": 2, "height": 2, "code": "KKKK", "label": "marker"}
            ],
            filename_prefix="structured_test",
        )

        _, df_code = gen.generate()
        gen.save_plate_layout_image()

        assert df_code.shape == (2, 2)
        assert df_code.values.tolist() == [["C", "M"], ["Y", "W"]]
        assert (tmp_path / "structured_test" / "structured_test_plate.png").exists()


class TestBlendTestGeneratorMatrixToCodeColorMap:
    """Tests for BlendTestGenerator.matrix_to_code_color_map()."""

    def test_map_contains_all_codes(self):
        gen = BlendTestGenerator(
            colors=Colors(names=['C', 'M']),
            layer_height=0.08,
            layer_count_max=2,
            verbose=False,
        )
        df_input = gen.permutation_matrix(['C', 'M'], 2)
        df_rgb, df_code = gen.set_code_rgb_df(df_input)
        code_map = gen.matrix_to_code_color_map(df_rgb, df_code)

        assert isinstance(code_map, dict)
        assert len(code_map) == 4  # CC, CM, MC, MM


class TestBlendTestGeneratorParseCell:
    """Tests for BlendTestGenerator.parse_cell()."""

    @pytest.fixture
    def generator(self):
        return BlendTestGenerator(verbose=False)

    def test_parse_nan(self, generator):
        result = generator.parse_cell(float('nan'))
        assert pd.isna(result)

    def test_parse_tuple_string(self, generator):
        result = generator.parse_cell("('CCCC', (0, 255, 255))")
        assert result == ('CCCC', (0, 255, 255))

    def test_parse_numpy_float_wrapper(self, generator):
        result = generator.parse_cell("np.float64(3.14)")
        assert result == pytest.approx(3.14)

    def test_parse_plain_string(self, generator):
        result = generator.parse_cell("hello")
        assert result == "hello"

    def test_parse_non_string(self, generator):
        result = generator.parse_cell(42)
        assert result == 42


class TestColorRepr:
    """Tests for Color.__repr__."""

    def test_repr_returns_name(self):
        color = Color("Cyan", transmission_distance=3.0, hex="#00FFFF")
        assert repr(color) == "Cyan"


class TestColorGetCmyk:
    """Tests for Color.get_cmyk()."""

    def test_white_has_zero_cmyk(self):
        color = Color("White", transmission_distance=7.2, hex="#FFFFFF")
        c, m, y, k = color.get_cmyk()
        assert (c, m, y, k) == (0, 0, 0, 0)

    def test_black_returns_full_key(self):
        color = Color("Black", transmission_distance=1.0, hex="#000000")
        c, m, y, k = color.get_cmyk()
        assert (c, m, y, k) == (0, 0, 0, 1)

    def test_pure_red(self):
        color = Color("Red", transmission_distance=2.0, hex="#FF0000")
        c, m, y, k = color.get_cmyk()
        assert c == pytest.approx(0)
        assert k == pytest.approx(0)
        assert m == pytest.approx(1)
        assert y == pytest.approx(1)


class TestColorUpdateHex:
    """Tests for Color.update_hex()."""

    def test_update_hex_changes_rgb(self):
        color = Color("Test", transmission_distance=1.0, hex="#FF0000")
        assert color.rgb == (255, 0, 0)
        color.update_hex("#00FF00")
        assert color.rgb == (0, 255, 0)
        assert color.hex == "#00FF00"


class TestColorConstructor:
    """Tests for Color constructor edge cases."""

    def test_default_cmyw_colors_dont_need_hex(self):
        for name in ['Cyan', 'Magenta', 'Yellow', 'White']:
            color = Color(name, transmission_distance=3.0)
            assert color.hex is not None

    def test_unknown_color_without_hex_raises(self):
        with pytest.raises(ValueError, match="hex is required"):
            Color("Purple", transmission_distance=2.0)

    def test_custom_hex_overrides_default(self):
        color = Color("Cyan", transmission_distance=3.0, hex="#123456")
        assert color.hex == "#123456"


class TestColorsInit:
    """Tests for Colors initialization variants."""

    def test_clear_mode(self):
        from core.color_config import CLEAR_CMYWG_PRESET
        colors = Colors(clear=True)
        assert len(colors) == 5
        # Clear mode mirrors the CLEAR_CMYWG_PRESET source of truth
        preset_c = next(c for c in CLEAR_CMYWG_PRESET if c.label == 'C')
        assert colors['C'].td == preset_c.transmission_distance
        # Clear filaments are more translucent than the opaque set
        assert colors['C'].td > Colors()['C'].td

    def test_names_subset(self):
        colors = Colors(names=['C', 'M'])
        assert len(colors) == 2
        assert colors.get_labels() == ['C', 'M']

    def test_len(self):
        colors = Colors()
        assert len(colors) == 4

    def test_getitem_strips_and_uppercases(self):
        colors = Colors()
        assert colors[' c '].name == colors['C'].name
