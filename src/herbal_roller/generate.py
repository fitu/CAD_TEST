"""Revision 2: axially insertable D shafts, bolted split bearings, oriented meshes.

All CAD geometry is in assembled millimetre coordinates: X = shaft direction.
Hardware is an unthreaded envelope, not a printable substitute for purchased parts.
"""
import argparse
import json
import math
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import cadquery as cq


def cylinder(x, y, z, r, length):
    return cq.Workplane('YZ', origin=(x, y, z)).circle(r).extrude(length)


def vertical(x, y, z, r, length):
    return cq.Workplane('XY', origin=(x, y, z)).circle(r).extrude(length)


def box(x, y, z, dx, dy, dz):
    return cq.Workplane('XY').box(dx, dy, dz).translate((x, y, z))


def capsule(x, z, spacing, radius, length, center_y=0):
    shape = box(x + length / 2, center_y, z, length, spacing, 2 * radius)
    for y in (center_y - spacing / 2, center_y + spacing / 2):
        shape = shape.union(cylinder(x, y, z, radius, length))
    return shape


def d_profile(x, y, z, radius, flat_depth, length, clearance=0):
    """D prism with clearance on BOTH curved and planar mating surfaces."""
    rr = radius + clearance
    flat_z = z - radius + flat_depth - clearance
    shape = cylinder(x, y, z, rr, length)
    return shape.cut(box(x + length / 2, y, flat_z - rr, length + 2, 4 * rr, 2 * rr))


def ring(x, y, z, outer, inner, length):
    return cylinder(x, y, z, outer, length).cut(cylinder(x - 1, y, z, inner, length + 2))


def hex_z(x, y, z, flats, height):
    return cq.Workplane('XY', origin=(x, y, z)).polygon(6, flats / math.cos(math.pi / 6)).extrude(height)


def hex_x(x, y, z, flats, height):
    return cq.Workplane('YZ', origin=(x, y, z)).polygon(6, flats / math.cos(math.pi / 6)).extrude(height)


def load_config(path):
    c = json.loads(Path(path).read_text())
    keys = {'working_width', 'roller_radius', 'roller_spacing', 'axis_height',
            'shaft_radius', 'shaft_flat_depth', 'keyed_clearance', 'bearing_clearance',
            'loading_travel', 'apron_thickness', 'apron_clearance', 'apron_seam_overlap', 'apron_open_slack'}
    if set(c) != keys or any(isinstance(v, bool) or not isinstance(v, (float, int))
                            or not math.isfinite(v) or not 0 < v < 1000 for v in c.values()):
        raise ValueError('Exactly the documented finite positive dimensions are required')
    # Hardware is fixed M3x40. Limits avoid implying arbitrary CAD is hardware-compatible.
    if c['axis_height'] != 32 or c['shaft_radius'] != 3:
        raise ValueError('Revision 2 uses 32 mm shaft height and 6 mm shafts with M3x40 frame bolts')
    if not 50 <= c['working_width'] <= 110 or not 7 <= c['roller_radius'] <= 9:
        raise ValueError('Supported working width: 50..110; roller radius: 7..9 mm')
    if not 0.5 <= c['shaft_flat_depth'] <= 0.8:
        raise ValueError('Flat depth must be 0.5..0.8 mm to retain a keyed face after clearance')
    if not 0.15 <= c['keyed_clearance'] <= 0.4 or not 0.2 <= c['bearing_clearance'] <= 0.5:
        raise ValueError('Unsupported keyed or bearing fit')
    if not 2 * c['roller_radius'] + 6 <= c['roller_spacing'] <= 32:
        raise ValueError('Roller spacing must provide at least 6 mm surface gap and be <=32 mm')
    if not 6 <= c['loading_travel'] <= 16:
        raise ValueError('Loading travel must be 6..16 mm')
    if not 0.2 <= c['apron_thickness'] <= 0.8 or c['apron_clearance'] > 0.5:
        raise ValueError('Unsupported apron section')
    if not 8 <= c['apron_open_slack'] <= 16:
        raise ValueError('Open-position apron slack must be 8..16 mm')
    return c


