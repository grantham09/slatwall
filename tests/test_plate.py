import unittest
from dataclasses import replace
from build123d import import_step
from tempfile import TemporaryDirectory
from pathlib import Path
from build123d import export_step, Box, Pos, Align
from slatwall_plate import PlateParameters, make_plate


class PlateTests(unittest.TestCase):
    def test_parameter_variants_are_single_valid_solids(self):
        for p in [PlateParameters(),
                  replace(PlateParameters(), width=110, height=125, slot_pitch=90),
                  replace(PlateParameters(), snap_width=22, snap_length=35)]:
            with self.subTest(p=p):
                part = make_plate(p)
                self.assertTrue(part.is_valid)
                self.assertEqual(len(part.solids()), 1)
                self.assertGreater(part.volume, 0)
                self.assertAlmostEqual(part.bounding_box().size.X, p.width)
                self.assertAlmostEqual(part.bounding_box().size.Z, p.height)

    def test_measured_wall_dimensions(self):
        p = PlateParameters()
        self.assertAlmostEqual(p.slat_face_height, 36.5)
        self.assertAlmostEqual(p.internal_gap, 19.5)
        self.assertAlmostEqual(p.slot_pitch, 46)
        self.assertLess(p.lip_thickness + p.clearance + p.hook_thickness, p.slot_depth)

    def test_lower_detent_points_up_and_clears_seated_lip(self):
        p = PlateParameters()
        part = make_plate(p)
        lower = (p.height-p.slot_pitch)/2
        # Isolate the lower catch behind the wall face.
        region = Pos(0, -p.slot_depth, lower-10) * Box(
            p.snap_width, p.slot_depth-0.01, 20,
            align=(Align.CENTER, Align.MIN, Align.MIN))
        catch = part & region
        bounds = catch.bounding_box()
        self.assertAlmostEqual(bounds.max.Z,
                               lower+p.slot_height/2+p.snap_engagement, places=4)
        self.assertAlmostEqual(bounds.min.Z, lower-p.snap_thickness, places=4)
        lip = Pos(0, -p.lip_thickness, lower+p.slot_height/2) * Box(
            p.width, p.lip_thickness, p.bottom_lip_rise,
            align=(Align.CENTER, Align.MIN, Align.MIN))
        collision = part & lip
        self.assertLess(collision.volume if collision else 0, 1e-6)

    def test_step_round_trip(self):
        part = make_plate()
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'plate.step'
            export_step(part, path)
            restored = import_step(path)
            self.assertTrue(restored.is_valid)
            self.assertEqual(len(restored.solids()), 1)
            self.assertAlmostEqual(restored.volume, part.volume, places=3)

    def test_impossible_depth_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'slot_depth'):
            make_plate(replace(PlateParameters(), slot_depth=3))


if __name__ == '__main__':
    unittest.main()
