import itertools
import json
from pathlib import Path
from zipfile import ZipFile

import cadquery as cq
import pytest
import trimesh

from herbal_roller.generate import (
    apron_dimensions, auxiliary, build, cylinder, export, hardware,
    layout, load_config, print_pose, reference,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def config():
    return load_config(ROOT / 'config/sample.json')


@pytest.fixture(scope='module')
def parts(config):
    return build(config)


@pytest.fixture(scope='module')
def exported(tmp_path_factory, config):
    directory = tmp_path_factory.mktemp('exports')
    export(config, directory)
    return directory


def intersection_volume(a, b):
    bb1, bb2 = a.val().BoundingBox(), b.val().BoundingBox()
    # Skip parts whose bounds have no positive overlap on at least one axis.
    if any(min(getattr(bb1, k + 'max'), getattr(bb2, k + 'max')) -
           max(getattr(bb1, k + 'min'), getattr(bb2, k + 'min')) < 1e-6 for k in 'xyz'):
        return 0
    return sum(s.Volume() for s in a.intersect(b).solids().vals())


def test_all_parts_are_single_valid_solids(parts):
    assert len(parts) == 38
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
    bb = parts['frame'].val().BoundingBox()
    assert bb.xlen == pytest.approx(c['working_width'] + 44)
    assert bb.zlen == pytest.approx(c['axis_height'])
    for name in ('drive_shaft', 'follower_shaft'):
        bb = parts[name].val().BoundingBox()
        assert bb.ylen == pytest.approx(2 * c['shaft_radius'])
        assert bb.zlen == pytest.approx(2 * c['shaft_radius'] - c['shaft_flat_depth'])
    a = apron_dimensions(c)
    assert a['cut_length_mm'] - a['loop_length_mm'] == pytest.approx(c['apron_seam_overlap'])
    assert a['closed_slack_mm'] == pytest.approx(2 * c['loading_travel'] + c['apron_open_slack'])


def test_closed_assembly_has_no_solid_interferences(parts):
    items = [(n, p) for n, p in parts.items() if not auxiliary(n)]
    for (na, a), (nb, b) in itertools.combinations(items, 2):
        assert intersection_volume(a, b) < 1e-5, f'{na} intersects {nb}'


def test_d_shaft_can_slide_axially_through_drum_and_wheel(parts, config):
    # A full D-prism envelope, not just the final position, must pass the bore.
    # Cross holes only remove material, so this continuous envelope is conservative.
    q, sr, h = layout(config), config['shaft_radius'], config['axis_height']
    from herbal_roller.generate import d_profile
    for role in ('drive', 'follower'):
        y = q['front'] if role == 'drive' else q['rear']
        envelope = d_profile(-250, y, h, sr, config['shaft_flat_depth'], 500)
        assert intersection_volume(envelope, parts[f'{role}_drum']) < 1e-6
        if role == 'drive':
            assert intersection_volume(envelope, parts['handwheel']) < 1e-6
    # Retaining pins are separate removable hardware, never an integral obstruction.
    assert len([n for n in parts if n.endswith('_split_pin')]) == 4


def test_subassemblies_lower_into_uncapped_frame(parts):
    for dz in (0, 0.5, 1, 2, 3, 4, 8, 20, 40):
        for role in ('drive', 'follower'):
            for suffix in ('shaft', 'drum', 'spacer'):
                names = [f'{role}_{suffix}'] if suffix != 'spacer' else [f'left_{role}_spacer', f'right_{role}_spacer']
                for name in names:
                    assert intersection_volume(parts[name].translate((0, 0, dz)), parts['frame']) < 1e-6, (name, dz)


def test_follower_travel_has_clearance(parts, config):
    moving = [(n, p) for n, p in parts.items() if 'follower' in n]
    stationary = [(n, p) for n, p in parts.items()
                  if 'follower' not in n and not reference(n) and not auxiliary(n)]
    for fraction in (0, 0.1, 0.25, 0.5, 0.75, 0.9, 1):
        for name, part in moving:
            moved = part.translate((0, fraction * config['loading_travel'], 0))
            for other, fixed in stationary:
                assert intersection_volume(moved, fixed) < 1e-5, (fraction, name, other)


def test_crank_swept_clearance(parts, config):
    q = layout(config)
    center = (0, q['front'], config['axis_height'])
    end = (1, q['front'], config['axis_height'])
    crank = [n for n in parts if n.startswith('hw_crank') or n in ('crank_grip', 'crank_sleeve')]
    obstacles = [n for n in parts if n not in crank and not auxiliary(n) and not reference(n)]
    for angle in range(0, 360, 30):
        for name in crank:
            moved = parts[name].rotate(center, end, angle)
            # Wheel rotates along with its off-centre hole; do not compare against its static pose.
            for fixed in obstacles:
                if fixed != 'handwheel':
                    assert intersection_volume(moved, parts[fixed]) < 1e-5, (angle, name, fixed)


def test_print_poses_have_actual_planar_beds(parts):
    for name, part in parts.items():
        if hardware(name) or reference(name):
            continue
        placed = print_pose(name, part)
        assert placed.val().BoundingBox().zmin == pytest.approx(0, abs=1e-6)
        bed_faces = [f for f in placed.faces().vals()
                     if f.geomType() == 'PLANE' and abs(f.BoundingBox().zmin) < 1e-6
                     and abs(f.BoundingBox().zmax) < 1e-6]
        assert sum(f.Area() for f in bed_faces) > 1, name
        if name.endswith('_shaft'):
            assert sum(f.Area() for f in bed_faces) > 100, name
        if name in ('drive_drum', 'follower_drum'):
            assert placed.val().BoundingBox().zlen == pytest.approx(74)


def test_step_roundtrip_and_assemblies(exported, parts):
    for name, original in parts.items():
        path = exported / f'{name}.step'
        assert path.stat().st_size > 1000
        restored = cq.importers.importStep(str(path))
        assert len(restored.solids().vals()) == 1
        assert restored.val().isValid()
        assert restored.val().Volume() == pytest.approx(original.val().Volume(), rel=1e-6)
    expected = sum(not auxiliary(n) for n in parts)
    for filename, count in [('assembly.step', expected), ('assembly_open.step', expected - 1)]:
        restored = cq.importers.importStep(str(exported / filename))
        assert len(restored.solids().vals()) == count
        assert all(s.isValid() for s in restored.solids().vals())


def test_stl_meshes_and_slicer_bundle(exported, parts):
    paths = list((exported / 'stl').rglob('*.stl'))
    assert len(paths) == len(parts)
    for path in paths:
        mesh = trimesh.load_mesh(path)
        assert mesh.is_watertight, path.name
        assert mesh.is_winding_consistent, path.name
        assert mesh.is_volume, path.name
        assert len(mesh.split(only_watertight=False)) == 1, path.name
        pose = print_pose(path.stem, parts[path.stem]).val()
        bb = pose.BoundingBox()
        assert mesh.extents == pytest.approx([bb.xlen, bb.ylen, bb.zlen], abs=0.03)
        assert mesh.bounds[0] == pytest.approx([0, 0, 0], abs=0.03)
        assert mesh.volume == pytest.approx(pose.Volume(), rel=0.005)
    with ZipFile(exported / 'slicer_parts.zip') as archive:
        assert archive.testzip() is None
        expected = {n + '.stl' for n in parts if not hardware(n) and not reference(n)}
        assert {n for n in archive.namelist() if n.endswith('.stl')} == expected
    manifest = json.loads((exported / 'manifest.json').read_text())
    assert manifest['revision'] == 2
    assert manifest['units'] == 'mm'


@pytest.mark.parametrize('key,value', [('roller_spacing', 5), ('axis_height', 24),
    ('shaft_flat_depth', 3), ('keyed_clearance', 0), ('working_width', float('nan'))])
def test_rejects_invalid_configuration(tmp_path, config, key, value):
    path = tmp_path / 'bad.json'
    path.write_text(json.dumps(dict(config, **{key: value})))
    with pytest.raises(ValueError):
        load_config(path)


def test_alternative_configuration(config):
    alternate = dict(config, working_width=90, roller_radius=9, roller_spacing=28, loading_travel=10)
    assert all(p.val().isValid() for p in build(alternate).values())


def test_caps_install_from_above(parts):
    stationary = [(n, p) for n, p in parts.items() if not auxiliary(n)
                  and not n.endswith('_bearing_cap') and not ('M3x40' in n)]
    for name in ('left_bearing_cap', 'right_bearing_cap'):
        for dz in (0, 0.5, 1, 2, 3, 4, 8, 20):
            for other, part in stationary:
                assert intersection_volume(parts[name].translate((0, 0, dz)), part) < 1e-5, (name, dz, other)
