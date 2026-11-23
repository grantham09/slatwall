"""Magnetic money clip with a captive print-in-place hinge (millimetres).

Run: .venv/bin/python magnetic_money_clip.py
View exported STEP in VS Code OCP CAD Viewer: python magnetic_money_clip.py --view
Print output/money_clip_print_in_place.stl as oriented, with no supports
inside the hinge. One jaw lies flat and the wallet-side jaw stands upright
at 90 degrees, ready to join an upright wallet. The hinge axis is horizontal.
The axle is fused to the three-knuckle jaw; the other jaw rotates around it.
The jaws close parallel; a second joint in the flat jaw adapts to money thickness.
Gently free the hinge after cooling. Clearances are starting values for PLA+;
verify with your printer before relying on the clip. Install twelve 10 x 5 x 2 mm
magnets in two rows per jaw, each with its own small snap cap. Both jaws
load from their money-facing sides (top of the flat jaw), so
its outer back stays continuous for wallet mounting. No glue is required.
"""
from pathlib import Path
from build123d import (
    Align, Axis, Box, Compound, Cylinder, Plane, Polygon, Pos, RectangleRounded, Rot,
    BuildSketch, BuildLine, Bezier, Polyline, make_face,
    extrude, fillet, loft, export_step, export_stl,
)
import argparse
from math import radians, cos, tan

# ------- User-adjustable parameters (millimetres) -------
WIDTH = 28.0
BODY_START_X = 5.3
TIP_X = 61.8  # About 1.5 times the previous 41.2 mm reach.
CORNER_RADIUS = 3.0
PLATE_EDGE_RADIUS = 0.6  # Round the outer face rims, not pocket or hinge edges.
PLATE_THICKNESS = 3.6
JAW_ANGLE = 0.0  # Both clamping faces are parallel; the extra joint adapts to cash.
HINGE_BLEND_RADIUS = 0.9
BED_LAND_RADIUS = 0.3
UPRIGHT_ROOT_RISE = 1.1  # Rise/run across the upright jaw width.

# The tips meet at closure; the moving jaw has clearance toward its root.
# The hinge is only a rotational joint: no flexing of printed jaws.
PIVOT_X = 0.0
PIVOT_Z = PLATE_THICKNESS
KNUCKLE_RADIUS = PLATE_THICKNESS  # Flat jaw and upright curved land remain on the bed
AXLE_D = 2.4
RADIAL_CLEARANCE = 0.30
PIN_HOLE_D = AXLE_D + 2 * RADIAL_CLEARANCE

# Second captive hinge, before the magnet pockets. Its barrel stays within
# the 3.6 mm plate thickness so neither face gets a raised lump.
SECOND_PIVOT_X = 12.0
SECOND_PIVOT_Z = PLATE_THICKNESS/2
SECOND_RADIUS = 1.8
SECOND_AXLE_D = 1.2
SECOND_BORE_D = SECOND_AXLE_D + 2*RADIAL_CLEARANCE
SECOND_SHOULDER = SECOND_RADIUS + .4

MAGNET_LENGTH = 10.0  # Along the jaw (X).
MAGNET_WIDTH = 5.0    # Across the jaw (Y).
MAGNET_SIZE = (MAGNET_LENGTH, MAGNET_WIDTH)
MAGNET_THICKNESS = 2.0
MAGNET_SKIN = 0.6
MAGNET_POCKET_SIZE = (12.3, 7.3)  # Includes room for the split cap skirt.
MAGNET_POCKET_DEPTH = PLATE_THICKNESS - MAGNET_SKIN
MAGNET_ROWS = (27.0, 49.0)
MAGNET_CENTRES = tuple((x, y) for x in MAGNET_ROWS for y in (-9.0, 0.0, 9.0))
CAP_SEAT_SIZE = (12.9, 7.9)
CAP_SEAT_DEPTH = 0.8
CAP_FACE_THICKNESS = 0.4  # Two 0.2 mm layers over the magnet; retain the 0.8 mm rim.
MAGNET_INSTALL_Z = CAP_FACE_THICKNESS + 0.1
MAGNET_STOP_Z = MAGNET_INSTALL_Z + MAGNET_THICKNESS + 0.1
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


