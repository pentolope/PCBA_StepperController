"""The board's manifest, generated from the design source rather than typed.

The manifest is what the validator reads: which files are the design, which
gates are mandatory, what the connectors carry, what the stackup is. Every
one of those is already stated somewhere in this repository, and a manifest
typed by hand is a second copy of all of it that can drift from the first.
"""
from __future__ import annotations

import json
import os
import sys

from . import build, layout, netlist, orientation, simulation

MANIFEST_PATH = os.path.join(layout.REPO_ROOT, "board", "manifest.json")

RELEASE_PROFILE_ID = "jlcpcb-4layer-assembled"

MANDATORY_GATES = (
    "ARCH.CONTENTS",
    "ARCH.PROVENANCE",
    "BOM.NATIVE_PARITY",
    "CONTRACT.CONNECTOR",
    "CONTRACT.PLACEMENT",
    "CPL.NATIVE_PARITY",
    "DRC.AUTHORITATIVE",
    "DRC.CONSTRAINT_FLOOR",
    "DRC.NO_SUPPRESSED_RULES",
    "ERC.AUTHORITATIVE",
    "NET.TOPOLOGY",
    "PROV.REPORT_FRESHNESS",
    "ROUTE.GEOMETRY_HYGIENE",
    "ROUTE.PROVENANCE",
    "ROUTE.TINY_SEGMENTS",
    "SIM.MODEL_PROVENANCE",
    "SIM.SCENARIOS",
    "SIM.STAGE_COVERAGE",
    "STACK.GERBER_PARITY",
    "STACK.NATIVE_VS_MANIFEST",
    "VIA.ANNULUS_MASK_OVERLAP",
    "VIA.IN_PAD_CONTACT",
    "VIA.MASK_CLEARANCE_TARGET",
)

#: Gates that judge the design itself rather than the fabrication artifacts.
ACCEPTANCE_GATES = (
    "ERC.AUTHORITATIVE",
    "DRC.AUTHORITATIVE",
    "DRC.NO_SUPPRESSED_RULES",
    "DRC.CONSTRAINT_FLOOR",
    "NET.TOPOLOGY",
    "ROUTE.GEOMETRY_HYGIENE",
    "ROUTE.TINY_SEGMENTS",
    "ROUTE.PROVENANCE",
    "CONTRACT.PLACEMENT",
    "CONTRACT.CONNECTOR",
    "STACK.NATIVE_VS_MANIFEST",
    "VIA.ANNULUS_MASK_OVERLAP",
    "VIA.IN_PAD_CONTACT",
    "SIM.SCENARIOS",
    "SIM.STAGE_COVERAGE",
)

REQUIRED_EVIDENCE = (
    "evidence/index.json",
    "fab/selection.json",
    "generated/requirements.json",
    "generated/routing.json",
    "generated/thermal.json",
    "fab/physical_inputs.json",
)

CONNECTOR_PITCH_MM = {"J1": 5.08, "J2": 3.96, "J3": 2.54, "J4": 2.54,
                      "J5": 2.54}

CONNECTOR_ID = {"J1": "supply_input", "J2": "motor_output",
                "J3": "control_header", "J4": "debug_header",
                "J5": "configuration_header"}


def connector_contracts():
    pin_net = netlist.pin_to_net()
    contracts = []
    for reference in sorted(netlist.CONNECTOR_FUNCTION_NETS,
                            key=lambda name: int(name[1:])):
        pins = {}
        for pin_ref, net in pin_net.items():
            owner, _, number = pin_ref.partition(".")
            if owner == reference:
                pins[number] = net
        contracts.append({
            "id": CONNECTOR_ID[reference],
            "reference": reference,
            "required_positions": len(pins),
            "required_rows": 1,
            "required_pitch_mm": CONNECTOR_PITCH_MM[reference],
            "required_side": "front",
            "population": {"dnp": False, "exclude_from_bom": False},
            "pin_map": {number: pins[number]
                        for number in sorted(pins, key=int)},
        })
    return contracts