def layout(c):
    w, d = c['working_width'], c['roller_spacing']
    inner = w / 2 + 6
    outer = inner + 8
    return dict(inner=inner, outer=outer, center=inner + 4, front=-d / 2,
                rear=d / 2, ycenter=c['loading_travel'] / 2,
                wall_length=d + c['loading_travel'] + 32)


def hardware(name):
    return name.startswith('hw_')


def reference(name):
    return name in ('flexible_apron_reference', 'apron_cutting_template')


def auxiliary(name):
    return name == 'fit_coupon' or name == 'apron_cutting_template'


def build(c):
    w, r, h, sr = (c[k] for k in ('working_width', 'roller_radius', 'axis_height', 'shaft_radius'))
    q = layout(c)
    inner, outer, front, rear = (q[k] for k in ('inner', 'outer', 'front', 'rear'))
    travel, b = c['loading_travel'], sr + c['bearing_clearance']
    p = {}
    frame = box(0, q['ycenter'], 3, w + 44, q['wall_length'] + 12, 6)
    for side, sign in [('left', -1), ('right', 1)]:
        x = sign * q['center']
        low = box(x, q['ycenter'], (6 + h) / 2, 8, q['wall_length'], h - 6)
        cap = box(x, q['ycenter'], h + 4, 8, q['wall_length'], 8)
        drive_slot = cylinder(x - 5, front, h, b, 10)
        follower_slot = capsule(x - 5, h, travel, b, 10, rear + travel / 2)
        # Open top on the lower saddles; cap completes the upper bearing half.
        low = low.cut(drive_slot).cut(follower_slot)
        cap = cap.cut(drive_slot).cut(follower_slot)
        for end, y in [('front', front - 10), ('rear', rear + travel + 10)]:
            hole = vertical(x, y, -1, 1.7, h + 11)
            low, cap = low.cut(hole), cap.cut(hole)
            frame = frame.cut(hole).cut(hex_z(x, y, 0, 5.9, 3.5))
            p[f'hw_{side}_{end}_M3x40_bolt'] = vertical(x, y, 0, 1.5, h + 8).union(vertical(x, y, h + 8, 2.75, 3))
            p[f'hw_{side}_{end}_M3_nut'] = hex_z(x, y, 1.1, 5.5, 2.4).cut(vertical(x, y, 0, 1.5, 5))
        frame = frame.union(low)
        p[f'{side}_bearing_cap'] = cap
    p['frame'] = frame
    wheel_right, wheel_left = -outer - 7.3, -outer - 13.3
    for role, y in [('drive', front), ('follower', rear)]:
        drum = cylinder(-w / 2, y, h, r, w)
        bore = (d_profile(-w / 2 - 1, y, h, sr, c['shaft_flat_depth'], w + 2, c['keyed_clearance'])
                if role == 'drive' else cylinder(-w / 2 - 1, y, h, b, w + 2))
        p[f'{role}_drum'] = drum.cut(bore)
        lo = wheel_left - 3.7 if role == 'drive' else -outer - 5
        hi = outer + 5
        shaft = d_profile(lo, y, h, sr, c['shaft_flat_depth'], hi - lo)
        pins = [wheel_left - 1.2 if role == 'drive' else -outer - 2.5, outer + 2.5]
        for side, px in zip(('left', 'right'), pins):
            shaft = shaft.cut(vertical(px, y, h - sr - 1, 1.1, 2 * sr + 2))
            # Simplified unbent 2x12 split cotter envelope, slit included.
            pin = vertical(px, y, h - 6, 0.95, 12)
            pin = pin.cut(box(px, y, h - 2, 0.25, 3, 8))
            p[f'hw_{side}_{role}_2x12_split_pin'] = pin
        p[f'{role}_shaft'] = shaft
        for side, sign in [('left', -1), ('right', 1)]:
            sx = w / 2 if sign > 0 else -inner + 0.3
            p[f'{side}_{role}_spacer'] = ring(sx, y, h, 5, sr + 0.3, 5.7)
            wx = outer + 0.3 if sign > 0 else -outer - 1.3
            p[f'hw_{side}_{role}_M6_washer'] = ring(wx, y, h, 6, 3.3, 1)
    # D bore lets the complete wheel slide axially on/off the constant-section shaft.
    wheel = cylinder(wheel_left, front, h, 18, 6)
    wheel = wheel.cut(d_profile(wheel_left - 1, front, h, sr, c['shaft_flat_depth'], 8, c['keyed_clearance']))
    crank_z = h + 13
    wheel = wheel.cut(cylinder(wheel_left - 1, front, crank_z, 1.7, 8))
    p['handwheel'] = wheel
    p['wheel_spacer'] = ring(wheel_right, front, h, 5, 3.3, 6)
    # Shoulder sleeve takes bolt clamp force; the grip turns with 0.3 mm end clearance.
    bolt_start = wheel_left - 14.7
    p['crank_sleeve'] = ring(bolt_start + 0.5, front, crank_z, 2.5, 1.7, 13.7)
    p['crank_grip'] = ring(bolt_start + 0.8, front, crank_z, 4.5, 2.8, 13.1)
    p['hw_crank_outer_M3_washer'] = ring(bolt_start, front, crank_z, 4, 1.7, 0.5)
    p['hw_crank_inner_M3_washer'] = ring(wheel_left - 0.5, front, crank_z, 4, 1.7, 0.5)
    p['hw_crank_M3x25_bolt'] = cylinder(bolt_start, front, crank_z, 1.5, 25).union(cylinder(bolt_start - 3, front, crank_z, 2.75, 3))
    p['hw_crank_M3_nut'] = hex_x(wheel_right, front, crank_z, 5.5, 2.4).cut(cylinder(wheel_right - 1, front, crank_z, 1.5, 5))
    # Display envelope only: working apron has slack, not represented by this shape.
    ir = r + c['apron_clearance']
    width = w - 1
    p['flexible_apron_reference'] = capsule(-width / 2, h, c['roller_spacing'], ir + c['apron_thickness'], width).cut(
        capsule(-width / 2 - 1, h, c['roller_spacing'], ir, width + 2))
    length = apron_dimensions(c)['cut_length_mm']
    p['apron_cutting_template'] = box(0, 0, c['apron_thickness'] / 2, width, length, c['apron_thickness'])
    # Three individually labelled fits in a sacrificial test plate, not in assembly.
    coupon = box(0, 0, 3, 36, 14, 6)
    for x, clearance in [(-11, 0.15), (0, 0.25), (11, 0.35)]:
        cut = d_profile(-4, 0, 0, sr, c['shaft_flat_depth'], 8, clearance)
        cut = cut.rotate((0, 0, 0), (0, 1, 0), -90).translate((x, 0, 3))
        coupon = coupon.cut(cut)
    p['fit_coupon'] = coupon
    return p