def pocket_profile(size):
    """Pointed ends along X become 45-degree roofs on the upright jaw.

    Size gives the magnet's central rectangular space. Each X end adds a
    half-height triangular tip; the top cavity closes gradually instead of
    bridging its full width. The lower, flat jaw retains short roof bridges.
    """
    w, h = size
    return Polygon((-w/2, -h/2), (w/2, -h/2), ((w+h)/2, 0),
                   (w/2, h/2), (-w/2, h/2), (-(w+h)/2, 0), align=None)


def pocket_prism(size, depth):
    return extrude(pocket_profile(size), amount=depth)


def make_magnet_cap():
    """Pointed local snap cap for one 10 x 5 x 2 mm magnet.

    Print flange down, skirt up. The 0.9 mm walls and gradual snap ridge
    avoid thin features and steep cap overhangs. Four open slots split the
    skirt; its bead catches in the matching pointed groove. Physical snap
    force and retention still need a trial with your print settings.
    """
    flange = pocket_prism(CAP_FLANGE_SIZE, CAP_SEAT_DEPTH)
    skirt = Pos(0, 0, CAP_SEAT_DEPTH) * pocket_prism(
        CAP_SKIRT_SIZE, CAP_SKIRT_TOP - CAP_SEAT_DEPTH)
    bead = loft([
        Pos(0, 0, CAP_BEAD_ROOT_Z) * pocket_profile(CAP_SKIRT_SIZE),
        Pos(0, 0, CAP_BEAD_PEAK_Z) * pocket_profile(CAP_BEAD_SIZE),
        Pos(0, 0, CAP_SKIRT_TOP) * pocket_profile(CAP_SKIRT_SIZE),
    ], ruled=True)
    cap = flange.fuse(skirt, bead)
    cap = cap - Pos(0, 0, CAP_FACE_THICKNESS) * pocket_prism(
        CAP_SKIRT_INNER_SIZE, CAP_SKIRT_TOP)
    for sign in (-1, 1):
        x_slot = Pos(sign*(sum(CAP_SKIRT_INNER_SIZE)/2 + 1), 0, CAP_FACE_THICKNESS) * Box(
            3, .8, 3, align=(Align.CENTER, Align.CENTER, Align.MIN))
        y_slot = Pos(0, sign*(CAP_SKIRT_INNER_SIZE[1]/2 + .75), CAP_FACE_THICKNESS) * Box(
            .8, 2, 3, align=(Align.CENTER, Align.CENTER, Align.MIN))
        cap = cap - x_slot - y_slot
    return cap


def magnet_loading_location(money_side=False):
    """Place rear-loading geometry on the money side of the upright body."""
    return (Pos(0, 0, PLATE_THICKNESS) * Rot(180, 0, 0)
            if money_side else Pos(0, 0, 0))


def make_magnet_spacer():
    """Optional 0.4 mm retrofit spacer for jaws printed before the thin caps.

    New jaws have these stops fused in. Print spacers small face down; when
    installing in an old pocket, the larger face rests against the pocket floor.
    """
    height = MAGNET_POCKET_DEPTH - MAGNET_STOP_Z
    return loft([
        RectangleRounded(MAGNET_LENGTH-2*height, MAGNET_WIDTH-2*height, .3),
        Pos(0, 0, height) * RectangleRounded(*MAGNET_SIZE, .3+height),
    ], ruled=True)


def cut_magnet_pockets(jaw, *, money_side=False):
    """Cut cap seats and snap grooves while keeping the opposite face solid."""
    loading = magnet_loading_location(money_side)
    # Advance the magnet toward the thinner cap, keeping 0.1 mm clearance
    # at each face. A sloped backstop prevents it falling into the old space.
    # The 45-degree sides preserve the low-support printing intent.
    stop = Pos(0, 0, MAGNET_STOP_Z) * make_magnet_spacer()
    stops = []
    for x, y in MAGNET_CENTRES:
        for size, bottom, depth in (
                (MAGNET_POCKET_SIZE, -.1, MAGNET_POCKET_DEPTH + .1),
                (CAP_SEAT_SIZE, -.1, CAP_SEAT_DEPTH + .1),
                (CAP_GROOVE_SIZE, CAP_GROOVE_BOTTOM,
                 CAP_GROOVE_TOP - CAP_GROOVE_BOTTOM)):
            cutter = Pos(x, y, bottom) * pocket_prism(size, depth)
            jaw = jaw - loading * cutter
        stops.append(loading * Pos(x, y, 0) * stop)
    return jaw.fuse(*stops)


