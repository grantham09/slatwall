"""Magnetic money clip with a captive print-in-place hinge (millimetres).

Run: .venv/bin/python magnetic_money_clip.py
View exported STEP in VS Code OCP CAD Viewer: python magnetic_money_clip.py --view
Print output/money_clip_print_in_place.stl as oriented, with no supports
inside the hinge. One jaw lies flat and the other stands upright at 90 degrees;
the hinge axis is horizontal. Use a brim if needed, keeping it out of hinge gaps.
The axle is fused to the three-knuckle jaw; the other jaw rotates around it.
The moving jaw slopes inward by 3 degrees so the smooth tips meet first.
Gently free the hinge after cooling. Clearances are starting values for PLA+;
verify with your printer before relying on the clip. Install six 8 x 2 mm
magnets from the back and retain each with its own small printed snap cap.
The 0.6 mm PLA clamping skin covers the magnets; no glue is required.
"""
from pathlib import Path
from build123d import (
    Align, Axis, Box, Compound, Cone, Cylinder, Plane, Pos, RectangleRounded, Rot,
    BuildSketch, BuildLine, Bezier, Polyline, make_face,
    extrude, fillet, export_step, export_stl,
)
import argparse
from math import radians, cos, tan

# ------- User-adjustable parameters (millimetres) -------
WIDTH = 28.0
BODY_START_X = 5.3
TIP_X = 41.2
CORNER_RADIUS = 3.0
PLATE_THICKNESS = 3.6
JAW_ANGLE = 3.0  # Moving jaw converges toward the straight jaw at its tip.
HINGE_BLEND_RADIUS = 0.9
BED_LAND_RADIUS = 0.3

# The tips meet at closure; the moving jaw has clearance toward its root.
# The hinge is only a rotational joint: no flexing of printed jaws.
PIVOT_X = 0.0
PIVOT_Z = PLATE_THICKNESS
KNUCKLE_RADIUS = PLATE_THICKNESS  # Flat jaw and upright curved land remain on the bed
AXLE_D = 2.4
RADIAL_CLEARANCE = 0.30
PIN_HOLE_D = AXLE_D + 2 * RADIAL_CLEARANCE

MAGNET_D = 8.0
MAGNET_THICKNESS = 2.0
MAGNET_SKIN = 0.6
MAGNET_POCKET_D = 9.2  # Room for the magnet and the cap's split retaining skirt.
MAGNET_POCKET_DEPTH = PLATE_THICKNESS - MAGNET_SKIN
MAGNET_CENTRES = ((34.0, -7.0), (34.0, 7.0), (23.0, 0.0))
CAP_SEAT_D = 9.8
CAP_SEAT_DEPTH = 0.8
CAP_GROOVE_D = 9.7
CAP_GROOVE_BOTTOM = 2.15
CAP_GROOVE_TOP = 2.75
CAP_DISC_D = 9.55
CAP_SKIRT_D = 9.0
CAP_SKIRT_INNER_D = 8.3
CAP_BEAD_D = 9.5
CAP_SKIRT_TOP = 2.8


def make_magnet_cap():
    """Local rear snap cap: flat outside down, four split skirt fingers up.

    The bead flexes through the 9.2 mm throat and catches in its annular
    groove. The central disc traps the magnet without adhesive. Trial-fit
    one cap before fitting all six; PLA snap retention is printer-dependent.
    """
    disc = Cylinder(CAP_DISC_D/2, CAP_SEAT_DEPTH,
                    align=(Align.CENTER, Align.CENTER, Align.MIN))
    skirt = Pos(0, 0, CAP_SEAT_DEPTH) * Cylinder(
        CAP_SKIRT_D/2, CAP_SKIRT_TOP - CAP_SEAT_DEPTH,
        align=(Align.CENTER, Align.CENTER, Align.MIN))
    bead = Pos(0, 0, 2.3) * Cone(CAP_SKIRT_D/2, CAP_BEAD_D/2, .2,
                                align=(Align.CENTER, Align.CENTER, Align.MIN))
    bead = bead.fuse(Pos(0, 0, 2.5) * Cone(CAP_BEAD_D/2, CAP_SKIRT_D/2, .2,
                                         align=(Align.CENTER, Align.CENTER, Align.MIN)))
    cap = disc.fuse(skirt, bead)
    cap = cap - Pos(0, 0, CAP_SEAT_DEPTH) * Cylinder(
        CAP_SKIRT_INNER_D/2, CAP_SKIRT_TOP,
        align=(Align.CENTER, Align.CENTER, Align.MIN))
    for angle in (0, 90, 180, 270):
        slot = Rot(0, 0, angle) * Pos(3.9, 0, .35) * Box(
            2, .6, 3, align=(Align.MIN, Align.CENTER, Align.MIN))
        cap = cap - slot
    return cap


def cut_magnet_pockets(jaw):
    """Rear loading: continuous PLA face, recessed cap seat and snap groove."""
    for x, y in MAGNET_CENTRES:
        for diameter, bottom, depth in (
                (MAGNET_POCKET_D, -.1, MAGNET_POCKET_DEPTH + .1),
                (CAP_SEAT_D, -.1, CAP_SEAT_DEPTH + .1),
                (CAP_GROOVE_D, CAP_GROOVE_BOTTOM,
                 CAP_GROOVE_TOP - CAP_GROOVE_BOTTOM)):
            jaw = jaw - Pos(x, y, bottom) * Cylinder(
                diameter/2, depth,
                align=(Align.CENTER, Align.CENTER, Align.MIN))
    return jaw


