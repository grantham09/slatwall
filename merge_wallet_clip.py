"""Recess the money clip into the lever-free back of the supplied Cascade V3 STL.

The supplied wallet uses X for width, Y for thickness and Z for height.
Its lever projects toward -Y; the card cavity ends at Y=9.4 mm. This is a
measured fit for assets/cascade_card_wallet_v3_no_clip.stl, not an automatic
mounting algorithm for arbitrary wallet STLs.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import manifold3d as mf
import numpy as np
import trimesh
from build123d import Align, Box, Compound, Pos, Rot, export_stl, import_stl

import magnetic_money_clip as clip


CARD_BACK_Y = 9.4
CLIP_FACE_Y = CARD_BACK_Y + clip.PLATE_THICKNESS
JOINT_CLEARANCE = 0.35
BACK_WALL_BASE_Y = 11.4  # Outer surface between the supplied wallet's raised ribs.
MAX_SIDE_BLEND = 0.7
MAX_TOP_BLEND = 1.5
CAP_COLLAR_MARGIN = 0.35
SOURCE_SHA256 = 'cfcf29feb4395c374c6b497182334f99aaa6731955c9d74af330ce7121bf32c2'
# Rotate the clip's X extrusion direction toward the wallet's +Y face.
MOUNT_ROTATION = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=float)


def as_manifold(mesh):
    if not mesh.is_watertight or not mesh.is_winding_consistent or mesh.volume <= 0:
        raise ValueError('Boolean input must be a consistently wound, closed positive volume')
    result = mf.Manifold(mf.Mesh(
        vert_properties=np.ascontiguousarray(mesh.vertices, dtype=np.float32),
        tri_verts=np.ascontiguousarray(mesh.faces, dtype=np.uint32)))
    if result.status() != mf.Error.NoError:
        raise ValueError(f'Manifold conversion failed: {result.status()}')
    return result


def as_mesh(solid):
    if solid.status() != mf.Error.NoError or solid.is_empty():
        raise ValueError(f'Boolean result failed: {solid.status()}')
    data = solid.to_mesh()
    result = trimesh.Trimesh(vertices=np.asarray(data.vert_properties)[:, :3],
                             faces=np.asarray(data.tri_verts), process=False)
    if not result.is_watertight or result.volume <= 0:
        raise ValueError('Boolean result is not a closed positive volume')
    return result


def tessellate(shape, directory, name):
    path = Path(directory) / (name + '.stl')
    export_stl(shape, path, tolerance=.01, angular_tolerance=.1)
    mesh = trimesh.load_mesh(path, process=True)
    if not mesh.is_watertight:
        # OCCT's ellipsoid bowl poles produce three micron-scale duplicate
        # vertices/degenerate facets. Weld at 1e-6 mm and drop only collapsed
        # triangles; never fill a boundary or change the intended cavities.
        volume = mesh.volume
        mesh.merge_vertices(digits_vertex=6)
        mesh.update_faces(mesh.nondegenerate_faces())
        mesh.remove_unreferenced_vertices()
        if not mesh.is_watertight or abs(mesh.volume-volume) > .001:
            raise ValueError(f'{name}: tessellation seam cleanup failed')
    return mesh


def mount(mesh):
    result = mesh.copy()
    transform = np.eye(4)
    transform[:3, :3] = MOUNT_ROTATION
    transform[1, 3] = CLIP_FACE_Y
    result.apply_transform(transform)
    return result


def pocket_cutters():
    loading = clip.magnet_loading_location(True)
    place_wallet = clip.main_hinge_location(-90) * Pos(0, 0, 2*clip.PIVOT_Z)
    place_wallet = place_wallet * Rot(180, 0, 0) * clip.moving_body_location()
    cutters = []
    for x, y in clip.MAGNET_CENTRES:
        for size, bottom, depth in (
                (clip.MAGNET_POCKET_SIZE, -.1, clip.MAGNET_POCKET_DEPTH+.1),
                (clip.CAP_SEAT_SIZE, -.1, clip.CAP_SEAT_DEPTH+.1),
                (clip.CAP_GROOVE_SIZE, clip.CAP_GROOVE_BOTTOM,
                 clip.CAP_GROOVE_TOP-clip.CAP_GROOVE_BOTTOM)):
            cutters.append(place_wallet * loading * Pos(x, y, bottom)
                           * clip.pocket_prism(size, depth))
    return Compound(children=cutters)


def blend_fixed_perimeter(solid, fixed_bounds, pocket_bounds):
    """Taper only exposed plate rims into the existing wallet back.

    Widths are limited by the actual seat bounds, preserving a full-height
    collar around every cap. The original shell is joined afterwards and
    supplies its unchanged wall/rib surface at the outside of the blends.
    """
    rise = CLIP_FACE_Y - BACK_WALL_BASE_Y
    widths = {}

    def profile(edge, width, sign=1):
        # Smoothstep is tangent to the plate face and the base wall level.
        # Linear facets approximate the curve to well below STL tolerance.
        points = [(edge-sign*width, CLIP_FACE_Y+1),
                  (edge+sign, CLIP_FACE_Y+1), (edge+sign, BACK_WALL_BASE_Y)]
        for t in np.linspace(0, 1, 65):
            y = BACK_WALL_BASE_Y + rise*t*t*(3-2*t)
            points.append((edge-sign*width*t, y))
        points = np.asarray(points)
        area = np.sum(points[:, 0]*np.roll(points[:, 1], -1)
                      - np.roll(points[:, 0], -1)*points[:, 1])
        if area < 0:
            points = points[::-1]
        return mf.CrossSection([points])

    for sign, index, name in ((-1, 0, 'left'), (1, 1, 'right')):
        edge = fixed_bounds[index, 0]
        free_rim = sign*(edge-pocket_bounds[index, 0])
        width = min(MAX_SIDE_BLEND, max(0, free_rim-CAP_COLLAR_MARGIN))
        widths[name] = float(width)
        if width > 1e-5 and rise > 0:
            cutter = profile(edge, width, sign).extrude(
                fixed_bounds[1, 2]-fixed_bounds[0, 2]+2).translate(
                    (0, 0, fixed_bounds[0, 2]-1))
            solid = solid-cutter
    width = min(MAX_TOP_BLEND,
                max(0, fixed_bounds[1, 2]-pocket_bounds[1, 2]-CAP_COLLAR_MARGIN))
    widths['top'] = float(width)
    if width > 1e-5 and rise > 0:
        cutter = profile(fixed_bounds[1, 2], width).extrude(
            fixed_bounds[1, 0]-fixed_bounds[0, 0]+2).rotate((0, -90, 0)).translate(
                (fixed_bounds[1, 0]+1, 0, 0))
        solid = solid-cutter
    return solid, widths


def build(wallet_path, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    source_hash = sha256(Path(wallet_path).read_bytes()).hexdigest()
    if source_hash != SOURCE_SHA256:
        raise ValueError('This measured fit requires the supplied Cascade V3 STL; remeasure other versions')
    original = trimesh.load_mesh(wallet_path, process=True)
    parts = original.split(only_watertight=False)
    if len(parts) != 2 or not all(p.is_watertight for p in parts):
        raise ValueError('Expected the supplied wallet: one shell and one separate mechanism')
    shell = max(parts, key=lambda p: p.extents[2])
    mechanism = min(parts, key=lambda p: p.extents[2])
    if not np.allclose(original.bounds, [[-30, -3.9862411, 0], [30, 11.9, 106.5]], atol=.01):
        raise ValueError('Wallet bounds differ from the measured Cascade V3 input')

    with TemporaryDirectory() as temporary:
        root_cad, closing_cad, fixed_cad = clip.make_clip(90)
        root = mount(tessellate(root_cad, temporary, 'root'))
        closing = mount(tessellate(closing_cad, temporary, 'closing'))
        fixed = mount(tessellate(fixed_cad, temporary, 'fixed'))
        caps = mount(tessellate(clip.make_caps_print_layout(), temporary, 'caps'))
        voids = mount(tessellate(pocket_cutters(), temporary, 'pocket_voids'))

        # Trim only the root web's tiny rear bulge: no new geometry may enter
        # the original card/mechanism space in front of the back-wall plane.
        fixed_solid = as_manifold(fixed).trim_by_plane((0, 1, 0), CARD_BACK_Y)
        fixed_solid, edge_blends = blend_fixed_perimeter(fixed_solid, fixed.bounds, voids.bounds)
        # Remove old wall material from the magnet seats before uniting the
        # plate, otherwise the overlapping wallet wall would refill the holes.
        shell_solid = as_manifold(shell)
        hinge_clearance = mf.Manifold.cylinder(
            clip.WIDTH + 2*JOINT_CLEARANCE,
            clip.KNUCKLE_RADIUS + JOINT_CLEARANCE,
            circular_segments=180, center=True).rotate((0, 90, 0)).translate(
                (0, CLIP_FACE_Y, clip.PIVOT_Z))
        cavity_solid = mf.Manifold.batch_boolean(
            [as_manifold(p) for p in voids.split()], mf.OpType.Add)
        foot_clearance = mf.Manifold.cube((clip.WIDTH+2*JOINT_CLEARANCE, 5, 1.3)).translate(
            (-clip.WIDTH/2-JOINT_CLEARANCE, CARD_BACK_Y-.1, -.1))
        recessed_shell = shell_solid - cavity_solid - (hinge_clearance + foot_clearance)
        merged_solid = recessed_shell + fixed_solid
        merged = as_mesh(merged_solid)
        if len(merged.split()) != 1:
            raise ValueError('Clip is not joined to the wallet shell as one connected solid')

        pieces = {'wallet_with_fixed_clip': merged, 'original_card_mechanism': mechanism,
                  'clip_root_link': root, 'clip_closing_plate': closing}
        pieces.update({f'magnet_cap_{i+1:02d}': p for i, p in enumerate(caps.split())})
        if len(pieces) != 20:
            raise ValueError('Expected wallet, mechanism, two moving clip pieces and 16 caps')
        for name, mesh in pieces.items():
            if not mesh.is_watertight:
                raise ValueError(f'{name} is not watertight')
            mesh.export(output / f'{name}.stl')
        combined = trimesh.util.concatenate(list(pieces.values()))
        combined.export(output / 'cascade_wallet_with_clip_print.stl')

        # Closed inspection assembly: wallet remains upright; only the two
        # flat moving pieces fold up. The shell and card mechanism never move.
        closed_root = mount(tessellate(clip.main_hinge_location(-90)*root_cad,
                                      temporary, 'closed_root'))
        closed_closing = mount(tessellate(clip.main_hinge_location(-90)*closing_cad,
                                         temporary, 'closed_closing'))
        cap_cad = clip.make_magnet_cap()
        fixed_caps = []
        moving_caps = []
        wallet_location = (clip.main_hinge_location(-90)*Pos(0, 0, 2*clip.PIVOT_Z)
                           * Rot(180, 0, 0)*clip.moving_body_location())
        for x, y in clip.MAGNET_CENTRES:
            local = clip.magnet_loading_location(True)*Pos(x, y, 0)*cap_cad
            fixed_caps.append(wallet_location*local)
            moving_caps.append(clip.main_hinge_location(-90)*local)
        # Opposing cap faces touch in the empty closed view. Tessellate the
        # two sets separately so those coincident faces are not welded.
        assembled_caps = trimesh.util.concatenate([
            mount(tessellate(Compound(children=fixed_caps), temporary, 'fixed_caps')),
            mount(tessellate(Compound(children=moving_caps), temporary, 'moving_caps'))])
        preview = trimesh.util.concatenate([merged, mechanism, closed_root,
                                            closed_closing, assembled_caps])
        preview.export(output / 'cascade_wallet_clip_closed_preview.stl')

        # Check original mechanism and sampled clip movement against the new
        # fixed body. Recess cutting is never permitted to fuse these parts.
        checks = {}
        fixed_caps_mesh = mount(tessellate(Compound(children=fixed_caps),
                                           temporary, 'cap_seat_check'))
        magnets_cad = []
        for x, y in clip.MAGNET_CENTRES:
            magnet = Pos(x, y, clip.MAGNET_INSTALL_Z)*Box(
                *clip.MAGNET_SIZE, clip.MAGNET_THICKNESS,
                align=(Align.CENTER, Align.CENTER, Align.MIN))
            magnets_cad.append(wallet_location*clip.magnet_loading_location(True)*magnet)
        magnets_mesh = mount(tessellate(Compound(children=magnets_cad),
                                        temporary, 'magnet_chamber_check'))
        for name, moving in [('original_card_mechanism', mechanism),
                             ('root_open', root), ('closing_open', closing),
                             ('root_closed', closed_root), ('closing_closed', closed_closing),
                             ('fixed_cap_seats', fixed_caps_mesh), ('magnet_chambers', magnets_mesh)]:
            overlap = (merged_solid ^ as_manifold(moving)).volume()
            checks[name] = float(overlap)
            if overlap > .02:
                raise ValueError(f'{name} overlaps the fixed wallet by {overlap:.4f} mm3')
        for degrees in (15, 30, 45, 60, 75):
            for name, shape in [('root', root_cad), ('closing', closing_cad)]:
                moving = mount(tessellate(clip.main_hinge_location(-degrees)*shape,
                                          temporary, f'{name}_{degrees}'))
                overlap = (merged_solid ^ as_manifold(moving)).volume()
                checks[f'{name}_{degrees}deg'] = float(overlap)
                if overlap > .02:
                    raise ValueError(f'{name} at {degrees} degrees overlaps the shell')
        cash_root, cash_closing, _ = clip.make_cash_configuration(15)
        for name, shape in [('root_cash_3mm', cash_root), ('closing_cash_3mm', cash_closing)]:
            moving = mount(tessellate(clip.main_hinge_location(-90)*shape,
                                      temporary, name))
            overlap = (merged_solid ^ as_manifold(moving)).volume()
            checks[name] = float(overlap)
            if overlap > .02:
                raise ValueError(f'{name} collides with the wallet')
        # Bound check protects card space; original wallet itself remains on
        # both sides of that space, so check newly added material only.
        added = as_mesh(merged_solid - shell_solid)
        if added.bounds[0, 1] < CARD_BACK_Y-.001:
            raise ValueError('Added clip material enters the original card cavity')
        removed = shell_solid - merged_solid
        removed_mesh = as_mesh(removed)
        removed_mesh.export(output / 'removed_wallet_wall_reference.stl')
        report = {
            'source_file': str(Path(wallet_path).name),
            'source_sha256': source_hash,
            'input_components': len(parts), 'print_components': len(pieces),
            'mount_side': '+Y, opposite the lever', 'card_cavity_back_y_mm': CARD_BACK_Y,
            'clip_money_face_y_mm': CLIP_FACE_Y,
            'fixed_plate_edge_blend_widths_mm': edge_blends,
            'full_height_cap_collar_mm': CAP_COLLAR_MARGIN,
            'fixed_face_protrusion_past_original_back_mm': CLIP_FACE_Y-shell.bounds[1, 1],
            'closed_protrusion_past_original_back_mm': preview.bounds[1, 1]-shell.bounds[1, 1],
            'closed_bounds_mm': preview.bounds.tolist(), 'print_bounds_mm': combined.bounds.tolist(),
            'wall_removed_mm3': removed.volume(), 'new_material_min_y_mm': added.bounds[0, 1],
            'intersection_checks_mm3': checks,
            'notes': ['Print the print STL, not the closed preview.',
                      'Card mechanism geometry is unchanged; full actuation is not physically tested.',
                      'Magnet seats and both clip hinges remain separate and accessible.'],
        }
        (output / 'merge_report.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2))
        return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wallet', type=Path,
                        default=Path(__file__).parent/'assets/cascade_card_wallet_v3_no_clip.stl')
    parser.add_argument('--output', type=Path, default=Path('output/wallet_merge'))
    parser.add_argument('--view', action='store_true',
                        help='Show the exported STL in VS Code OCP CAD Viewer (requires ocp-vscode)')
    parser.add_argument('--view-state', choices=('print', 'closed'), default='print',
                        help='Assembly to display with --view (default: print)')
    args = parser.parse_args(argv)
    build(args.wallet, args.output)
    if args.view:
        try:
            from ocp_vscode import show
        except ImportError:
            parser.exit(1, 'Exports saved. Viewing requires ocp-vscode and the VS Code '
                        'OCP CAD Viewer extension. Install the bridge with: '
                        'python -m pip install ocp-vscode\n')
        filename = ('cascade_wallet_clip_closed_preview.stl' if args.view_state == 'closed'
                    else 'cascade_wallet_with_clip_print.stl')
        # STL reference import preserves the exported mesh and avoids creating
        # an editable CAD face for every triangle of the wallet.
        reference = import_stl(args.output/filename)
        show(reference, names=[f'Cascade wallet + money clip — {args.view_state}'])


if __name__ == '__main__':
    main()