def placement_rules():
    """Groups the board must contain, counted rather than located."""
    return [
        {"id": "SENSE_RESISTORS", "reference_regex": r"^RS[12]$", "count": 2},
        {"id": "BULK_CAPACITORS",
         "reference_regex": r"^C(1|2|20|21)$",
         "count": len(netlist.BULK_REFERENCES)},
        {"id": "ESD_CLAMPS", "reference_regex": r"^D[2-9]$",
         "count": len(netlist.ESD_CLAMP_NETS)},
        {"id": "INDICATORS", "reference_regex": r"^D1[01]$", "count": 2},
        {"id": "PROBES", "reference_regex": r"^TP([1-9]|1[0-2])$",
         "count": 12},
        {"id": "MOUNTING", "reference_regex": r"^H[1-4]$", "count": 4},
    ]


def net_topology_rules():
    """The routes whose topology is a requirement rather than a result.

    A phase conductor carries the whole coil current, so it stays on the
    outer layers and takes at most the one layer change its escape needs. A
    sense conductor is generated rather than searched and takes none at all:
    a via in it would put the reference's own current between the resistor
    and the pin that measures it.
    """
    rules = []
    for function, pin in sorted(netlist.MOTOR_CONNECTOR_PINS.items(),
                                key=lambda item: item[1]):
        rules.append({
            "id": "PHASE_%s" % function,
            "net_regex": r"^PHASE_%s$" % function,
            "source_pad_regex": r"^U1\.%s$" % netlist.DRIVER_PINS[
                "O%s" % function],
            "load_pad_regex": r"^J2\.%d$" % pin,
            "max_vias_per_net": 1,
            "permitted_layers": ["F.Cu", "B.Cu"],
        })
    for phase in netlist.PHASES:
        rules.append({
            "id": "SENSE_%s" % phase,
            "net_regex": r"^SENSE_%s$" % phase,
            "source_pad_regex": r"^U1\.%s$" % netlist.DRIVER_PINS[
                "BR%s" % phase],
            "load_pad_regex": r"^%s\.1$" % netlist.SENSE_RESISTOR_REFERENCES[
                phase],
            "max_vias_per_net": 0,
            "permitted_layers": ["F.Cu"],
        })
    return rules


def stackup_expected():
    """What each copper layer is for, outer first."""
    expected = []
    for _, net in build.LAYER_ROLES:
        if net == "signal":
            expected.append({"role": "signal"})
        else:
            expected.append({"role": "plane", "plane_net": net})
    return expected


def simulation_stages():
    return simulation.stages()


