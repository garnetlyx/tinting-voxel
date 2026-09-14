"""
Unit tests for dynamic N-color architecture.

Tests ColorConfig, Colors.from_configs(), mesh map generation,
and filename backward compatibility.
"""
import pytest

from core.blend_color import Color, Colors
from core.color_config import (
    BAMBU_CMYW_PHASE6_PRESET,
    BAMBU_CMYWK_PHASE6_PRESET,
    CLEAR_CMYW_PRESET,
    ColorConfig,
    get_available_presets,
    get_preset,
)
from services.stl_generator import get_filename_prefix, initialize_color_mapping


class TestColorConfig:
    """Tests for ColorConfig dataclass."""

    def test_create_valid_color_config(self):
        """ColorConfig creates successfully with valid inputs."""
        config = ColorConfig(
            name="Cyan",
            hex="#00FFFF",
            transmission_distance=3.0
        )
        assert config.name == "Cyan"
        assert config.hex == "#00FFFF"
        assert config.transmission_distance == 3.0
        assert config.label == "C"

    def test_label_extracts_first_character(self):
        """Label property returns uppercase first character."""
        config = ColorConfig(name="magenta", hex="#FF00FF", transmission_distance=1.9)
        assert config.label == "M"

    def test_invalid_empty_name(self):
        """Empty name raises ValueError."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            ColorConfig(name="", hex="#00FFFF", transmission_distance=3.0)

    def test_invalid_hex_format_short(self):
        """Short hex code raises ValueError."""
        with pytest.raises(ValueError, match="Invalid hex color format"):
            ColorConfig(name="Cyan", hex="#FFF", transmission_distance=3.0)

    def test_invalid_hex_format_letters(self):
        """Invalid hex characters raise ValueError."""
        with pytest.raises(ValueError, match="Invalid hex color format"):
            ColorConfig(name="Cyan", hex="#GGGGGG", transmission_distance=3.0)

    def test_invalid_transmission_distance_zero(self):
        """Zero transmission distance raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            ColorConfig(name="Cyan", hex="#00FFFF", transmission_distance=0)

    def test_invalid_transmission_distance_negative(self):
        """Negative transmission distance raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            ColorConfig(name="Cyan", hex="#00FFFF", transmission_distance=-1.0)


class TestPresets:
    """Tests for preset color configurations."""

    def test_bambu_cmyw_phase6_preset_exists(self):
        """BAMBU_CMYW_PHASE6_PRESET has 4 colors."""
        assert len(BAMBU_CMYW_PHASE6_PRESET) == 4
        labels = [c.label for c in BAMBU_CMYW_PHASE6_PRESET]
        assert set(labels) == {'C', 'M', 'Y', 'W'}

    def test_clear_cmyw_preset_exists(self):
        """CLEAR_CMYW_PRESET has 4 colors (stained-glass CMYW; grey dropped)."""
        assert len(CLEAR_CMYW_PRESET) == 4
        labels = [c.label for c in CLEAR_CMYW_PRESET]
        assert set(labels) == {'C', 'M', 'Y', 'W'}

    def test_get_preset_bambu(self):
        """get_preset returns BAMBU_CMYW_PHASE6_PRESET for 'bambu_cmyw_phase6'."""
        preset = get_preset("bambu_cmyw_phase6")
        assert preset == BAMBU_CMYW_PHASE6_PRESET

    def test_get_preset_clear(self):
        """get_preset returns CLEAR_CMYW_PRESET for 'clear_cmyw'."""
        preset = get_preset("clear_cmyw")
        assert preset == CLEAR_CMYW_PRESET


    def test_get_preset_phase6_cmyw(self):
        """get_preset returns Phase 6 CMYW preset for 'bambu_cmyw_phase6'."""
        preset = get_preset("bambu_cmyw_phase6")
        assert preset is not None
        assert len(preset) == 4
        assert {color.label for color in preset} == {"C", "M", "Y", "W"}


    def test_get_preset_invalid_returns_none(self):
        """get_preset returns None for unknown presets."""
        assert get_preset("unknown_preset") is None


class TestColorsFromConfigs:
    """Tests for Colors.from_configs() factory method."""

    def test_from_configs_creates_colors(self):
        """from_configs creates Colors instance with correct colors."""
        configs = [
            ColorConfig(name="Cyan", hex="#00FFFF", transmission_distance=3.0),
            ColorConfig(name="Magenta", hex="#FF00FF", transmission_distance=1.9),
            ColorConfig(name="Yellow", hex="#FFFF00", transmission_distance=2.5),
            ColorConfig(name="White", hex="#FFFFFF", transmission_distance=1.0),
        ]
        colors = Colors.from_configs(configs)

        assert len(colors) == 4
        assert colors.get_labels() == ['C', 'M', 'Y', 'W']
        assert colors['C'].name == "Cyan"
        assert colors['M'].name == "Magenta"

    def test_from_configs_with_preset(self):
        """from_configs works with preset configurations."""
        colors = Colors.from_configs(BAMBU_CMYW_PHASE6_PRESET)

        assert len(colors) == 4
        assert set(colors.get_labels()) == {'C', 'M', 'Y', 'W'}

    def test_from_configs_preserves_order(self):
        """from_configs preserves color order."""
        configs = [
            ColorConfig(name="Red", hex="#FF0000", transmission_distance=2.0),
            ColorConfig(name="Green", hex="#00FF00", transmission_distance=2.5),
            ColorConfig(name="Blue", hex="#0000FF", transmission_distance=3.0),
            ColorConfig(name="Yellow", hex="#FFFF00", transmission_distance=2.8),
        ]
        colors = Colors.from_configs(configs)

        assert colors.get_labels() == ['R', 'G', 'B', 'Y']

    def test_from_configs_sets_transmission_distance(self):
        """from_configs correctly sets transmission distance."""
        configs = [
            ColorConfig(name="Cyan", hex="#00FFFF", transmission_distance=5.5),
            ColorConfig(name="Magenta", hex="#FF00FF", transmission_distance=2.0),
            ColorConfig(name="Yellow", hex="#FFFF00", transmission_distance=3.0),
            ColorConfig(name="White", hex="#FFFFFF", transmission_distance=1.0),
        ]
        colors = Colors.from_configs(configs)

        assert colors['C'].td == 5.5

    def test_from_configs_preserves_folded_td_and_k(self):
        """from_configs carries the paper-fitted td/k and td_rgb verbatim."""
        colors = Colors.from_configs(BAMBU_CMYWK_PHASE6_PRESET)

        assert colors["C"].td == pytest.approx(2.1381256008389844)
        assert colors["C"].k == pytest.approx(3.4996)
        assert colors["W"].k == pytest.approx(6.3168)
        assert colors["K"].k == pytest.approx(23.1863)
        assert colors["C"].td_rgb is None

    def test_from_configs_preserves_per_channel_td(self):
        """from_configs carries the staircase per-channel td_rgb verbatim."""
        colors = Colors.from_configs(CLEAR_CMYW_PRESET)

        assert colors["C"].td_rgb == (
            1.3490352079515975, 2.5371501740106988, 4.088658622221301,
        )
        assert colors["W"].td_rgb == (
            17.949461574719358, 18.902845340687115, 17.207703003749966,
        )


class TestDynamicMeshMap:
    """Tests for dynamic mesh map generation."""

    @pytest.mark.parametrize("color_count", [4, 6, 8, 10])
    def test_initialize_color_mapping_creates_correct_combinations(self, color_count):
        """initialize_color_mapping creates N^layer_count combinations."""
        # Create N colors with unique first letters
        names = ["Alpha", "Beta", "Cyan", "Delta", "Echo", "Foxtrot",
                 "Green", "Hue", "Indigo", "Jade"][:color_count]
        configs = [
            ColorConfig(
                name=name,
                hex=f"#{(i*25):02x}{(i*25):02x}{(i*25):02x}",
                transmission_distance=float(i + 1)
            )
            for i, name in enumerate(names)
        ]
        colors = Colors.from_configs(configs)

        layer_count = 4
        initialize_color_mapping(
            layer_count=layer_count,
            layer_height=0.08,
            colors=colors
        )

        # Import to check global state
        from services import stl_generator
        assert stl_generator._current_colors is not None
        assert len(stl_generator._current_colors) == color_count

        # Verify combinations count: N^layer_count
        expected_combos = color_count ** layer_count
        actual_combos = len(stl_generator._reference_code_matrix.values.flatten())
        # Account for padding in matrix
        assert actual_combos >= expected_combos


class TestFilenamePrefix:
    """Tests for filename prefix generation."""

    def test_cmyw_produces_cmyw_prefix(self):
        """Standard CMYW colors produce 'CMYW' prefix."""
        colors = Colors()  # Default CMYK
        prefix = get_filename_prefix(colors)
        assert prefix == "CMYW"

    def test_cmyw_order_independent(self):
        """CMYW prefix works regardless of label order."""
        configs = [
            ColorConfig(name="White", hex="#FFFFFF", transmission_distance=7.2),
            ColorConfig(name="Yellow", hex="#FFFF00", transmission_distance=2.5),
            ColorConfig(name="Magenta", hex="#FF00FF", transmission_distance=1.9),
            ColorConfig(name="Cyan", hex="#00FFFF", transmission_distance=3.0),
        ]
        colors = Colors.from_configs(configs)
        prefix = get_filename_prefix(colors)
        assert prefix == "CMYW"

    def test_custom_colors_produce_custom_prefix(self):
        """Non-CMYW colors produce joined label prefix."""
        configs = [
            ColorConfig(name="Red", hex="#FF0000", transmission_distance=2.0),
            ColorConfig(name="Green", hex="#00FF00", transmission_distance=2.5),
            ColorConfig(name="Blue", hex="#0000FF", transmission_distance=3.0),
            ColorConfig(name="Yellow", hex="#FFFF00", transmission_distance=2.8),
        ]
        colors = Colors.from_configs(configs)
        prefix = get_filename_prefix(colors)
        assert prefix == "RGBY"

    def test_six_color_prefix(self):
        """Six colors produce six-character prefix."""
        configs = [
            ColorConfig(name="Red", hex="#FF0000", transmission_distance=2.0),
            ColorConfig(name="Orange", hex="#FF8000", transmission_distance=2.2),
            ColorConfig(name="Yellow", hex="#FFFF00", transmission_distance=2.5),
            ColorConfig(name="Green", hex="#00FF00", transmission_distance=2.5),
            ColorConfig(name="Blue", hex="#0000FF", transmission_distance=3.0),
            ColorConfig(name="Violet", hex="#8000FF", transmission_distance=2.8),
        ]
        colors = Colors.from_configs(configs)
        prefix = get_filename_prefix(colors)
        assert prefix == "ROYGBV"


class TestColorsGetLabels:
    """Tests for Colors.get_labels() method."""

    def test_get_labels_returns_strings(self):
        """get_labels returns list of strings."""
        colors = Colors()
        labels = colors.get_labels()
        assert isinstance(labels, list)
        assert all(isinstance(label, str) for label in labels)

    def test_get_labels_default_cmyw(self):
        """Default Colors has CMYW labels."""
        colors = Colors()
        labels = colors.get_labels()
        assert set(labels) == {'C', 'M', 'Y', 'W'}

    def test_get_labels_custom_colors(self):
        """Custom colors return correct labels."""
        configs = [
            ColorConfig(name="Red", hex="#FF0000", transmission_distance=2.0),
            ColorConfig(name="Green", hex="#00FF00", transmission_distance=2.5),
            ColorConfig(name="Blue", hex="#0000FF", transmission_distance=3.0),
            ColorConfig(name="Yellow", hex="#FFFF00", transmission_distance=2.8),
        ]
        colors = Colors.from_configs(configs)
        labels = colors.get_labels()
        assert labels == ['R', 'G', 'B', 'Y']


class TestBackwardCompatibility:
    """Tests ensuring backward compatibility with existing code."""

    def test_default_colors_unchanged(self):
        """Default Colors() behavior is unchanged."""
        colors = Colors()
        assert len(colors) == 4
        assert 'C' in colors.get_labels()
        assert 'M' in colors.get_labels()
        assert 'Y' in colors.get_labels()
        assert 'W' in colors.get_labels()

    def test_color_object_attributes(self):
        """Color objects have expected attributes."""
        colors = Colors()
        cyan = colors['C']
        assert hasattr(cyan, 'name')
        assert hasattr(cyan, 'td')
        assert hasattr(cyan, 'hex')
        assert hasattr(cyan, 'rgb')

    def test_initialize_color_mapping_without_colors(self):
        """initialize_color_mapping works without colors parameter."""
        initialize_color_mapping(layer_count=4, layer_height=0.08)

        from services import stl_generator
        assert stl_generator._reference_code_matrix is not None
        assert stl_generator._current_colors is not None
        assert len(stl_generator._current_colors) == 4

    def test_calibrated_colors_init_matrix(self):
        """Calibrated presets initialize the reference matrix under the
        unified formula."""
        colors = Colors.from_configs(BAMBU_CMYW_PHASE6_PRESET)
        initialize_color_mapping(layer_count=4, layer_height=0.08, colors=colors)

        from services import stl_generator
        assert stl_generator._reference_code_matrix is not None
