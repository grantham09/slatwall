"""Hinged magnetic money clip v2 for a Bambu A1 (PLA+).

This is a *rigid* two-part clip. No PLA+ spring or snap-fit is required.
The jaws close face-to-face when empty and open by rotating on a filament pin.

Requires: pip install build123d
Run: python magnetic_money_clip_build123d_v2.py

Both exported STLs are print-oriented: flat bottom at z=0, magnet pockets UP.
Print the two jaws separately, then flip the two-knuckle jaw to assemble.

Hardware:
  - 4 neodymium disc magnets, 8 mm diameter x 2 mm thick
    (two in each jaw; opposing magnets must ATTRACT)
  - 1.75 mm PLA+ filament, straightened, for a ~29 mm hinge pin
  - A tiny amount of cyanoacrylate or epoxy for magnets

The magnet pockets are blind and intentionally slightly oversize for glue.
Do not glue the hinge barrels or get glue into the pin holes.

Important: Geometric model validated with matching OCCT CAD solids, but this
build123d file wasn't run here because build123d was not installed in the
runtime. On-printer fit / magnet force remain to be tested.
"""
from pathlib import Path
from build123d import (
    Align, Box, Compound, Cylinder, Pos, RectangleRounded, Rot,
    extrude, export_step, export_stl,
)
from ocp_vscode import show

# ------- User-adjustable parameters (millimetres) -------
WIDTH = 28.0
BODY_START_X = 5.3
TIP_X = 41.2
CORNER_RADIUS = 3.0
PLATE_THICKNESS = 3.5

# Zero nominal closed gap: when flipped, flat inner faces meet at Z=3.5.
# The hinge is only a rotational joint: no flexing of printed jaws.
PIVOT_X = 0.0
PIVOT_Z = PLATE_THICKNESS
KNUCKLE_RADIUS = 3.5      # 7.0 mm outside diameter, 2.5 mm wall at pin
PIN_HOLE_D = 2.05         # Clearance hole for ~1.75 mm filament

MAGNET_D = 8.0
MAGNET_THICKNESS = 2.0
MAGNET_POCKET_D = 8.20  # Diameter clearance for glued magnets
MAGNET_POCKET_DEPTH = 2.10
MAGNET_X = 34.0
MAGNET_Y = (-7.0, 7.0)

# 0.35 mm clearance between adjacent knuckle end faces.
THREE_KNUCKLES = [(-13.75, -9.10), (-2.70, 2.70), (9.10, 13.75)]
TWO_KNUCKLES   = [(-8.75, -3.05), (3.05, 8.75)]


def make_jaw(knuckles):
    """A pocket-up, support-free print with reinforced hinge webs."""
    length = TIP_X - BODY_START_X
    jaw = Pos((BODY_START_X + TIP_X)/2, 0, 0) * extrude(
        RectangleRounded(length, WIDTH, CORNER_RADIUS),
        amount=PLATE_THICKNESS,
    )

    for low, high in knuckles:
        middle = (low + high) / 2
        segment_width = high - low

        # The barrel is 7 mm OD; 2.05 mm bore gives substantial PLA+ walls.
        barrel = (
            Pos(PIVOT_X, middle, PIVOT_Z) * Rot(90, 0, 0)
            * Cylinder(KNUCKLE_RADIUS, segment_width,
                       align=(Align.CENTER, Align.CENTER, Align.CENTER))
        )

        # A deep, broad web joins the barrel to the plate; it is not a spring.
        # 2.0 .. 8.0 mm in X; z=0 .. 3.5. It overlaps the round barrel.
        reinforcement = Pos(5.0, middle, 0) * Box(
            6.0, segment_width, PLATE_THICKNESS,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        )

        # A flat first-layer land under the horizontal bore (support free).
        foot = Pos(0.0, middle, 0) * Box(
            6.2, segment_width, 0.85,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        )
        jaw = jaw + barrel + reinforcement + foot

    pin_hole = (
        Pos(PIVOT_X, 0, PIVOT_Z) * Rot(90, 0, 0)
        * Cylinder(PIN_HOLE_D/2, WIDTH + 2,
                   align=(Align.CENTER, Align.CENTER, Align.CENTER))
    )
    jaw = jaw - pin_hole

    # Inner face: 8 x 2 mm magnets are set ~0.10 mm below the PLA+ face.
    for y in MAGNET_Y:
        pocket = Pos(MAGNET_X, y, PLATE_THICKNESS - MAGNET_POCKET_DEPTH) * Cylinder(
            MAGNET_POCKET_D/2, MAGNET_POCKET_DEPTH + 0.20,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        )
        jaw = jaw - pocket

    # Recessed (not raised) grip grooves allow the jaws to close flush.
    for x in (39.0, 40.0):
        recess = Pos(x, 0, PLATE_THICKNESS - 0.24) * Box(
            0.45, 21.0, 0.40,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        )
        jaw = jaw - recess

    return jaw


def main():
    out = Path(__file__).resolve().parent
    lower = make_jaw(THREE_KNUCKLES)
    upper = make_jaw(TWO_KNUCKLES)

    export_stl(lower, str(out/'money_clip_v2_3_knuckles.stl'))
    export_stl(upper, str(out/'money_clip_v2_2_knuckles.stl'))
    export_step(lower, str(out/'money_clip_v2_3_knuckles.step'))
    export_step(upper, str(out/'money_clip_v2_2_knuckles.step'))

    # Mirror around hinge centre by rotating 180 degrees around the X axis.
    # The plates are face-to-face, nominal empty gap 0.0 mm.
    top_closed = Pos(0, 0, 2*PIVOT_Z) * Rot(180, 0, 0) * upper
    closed_assembly = Compound(children=[lower, top_closed])
    export_step(closed_assembly, str(out/'money_clip_v2_closed_assembly.step'))

    # A 14-degree open view to inspect the interleaved knuckles in a CAD app.
    top_open = (Pos(0, 0, PIVOT_Z) * Rot(0, -14, 0)
                * Pos(0, 0, -PIVOT_Z) * top_closed)
    open_assembly = Compound(children=[lower, top_open])
    show(open_assembly, names=["Mounting plate"])
    #export_step(open_assembly, str(out/'money_clip_v2_open_assembly.step'))

    print('Jaw STLs, jaw STEPs and closed assembly STEP saved to:', out)
    print('Empty closed jaw gap: 0 mm (contacting inside faces).')
    print('Print both jaws FLAT, with magnet pockets facing UP, no supports.')

if __name__ == '__main__':
    main()
