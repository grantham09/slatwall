import unittest
from build123d import Align, Box, GeomType, Plane, Pos, Rot
from magnetic_money_clip import (
    make_clip, make_jaw, make_print_layout, RADIAL_CLEARANCE,
    PLATE_THICKNESS, TIP_X, THREE_KNUCKLES, TWO_KNUCKLES,
    MAGNET_CENTRES, MAGNET_SKIN, MAGNET_POCKET_DEPTH,
    MAGNET_LENGTH, MAGNET_WIDTH, MAGNET_THICKNESS, MAGNET_SIZE, CAP_FLANGE_SIZE,
    MAGNET_POCKET_SIZE, pocket_prism,
    CAP_TAB_THICKNESS, CAP_SKIRT_SIZE, CAP_SKIRT_INNER_SIZE,
    make_magnet_cap, make_caps_print_layout, make_closed_assembly,
    moving_body_location, magnet_loading_location,
)


class MoneyClipTests(unittest.TestCase):
    def test_jaws_remain_separate_through_rotation(self):
        for angle in (0, 14, 45, 90, 135, 180):
            with self.subTest(angle=angle):
                fixed, moving = make_clip(angle)
                for jaw in (fixed, moving):
                    self.assertTrue(jaw.is_valid)
                    self.assertEqual(len(jaw.solids()), 1)
                overlap = fixed & moving
                self.assertLess(overlap.volume if overlap else 0, 1e-6)
                if angle:
                    self.assertAlmostEqual(fixed.distance_to(moving),
                                           RADIAL_CLEARANCE, places=5)

    def test_print_layout_has_two_solids_on_bed(self):
        layout = make_print_layout()
        self.assertEqual(len(layout.solids()), 2)
        for jaw in layout.solids():
            self.assertTrue(jaw.is_valid)
            self.assertAlmostEqual(jaw.bounding_box().min.Z, 0, places=5)
        flat, upright = layout.solids()
        self.assertAlmostEqual(flat.bounding_box().size.Z, 2*PLATE_THICKNESS, places=5)
        self.assertGreater(upright.bounding_box().size.X, 2*PLATE_THICKNESS)
        self.assertGreater(upright.bounding_box().max.Z, TIP_X)
        # Both jaws need actual flat bed contact, not a tangent cylinder edge.
        bed_slice = Pos(0, 0, 0) * Box(100, 100, .01,
                            align=(Align.CENTER, Align.CENTER, Align.MIN))
        for jaw in layout.solids():
            self.assertGreater((jaw & bed_slice).volume, .05)

    def test_upright_body_bottom_has_slopes_instead_of_flat_ledges(self):
        _, jaw = make_clip(90)
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
        self.assertEqual(len(MAGNET_CENTRES), 3)
        self.assertEqual((MAGNET_LENGTH, MAGNET_WIDTH, MAGNET_THICKNESS), (10, 5, 2))
        self.assertAlmostEqual(PLATE_THICKNESS - MAGNET_POCKET_DEPTH, MAGNET_SKIN)
        for knuckles in (THREE_KNUCKLES, TWO_KNUCKLES):
            jaw = make_jaw(knuckles, captive_axle=knuckles == THREE_KNUCKLES)
            for x, y in MAGNET_CENTRES:
                magnet = Pos(x, y, .9) * Box(
                    *MAGNET_SIZE, MAGNET_THICKNESS,
                    align=(Align.CENTER, Align.CENTER, Align.MIN))
                skin = Pos(x, y, MAGNET_POCKET_DEPTH + .1) * Box(
                    10.6, 5.6, MAGNET_SKIN - .2,
                    align=(Align.CENTER, Align.CENTER, Align.MIN))
                if knuckles == TWO_KNUCKLES:
                    placement = moving_body_location() * magnet_loading_location(True)
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
            placement = (Pos(0, 0, 0) if captive else
                         moving_body_location() * magnet_loading_location(True))
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
                magnet = placement * Pos(x, y, .9) * Box(
                    *MAGNET_SIZE, MAGNET_THICKNESS,
                    align=(Align.CENTER, Align.CENTER, Align.MIN))
                overlap = magnet & fitted
                self.assertLess(overlap.volume if overlap else 0, 1e-6)
        self.assertEqual(len(make_caps_print_layout().solids()), 6)
        self.assertEqual(len(make_closed_assembly().solids()), 8)

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
        self.assertEqual(len({x for x, _ in MAGNET_CENTRES}), 1)
        self.assertEqual(len({y for _, y in MAGNET_CENTRES}), 3)

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

    def test_smooth_tips_and_inward_jaw(self):
        for knuckles in (THREE_KNUCKLES, TWO_KNUCKLES):
            jaw = make_jaw(knuckles, captive_axle=knuckles == THREE_KNUCKLES)
            for x in (39, 40):
                probe = Pos(x, 0, PLATE_THICKNESS - .2) * Box(.3, 10, .1)
                if knuckles == TWO_KNUCKLES:
                    probe = moving_body_location() * probe
                self.assertAlmostEqual((jaw & probe).volume, probe.volume, places=5)
        fixed, moving = make_clip(0)
        self.assertAlmostEqual(fixed.distance_to(moving), 0, places=5)
        root_gap = Pos(10, 0, PLATE_THICKNESS + .4) * Box(.4, 4, .4)
        overlap = moving & root_gap
        self.assertLess(overlap.volume if overlap else 0, 1e-6)
        tip_contact = Pos(40, 0, PLATE_THICKNESS + .3) * Box(.4, 4, .2)
        self.assertAlmostEqual((moving & tip_contact).volume, tip_contact.volume, places=5)
        # Closing past tip contact must be stopped by the jaw, not the hinge.
        fixed, moving = make_clip(-1)
        self.assertGreater((fixed & moving).volume, .1)

    def test_curved_hinge_underside_reaches_bed_with_support_slope(self):
        _, moving = make_clip(90)
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
