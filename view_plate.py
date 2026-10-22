"""Run in VS Code with OCP CAD Viewer and ocp-vscode installed."""
from ocp_vscode import show
from slatwall_plate import PlateParameters, make_plate

# All dimensions describe the model itself, in millimetres.
parameters = PlateParameters(
    width=80.0,
    height=70.0,
    plate_thickness=4.0,
    hook_spacing=36.5,  # clear gap between straight arms, excluding returns
    hook_width=36.0,
    hook_thickness=2.4,
    hook_drop=4.0,
    lip_thickness=1.5,  # clear gap behind the plate; include your fit allowance
    snap_width=16.0,
    snap_thickness=1.8,
    snap_length=28.0,
    snap_peak=1.2,
    release_gap=1.0,
    release_tab_length=0.0,  # flush with plate bottom; grip remains present
    release_grip_radius=2.0,
)
plate = make_plate(parameters)
show(plate, names=["Mounting plate"])
