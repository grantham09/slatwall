"""Parametric slatwall adapter. All dimensions are millimetres.

Coordinates: X across wall, Y away from wall, Z up. The flat mating face
is Y=plate_thickness; hooks project into negative Y. Parameters describe the part, not the wall.
Physical fit still needs a test print.
"""
from dataclasses import dataclass
from pathlib import Path
import argparse
from build123d import Align, Box, Cylinder, Plane, Polygon, Pos, BuildSketch, BuildLine, Polyline, Bezier, make_face, extrude, export_step, export_stl


@dataclass(frozen=True)
class PlateParameters:
    """Dimensions of the part itself, in mm; no wall profile is assumed."""
    width: float = 80.0
    height: float = 70.0
    plate_thickness: float = 4.0
    hook_spacing: float = 36.5  # clear Z gap between straight hook arms
    hook_width: float = 36.0
    hook_thickness: float = 2.4
    hook_drop: float = 4.0  # below underside of upper straight arm
    lip_thickness: float = 1.5  # clear Y gap behind plate to hook return
    snap_width: float = 16.0
    snap_thickness: float = 1.8
    snap_length: float = 28.0  # lower arm top to tongue root
    snap_peak: float = 1.2  # above top of lower straight arm
    release_gap: float = 1.0
    release_tab_length: float = 0.0  # below plate; zero leaves tab flush with plate bottom
    release_grip_radius: float = 2.0

    def validate(self):
        from math import isfinite
        for name, value in vars(self).items():
            if not isfinite(value) or value < 0 or (value == 0 and name != 'release_tab_length'):
                raise ValueError(f"{name} must be finite and " +
                                 ("nonnegative" if name == 'release_tab_length' else "positive"))
        if self.hook_spacing + self.hook_thickness + self.snap_thickness >= self.height:
            raise ValueError("height must contain both straight arms and hook_spacing")
        if self.hook_drop + self.snap_peak >= self.hook_spacing:
            raise ValueError("hook_drop and snap_peak must leave space between returns")
        if max(self.hook_width, self.snap_width + 2*self.release_gap) >= self.width:
            raise ValueError("hook and snap relief must fit inside plate width")
        if self.snap_thickness >= self.plate_thickness:
            raise ValueError("snap_thickness must be less than plate_thickness")
        if self.snap_length + 1 >= self.hook_spacing:
            raise ValueError("snap_length must leave room for its root below the top arm")
        if self.snap_peak >= self.snap_length:
            raise ValueError("snap_peak must stay below the tongue root")
        if self.release_grip_radius >= 2*self.snap_thickness:
            raise ValueError("release grip must stay in front of the plate back")
        lower = (self.height-self.hook_spacing-self.hook_thickness-self.snap_thickness)/2 + self.snap_thickness
        if 2*self.release_grip_radius >= lower+self.snap_length+self.release_tab_length:
            raise ValueError("release grip must stay below the tongue root")


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
    p.validate()
    # Centre the straight arms as a pair, excluding their returns.
    lower = (p.height-p.hook_spacing-p.hook_thickness-p.snap_thickness)/2 + p.snap_thickness
    upper = lower + p.hook_spacing + p.hook_thickness/2
    t = p.hook_thickness
    back = p.lip_thickness
    plate = _box(p.width, p.plate_thickness, p.height)
    # Upper downward return catches behind the lip below the upper opening.
    hook = _profile([(0, upper+t/2), (-back-t, upper+t/2),
                     (-back-t, upper-t/2-p.hook_drop),
                     (-back, upper-t/2-p.hook_drop), (-back, upper-t/2),
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
    # Always retain the finger grip, even when the tab ends at Z=0.
    # Its width stays within the tongue so it cannot bridge the side gaps.
    grip = Pos(0, p.snap_thickness+p.release_grip_radius/2,
               -p.release_tab_length+p.release_grip_radius) * Cylinder(
                   p.release_grip_radius, p.snap_width, rotation=(0, 90, 0))
    # Upward rounded detent: both curved shoulders cam over the lip.
    # The crown is behind the metal, with no downward retaining barb.
    peak = lower + p.snap_peak
    # Reuse hook_thickness for the curved catch depth; no slot-depth input.
    projection = back + p.hook_thickness
    crown_y = -(back + projection)/2
    with BuildSketch(Plane.YZ) as detent:
        with BuildLine():
            Polyline((p.snap_thickness, bottom),
                     (-projection, bottom))
            Bezier((-projection, bottom),
                   (-projection, peak),
                   ((-projection+crown_y)/2, peak), (crown_y, peak))
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
