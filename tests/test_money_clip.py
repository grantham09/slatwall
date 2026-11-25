import unittest
from itertools import combinations
from math import radians, sin, cos
from build123d import Align, Box, GeomType, Plane, Pos, Rot
from magnetic_money_clip import (
    make_clip, make_jaw, make_print_layout, RADIAL_CLEARANCE,
    PLATE_THICKNESS, TIP_X, WIDTH, PLATE_EDGE_RADIUS, THREE_KNUCKLES, TWO_KNUCKLES,
    MAGNET_CENTRES, MAGNET_SKIN, MAGNET_POCKET_DEPTH,
    MAGNET_LENGTH, MAGNET_WIDTH, MAGNET_THICKNESS, MAGNET_SIZE, CAP_FLANGE_SIZE,
    MAGNET_POCKET_SIZE, pocket_prism,
    CAP_TAB_THICKNESS, CAP_SKIRT_SIZE, CAP_SKIRT_INNER_SIZE,
    CAP_FACE_THICKNESS, CAP_SEAT_DEPTH, MAGNET_INSTALL_Z,
    make_magnet_cap, make_caps_print_layout, make_closed_assembly,
    moving_body_location, magnet_loading_location, make_cash_configuration,
    SECOND_RADIUS, SECOND_BORE_D, SECOND_PIVOT_X, SECOND_PIVOT_Z,
)