# 0.35 mm clearance between adjacent knuckle end faces.
THREE_KNUCKLES = [(-14.0, -9.10), (-2.70, 2.70), (9.10, 14.0)]
TWO_KNUCKLES   = [(-8.75, -3.05), (3.05, 8.75)]


def upright_root_mask():
    """Keep only body material supported by the two hinge webs or a slope.

    The centre gap gets a shallow inverted V, and the two outside corners
    rise toward the jaw edges. In print orientation these faces slope about
    42 degrees from vertical, replacing the three horizontal underside ledges.
    """
    ys = [-WIDTH/2, *(v for interval in TWO_KNUCKLES for v in interval),
          0, WIDTH/2]
    points = []
    for y in sorted(ys):
        distance = min(max(low-y, 0, y-high) for low, high in TWO_KNUCKLES)
        points.append((BODY_START_X + UPRIGHT_ROOT_RISE*distance, y))
    points += [(TIP_X+1, WIDTH/2), (TIP_X+1, -WIDTH/2)]
    return extrude(Polygon(*points, align=None), amount=PLATE_THICKNESS, dir=(0, 0, 1))


def moving_body_location():
    """Body placement about its inner tip; zero cant keeps clamping faces parallel."""
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
    # Round the outside rims before cutting pockets or adding hinge parts.
    # This keeps the cap seats, joint clearances and support slopes exact.
    perimeter = [edge for edge in jaw.edges()
                 if edge.bounding_box().size.Z < 1e-6]
    jaw = fillet(perimeter, PLATE_EDGE_RADIUS)

    if not captive_axle:
        jaw = jaw & upright_root_mask()
    jaw = cut_magnet_pockets(jaw, money_side=True)
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


def split_bottom_jaw(jaw):
    """Two rigid flat pieces joined by a captive hinge ahead of the magnets."""
    def portion(low, high):
        return jaw & (Pos((low+high)/2, 0, 4) * Box(high-low, WIDTH+4, 20))
    root = portion(-10, SECOND_PIVOT_X - SECOND_SHOULDER)
    closing = portion(SECOND_PIVOT_X + SECOND_SHOULDER, TIP_X + 1)
    for intervals, is_root in ((THREE_KNUCKLES, True), (TWO_KNUCKLES, False)):
        piece = root if is_root else closing
        for low, high in intervals:
            middle, width = (low+high)/2, high-low
            barrel = Pos(SECOND_PIVOT_X, middle, SECOND_PIVOT_Z) * Rot(90, 0, 0) * Cylinder(
                SECOND_RADIUS, width, align=(Align.CENTER, Align.CENTER, Align.CENTER))
            end = (SECOND_PIVOT_X - SECOND_SHOULDER - .3 if is_root
                   else SECOND_PIVOT_X + SECOND_SHOULDER + .3)
            web = Pos((end+SECOND_PIVOT_X)/2, middle, 0) * Box(
                abs(end-SECOND_PIVOT_X), width, PLATE_THICKNESS,
                align=(Align.CENTER, Align.CENTER, Align.MIN))
            land = Pos(SECOND_PIVOT_X, middle, 0) * Box(
                2.8, width, .6, align=(Align.CENTER, Align.CENTER, Align.MIN))
            piece = piece.fuse(barrel, web, land)
        pin = Pos(SECOND_PIVOT_X, 0, SECOND_PIVOT_Z) * Rot(90, 0, 0) * Cylinder(
            (SECOND_AXLE_D if is_root else SECOND_BORE_D)/2,
            WIDTH if is_root else WIDTH+2,
            align=(Align.CENTER, Align.CENTER, Align.CENTER))
        if is_root:
            root = piece.fuse(pin)
        else:
            closing = piece - pin
    return root, closing


