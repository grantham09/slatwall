"""Integration checks for the supplied wallet and actual exported print mesh."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

try:
    import numpy as np
    import trimesh
    from merge_wallet_clip import build, CARD_BACK_Y
    import magnetic_money_clip as clip
except ImportError:
    build = None


@unittest.skipIf(build is None, 'Install requirements-wallet.txt for mesh integration checks')
class WalletMergeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = TemporaryDirectory()
        cls.output = Path(cls.directory.name)
        cls.source = Path(__file__).resolve().parents[1]/'assets/cascade_card_wallet_v3_no_clip.stl'
        with redirect_stdout(StringIO()):
            cls.report = build(cls.source, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_exported_print_mesh_contains_twenty_closed_parts(self):
        mesh = trimesh.load_mesh(self.output/'cascade_wallet_with_clip_print.stl')
        self.assertTrue(mesh.is_watertight)
        parts = mesh.split(only_watertight=False, repair=False)
        self.assertEqual(len(parts), 20)
        self.assertTrue(all(p.is_watertight and p.volume > 0 for p in parts))
        self.assertTrue(all(abs(p.bounds[0, 2]) < .001 for p in parts))
        shell = trimesh.load_mesh(self.output/'wallet_with_fixed_clip.stl')
        self.assertEqual(len(shell.split(repair=False)), 1)

    def test_original_card_mechanism_geometry_is_unchanged(self):
        original = trimesh.load_mesh(self.source)
        mechanism = min(original.split(repair=False), key=lambda p: p.extents[2])
        exported = trimesh.load_mesh(self.output/'original_card_mechanism.stl')
        self.assertEqual(len(mechanism.faces), len(exported.faces))
        np.testing.assert_array_equal(np.unique(mechanism.vertices, axis=0),
                                      np.unique(exported.vertices, axis=0))

    def test_moving_parts_and_magnet_chambers_are_clear(self):
        checks = self.report['intersection_checks_mm3']
        self.assertIn('fixed_cap_seats', checks)
        self.assertIn('magnet_chambers', checks)
        self.assertIn('closing_cash_3mm', checks)
        self.assertGreaterEqual(len(checks), 19)
        for name, volume in checks.items():
            with self.subTest(name=name):
                self.assertLess(abs(volume), 1e-5)

    def test_mount_is_recessed_without_entering_card_space(self):
        self.assertGreaterEqual(self.report['new_material_min_y_mm'], CARD_BACK_Y-.001)
        self.assertAlmostEqual(self.report['closed_protrusion_past_original_back_mm'], 4.7, places=3)
        self.assertAlmostEqual(self.report['fixed_face_protrusion_past_original_back_mm'], 1.1, places=3)
        self.assertGreater(self.report['wall_removed_mm3'], 0)

    @staticmethod
    def back_surface_y(mesh, x, z):
        """Independent ray/triangle intersection through the actual STL surface."""
        triangles = mesh.triangles
        a = triangles[:, 0][:, [0, 2]]
        b = triangles[:, 1][:, [0, 2]]-a
        c = triangles[:, 2][:, [0, 2]]-a
        p = np.array([x, z])-a
        denominator = b[:, 0]*c[:, 1]-b[:, 1]*c[:, 0]
        valid = abs(denominator) > 1e-10
        u, v = np.zeros(len(triangles)), np.zeros(len(triangles))
        u[valid] = (p[valid, 0]*c[valid, 1]-p[valid, 1]*c[valid, 0])/denominator[valid]
        v[valid] = (b[valid, 0]*p[valid, 1]-b[valid, 1]*p[valid, 0])/denominator[valid]
        hits = valid & (u >= -1e-7) & (v >= -1e-7) & (u+v <= 1+1e-7)
        ys = (triangles[:, 0, 1] + u*(triangles[:, 1, 1]-triangles[:, 0, 1])
              + v*(triangles[:, 2, 1]-triangles[:, 0, 1]))
        if not np.any(hits):
            raise AssertionError('Surface sample did not hit the mesh')
        return ys[hits].max()

    def test_fixed_plate_edges_blend_flush_with_original_wall(self):
        original = trimesh.load_mesh(self.source)
        shell = max(original.split(repair=False), key=lambda p: p.extents[2])
        merged = trimesh.load_mesh(self.output/'wallet_with_fixed_clip.stl')
        samples = [(x, z) for x in (-clip.WIDTH/2+.0001, clip.WIDTH/2-.0001)
                   for z in (25, 35, 50, 60)]
        samples += [(x, clip.TIP_X+clip.PIVOT_Z-.0001) for x in (-10, 0, 10)]
        for x, z in samples:
            with self.subTest(x=x, z=z):
                original_y = self.back_surface_y(shell, x, z)
                merged_y = self.back_surface_y(merged, x, z)
                self.assertAlmostEqual(merged_y, original_y, delta=.01)


if __name__ == '__main__':
    unittest.main()