# 0.35 mm clearance between adjacent knuckle end faces.
THREE_KNUCKLES = [(-14.0, -9.10), (-2.70, 2.70), (9.10, 14.0)]
TWO_KNUCKLES   = [(-8.75, -3.05), (3.05, 8.75)]


def moving_body_location():
    """Incline the moving body about its inner tip; leave hinge axis unchanged."""
    return (Pos(TIP_X, 0, PLATE_THICKNESS) * Rot(0, -JAW_ANGLE, 0)
            * Pos(-TIP_X, 0, -PLATE_THICKNESS))


def round_hinge_transitions(jaw, captive_axle):
    """Blend side-profile corners without rounding knuckle ends or the bore.

    Only edges parallel to the axle are changed. Flat centres of the bed
    lands remain, and the axial clearance faces keep their original positions.
    """
    def blend(predicate, radius):
        nonlocal jaw
        edges = [edge for edge in jaw.edges().filter_by(Axis.Y)
                 if predicate(edge.center())]
        if not edges:
            raise ValueError('Expected hinge transition edges were not found')
        jaw = fillet(edges, radius)

    if captive_axle:
        blend(lambda p: abs(p.X - KNUCKLE_RADIUS) < 1e-5
              and abs(p.Z - PIVOT_Z) < 1e-5, HINGE_BLEND_RADIUS)
        blend(lambda p: abs(p.X + (PLATE_THICKNESS - 0.2)) < 1e-5
              and p.Z < 0.9, BED_LAND_RADIUS)
    # The moving underside is already a smooth Bezier down to its flat base.
    return jaw


def make_jaw(knuckles, *, captive_axle=False):
    """Build one jaw in its modelling orientation with reinforced hinge webs."""
    length = TIP_X - BODY_START_X
    jaw = Pos((BODY_START_X + TIP_X)/2, 0, 0) * extrude(
        RectangleRounded(length, WIDTH, CORNER_RADIUS),
        amount=PLATE_THICKNESS,
    )

    jaw = cut_magnet_pockets(jaw)
    if not captive_axle:
        jaw = moving_body_location() * jaw

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

        if not captive_axle:
            # Follow the inclined body back toward the barrel without a
            # raised inner ledge that would touch the straight jaw early.
            a = radians(JAW_ANGLE)
            def inner_z(x):
                return PLATE_THICKNESS + tan(a) * (x - TIP_X)
            vertical_thickness = PLATE_THICKNESS / cos(a)
            outer_end = inner_z(BODY_START_X) - vertical_thickness
            run = (BODY_START_X + PLATE_THICKNESS) / 3
            with BuildSketch(Plane.XZ) as web:
                with BuildLine():
                    Bezier((-PLATE_THICKNESS, 1.5),
                           (-PLATE_THICKNESS + run, -1.1),
                           (BODY_START_X - run, outer_end - tan(a)*run),
                           (BODY_START_X, outer_end))
                    Polyline((BODY_START_X, outer_end),
                             (8, inner_z(8) - vertical_thickness),
                             (8, inner_z(8)), (1, inner_z(1)),
                             (1, PIVOT_Z + 1.3),
                             (-PLATE_THICKNESS, PIVOT_Z + 1.3),
                             (-PLATE_THICKNESS, 1.5))
                make_face()
            reinforcement = Pos(0, low, 0) * extrude(
                web.sketch, amount=segment_width, dir=(0, 1, 0))

        # A flat land on the back of the jaw.
        foot = Pos(0.0, middle, 0) * Box(
            2 * (PLATE_THICKNESS - 0.2), segment_width, 0.85,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        )
        if captive_axle:
            jaw = jaw.fuse(barrel, reinforcement, foot)
        else:
            # The curved web includes its own flat bed land. Extra pads here
            # would protrude through the curve and recreate a small ledge.
            jaw = jaw.fuse(barrel, reinforcement)

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

    return round_hinge_transitions(jaw, captive_axle)


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


def make_caps_print_layout():
    cap = make_magnet_cap()
    return Compound(children=[Pos(55 + 12*i, y, 0) * cap
                              for i in range(3) for y in (-7, 7)])


def make_closed_assembly():
    lower, upper = make_clip(0)
    cap = make_magnet_cap()
    caps = []
    for x, y in MAGNET_CENTRES:
        local = Pos(x, y, 0) * cap
        caps.append(local)
        caps.append(Pos(0, 0, 2*PIVOT_Z) * Rot(180, 0, 0)
                    * moving_body_location() * local)
    return Compound(children=[lower, upper, *caps])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('output'))
    parser.add_argument('--view', action='store_true',
                        help='Show the exported STEP in VS Code OCP CAD Viewer (requires ocp-vscode)')
    parser.add_argument('--view-state', choices=('print', 'closed'), default='print',
                        help='Assembly to display with --view (default: print)')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    layout = Compound(children=[make_print_layout(), make_caps_print_layout()])
    export_stl(layout, args.output / 'money_clip_print_in_place.stl')
    export_step(layout, args.output / 'money_clip_print_in_place.step')
    export_stl(make_magnet_cap(), args.output / 'money_clip_magnet_cap.stl')
    export_step(make_magnet_cap(), args.output / 'money_clip_magnet_cap.step')
    export_step(make_closed_assembly(),
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
        filename = ('money_clip_closed.step' if args.view_state == 'closed'
                    else 'money_clip_print_in_place.step')
        exported = import_step(args.output / filename)
        show(exported, names=[f'Money clip — {args.view_state}'])


if __name__ == '__main__':
    main()
