import unittest
from magnetic_money_clip import make_clip, make_print_layout, RADIAL_CLEARANCE


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
            self.assertAlmostEqual(jaw.bounding_box().size.Z, 28, places=5)
