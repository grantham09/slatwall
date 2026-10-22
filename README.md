# Parametric mounting plate

A build123d plate with a downward top hook, a rounded upward lower catch,
and a release tab. All dimensions describe the part itself, in mm.
No slot height, depth, pitch, or internal wall profile is assumed.

## Parameters

| Parameter | Default | Meaning |
| --- | ---: | --- |
| width | 80 | Plate width, X |
| height | 70 | Plate body height, Z; excludes release tab |
| plate_thickness | 4 | Plate thickness, Y |
| hook_spacing | 36.5 | Clear vertical gap from top of lower straight arm to underside of upper straight arm; excludes both returns |
| hook_width | 36 | Upper hook width across X |
| hook_thickness | 2.4 | Upper arm and return thickness; also sets rounded catch depth behind its lip gap |
| hook_drop | 4 | Downward return below underside of upper straight arm |
| lip_thickness | 1.5 | Clear gap behind plate to inside of upper return; also locates lower curve's inner shoulder |
| snap_width | 16 | Lower catch and tongue width across X |
| snap_thickness | 1.8 | Lower straight arm and flexible tongue thickness |
| snap_length | 28 | Vertical distance from top of lower arm to tongue root |
| snap_peak | 1.2 | Rounded crown height above top of lower straight arm |
| release_gap | 1 | Clearance on each side of tongue |
| release_tab_length | 0 | Extension below plate; zero leaves tab flush, with grip present |
| release_grip_radius | 2 | Rounded finger crossbar radius |

`hook_spacing` is **not centre-to-centre**. For example, the 36.5 mm gap does
not include either arm's thickness, the 4 mm downward return, or the 1.2 mm
upward crown. Changing either return leaves that gap unchanged. The two
straight arms together are centred vertically on the plate.

`lip_thickness` is the actual gap in the model, with no hidden fit allowance.
Add any desired printing allowance to this value yourself. The lower catch's
rear projection is derived as `lip_thickness + hook_thickness`; its rounded
Bezier shoulders scale with that depth and `snap_peak`.

## Run and export

```sh
python -m pip install -r requirements.txt
python slatwall_plate.py
python -m unittest discover -s tests -v
```

Exports `output/slatwall_plate.step` and `.stl`.

## OCP CAD Viewer

Install the OCP CAD Viewer extension in VS Code and its Python bridge:

```sh
python -m pip install ocp-vscode
```

Run `view_plate.py`. Its `PlateParameters(...)` call lists all editable
parameters. The viewer is optional for export and tests.

## Combine with another model

```python
from slatwall_plate import PlateParameters, make_plate

plate = make_plate(PlateParameters(hook_spacing=36.5, snap_peak=1.2))
# combined = plate + accessory
```

X runs across the plate, Z points up, and Y points away from its back.
The plate back is Y=0, front mating face is Y=plate_thickness, and hooks
project into negative Y. Keep the flexible tongue and its front travel clear;
do not bridge its relief slots with the accessory.

## Release and printing

With `release_tab_length=0`, the tab ends flush with the plate bottom and
retains its rounded grip on the front. Increase it to extend the tab below
the plate (for example, `release_tab_length=12`). Pull its rounded crossbar outward (+Y) to flex the lower catch clear,
then tilt the bottom away and lift the top hook off. Leave access to the tab
when adding an accessory. The grip stays within the tongue width, so it does not bridge the side
relief gaps, including when tab length is zero.

For PLA on your Bambu A1, test the fit and release before adding a large
accessory. Check layer orientation at the tongue root and keep support scars
off the hook surfaces. Reduce `snap_peak` or adjust tongue thickness/length
if the snap needs excessive force. CAD checks verify solid geometry, not
release force, fatigue, load capacity, or compatibility with a particular wall.
