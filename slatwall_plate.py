"""Parametric slatwall adapter. All dimensions are millimetres.

Coordinates: X across wall, Y away from wall, Z up. The flat mating face
is Y=plate_thickness; hooks project into negative Y. Defaults use approximate user measurements of Knoll Dividend slatwall;
physical fit still needs a test print.
"""
from dataclasses import dataclass
from pathlib import Path
import argparse
from build123d import Align, Box, Cylinder, Plane, Polygon, Pos, BuildSketch, BuildLine, Polyline, Bezier, make_face, extrude, export_step, export_stl


@dataclass(frozen=True)
class PlateParameters:
    width: float = 80.0
    height: float = 70.0
    plate_thickness: float = 4.0
    slot_pitch: float = 36.5  # centre to centre of adjacent openings
    slot_height: float = 9.5
    lip_thickness: float = 1.5  # front-to-back thickness of wall lip
    slot_depth: float = 7.0  # available depth behind front wall face
    clearance: float = 0.5
    hook_width: float = 36.0
    hook_thickness: float = 2.4
    hook_drop: float = 4  # downward distance from upper opening centre
    snap_width: float = 16.0
    snap_thickness: float = 1.8
    snap_length: float = 28.0
    snap_engagement: float = 1.2  # above lower opening, into the lip above it
    snap_projection: float = 4.0
    release_gap: float = 1.0
    release_tab_length: float = 0.0  # extension below plate bottom (Z=0)
    release_grip_radius: float = 2.0  # rounded crossbar at tab tip
    bottom_lip_rise: float = 6.5  # lip above the opening, on the slat above
    top_lip_drop: float = 2  # lip below the opening, on the slat below

    @property
    def internal_gap(self):
        return self.slot_height + self.bottom_lip_rise + self.top_lip_drop

    @property
    def slat_face_height(self):
        return self.slot_pitch - self.slot_height

    def validate(self):
        for name, value in vars(self).items():
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if 2*self.release_grip_radius >= self.release_tab_length:
            raise ValueError("release grip must fit below the plate")
        if self.release_grip_radius >= 2*self.snap_thickness:
            raise ValueError("release grip must stay in front of the wall")
        margin = (self.height - self.slot_pitch) / 2
        if margin <= self.slot_height / 2 + self.snap_engagement:
            raise ValueError("height must leave room below the lower latch")
        if self.slot_pitch <= self.slot_height:
            raise ValueError("slot_pitch must exceed slot_height")
        if self.hook_drop + self.clearance >= self.slot_height/2 + self.top_lip_drop:
            raise ValueError("upper hook must fit within the internal gap")
        if self.snap_engagement + self.clearance >= self.bottom_lip_rise:
            raise ValueError("snap_engagement must fit behind the lip above the opening")
        if self.hook_drop <= self.slot_height / 2:
            raise ValueError("hook_drop must reach below the upper opening")
        if self.hook_thickness + 2 * self.clearance >= self.slot_height:
            raise ValueError("hook_thickness must fit through the opening")
        if max(self.hook_width, self.snap_width + 2*self.release_gap) >= self.width:
            raise ValueError("hook and snap window must fit inside plate width")
        if self.snap_thickness >= self.plate_thickness:
            raise ValueError("snap_thickness must be less than plate_thickness")
        if self.snap_projection <= self.lip_thickness + self.clearance:
            raise ValueError("snap must extend behind the lip")
        if max(self.snap_projection, self.lip_thickness + self.clearance + self.hook_thickness) >= self.slot_depth:
            raise ValueError("hooks must fit inside slot_depth")
        if self.snap_length <= self.slot_height or self.snap_length + 3 >= self.slot_pitch:
            raise ValueError("snap_length must fit between the openings")


def _box(width, depth, height, x=0, y=0, z=0):
    return Pos(x, y, z) * Box(width, depth, height,
                            align=(Align.CENTER, Align.MIN, Align.MIN))


def _profile(points, width):
    # In Plane.YZ the local horizontal axis is Y, vertical is Z.
    return Pos(-width/2, 0, 0) * extrude(
        Plane.YZ * Polygon(*points, align=None), amount=width, dir=(1, 0, 0))


def make_plate(p: PlateParameters = PlateParameters()):
    """Return one solid, ready for boolean union with an accessory.

    Keep the snap window clear when attaching another model. The snap bends
    toward +Y, so it also needs clearance in front of the tongue.
    """
    #p.validate()
    lower = (p.height - p.slot_pitch) / 2
    upper = lower + p.slot_pitch
    t = p.hook_thickness
    back = p.lip_thickness + p.clearance
    plate = _box(p.width, p.plate_thickness, p.height)
    # Upper downward return catches behind the lip below the upper opening.
    hook = _profile([(0, upper+t/2), (-back-t, upper+t/2),
                     (-back-t, upper-p.hook_drop),
                     (-back, upper-p.hook_drop), (-back, upper-t/2),
                     (0, upper-t/2)], p.hook_width)
    # Cut a full window and reconnect a thinner downward cantilever at its root.
    root = lower + p.snap_length
    bottom = lower - p.snap_thickness
    # Open the relief through the plate's bottom edge so the pull tab
    # cannot fuse to the plate or its bottom rail.
    window_bottom = -p.release_tab_length - p.release_gap
    window = _box(p.snap_width + 2*p.release_gap, p.plate_thickness+2,
                  root-window_bottom, y=-1, z=window_bottom)
    plate = plate - window
    tongue = _box(p.snap_width, p.snap_thickness,
                  root+1+p.release_tab_length, z=-p.release_tab_length)
    # Round crossbar provides a fingertip purchase, below the accessory.
    grip = Pos(0, p.snap_thickness+p.release_grip_radius/2,
               -p.release_tab_length+p.release_grip_radius) * Cylinder(
                   p.release_grip_radius, p.snap_width, rotation=(0, 90, 0))
    # Upward rounded detent: both curved shoulders cam over the lip.
    # The crown is behind the metal, with no downward retaining barb.
    peak = lower + p.snap_engagement
    crown_y = -(back + p.snap_projection)/2
    with BuildSketch(Plane.YZ) as detent:
        with BuildLine():
            Polyline((p.snap_thickness, bottom),
                     (-p.snap_projection, bottom))
            Bezier((-p.snap_projection, bottom),
                   (-p.snap_projection, peak),
                   ((-p.snap_projection+crown_y)/2, peak), (crown_y, peak))
            Bezier((crown_y, peak), (-back, peak),
                   (-back, lower), (0, lower))
            Polyline((0, lower), (p.snap_thickness, lower),
                     (p.snap_thickness, bottom))
        make_face()
    tooth = Pos(-p.snap_width/2, 0, 0) * extrude(
        detent.sketch, amount=p.snap_width, dir=(1, 0, 0))
    return plate + hook + tongue + tooth + grip


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('output'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    part = make_plate()
    export_step(part, args.output / 'slatwall_plate.step')
    export_stl(part, args.output / 'slatwall_plate.stl')
    print(f'Exported STEP and STL to {args.output}')


if __name__ == '__main__':
    main()
