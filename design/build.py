from __future__ import annotations

import json
import os
import sys

from . import netlist, schematic

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

COPPER_LAYERS = 4

#: Copper layer roles, outer first. The reference plane sits directly under
#: the component layer: it is the driver's star point, the return path under
#: every signal routed above it, and the horizontal spread of the exposed
#: pad's heat. The motor rail is the second inner layer, so the chopper loop
#: closes between two adjacent planes rather than around the board.
LAYER_ROLES = (
    ("F.Cu", "signal"),
    ("In1.Cu", "GND"),
    ("In2.Cu", "VM"),
    ("B.Cu", "GND"),
)


def schematic_path():
    return os.path.join(REPO_ROOT, netlist.PROJECT_NAME + ".kicad_sch")


def project_path():
    return os.path.join(REPO_ROOT, netlist.PROJECT_NAME + ".kicad_pro")


def generate_schematic_text():
    netlist.pin_to_net()
    tree = schematic.build(
        netlist.PARTS, netlist.NETS, set(netlist.NO_CONNECT),
        netlist.PROJECT_NAME)
    return schematic.render(tree)


DESIGN_RULES = {
    "min_clearance": 0.15,
    "min_track_width": 0.15,
    "min_via_diameter": 0.45,
    "min_via_annular_width": 0.1,
    "min_through_hole_diameter": 0.25,
    "min_hole_clearance": 0.25,
    "min_hole_to_hole": 0.25,
    "min_copper_edge_clearance": 0.3,
}


#: One class. Every net on this board shares one clearance requirement: the
#: highest potential anywhere is the motor rail and there is no isolation
#: barrier. Conductor width for the phase current is a routing constraint and
#: belongs with the layout.
NET_CLASSES = [{
    "name": "Default",
    "clearance": 0.15,
    "track_width": 0.25,
    "via_diameter": 0.6,
    "via_drill": 0.3,
}]


def project_document(root_sheet_uuid):
    return {
        "board": {
            "design_settings": {
                "rule_severities": {
                    "missing_courtyard": "warning",
                    "track_not_centered_on_via": "warning",
                    "tuning_profile_track_geometries": "warning",
                    "footprint_filters_mismatch": "warning",
                    "footprint_type_mismatch": "warning",
                },
                "rules": dict(DESIGN_RULES),
            },
            "drc_exclusions": [],
            "layer_presets": [],
            "viewports": [],
        },
        "boards": [],
        "cvpcb": {"equivalence_files": []},
        "erc": {
            "erc_exclusions": [],
            "meta": {"version": 0},
            "pin_map": [],
            "rule_severities": {
                "single_global_label": "warning",
                "four_way_junction": "warning",
                "simulation_model_issue": "warning",
                "footprint_filter": "warning",
            },
        },
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": netlist.PROJECT_NAME + ".kicad_pro",
                 "version": 3},
        "net_settings": {"classes": [dict(entry) for entry in NET_CLASSES]},
        "pcbnew": {"last_paths": {}, "page_layout_descr_file": ""},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [[root_sheet_uuid, "Root"]],
        "text_variables": {},
    }


def write_project():
    root_uuid = str(schematic._uuid("sheet", netlist.PROJECT_NAME))
    with open(project_path(), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(project_document(root_uuid), handle, indent=2)
        handle.write("\n")
    return (project_path(),)


def write():
    text = generate_schematic_text()
    with open(schematic_path(), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return (schematic_path(),) + write_project()


if __name__ == "__main__":
    for path in write():
        sys.stdout.write(path + "\n")
