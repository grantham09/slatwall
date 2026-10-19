"""Run in VS Code with OCP CAD Viewer and ocp-vscode installed."""
from ocp_vscode import show
from slatwall_plate import PlateParameters, make_plate

# Edit these parameters, then run this file in OCP CAD Viewer.
parameters = PlateParameters()
plate = make_plate(parameters)
show(plate, names=["Slatwall mounting plate"])
