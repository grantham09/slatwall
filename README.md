# Parametric slatwall mounting plate

A build123d plate for combining with other printable models: an upward return
hook at the upper opening and a flexible tongue carrying an upward rounded lower snap.
Target wall: **Knoll Dividend**. Target printer/material: **Bambu A1, PLA**.
Defaults use your approximate wall measurements, with metal thickness set to
the upper estimate of 1.5 mm. The 36.5 mm measurement is interpreted as vertical
slat face height, so opening pitch is 36.5 + 9.5 = 46 mm. If that measurement
means something else, adjust slot_pitch before printing.
All dimensions are in millimetres. **Defaults are measured estimates, not a
physically verified fit.** Measure your wall before printing.

## Run

```sh
python -m pip install -r requirements.txt
python slatwall_plate.py
python -m unittest discover -s tests -v
```

Exports `output/slatwall_plate.step` and `.stl`. STEP preserves CAD geometry;
STL is for slicing. Open either in your CAD application to inspect the design.

## Customize and combine

```python
from build123d import export_step
from slatwall_plate import PlateParameters, make_plate

params = PlateParameters(width=80, height=70, slot_pitch=46.0)
plate = make_plate(params)
# combined = plate + accessory  # place accessory against the front face
export_step(plate, "my_plate.step")
```

X runs across the wall, Z points upward, and positive Y points away from the
wall. The wall front is Y=0; the plate occupies Y=0 through plate_thickness.
The accessory mating face is Y=plate_thickness. The two opening centres are
vertically centred on the plate and separated by slot_pitch.

Measure and adjust:

| Parameter | Meaning | Example |
| --- | --- | --- |
| slot_pitch | Centre-to-centre distance between target openings | 46 |
| slot_height | Clear vertical opening | 9.5 |
| lip_thickness | Wall lip thickness front to back | 1.5 |
| slot_depth | Available depth from wall face into slot | 7 |
| clearance | Fit allowance behind lip | 0.5 |
| hook_rise | Upper hook height above opening centre | 6.5 |
| snap_engagement | Lower catch extension above opening edge | 1.2 |
| snap_projection | Lower catch depth behind wall face | 4 |
| snap_length / snap_thickness | Flexible tongue length / thickness | 28 / 1.8 |

The model assumes two straight openings with room behind both retaining lips.
The bottom lip rise (6.5 mm) and top lip drop (3.5 mm) are also parameters.
Together with the 9.5 mm opening they give an internal gap of 19.5 mm.
These describe the cavity above and below each opening, not wall metal
thickness. The 7 mm depth is an estimate and needs a physical fit check.
The upper hook reaches 4.4 mm behind the wall face; the lower catch reaches
4 mm. The default plate is 80 mm wide by 70 mm high.
Real slatwall may have a different internal profile. Opening height and depth
alone do not guarantee that the tilted upper hook can be inserted.

## Installation and printing

Insert the upper hook with the plate tilted outward, lift it behind the upper
lip, then rotate the bottom toward the wall until the rounded lower catch seats behind the lip above the lower opening.
Both shoulders of this upward catch are curved, allowing it to cam on and off.
To remove, gently pull the bottom outward; the tongue must flex enough for the
rounded crown to pass the lip. If needed, assist the tongue through its relief
window, then lower the upper hook out of its opening. Actual release force
depends on the material, print orientation, and wall profile; test it in PLA. Leave access to the tongue
and space in front of it when adding another model; do not bridge the window.

For your Bambu A1 and PLA, start with a small fit print before attaching a
large accessory. Use the Bambu Studio profile matching your actual PLA and
nozzle. The default tongue is 28 mm long and 1.8 mm thick; these are starting
values, not a validated PLA flexure. If insertion needs excessive force, stop
and reduce engagement or increase tongue length rather than forcing the latch.
Use several wall loops so the thin tongue is mostly continuous walls, and
inspect the sliced root for continuity. Orient the part so bending stress runs
along continuous extrusion paths; avoid layer separation across the tongue
root. Hooks extend behind the plate, so a face-down orientation may require
supports or a different orientation. Keep support scars off the latch surfaces.
Tune clearance, snap thickness, length, and engagement to the printer and
material. PLA can be brittle under repeated flexing. No load rating or physical
snap-fit validation has been established by the CAD checks.

## OCP CAD Viewer

With the OCP CAD Viewer extension installed in VS Code, install its Python
bridge in your selected interpreter:

```sh
python -m pip install ocp-vscode
```

Open `view_plate.py` and run it using the viewer. Edit `parameters` there to
try different dimensions; `slatwall_plate.py` contains the full parametric
model. The viewer bridge is optional for STEP/STL export and tests.