def document():
    project = netlist.PROJECT_NAME
    classes = {entry["name"]: {key: value
                               for key, value in entry.items()
                               if key != "name"}
               for entry in build.NET_CLASSES}
    copper = ",".join(name for name, _ in build.LAYER_ROLES)
    return {
        "schema_version": 2,
        "board_id": project,
        "constraint_version": "layout-stage-2026-09-02",
        "project_root": "..",
        "tools": {"kicad_cli": "kicad-cli"},
        "sources": {
            "schematic": project + ".kicad_sch",
            "project": project + ".kicad_pro",
            "pcb": project + ".kicad_pcb",
        },
        "board_origin_mm": [0.0, 0.0],
        "documentation_globs": ["BRIEF.md"],
        "checks": {
            "erc": {"extra_flags": []},
            "drc": {
                "extra_flags": [],
                "forbidden_severities": ["ignore"],
                "permitted_ignored_rules": [],
                "constraint_floor": {
                    "rules": dict(build.DESIGN_RULES),
                    "net_classes": classes,
                },
            },
        },
        "waivers": [],
        "geometry_profile": {
            "version": "geom-1",
            "tolerances": {
                "waiver_location_mm": {"value": 0.001, "units": "mm"},
                "polygon_chord_error_mm": {"value": 0.001, "units": "mm"},
                "contact_mm": {"value": 1e-06, "units": "mm"},
                "coordinate_match_mm": {"value": 0.002, "units": "mm"},
                "rotation_match_deg": {"value": 0.1, "units": "deg"},
                "dimension_match_mm": {"value": 0.002, "units": "mm"},
                "clearance_match_mm": {"value": 0.01, "units": "mm"},
                "layer_symmetric_difference_mm2": {"value": 0.05,
                                                   "units": "mm2"},
            },
        },
        "stackup": {"expected": stackup_expected()},
        "placement_rules": placement_rules(),
        "net_topology": {"rules": net_topology_rules()},
        "routing": {
            "min_segment_mm": 0.1,
            "short_segment_justification": {"allow_pad_or_via_entry": True},
            "hygiene": {"forbid_duplicate_geometry": True,
                        "forbid_net_crossings": True,
                        "forbid_dangling": True},
            "provenance": "generated/routing.json",
            "acceptance_gates": list(ACCEPTANCE_GATES),
        },
        "via_mask": {
            "pad_contact": {"populated_pad_attributes": ["SMD"],
                            "require_paste": True},
            "metric": "annulus_to_opening_mm",
            "contact_semantics":
                "annulus_contacts counts zero-distance tangency as contact; "
                "annulus_strict_overlaps counts positive shared area only",
            "mask_dam_rule": "contact",
            "design_target_mm": 0.15,
        },
        "artifacts": {
            "gerber_dir": "generated/release/gerbers",
            "bom": "generated/release/bom.csv",
            "cpl": "generated/release/cpl.csv",
            "fabrication_manifest": "generated/release/fabrication.json",
            "validation_report": "generated/release/validation.json",
            "position_tolerance_mm": 0.01,
            "cpl_fields": {"designator": "Designator", "x": "Mid X",
                           "y": "Mid Y", "side": "Layer",
                           "rotation": "Rotation"},
            "cpl_origin": {"frame": "absolute page origin",
                           "offset_mm": [0.0, 0.0]},
            "gerber_export_flags": [
                "--layers",
                copper + ",F.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,"
                "Edge.Cuts",
                "--no-protel-ext", "--use-drill-file-origin",
                "--subtract-soldermask"],
            "reports_dir": "generated/release/reports",
        },
        "archive": {
            "zip": "generated/release/%s-fabrication.zip" % project,
            "allow": archive_allow(),
        },
        "assembly": {
            "schematic_fields": ["LCSC", "MPN", "Manufacturer"],
            "required_part_fields": ["LCSC"],
            "bom_fields": {"designators": "Designator", "value": "Comment",
                           "footprint": "Footprint", "quantity": "Quantity",
                           "LCSC": "LCSC Part #"},
            "schematic_export": {
                "fields": ["Reference", "Value", "Footprint", "${DNP}",
                           "${EXCLUDE_FROM_BOM}", "LCSC", "MPN",
                           "Manufacturer"],
                "labels": ["Reference", "Value", "Footprint", "DNP",
                           "ExcludeFromBOM", "LCSC", "MPN", "Manufacturer"],
                "flags": [],
                "reference_label": "Reference",
                "value_label": "Value",
                "footprint_label": "Footprint",
                "dnp_label": "DNP",
                "exclude_label": "ExcludeFromBOM",
                "true_tokens": ["1", "true", "yes", "x", "dnp"],
            },
            "compared_part_fields": ["LCSC", "MPN", "Manufacturer"],
        },
        "release_generation": {
            "lock_file_globs": ["*.lck", "~*.lck", ".#*", "*-lock",
                                "*.kicad_prl-lock"],
            "erc": {"output": "erc.json"},
            "drc": {"output": "drc.json"},
            "drill": {"flags": ["--format", "excellon",
                                "--excellon-separate-th", "--drill-origin",
                                "plot"]},
            "bom": {
                "output": "bom.csv",
                "fields": ["${QUANTITY}", "Reference", "Value", "Footprint",
                           "LCSC"],
                "labels": ["Quantity", "Designator", "Comment", "Footprint",
                           "LCSC Part #"],
                "group_by": ["Value", "Footprint", "LCSC"],
                "flags": ["--exclude-dnp", "--ref-range-delimiter", ""],
                "field_map": {"designators": "Designator", "value": "Comment",
                              "footprint": "Footprint",
                              "quantity": "Quantity",
                              "LCSC": "LCSC Part #"},
            },
            "cpl": {
                "output": "cpl.csv",
                "flags": ["--format", "csv", "--units", "mm", "--side",
                          "both", "--exclude-dnp"],
                "field_map": {"designator": "Ref", "x": "PosX", "y": "PosY",
                              "side": "Side", "rotation": "Rot"},
                "origin": {"frame": "absolute page origin",
                           "offset_mm": [0.0, 0.0]},
            },
            "archive": {"zip": "%s-fabrication.zip" % project},
            "fab_format": {
                "cpl": {
                    "columns": [
                        {"from": "Ref", "label": "Designator"},
                        {"from": "PosX", "label": "Mid X"},
                        {"from": "PosY", "label": "Mid Y"},
                        {"from": "Side", "label": "Layer",
                         "values": {"top": "Top", "bottom": "Bottom"}},
                        {"from": "Rot", "label": "Rotation"},
                    ],
                    "required_columns": ["Designator", "Mid X", "Mid Y",
                                         "Layer", "Rotation"],
                    "field_map": {"designator": "Designator",
                                  "rotation": "Rotation"},
                },
            },
            "cpl_orientation": orientation.specification(),
        },
        "reports": {
            "files": ["generated/release/reports/erc.json",
                      "generated/release/reports/drc.json"],
            "source_field": "source",
            "date_field": "date",
            "require_source_hash": True,
            "tolerance_seconds": 0,
            "source_closure": ["*.kicad_sch", "*.kicad_pcb", "*.kicad_pro",
                               "*.kicad_dru", "constraints/*.json",
                               "sim/*.json", "fab/*.json",
                               "components/*.json", "evidence/index.json",
                               "tools/jlc_orientation.py",
                               "fabrication/jlc_orientation/*.json",
                               "fabrication/jlc_orientation/raw/*.json"],
            "source_hash_field": "source_sha256",
            "closure_field": "source_closure_sha256",
        },
        "fixture": {"attributes_file": ".gitattributes"},
        "release_profile": {
            "id": RELEASE_PROFILE_ID,
            "mandatory_gates": list(MANDATORY_GATES),
            "required_evidence": list(REQUIRED_EVIDENCE),
        },
        "simulation": {
            "models": "sim/models.json",
            "extracted_models": {
                "physical_inputs": "fab/physical_inputs.json",
                "paths": simulation.extracted_paths(),
            },
            "stages": simulation_stages(),
            "required_stages": ["pre_layout", "post_layout"],
        },
        "connector_gender_tokens": {
            "receptacle": ["receptacle", "socket", "female"],
            "plug": ["plug", "header", "male"],
        },
        "connector_contracts": connector_contracts(),
    }


def archive_allow():
    """One entry per file the fabrication archive is allowed to carry."""
    functions = []
    total = len(build.LAYER_ROLES)
    for index, (name, _) in enumerate(build.LAYER_ROLES):
        if index == 0:
            where = "Top"
        elif index == total - 1:
            where = "Bot"
        else:
            where = "Inr"
        functions.append("Copper,L%d,%s" % (index + 1, where))
    functions.extend([
        "Soldermask,Top", "Soldermask,Bot", "Legend,Top", "Legend,Bot",
        "Paste,Top", "Profile,NP", "Drill/plated", "Drill/nonplated",
        "JobFile",
    ])
    allow = []
    for function in functions:
        allow.append({"file_function": function,
                      "require_payload": function != "Legend,Bot",
                      "min_count": 1})
    return allow


def write():
    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    return MANIFEST_PATH


if __name__ == "__main__":
    sys.stdout.write(write() + "\n")
