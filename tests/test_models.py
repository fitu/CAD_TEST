import json
from pathlib import Path
import cadquery as cq
import pytest
from herbal_roller.generate import build, export, load_config

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def config():
    return load_config(ROOT / 'config/sample.json')


@pytest.fixture(scope='module')
def parts(config):
    return build(config)


def test_all_parts_are_single_valid_solids(parts):
    assert len(parts) == 17
    for name, part in parts.items():
        assert len(part.solids().vals()) == 1, name
        assert part.val().isValid(), name
        assert part.val().Volume() > 0, name


def test_dimensions_and_clearances(parts, config):
    c = config
    for name in ('drive_drum', 'follower_drum'):
        bb = parts[name].val().BoundingBox()
        assert bb.xlen == pytest.approx(c['working_width'])
        assert bb.ylen == pytest.approx(2 * c['roller_radius'])
        assert bb.zlen == pytest.approx(2 * c['roller_radius'])
    expected = c['working_width'] * (2 * c['roller_spacing'] * c['apron_thickness'] +
        3.141592653589793 * ((c['roller_radius'] + c['apron_clearance'] + c['apron_thickness']) ** 2 -
                              (c['roller_radius'] + c['apron_clearance']) ** 2))
    assert parts['flexible_apron'].val().Volume() == pytest.approx(expected)
    assert parts['flexible_apron'].val().BoundingBox().zmin > 6
    for drum in ('drive_drum', 'follower_drum'):
        assert parts[drum].intersect(parts['flexible_apron']).val().Volume() == pytest.approx(0, abs=1e-7)


def test_step_roundtrip_and_assembly(tmp_path, config):
    parts = export(config, tmp_path)
    for name, original in parts.items():
        path = tmp_path / f'{name}.step'
        assert path.stat().st_size > 1000
        restored = cq.importers.importStep(str(path))
        assert len(restored.solids().vals()) == 1
        assert restored.val().isValid()
        assert restored.val().Volume() == pytest.approx(original.val().Volume(), rel=1e-6)
    path = tmp_path / 'assembly.step'
    assert path.stat().st_size > 1000
    restored = cq.importers.importStep(str(path))
    assert len(restored.solids().vals()) == len(parts)
    assert all(s.isValid() for s in restored.solids().vals())
    assert json.loads((tmp_path / 'manifest.json').read_text())['units'] == 'mm'


def test_rejects_overlapping_rollers(tmp_path, config):
    path = tmp_path / 'bad.json'
    path.write_text(json.dumps(dict(config, roller_spacing=5)))
    with pytest.raises(ValueError):
        load_config(path)


def test_alternative_configuration(config):
    alternate = dict(config, working_width=90, roller_radius=7, roller_spacing=24, axis_height=26)
    assert all(p.val().isValid() for p in build(alternate).values())