class MoneyClipTests(unittest.TestCase):
    @staticmethod
    def overlap_volume(first, second):
        overlap = first & second
        return (sum(shape.volume for shape in overlap) if isinstance(overlap, list)
                else overlap.volume if overlap else 0)

    def test_jaws_remain_separate_through_rotation(self):
        for angle in (0, 14, 45, 90, 135, 180):
            with self.subTest(angle=angle):
                root, closing, wallet = make_clip(angle)
                for piece in (root, closing, wallet):
                    self.assertTrue(piece.is_valid)
                    self.assertEqual(len(piece.solids()), 1)
                for a, b in combinations((root, closing, wallet), 2):
                    self.assertLess(self.overlap_volume(a, b), 1e-6)
                if angle:
                    self.assertAlmostEqual(root.distance_to(wallet), RADIAL_CLEARANCE, places=5)

    def test_second_joint_moves_without_collisions(self):
        self.assertAlmostEqual(SECOND_RADIUS - SECOND_BORE_D/2, .9)
        for angle in (-20, 0, 20):
            parts = make_clip(90, angle)
            for a, b in combinations(parts, 2):
                self.assertLess(self.overlap_volume(a, b), 1e-6)

    def test_two_joints_hold_closing_plate_parallel_over_cash(self):
        for angle in (5, 15, 25):
            root, closing, wallet = make_cash_configuration(angle)
            for a, b in combinations((root, closing, wallet), 2):
                self.assertLess(self.overlap_volume(a, b), 1e-6)
            self.assertAlmostEqual(closing.bounding_box().size.Z, PLATE_THICKNESS, places=5)
            gap = PLATE_THICKNESS - closing.bounding_box().max.Z
            expected = SECOND_PIVOT_X*sin(radians(angle)) - (
                PLATE_THICKNESS-SECOND_PIVOT_Z)*(1-cos(radians(angle)))
            self.assertAlmostEqual(gap, expected, places=5)
            self.assertGreater(gap, 0)
            cash_probe = Pos(35, 0, PLATE_THICKNESS-gap/2) * Box(.5, .5, gap*.5)
            for piece in (root, closing, wallet):
                self.assertLess(self.overlap_volume(piece, cash_probe), 1e-6)

    def test_print_layout_has_three_solids_on_bed(self):
        layout = make_print_layout()
        self.assertEqual(len(layout.solids()), 3)
        root, closing, wallet = layout.solids()
        self.assertAlmostEqual(root.bounding_box().size.Z, 2*PLATE_THICKNESS, places=5)
        self.assertAlmostEqual(closing.bounding_box().size.Z, PLATE_THICKNESS, places=5)
        self.assertGreater(wallet.bounding_box().max.Z, TIP_X)
        bed_slice = Pos(30, 0, 0) * Box(100, 100, .01,
                            align=(Align.CENTER, Align.CENTER, Align.MIN))
        for piece in layout.solids():
            self.assertTrue(piece.is_valid)
            self.assertAlmostEqual(piece.bounding_box().min.Z, 0, places=5)
            self.assertGreater((piece & bed_slice).volume, .05)

    def test_upright_body_bottom_has_slopes_instead_of_flat_ledges(self):
        _, _, jaw = make_clip(90)
        bottom_faces = [face for face in jaw.faces()
                        if face.geom_type == GeomType.PLANE
                        and 8 < face.center().Z < 16
                        and face.normal_at().Z < -.1]
        self.assertEqual(len(bottom_faces), 4)
        for face in bottom_faces:
            self.assertLessEqual(-face.normal_at().Z, 2**-.5)
        self.assertEqual(len(jaw.solids()), 1)
        self.assertTrue(jaw.is_valid)

    def test_magnet_pockets_keep_opposite_faces_continuous(self):
        self.assertEqual(len(MAGNET_CENTRES), 8)
        self.assertEqual((MAGNET_LENGTH, MAGNET_WIDTH, MAGNET_THICKNESS), (10, 5, 2))
        self.assertAlmostEqual(PLATE_THICKNESS - MAGNET_POCKET_DEPTH, MAGNET_SKIN)
        for knuckles in (THREE_KNUCKLES, TWO_KNUCKLES):
            jaw = make_jaw(knuckles, captive_axle=knuckles == THREE_KNUCKLES)
            for x, y in MAGNET_CENTRES:
                magnet = Pos(x, y, MAGNET_INSTALL_Z) * Box(
                    *MAGNET_SIZE, MAGNET_THICKNESS,
                    align=(Align.CENTER, Align.CENTER, Align.MIN))
                skin = Pos(x, y, MAGNET_POCKET_DEPTH + .1) * Box(
                    10.6, 5.6, MAGNET_SKIN - .2,
                    align=(Align.CENTER, Align.CENTER, Align.MIN))
                placement = magnet_loading_location(True)
                if knuckles == TWO_KNUCKLES:
                    placement = moving_body_location() * placement
                magnet = placement * magnet
                skin = placement * skin
                overlap = jaw & magnet
                self.assertLess(overlap.volume if overlap else 0, 1e-6)
                self.assertAlmostEqual((jaw & skin).volume, skin.volume, places=5)

    def test_local_snap_caps_fit_and_are_mechanically_captured(self):
        cap = make_magnet_cap()
        self.assertTrue(cap.is_valid)
        self.assertEqual(len(cap.solids()), 1)
        self.assertAlmostEqual(cap.bounding_box().size.X, sum(CAP_FLANGE_SIZE), places=5)
        self.assertAlmostEqual(cap.bounding_box().size.Y, CAP_FLANGE_SIZE[1], places=5)
        for knuckles in (THREE_KNUCKLES, TWO_KNUCKLES):
            captive = knuckles == THREE_KNUCKLES
            jaw = make_jaw(knuckles, captive_axle=captive)
            placement = magnet_loading_location(True)
            if not captive:
                placement = moving_body_location() * placement
            for x, y in MAGNET_CENTRES:
                local = Pos(x, y, 0) * cap
                fitted = placement * local
                overlap = jaw & fitted
                self.assertLess(overlap.volume if overlap else 0, 1e-6)
                # Capture must work for both rear and money-side installation.
                pulled = placement * Pos(0, 0, -.5) * local
                pushed = placement * Pos(0, 0, .2) * local
                for displaced in (pulled, pushed):
                    collision = jaw & displaced
                    volume = (sum(shape.volume for shape in collision)
                              if isinstance(collision, list) else collision.volume)
                    self.assertGreater(volume, .01)
                magnet = placement * Pos(x, y, MAGNET_INSTALL_Z) * Box(
                    *MAGNET_SIZE, MAGNET_THICKNESS,
                    align=(Align.CENTER, Align.CENTER, Align.MIN))
                overlap = magnet & fitted
                self.assertLess(overlap.volume if overlap else 0, 1e-6)
        self.assertEqual(len(make_caps_print_layout().solids()), 16)
        self.assertEqual(len(make_closed_assembly().solids()), 19)

    def test_plate_outer_rims_are_rounded(self):
        self.assertAlmostEqual(PLATE_EDGE_RADIUS, .6)
        for knuckles in (THREE_KNUCKLES, TWO_KNUCKLES):
            jaw = make_jaw(knuckles, captive_axle=knuckles == THREE_KNUCKLES)
            for side in (-1, 1):
                for z in (.05, PLATE_THICKNESS-.05):
                    corner = Pos(43, side*(WIDTH/2-.05), z) * Box(.2, .04, .04)
                    inset = Pos(43, side*(WIDTH/2-.8), z) * Box(.2, .04, .04)
                    if knuckles == TWO_KNUCKLES:
                        corner = moving_body_location() * corner
                        inset = moving_body_location() * inset
                    self.assertLess(self.overlap_volume(jaw, corner), 1e-6)
                    self.assertAlmostEqual(self.overlap_volume(jaw, inset), inset.volume, places=5)

    def test_cap_cover_is_uniformly_thin_and_seats_flush(self):
        cap = make_magnet_cap()
        self.assertAlmostEqual(CAP_FACE_THICKNESS, .4)
        self.assertAlmostEqual(CAP_SEAT_DEPTH, .4)
        self.assertAlmostEqual(cap.bounding_box().size.Z, 2.4, places=5)
        face = Pos(0, 0, .2) * Box(4, 2, .2)
        space = Pos(0, 0, .6) * Box(4, 2, .2)
        rim = Pos(2, 3.7, .2) * Box(.1, .1, .2)
        self.assertAlmostEqual(self.overlap_volume(cap, face), face.volume, places=5)
        self.assertLess(self.overlap_volume(cap, space), 1e-6)
        self.assertAlmostEqual(self.overlap_volume(cap, rim), rim.volume, places=5)
        above_rim = Pos(2, 3.7, .6) * Box(.1, .1, .2)
        self.assertLess(self.overlap_volume(cap, above_rim), 1e-6)
        installed = magnet_loading_location(True) * cap
        self.assertAlmostEqual(installed.bounding_box().max.Z, PLATE_THICKNESS, places=5)
        edge = Pos(0, 2.45, .37) * Box(.1, .05, .04)
        self.assertAlmostEqual(self.overlap_volume(cap, edge), edge.volume, places=5)

    def test_flat_pocket_floors_keep_magnets_near_thin_faces(self):
        cap = make_magnet_cap()
        jaw = make_jaw(THREE_KNUCKLES, captive_axle=True)
        loading = magnet_loading_location(True)
        for x, y in MAGNET_CENTRES:
            local = Pos(x, y, MAGNET_INSTALL_Z) * Box(
                *MAGNET_SIZE, MAGNET_THICKNESS,
                align=(Align.CENTER, Align.CENTER, Align.MIN))
            self.assertLess(self.overlap_volume(jaw, loading*local), 1e-6)
            pushed_back = loading * Pos(0, 0, .3) * local
            self.assertGreater(self.overlap_volume(jaw, pushed_back), .1)
            pushed_forward = Pos(0, 0, -.2) * local
            self.assertGreater(self.overlap_volume(Pos(x, y, 0)*cap, pushed_forward), .1)

    def test_cap_tabs_have_printable_wall_thickness(self):
        cap = make_magnet_cap()
        for outer, inner in zip(CAP_SKIRT_SIZE, CAP_SKIRT_INNER_SIZE):
            self.assertAlmostEqual((outer-inner)/2, CAP_TAB_THICKNESS)
            self.assertGreaterEqual((outer-inner)/2, .89)
        # Check actual wall material away from slots, below the snap ridge.
        for sign in (-1, 1):
            probes = (
                Pos(2, sign*3.1, 1.4) * Box(1, .85, .6),
                Pos(6.9, sign*1.8, 1.4) * Box(.6, .6, .6),
            )
            for probe in probes:
                self.assertAlmostEqual((cap & probe).volume, probe.volume, places=5)

    def test_cap_overhangs_stay_within_45_degrees_when_flange_down(self):
        cap = make_magnet_cap()
        self.assertAlmostEqual(cap.bounding_box().min.Z, 0, places=5)
        downward_faces = [face for face in cap.faces()
                          if face.center().Z > .01 and face.normal_at().Z < -1e-5]
        self.assertGreater(len(downward_faces), 0)
        for face in downward_faces:
            # Face slope from vertical <= 45 degrees; exclude the bed face.
            self.assertLessEqual(-face.normal_at().Z, 2**-.5 + 1e-6)

    def test_wallet_jaw_pocket_roofs_are_sloped_in_upright_orientation(self):
        orientation = Rot(0, -90, 0) * Rot(180, 0, 0) * moving_body_location()
        cutter = orientation * pocket_prism(MAGNET_POCKET_SIZE, 3)
        roof_faces = [face for face in cutter.faces() if face.normal_at().Z > .1]
        self.assertEqual(len(roof_faces), 2)
        for face in roof_faces:
            self.assertLessEqual(face.normal_at().Z, 2**-.5 + 1e-6)
            self.assertGreater(face.normal_at().Z, .7)
        self.assertEqual(len({x for x, _ in MAGNET_CENTRES}), 2)
        self.assertEqual(len({y for _, y in MAGNET_CENTRES}), 4)

    def test_upright_caps_open_toward_money_and_back_is_solid(self):
        jaw = make_jaw(TWO_KNUCKLES)
        for x, y in MAGNET_CENTRES:
            mouth = moving_body_location() * Pos(x, y, PLATE_THICKNESS - .3) * Box(
                9.8, 4.8, .2, align=(Align.CENTER, Align.CENTER, Align.MIN))
            back = moving_body_location() * Pos(x, y, .1) * Box(
                10.6, 5.6, .3, align=(Align.CENTER, Align.CENTER, Align.MIN))
            overlap = jaw & mouth
            self.assertLess(overlap.volume if overlap else 0, 1e-6)
            self.assertAlmostEqual((jaw & back).volume, back.volume, places=5)

    def test_smooth_tips_and_parallel_jaws(self):
        for knuckles in (THREE_KNUCKLES, TWO_KNUCKLES):
            jaw = make_jaw(knuckles, captive_axle=knuckles == THREE_KNUCKLES)
            for x in (TIP_X - 1.8, TIP_X - 1.2):
                probe = Pos(x, 0, PLATE_THICKNESS - .2) * Box(.3, 10, .1)
                if knuckles == TWO_KNUCKLES:
                    probe = moving_body_location() * probe
                self.assertAlmostEqual((jaw & probe).volume, probe.volume, places=5)
        root, closing, moving = make_clip(0)
        self.assertAlmostEqual(closing.distance_to(moving), 0, places=5)
        root_contact = Pos(10, 0, PLATE_THICKNESS + .4) * Box(.4, 4, .4)
        self.assertAlmostEqual((moving & root_contact).volume, root_contact.volume, places=5)
        tip_contact = Pos(TIP_X - 1.2, 0, PLATE_THICKNESS + .3) * Box(.4, 4, .2)
        self.assertAlmostEqual((moving & tip_contact).volume, tip_contact.volume, places=5)
        # Closing past tip contact must be stopped by the jaw, not the hinge.
        root, closing, moving = make_clip(-1)
        self.assertGreater(self.overlap_volume(closing, moving), .1)

    def test_curved_hinge_underside_reaches_bed_with_support_slope(self):
        _, _, moving = make_clip(90)
        for y in (-6, 6):
            section = moving.intersect(Plane.XZ.offset(-y))
            curves = [edge for edge in section.edges()
                      if edge.geom_type == GeomType.BSPLINE
                      and min(edge.position_at(0).Z, edge.position_at(1).Z) < .001
                      and max(edge.position_at(0).Z, edge.position_at(1).Z) > 8]
            self.assertEqual(len(curves), 1)
            curve = curves[0]
            for i in range(101):
                tangent = curve.tangent_at(i/100)
                # At most 45 degrees outward from vertical along the curve.
                self.assertLessEqual(abs(tangent.X), abs(tangent.Z) + 1e-6)
            # It must bow away from the old straight ramp.
            midpoint = curve.position_at(.5)
            chord = (curve.position_at(0) + curve.position_at(1)) * .5
            self.assertGreater((midpoint - chord).length, .3)
