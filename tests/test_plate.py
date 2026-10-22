import unittest
from dataclasses import fields, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from build123d import Align, Box, Pos, export_step, import_step
from slatwall_plate import PlateParameters, make_plate


class PlateTests(unittest.TestCase):
    def test_public_parameters(self):
        self.assertEqual([f.name for f in fields(PlateParameters)], [
            'width', 'height', 'plate_thickness', 'hook_spacing', 'hook_width',
            'hook_thickness', 'hook_drop', 'lip_thickness', 'snap_width',
            'snap_thickness', 'snap_length', 'snap_peak', 'release_gap',
            'release_tab_length', 'release_grip_radius'])

    def test_variants_are_single_valid_solids(self):
        for overrides in ({}, dict(width=110, height=125, hook_spacing=90),
                          dict(snap_width=22, snap_length=32, snap_peak=2),
                          dict(hook_thickness=3, hook_drop=6, lip_thickness=2),
                          dict(release_tab_length=12)):
            p = replace(PlateParameters(), **overrides)
            with self.subTest(overrides=overrides):
                part = make_plate(p)
                self.assertTrue(part.is_valid)
                self.assertEqual(len(part.solids()), 1)
                self.assertAlmostEqual(part.bounding_box().size.X, p.width, places=5)
                self.assertAlmostEqual(part.bounding_box().size.Z,
                                       p.height+p.release_tab_length, places=5)

    def test_direct_hook_dimensions(self):
        # Inspect the generated geometry; neither return changes the arm gap.
        for drop, peak in ((4, 1.2), (6, 3), (2, .6)):
            p = replace(PlateParameters(), hook_drop=drop, snap_peak=peak)
            part = make_plate(p)
            depth = p.lip_thickness+p.hook_thickness
            # The straight arms are centred together inside the plate.
            pair_bottom = (p.height-p.hook_spacing-p.hook_thickness-p.snap_thickness)/2
            lower_top = pair_bottom+p.snap_thickness
            upper_bottom = lower_top+p.hook_spacing
            split = (lower_top+upper_bottom)/2
            def rear_region(z, height):
                return Pos(0, -depth-1, z) * Box(
                    p.width, depth+0.99, height,
                    align=(Align.CENTER, Align.MIN, Align.MIN))
            top = (part & rear_region(split, p.height)).bounding_box()
            bottom = (part & rear_region(0, split)).bounding_box()
            self.assertAlmostEqual(top.max.Z-p.hook_thickness -
                                   (bottom.min.Z+p.snap_thickness), p.hook_spacing, places=5)
            self.assertAlmostEqual(upper_bottom-top.min.Z, drop, places=5)
            self.assertAlmostEqual(bottom.max.Z-lower_top, peak, places=5)
            self.assertAlmostEqual(top.min.Y, -depth, places=5)
            # Check the clear space behind the plate, under the upper bridge.
            gap = Pos(0, -p.lip_thickness/2, upper_bottom-drop/2) * Box(
                p.hook_width*.8, p.lip_thickness*.8, drop*.8)
            overlap = part & gap
            self.assertLess(overlap.volume if overlap else 0, 1e-6)

    def test_release_tab_and_free_side_gaps(self):
        for length in (0, 2, 8, 12, 18):
            p = replace(PlateParameters(), release_tab_length=length)
            part = make_plate(p)
            self.assertEqual(len(part.solids()), 1)
            self.assertAlmostEqual(part.bounding_box().min.Z, -length, places=5)
            for sign in (-1, 1):
                gap = Pos(sign*(p.snap_width/2+p.release_gap/2),
                          p.plate_thickness/2, 2) * Box(
                              p.release_gap*.8, p.plate_thickness, 3)
                overlap = part & gap
                self.assertLess(overlap.volume if overlap else 0, 1e-6)
            # Probe the grip ahead of the tongue: must exist even at zero.
            grip_probe = Pos(0, p.snap_thickness+p.release_grip_radius,
                             -length+p.release_grip_radius) * Box(
                                 p.snap_width*.5, p.release_grip_radius*.4,
                                 p.release_grip_radius*.4)
            self.assertAlmostEqual((part & grip_probe).volume,
                                   grip_probe.volume, places=5)
            self.assertTrue(part.is_valid)
            if length:
                tab = Pos(0, p.snap_thickness/2, -length/2) * Box(
                    p.snap_width*.8, p.snap_thickness*.8, length*.4)
                self.assertAlmostEqual((part & tab).volume, tab.volume, places=5)

    def test_step_round_trip(self):
        part = make_plate()
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'plate.step'
            export_step(part, path)
            restored = import_step(path)
            self.assertTrue(restored.is_valid)
            self.assertEqual(len(restored.solids()), 1)
            self.assertAlmostEqual(restored.volume, part.volume, places=3)

    def test_invalid_geometry_rejected(self):
        for overrides in (dict(hook_spacing=80), dict(snap_length=40),
                          dict(snap_width=80), dict(release_tab_length=-1),
                          dict(release_grip_radius=4), dict(snap_peak=30),
                          dict(hook_drop=float('nan'))):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                make_plate(replace(PlateParameters(), **overrides))


if __name__ == '__main__':
    unittest.main()
