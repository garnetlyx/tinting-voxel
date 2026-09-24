"""Unit tests for 3MF generation service."""
import pytest
import zipfile
from io import BytesIO

from core.blend_color import Colors
from services.threemf_generator import generate_3mf
from tests.label_maps import labels_from_blocks


def test_svg_3mf_uses_selected_backing_and_detail_size(monkeypatch, default_colors):
    from services import threemf_generator

    observed = {}
    compute = threemf_generator.compute_reference_matrices
    finalize = threemf_generator.finalize_vector_partition

    def capture_matrix(*args, **kwargs):
        observed['matrix'] = kwargs
        return compute(*args, **kwargs)

    def capture_partition(*args):
        observed['partition'] = args
        return finalize(*args)

    monkeypatch.setattr(threemf_generator, 'compute_reference_matrices', capture_matrix)
    monkeypatch.setattr(threemf_generator, 'finalize_vector_partition', capture_partition)
    result = threemf_generator.generate_svg_3mf(
        vector_results=[{
            'color': (255, 0, 0),
            'regions': [{'outer': [(0, 0), (4, 0), (4, 4), (0, 4)], 'holes': []}],
        }],
        layer_height=0.08,
        pixel_size=0.2,
        layer_count=4,
        image_dimensions={'width': 5, 'height': 5},
        colors=default_colors,
        white_backing_layers=2,
        backing_mode='black',
        detail_size=0.82,
    )
    assert zipfile.is_zipfile(BytesIO(result))
    assert observed['matrix']['backing_layers'] == 2
    assert observed['matrix']['backing_mode'] == 'black'
    assert observed['partition'][2:] == (0.2, 0.82)


@pytest.fixture
def default_colors():
    return Colors()


@pytest.fixture
def simple_color_blocks():
    return [
        {
            'r': 0, 'g': 255, 'b': 255,
            'count': 2,
            'pixels': [{'x': 0, 'y': 0}, {'x': 1, 'y': 0}],
            'hex': '#00FFFF',
        },
        {
            'r': 255, 'g': 0, 'b': 255,
            'count': 1,
            'pixels': [{'x': 2, 'y': 0}],
            'hex': '#FF00FF',
        },
    ]


class TestGenerate3MF:
    """Tests for generate_3mf function."""

    def test_basic_output_is_bytes(self, simple_color_blocks, default_colors):
        """generate_3mf returns bytes."""
        result = generate_3mf(
            color_blocks=simple_color_blocks,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            labels=labels_from_blocks(simple_color_blocks, 4, 4),
            colors=default_colors,
        )
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_output_is_valid_zip(self, simple_color_blocks, default_colors):
        """3MF is a ZIP archive."""
        result = generate_3mf(
            color_blocks=simple_color_blocks,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            labels=labels_from_blocks(simple_color_blocks, 4, 4),
            colors=default_colors,
        )
        buf = BytesIO(result)
        assert zipfile.is_zipfile(buf)

    def test_3mf_contains_model(self, simple_color_blocks, default_colors):
        """3MF archive contains 3D/3dmodel.model XML file."""
        result = generate_3mf(
            color_blocks=simple_color_blocks,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            labels=labels_from_blocks(simple_color_blocks, 4, 4),
            colors=default_colors,
        )
        buf = BytesIO(result)
        with zipfile.ZipFile(buf, 'r') as zf:
            names = zf.namelist()
            has_model = any('3dmodel.model' in n for n in names)
            assert has_model, f"Expected 3dmodel.model in archive, got: {names}"

    def test_empty_color_blocks_raises(self, default_colors):
        """Empty color blocks raises ValueError."""
        with pytest.raises(ValueError, match="No color blocks"):
            generate_3mf(
                color_blocks=[],
                labels=labels_from_blocks([], 4, 4),
                layer_height=0.08,
                pixel_size=0.08,
                layer_count=4,
                colors=default_colors,
            )

    def test_none_colors_raises(self, simple_color_blocks):
        """None colors raises ValueError."""
        with pytest.raises(ValueError, match="Colors instance is required"):
            generate_3mf(
                color_blocks=simple_color_blocks,
                layer_height=0.08,
                pixel_size=0.08,
                layer_count=4,
                labels=labels_from_blocks(simple_color_blocks, 4, 4),
                colors=None,
            )

    def test_with_color_hex_map(self, simple_color_blocks, default_colors):
        """3MF generation with color hex map succeeds."""
        result = generate_3mf(
            color_blocks=simple_color_blocks,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            labels=labels_from_blocks(simple_color_blocks, 4, 4),
            colors=default_colors,
            color_hex_map={'C': '#0086D6', 'M': '#EC008C', 'Y': '#F4EE2A', 'W': '#FFFFFF'},
        )
        assert isinstance(result, bytes)
        assert len(result) > 0


def _model_xml(data: bytes):
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(BytesIO(data)) as archive:
        return ET.fromstring(archive.read("3D/3dmodel.model"))


CORE = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"
MATERIAL = "{http://schemas.microsoft.com/3dmanufacturing/material/2015/02}"


def test_3mf_is_one_object_with_a_colored_part_per_filament(simple_color_blocks, default_colors):
    """Slicers load one multi-part object (layers stay in register) whose parts
    carry the filament colors as a standard 3MF color group."""
    data = generate_3mf(
        color_blocks=simple_color_blocks, labels=labels_from_blocks(simple_color_blocks, 4, 4),
        layer_height=0.08, pixel_size=0.5, layer_count=4, colors=default_colors,
        color_hex_map={label: default_colors[label].hex for label in default_colors.get_labels()},
    )
    model = _model_xml(data)
    resources = model.find(f"{CORE}resources")
    colors = [c.get("color") for c in resources.find(f"{MATERIAL}colorgroup")]
    objects = resources.findall(f"{CORE}object")
    parts = [o for o in objects if o.find(f"{CORE}mesh") is not None]
    assembly = [o for o in objects if o.find(f"{CORE}components") is not None]

    assert len(assembly) == 1
    items = model.find(f"{CORE}build").findall(f"{CORE}item")
    assert [item.get("objectid") for item in items] == [assembly[0].get("id")]
    assert [c.get("objectid") for c in assembly[0].find(f"{CORE}components")] == [p.get("id") for p in parts]
    by_name = {default_colors[label].name: default_colors[label].hex.upper() for label in default_colors.get_labels()}
    for part in parts:
        assert part.get("pid") == resources.find(f"{MATERIAL}colorgroup").get("id")
        assert colors[int(part.get("pindex"))] == by_name[part.get("name")]


def test_3mf_parts_share_vertices_and_keep_every_box_face():
    from services.threemf_writer import Part, write_3mf

    boxes = [((0.0, 1.0), (0.0, 1.0), (0.0, 0.08)), ((1.0, 2.0), (0.0, 1.0), (0.0, 0.08))]
    model = _model_xml(write_3mf([Part("Cyan", "#3d79c6", boxes)], "Print"))
    mesh = model.find(f"{CORE}resources").find(f"{CORE}object").find(f"{CORE}mesh")
    vertices = [(float(v.get("x")), float(v.get("y")), float(v.get("z"))) for v in mesh.find(f"{CORE}vertices")]
    triangles = [tuple(int(t.get(k)) for k in ("v1", "v2", "v3")) for t in mesh.find(f"{CORE}triangles")]
    assert len(vertices) == 12  # two boxes sharing four corners
    assert len(triangles) == 24
    assert sorted({v[0] for v in vertices}) == [0.0, 1.0, 2.0]
    assert {v[2] for v in vertices} == {0.0, 0.08}
    assert all(max(t) < len(vertices) for t in triangles)