def main_hinge_location(angle):
    return Pos(0, 0, PIVOT_Z) * Rot(0, angle, 0) * Pos(0, 0, -PIVOT_Z)


def bottom_hinge_location(angle):
    return (Pos(SECOND_PIVOT_X, 0, SECOND_PIVOT_Z) * Rot(0, angle, 0)
            * Pos(-SECOND_PIVOT_X, 0, -SECOND_PIVOT_Z))


def make_clip(open_angle=90.0, bottom_angle=0.0):
    """Return root link, closing plate, wallet jaw; both joint angles in degrees.

    Print with the wallet upright at 90 degrees and the closing plate flat.
    The second joint lets the closing plate align with the wallet jaw as
    the short root link swings around different money thicknesses.
    """
    root, closing = split_bottom_jaw(make_jaw(THREE_KNUCKLES, captive_axle=True))
    closing = bottom_hinge_location(bottom_angle) * closing
    wallet = make_jaw(TWO_KNUCKLES)
    wallet = Pos(0, 0, 2*PIVOT_Z) * Rot(180, 0, 0) * wallet
    wallet = main_hinge_location(-open_angle) * wallet
    return root, closing, wallet


def make_cash_configuration(root_angle):
    """Demonstrate parallel faces over cash: equal opposite joint rotations."""
    root, closing, wallet = make_clip(0, -root_angle)
    movement = main_hinge_location(root_angle)
    return movement * root, movement * closing, wallet


def make_print_layout():
    """Keep the wallet-side jaw upright, with the opposite jaw flat."""
    return Compound(children=list(make_clip(90)))


def make_caps_print_layout():
    cap = make_magnet_cap()
    return Compound(children=[Pos(TIP_X + 15 + 14*i, y, 0) * Rot(0, 0, 90) * cap
                              for i in range(len(MAGNET_CENTRES)) for y in (-12, 12)])


def make_closed_assembly():
    root, closing, upper = make_clip(0)
    cap = make_magnet_cap()
    caps = []
    for x, y in MAGNET_CENTRES:
        local = Pos(x, y, 0) * cap
        caps.append(magnet_loading_location(True) * local)
        caps.append(Pos(0, 0, 2*PIVOT_Z) * Rot(180, 0, 0)
                    * moving_body_location() * magnet_loading_location(True) * local)
    return Compound(children=[root, closing, upper, *caps])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('output'))
    parser.add_argument('--view', action='store_true',
                        help='Show the exported STEP in VS Code OCP CAD Viewer (requires ocp-vscode)')
    parser.add_argument('--view-state', choices=('print', 'closed', 'cash'), default='print',
                        help='Assembly to display with --view (default: print)')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    layout = Compound(children=[make_print_layout(), make_caps_print_layout()])
    export_stl(layout, args.output / 'money_clip_print_in_place.stl')
    export_step(layout, args.output / 'money_clip_print_in_place.step')
    export_stl(make_magnet_cap(), args.output / 'money_clip_magnet_cap.stl')
    export_step(make_magnet_cap(), args.output / 'money_clip_magnet_cap.step')
    export_stl(make_magnet_spacer(), args.output / 'money_clip_magnet_spacer.stl')
    export_step(make_magnet_spacer(), args.output / 'money_clip_magnet_spacer.step')
    export_step(make_closed_assembly(),
                args.output / 'money_clip_closed.step')
    export_step(Compound(children=list(make_cash_configuration(15))),
                args.output / 'money_clip_cash.step')
    print(f'Exported print-in-place clip to {args.output}')
    print('Print as oriented: wallet-side jaw upright at 90 degrees; caps flange-down.')
    if args.view:
        try:
            from ocp_vscode import show
        except ImportError:
            parser.exit(1, 'Exports saved. Viewing requires ocp-vscode: '
                        'python -m pip install ocp-vscode\n')
        from build123d import import_step
        filename = {'closed': 'money_clip_closed.step',
                    'cash': 'money_clip_cash.step',
                    'print': 'money_clip_print_in_place.step'}[args.view_state]
        exported = import_step(args.output / filename)
        show(exported, names=[f'Money clip — {args.view_state}'])


if __name__ == '__main__':
    main()
