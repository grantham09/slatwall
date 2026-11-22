"""Magnetic money clip with a captive print-in-place hinge (millimetres).

Run: .venv/bin/python magnetic_money_clip.py
View exported STEP in VS Code OCP CAD Viewer: python magnetic_money_clip.py --view
Print output/money_clip_print_in_place.stl as oriented, with no supports
inside the hinge. One jaw lies flat and the other stands upright at 90 degrees;
the hinge axis is horizontal. Use a brim if needed, keeping it out of hinge gaps.
The axle is fused to the three-knuckle jaw; the other jaw rotates around it.
The moving jaw slopes inward by 3 degrees so the smooth tips meet first.
Gently free the hinge after cooling. Clearances are starting values for PLA+;
verify with your printer before relying on the clip. Install six 10 x 5 x 2 mm
magnets and retain each with its own small printed snap cap. The flat jaw
loads from the back; the upright jaw loads from the money-facing side so
its outer back stays continuous for wallet mounting. No glue is required.
"""
from pathlib import Path
from build123d import (
    Align, Axis, Box, Compound, Cylinder, Plane, Pos, RectangleRounded, Rot,
    BuildSketch, BuildLine, Bezier, Polyline, make_face,
    extrude, fillet, loft, export_step, export_stl,
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

MAGNET_LENGTH = 10.0  # Along the jaw (X).
MAGNET_WIDTH = 5.0    # Across the jaw (Y).
MAGNET_THICKNESS = 2.0
MAGNET_SKIN = 0.6
MAGNET_POCKET_SIZE = (12.3, 7.3)  # Includes room for the split cap skirt.
MAGNET_POCKET_DEPTH = PLATE_THICKNESS - MAGNET_SKIN
MAGNET_CENTRES = ((32.0, -9.0), (32.0, 0.0), (32.0, 9.0))
CAP_SEAT_SIZE = (12.9, 7.9)
CAP_SEAT_DEPTH = 0.8
CAP_GROOVE_SIZE = (12.7, 7.7)
CAP_GROOVE_BOTTOM = 2.10
CAP_GROOVE_TOP = 2.75
CAP_FLANGE_SIZE = (12.65, 7.65)
CAP_TAB_THICKNESS = 0.9
CAP_SKIRT_SIZE = (12.1, 7.1)
CAP_SKIRT_INNER_SIZE = (10.3, 5.3)
CAP_BEAD_SIZE = (12.5, 7.5)
CAP_SKIRT_TOP = 2.8
CAP_BEAD_ROOT_Z = 2.0
CAP_BEAD_PEAK_Z = 2.5


def rounded_prism(size, depth, radius=.3):
    return extrude(RectangleRounded(*size, radius), amount=depth)


def make_magnet_cap():
    """Small rectangular snap cap for one 10 x 5 x 2 mm magnet.

    Print flange down, skirt up. The ridge grows 0.20 mm outward over
    0.5 mm of height (21.8 degrees from vertical), avoiding the previous
    steep underside. Four slots let the skirt flex through the throat;
    the bead catches in the groove. Trial-fit one cap before fitting
    all six; printed PLA snap retention is not established by CAD checks.
    """
    flange = rounded_prism(CAP_FLANGE_SIZE, CAP_SEAT_DEPTH, .35)
    skirt = Pos(0, 0, CAP_SEAT_DEPTH) * rounded_prism(
        CAP_SKIRT_SIZE, CAP_SKIRT_TOP - CAP_SEAT_DEPTH)
    bead = loft([
        Pos(0, 0, CAP_BEAD_ROOT_Z) * RectangleRounded(*CAP_SKIRT_SIZE, .3),
        Pos(0, 0, CAP_BEAD_PEAK_Z) * RectangleRounded(*CAP_BEAD_SIZE, .5),
        Pos(0, 0, CAP_SKIRT_TOP) * RectangleRounded(*CAP_SKIRT_SIZE, .3),
    ], ruled=True)
    cap = flange.fuse(skirt, bead)
    cap = cap - Pos(0, 0, CAP_SEAT_DEPTH) * rounded_prism(
        CAP_SKIRT_INNER_SIZE, CAP_SKIRT_TOP, .1)
    for sign in (-1, 1):
        x_slot = Pos(sign*(CAP_SKIRT_INNER_SIZE[0]/2 + .75), 0, .35) * Box(
            2, .8, 3, align=(Align.CENTER, Align.CENTER, Align.MIN))
        y_slot = Pos(0, sign*(CAP_SKIRT_INNER_SIZE[1]/2 + .75), .35) * Box(
            .8, 2, 3, align=(Align.CENTER, Align.CENTER, Align.MIN))
        cap = cap - x_slot - y_slot
    return cap


def magnet_loading_location(money_side=False):
    """Place rear-loading geometry on the money side of the upright body."""
    return (Pos(0, 0, PLATE_THICKNESS) * Rot(180, 0, 0)
            if money_side else Pos(0, 0, 0))


def cut_magnet_pockets(jaw, *, money_side=False):
    """Cut cap seats and snap grooves while keeping the opposite face solid."""
    loading = magnet_loading_location(money_side)
    for x, y in MAGNET_CENTRES:
        for size, bottom, depth in (
                (MAGNET_POCKET_SIZE, -.1, MAGNET_POCKET_DEPTH + .1),
                (CAP_SEAT_SIZE, -.1, CAP_SEAT_DEPTH + .1),
                (CAP_GROOVE_SIZE, CAP_GROOVE_BOTTOM,
                 CAP_GROOVE_TOP - CAP_GROOVE_BOTTOM)):
            cutter = Pos(x, y, bottom) * rounded_prism(size, depth)
            jaw = jaw - loading * cutter
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

    jaw = cut_magnet_pockets(jaw, money_side=not captive_axle)
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
    return Compound(children=[Pos(55 + 14*i, y, 0) * cap
                              for i in range(3) for y in (-7, 7)])


def make_closed_assembly():
    lower, upper = make_clip(0)
    cap = make_magnet_cap()
    caps = []
    for x, y in MAGNET_CENTRES:
        local = Pos(x, y, 0) * cap
        caps.append(local)
        caps.append(Pos(0, 0, 2*PIVOT_Z) * Rot(180, 0, 0)
                    * moving_body_location() * magnet_loading_location(True) * local)
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