def apron_dimensions(c):
    neutral_radius = c['roller_radius'] + c['apron_clearance'] + c['apron_thickness'] / 2
    open_path = 2 * (c['roller_spacing'] + c['loading_travel']) + 2 * math.pi * neutral_radius
    loop = open_path + c['apron_open_slack']  # Loading requires slack even at the outer stop.
    return dict(width_mm=c['working_width'] - 1, loop_length_mm=loop,
                seam_overlap_mm=c['apron_seam_overlap'],
                cut_length_mm=loop + c['apron_seam_overlap'],
                open_slack_mm=c['apron_open_slack'],
                closed_slack_mm=2 * c['loading_travel'] + c['apron_open_slack'])


def print_pose(name, part):
    """Return mesh pose without altering geometry or assembly STEP coordinates."""
    if name.endswith('_bearing_cap'):
        part = part.rotate((0, 0, 0), (1, 0, 0), 180)
    elif name not in ('frame', 'fit_coupon') and not name.endswith('_shaft') and not reference(name) and not hardware(name):
        part = part.rotate((0, 0, 0), (0, 1, 0), -90)
    bb = part.val().BoundingBox()
    return part.translate((-bb.xmin, -bb.ymin, -bb.zmin))


def export(c, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    parts = build(c)
    assembly = cq.Assembly(name='herbal_paper_roller_v2_closed')
    opened = cq.Assembly(name='herbal_paper_roller_v2_open')
    manifest = dict(revision=2, units='mm', configuration=c, apron=apron_dimensions(c), parts={})
    current_files = set()
    print_files = []
    for name, part in parts.items():
        shape = part.val()
        if not shape.isValid() or len(part.solids().vals()) != 1 or shape.Volume() <= 0:
            raise RuntimeError(f'Invalid solid: {name}')
        step = out / f'{name}.step'
        cq.exporters.export(part, str(step))
        category = 'hardware' if hardware(name) else 'reference' if reference(name) else 'printed'
        subdir = 'stl/hardware' if hardware(name) else 'stl/reference' if reference(name) else 'stl'
        dest = out / subdir / f'{name}.stl'
        dest.parent.mkdir(parents=True, exist_ok=True)
        placed = print_pose(name, part)
        cq.exporters.export(placed, str(dest), tolerance=0.01, angularTolerance=0.1)
        current_files.update((step.resolve(), dest.resolve()))
        if category == 'printed':
            print_files.append(dest)
        if not auxiliary(name):
            col = cq.Color(0.25, 0.5, 0.9, 0.35) if reference(name) else cq.Color(0.55, 0.58, 0.6) if hardware(name) else cq.Color(0.9, 0.65, 0.25)
            assembly.add(part, name=name, color=col)
            if name == 'flexible_apron_reference':
                # Its closed taut envelope is intentionally omitted from open-state CAD.
                pass
            else:
                pos = part.translate((0, c['loading_travel'], 0)) if 'follower' in name else part
                opened.add(pos, name=name, color=col)
        bb, pb = shape.BoundingBox(), placed.val().BoundingBox()
        manifest['parts'][name] = dict(category=category, in_assembly=not auxiliary(name),
            volume_mm3=shape.Volume(), bounds_mm=[bb.xlen, bb.ylen, bb.zlen],
            stl_bounds_mm=[pb.xlen, pb.ylen, pb.zlen], stl_path=str(dest.relative_to(out)))
    assembly.export(str(out / 'assembly.step'))
    opened.export(str(out / 'assembly_open.step'))
    # Remove obsolete generator-owned files using the prior manifest, never arbitrary outputs.
    old_manifest = out / 'manifest.json'
    if old_manifest.exists():
        previous = json.loads(old_manifest.read_text())
        for old_name in previous.get('parts', {}):
            for old_file in [out / f'{old_name}.step', out / 'stl' / f'{old_name}.stl',
                             out / 'stl/reference' / f'{old_name}.stl', out / 'stl/hardware' / f'{old_name}.stl']:
                if old_file.resolve() not in current_files and old_file.is_file():
                    old_file.unlink()
    old_manifest.write_text(json.dumps(manifest, indent=2) + '\n')
    with ZipFile(out / 'slicer_parts.zip', 'w', compression=ZIP_DEFLATED) as archive:
        for path in sorted(print_files):
            archive.write(path, path.name)
        archive.writestr('READ_ME.txt',
            'Revision 2. Millimetres, 100% scale. Meshes are oriented for printing.\n'
            'Frame: base down. Caps: flat top down. Shafts: small flat down.\n'
            'Drums, wheel, grip, sleeves and spacers: axis vertical; brim suggested for drums.\n'
            'fit_coupon is calibration tooling, not an assembly part. Print it before a full set.\n'
            'Purchase the metal fasteners listed in README. Hardware and apron are excluded.\n'
            'Untested prototype. See README for assembly order and unresolved physical validation.\n')
    return parts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config/sample.json')
    parser.add_argument('--out', default='outputs')
    args = parser.parse_args()
    parts = export(load_config(args.config), args.out)
    print(f'Exported {len(parts)} parts, closed/open STEP assemblies and oriented STL ZIP to {args.out}')


if __name__ == '__main__':
    main()
