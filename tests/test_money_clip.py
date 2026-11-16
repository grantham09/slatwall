import unittest
from build123d import Align, Box, Cylinder, Pos
from magnetic_money_clip import (
    make_clip, make_jaw, make_print_layout, RADIAL_CLEARANCE,
    PLATE_THICKNESS, TIP_X, THREE_KNUCKLES, TWO_KNUCKLES,
    MAGNET_X, MAGNET_Y, MAGNET_POCKET_D, MAGNET_POCKET_DEPTH,
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
        self.assertAlmostEqual(upright.bounding_box().size.X, 2*PLATE_THICKNESS, places=5)
        self.assertAlmostEqual(upright.bounding_box().max.Z,
                               TIP_X + PLATE_THICKNESS, places=5)
        # Both jaws need actual flat bed contact, not a tangent cylinder edge.
        bed_slice = Pos(0, 0, 0) * Box(100, 100, .01,
                            align=(Align.CENTER, Align.CENTER, Align.MIN))
        for jaw in layout.solids():
            self.assertGreater((jaw & bed_slice).volume, .05)

    def test_three_blind_magnet_pockets_per_jaw(self):
        self.assertEqual(len(MAGNET_Y), 3)
        self.assertAlmostEqual(PLATE_THICKNESS - MAGNET_POCKET_DEPTH, .7)
        for knuckles in (THREE_KNUCKLES, TWO_KNUCKLES):
            jaw = make_jaw(knuckles)
            for y in MAGNET_Y:
                probe = Pos(MAGNET_X, y, PLATE_THICKNESS - 1) * Cylinder(
                    MAGNET_POCKET_D/2 - .1, .8,
                    align=(Align.CENTER, Align.CENTER, Align.MIN))
                overlap = jaw & probe
                self.assertLess(overlap.volume if overlap else 0, 1e-6)
                floor = Pos(MAGNET_X, y, .1) * Cylinder(
                    MAGNET_POCKET_D/2 - .1, .4,
                    align=(Align.CENTER, Align.CENTER, Align.MIN))
                self.assertAlmostEqual((jaw & floor).volume, floor.volume, places=5)
