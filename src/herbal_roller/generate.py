"""Generate millimetre-scale solids; global X is the roller axis."""
import argparse
import json
from pathlib import Path
import cadquery as cq


def cylinder(x, y, z, r, length):
    return cq.Workplane('YZ', origin=(x, y, z)).circle(r).extrude(length)


def capsule(x, z, spacing, radius, length):
    section = cq.Workplane('YZ', origin=(x, 0, z)).rect(spacing, 2 * radius).extrude(length)
    for y in (-spacing / 2, spacing / 2):
        section = section.union(cylinder(x, y, z, radius, length))
    return section


def load_config(path):
    c = json.loads(Path(path).read_text())
    required = {'working_width', 'roller_radius', 'roller_spacing', 'axis_height',
                'shaft_radius', 'bearing_clearance', 'apron_thickness', 'apron_clearance'}
    if set(c) != required or any(not isinstance(v, (int, float)) or isinstance(v, bool)
                                 or not 0 < v < 1000 for v in c.values()):
        raise ValueError('Configuration requires exactly the documented positive numeric dimensions')
    if c['working_width'] < 30 or c['roller_radius'] <= c['shaft_radius'] + 1:
        raise ValueError('Insufficient roller width or shaft wall')
    if c['roller_spacing'] <= 2 * (c['roller_radius'] + c['apron_clearance'] + c['apron_thickness']):
        raise ValueError('Rollers/apron need separation')
    if c['axis_height'] <= c['roller_radius'] + c['apron_thickness'] + 8:
        raise ValueError('Roller must clear base')
    if c['bearing_clearance'] > 0.5 or c['shaft_radius'] > 3:
        raise ValueError('Bearing clearance or shaft radius exceeds supported frame design')
    return c


def build(c):
    w, r, d, h, sr = (c[k] for k in ('working_width', 'roller_radius', 'roller_spacing', 'axis_height', 'shaft_radius'))
    b = sr + c['bearing_clearance']
    side = w / 2 + 5
    parts = {}
    parts['base'] = cq.Workplane('XY').box(w + 30, d + 40, 6).translate((0, 0, 3))
    # Side cheeks locate the drive shaft and cradle the liftable follower shaft.
    for label, x in [('left', -side - 4), ('right', side)]:
        wall = cq.Workplane('XY').box(4, d + 24, h + 7).translate((x + 2, 0, 6 + (h + 7) / 2))
        wall = wall.cut(cylinder(x - 1, -d / 2, h, b, 6))
        saddle = cylinder(x - 1, d / 2, h, b, 6)
        saddle = saddle.union(cq.Workplane('XY').box(6, 2 * b, 25).translate((x + 2, d / 2, h + 12.5)))
        parts[f'{label}_cheek'] = wall.cut(saddle)
    for label, y in [('drive', -d / 2), ('follower', d / 2)]:
        parts[f'{label}_drum'] = cylinder(-w / 2, y, h, r, w).cut(cylinder(-w / 2 - 1, y, h, sr, w + 2))
        shaft = cylinder(-side - 12, y, h, sr, 2 * side + 24)
        if label == 'drive':
            key = cq.Workplane('XY', origin=(0, y, h)).circle(0.8).extrude(r - 0.5)
            shaft = shaft.union(key)
            parts['drive_drum'] = parts['drive_drum'].cut(key)
            shaft = shaft.union(cq.Workplane('YZ', origin=(-side - 18, y, h)).polygon(6, 2 * sr).extrude(6))
        parts[f'{label}_shaft'] = shaft
    # Arms rotate about drive shaft; follower lifts with both arms as a unit.
    for label, x in [('left', -side - 7), ('right', side + 5)]:
        arm = capsule(x, h, d, 4, 2)
        for y in (-d / 2, d / 2):
            arm = arm.cut(cylinder(x - 1, y, h, b, 4))
        parts[f'{label}_swing_arm'] = arm
    # Slip washers retain shafts; real hardware needs a separately resolved retention method.
    for label, x in [('left', -side - 10), ('right', side + 9)]:
        for axis, y in [('drive', -d / 2), ('follower', d / 2)]:
            parts[f'{label}_{axis}_collar'] = cylinder(x, y, h, 3.5, 1.5).cut(cylinder(x - 1, y, h, sr, 4))
    wheel_x = -side - 18
    wheel = cylinder(wheel_x, -d / 2, h, 16, 4)
    wheel = wheel.cut(cq.Workplane('YZ', origin=(wheel_x - 1, -d / 2, h)).polygon(6, 2 * sr + 0.15).extrude(6))
    parts['handwheel'] = wheel
    parts['crank_pin'] = cylinder(wheel_x - 12, -d / 2, h + 11, 1.5, 14)
    parts['handwheel'] = wheel.cut(cylinder(wheel_x - 1, -d / 2, h + 11, 1.5, 3))
    parts['crank_grip'] = cylinder(wheel_x - 12, -d / 2, h + 11, 3, 9).cut(cylinder(wheel_x - 13, -d / 2, h + 11, 1.7, 11))
    inner = r + c['apron_clearance']
    parts['flexible_apron'] = capsule(-w / 2, h, d, inner + c['apron_thickness'], w).cut(capsule(-w / 2 - 1, h, d, inner, w + 2))
    return parts


def export(c, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    parts = build(c)
    assembly = cq.Assembly(name='herbal_paper_roller')
    manifest = {'units': 'mm', 'configuration': c, 'parts': {}}
    for name, part in parts.items():
        shape = part.val()
        if not shape.isValid() or len(part.solids().vals()) != 1 or shape.Volume() <= 0:
            raise RuntimeError(f'Invalid solid: {name}')
        cq.exporters.export(part, str(out / f'{name}.step'))
        color = (0.25, 0.55, 0.8, 0.5) if name == 'flexible_apron' else (0.7, 0.72, 0.75, 1)
        assembly.add(part, name=name, color=cq.Color(*color))
        bb = shape.BoundingBox()
        manifest['parts'][name] = {'volume_mm3': shape.Volume(), 'bounds_mm': [bb.xlen, bb.ylen, bb.zlen]}
    assembly.export(str(out / 'assembly.step'))
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return parts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config/sample.json')
    parser.add_argument('--out', default='outputs')
    args = parser.parse_args()
    parts = export(load_config(args.config), args.out)
    print(f'Exported {len(parts)} solid parts and assembly to {args.out}')


if __name__ == '__main__':
    main()
