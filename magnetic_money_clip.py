"""Magnetic money clip with a captive print-in-place hinge (millimetres).

Run: .venv/bin/python magnetic_money_clip.py
View exported STEP in VS Code OCP CAD Viewer: python magnetic_money_clip.py --view
Print output/money_clip_print_in_place.stl as oriented, with no supports
inside the hinge. One jaw lies flat and the other stands upright at 90 degrees;
the hinge axis is horizontal. Use a brim if needed, keeping it out of hinge gaps.
The axle is fused to the three-knuckle jaw; the other jaw rotates around it.
Gently free the hinge after cooling. Clearances are starting values for PLA+;
verify with your printer before relying on the clip. Install six 8 x 2 mm
magnets with opposing poles attracting, keeping adhesive out of the hinge.
"""
from pathlib import Path
from build123d import (
    Align, Box, Compound, Cylinder, Pos, RectangleRounded, Rot,
    extrude, export_step, export_stl,
)
import argparse

# ------- User-adjustable parameters (millimetres) -------
WIDTH = 28.0
BODY_START_X = 5.3
TIP_X = 41.2
CORNER_RADIUS = 3.0
PLATE_THICKNESS = 2.8

# Zero nominal closed gap: when flipped, flat inner faces meet at Z=PLATE_THICKNESS.
# The hinge is only a rotational joint: no flexing of printed jaws.
PIVOT_X = 0.0
PIVOT_Z = PLATE_THICKNESS
KNUCKLE_RADIUS = PLATE_THICKNESS  # 5.6 mm OD, flat jaw remains on the bed
AXLE_D = 2.4
RADIAL_CLEARANCE = 0.30
PIN_HOLE_D = AXLE_D + 2 * RADIAL_CLEARANCE

MAGNET_D = 8.0
MAGNET_THICKNESS = 2.0
MAGNET_POCKET_D = 8.20  # Diameter clearance for glued magnets
MAGNET_POCKET_DEPTH = 2.10
MAGNET_X = 34.0
MAGNET_Y = (-9.0, 0.0, 9.0)

# 0.35 mm clearance between adjacent knuckle end faces.
THREE_KNUCKLES = [(-14.0, -9.10), (-2.70, 2.70), (9.10, 14.0)]
TWO_KNUCKLES   = [(-8.75, -3.05), (3.05, 8.75)]


def make_jaw(knuckles, *, captive_axle=False):
    """Build one jaw in its modelling orientation with reinforced hinge webs."""
    length = TIP_X - BODY_START_X
    jaw = Pos((BODY_START_X + TIP_X)/2, 0, 0) * extrude(
        RectangleRounded(length, WIDTH, CORNER_RADIUS),
        amount=PLATE_THICKNESS,
    )

    for low, high in knuckles:
        middle = (low + high) / 2
        segment_width = high - low

        # The barrel surrounds either the integral axle or its clearance bore.
        barrel = (
            Pos(PIVOT_X, middle, PIVOT_Z) * Rot(90, 0, 0)
            * Cylinder(KNUCKLE_RADIUS, segment_width,
                       align=(Align.CENTER, Align.CENTER, Align.CENTER))
        )

        # A deep, broad web joins the barrel to the plate; it is not a spring.
        # 2.0 .. 8.0 mm in X; spans the jaw thickness and overlaps the barrel.
        reinforcement = Pos(5.0, middle, 0) * Box(
            6.0, segment_width, PLATE_THICKNESS,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        )

        # A flat land on the back of the jaw.
        foot = Pos(0.0, middle, 0) * Box(
            2 * (PLATE_THICKNESS - 0.2), segment_width, 0.85,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        )
        jaw = jaw.fuse(barrel, reinforcement, foot)
        if not captive_axle:
            # At 90 degrees this rear land becomes a flat bed-contact pad.
            # It stays within this knuckle's Y interval, preserving axial gaps.
            upright_land = Pos(-PLATE_THICKNESS, middle, PIVOT_Z) * Box(
                0.6, segment_width, 2.6,
                align=(Align.MIN, Align.CENTER, Align.CENTER),
            )
            jaw = jaw.fuse(upright_land)

    pin_hole = (
        Pos(PIVOT_X, 0, PIVOT_Z) * Rot(90, 0, 0)
        * Cylinder(PIN_HOLE_D/2, WIDTH + 2,
                   align=(Align.CENTER, Align.CENTER, Align.CENTER))
    )
    if captive_axle:
        axle = (Pos(PIVOT_X, 0, PIVOT_Z) * Rot(90, 0, 0)
                * Cylinder(AXLE_D/2, WIDTH,
                           align=(Align.CENTER, Align.CENTER, Align.CENTER)))
        jaw = jaw + axle
    else:
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


def make_clip(open_angle=90.0):
    """Return the two independent jaws; 0 degrees is closed.

    The lower jaw includes its axle. Rotate the upper about Y at the pivot,
    preserving the bore alignment. 90 degrees is the printing position.
    """
    lower = make_jaw(THREE_KNUCKLES, captive_axle=True)
    upper = make_jaw(TWO_KNUCKLES)
    upper = Pos(0, 0, 2*PIVOT_Z) * Rot(180, 0, 0) * upper
    upper = (Pos(PIVOT_X, 0, PIVOT_Z) * Rot(0, -open_angle, 0)
             * Pos(-PIVOT_X, 0, -PIVOT_Z) * upper)
    return lower, upper


def make_print_layout():
    """One jaw flat on the bed, the other upright; hinge axis along Y."""
    return Compound(children=list(make_clip(90)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('output'))
    parser.add_argument('--view', action='store_true',
                        help='Show the exported STEP in VS Code OCP CAD Viewer (requires ocp-vscode)')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    layout = make_print_layout()
    export_stl(layout, args.output / 'money_clip_print_in_place.stl')
    export_step(layout, args.output / 'money_clip_print_in_place.step')
    export_step(Compound(children=list(make_clip(0))),
                args.output / 'money_clip_closed.step')
    print(f'Exported print-in-place clip to {args.output}')
    print('Print as oriented: one jaw flat, one upright at 90 degrees. Keep hinge gaps clear.')
    if args.view:
        try:
            from ocp_vscode import show
        except ImportError:
            parser.exit(1, 'Exports saved. Viewing requires ocp-vscode: '
                        'python -m pip install ocp-vscode\n')
        from build123d import import_step
        exported = import_step(args.output / 'money_clip_print_in_place.step')
        show(exported, names=['Money clip — exported print layout'])


if __name__ == '__main__':
    main()
