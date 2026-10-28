# Desktop herbal paper roller — CadQuery concept

Parametric desktop roller for **non-tobacco herbal material**, modelled in millimetres with CadQuery 2.6.1. The sample has a 74 mm working width, 12 mm diameter drums, 20 mm shaft spacing, and a handwheel driving a keyed drum. A follower drum lifts on two swing arms; a flexible apron wraps around both drums. The filter is user-supplied and sits at one end of the apron pocket.

This is an untested mechanical concept, not a production-ready product. Valid CAD solids do not establish rolling performance. A perfect roll is not demonstrated. No strength, durability, manufacturing safety, material suitability, or inhalation safety claims are made.

## Run

Python 3.12 on Linux was used for the supplied outputs. From this checkout:

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
PYTHONPATH=src .venv/bin/python -m herbal_roller.generate --config config/sample.json --out outputs
PYTHONPATH=src .venv/bin/python -m pytest -q
```

In the prepared Codex environment the interpreter is `/workspace/cadquery-venv/bin/python`; substitute it for `.venv/bin/python`. No service or credentials are required after installation. Use the existing isolated checkout; a separate Git worktree is unnecessary.

`requirements.txt` pins direct dependencies; `requirements-lock.txt` records the complete installed dependency versions. For other Python versions/platforms, compatible wheels may differ.

## Files and configuration

- `src/herbal_roller/generate.py`: model construction, configuration validation, STEP export, and manifest generation.
- `config/sample.json`: sample dimensions. All values are millimetres. Unknown keys, non-positive values and unsupported geometric combinations are rejected.
- `outputs/*.step`: one solid per part file, and a named, coloured 17-part `assembly.step` in the closed reference position. Parts retain assembly coordinates; they are not individually moved to the origin.
- `outputs/manifest.json`: actual part bounding dimensions and volumes, together with the generating configuration.
- `tests/test_models.py`: validity, dimensions, apron section volume and drum clearance, invalid input rejection, alternate configuration, and STEP re-import tests.

Parameters are working width, roller radius, centre spacing, shaft height, shaft radius, radial bearing clearance, apron thickness, and apron radial clearance. Default bearing clearance is **0.25 mm radial** (0.5 mm diametral); this is a modelling choice, not a validated production fit. Other detail sizes are fixed prototype dimensions in the generator.

## Parts and assembly intent

| Parts | Count | Purpose |
|---|---:|---|
| Base | 1 | Desktop support |
| Left/right cheeks | 2 | Drive bearings and open follower saddles |
| Drive/follower drums | 2 | Working surfaces |
| Drive/follower shafts | 2 | Axles; drive has hex wheel end and integral radial torque key |
| Left/right swing arms | 2 | Lift follower about drive axis |
| Shaft collars | 4 | Reference retaining washers |
| Handwheel | 1 | Manual input, matching hex bore |
| Crank pin and grip | 2 | Grip rotates about pin |
| Flexible apron | 1 | Idealized endless belt |

X runs along the drums, Y between drums, and Z up from the base underside. The drive is at negative Y. Fit the apron around the drums before locating shafts in the cheeks. Place swing arms outside the cheeks; locate the follower shaft in both rear saddles. The wheel mounts on the left drive-shaft hex. The crank pin fits its blind wheel bore and carries the loose grip.

The separate cheeks meet the base at planar faces. Their attachment is **not engineered**; a bonded prototype would need a qualified adhesive/material choice, or a later revision should add fasteners. Collars are idealized plain rings: set screws, grooves, press fits, and axial retention are not specified. The drive key and mating pocket have nominal contact without manufacturing allowance. Bearings are plain bores. These details require engineering before fabrication; do not treat this assembly as a fabrication release.

## Intended operation and remaining design work

Lift the follower on its arms to open the apron, form a pocket, and place the filter and non-tobacco herbal material along the working width. Close the follower, rotate the handwheel to distribute material, introduce paper at the apron entrance, and continue rotation to draw it around the contents. Open the follower to remove the roll. Rotation direction, paper feeding and pocket formation must be established with a physical mock-up.

The exported apron is a **closed, tension-free geometric reference envelope** around the drums, not a simulated working pocket. Its nominal loop length is `2 * roller_spacing + 2*pi*(roller_radius + apron_clearance + apron_thickness/2)` (about 79.9 mm for the sample). The actual flexible sheet length, seam, friction, slack, tension and deformation need experimental development. The model supplies no tensioner, open-position latch, filter sizing insert, or automatic diameter control. A rigid printed apron will not function as intended. No paper, consumable filter, or loose material is included in the mechanical assembly.

Before fabrication or operation, resolve frame attachment and shaft/pin retention, validate clearances and tolerances for the chosen process, develop the flexible apron and surface materials, check access/pinch points, and test paper/filter dimensions. No FEA, torque analysis, fatigue analysis, contact simulation, or physical rolling tests have been performed.

## Inspect in a browser

1. Download `outputs/assembly.step` from the repository (use the raw/download action rather than saving GitHub's HTML page).
2. Open [Autodesk Viewer](https://viewer.autodesk.com/) in a browser, sign in if requested, and upload the STEP file. Uploading shares the design with that service; review its terms for private designs.
3. Orbit and zoom the assembly; use its model tree, hide/isolate and section tools where available to inspect the apron, internal shafts, and individual components. STEP transparency support varies, so hide the apron to see the drums.
4. Upload any individual part STEP for separate inspection. Check dimensions in millimetres against `manifest.json`.

A browser viewer is optional and was not used to validate these outputs. Automated validation uses OpenCascade STEP re-import, independent of any hosted viewer.
