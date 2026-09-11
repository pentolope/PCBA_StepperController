"""What the assembly process is, and what each part requires of it.

The board is built by one reflow pass over its top side; every part on
it is judged against that pass. The requirements are not written here:
they are read from `components/parameters.json`, where each figure
carries the frozen datasheet it came from, exactly like every other
device figure this board relies on. A part whose `assembly` block is
empty is one whose datasheet was read and states no soldering
condition - which is a different statement from a part nobody looked
at, and the toolkit refuses the second.

Through-hole connectors are fitted after the oven, so they are declared
hand-soldered and carry no reflow tolerance: the profile never reaches
them. Which footprints are not parts at all - the mounting holes and
the test pads - is declared by library identity rather than inferred
from KiCad's exclusion flags, which do not mean "not a part".
"""
from __future__ import annotations

import json
import sys

from . import libraries, netlist, rules

PART_NUMBER_FIELD = "LCSC"

#: The build this board declares: one pass, lead-free, top side only,
#: no wash. Everything placed is judged against it.
REFLOW_PASSES = 1
REFLOW_PEAK_C = 250.0
POPULATED_SIDES = ("top",)
CLEANING = "no_clean"

#: Part numbers whose bodies are through-hole. They are fitted after
#: the reflow pass, so the oven's peak is not a requirement on them.
HAND_FITTED = ("C160317", "C2932698", "C2932699", "C474952")

#: Placed footprints that are not parts: nothing buys them, they carry
#: no datasheet, and there is no process requirement to check.
FURNITURE_LIB_IDS = ("Mechanical:MountingHole", "Connector:TestPoint")

#: The parameter figures this board reads as process requirements, and
#: the toolkit field each one answers.
FIGURE_FIELDS = (("peak_solder_temp_max_c", "peak_temp_max_c", float),
                 ("reflow_passes_max", "max_reflow_passes", int))


def _placed():
    return {reference: part for reference, part in netlist.PARTS.items()
            if part.get("on_board")}


def census():
    """{part number: [references]} for everything placed and bought."""
    grouped = {}
    for reference, part in sorted(_placed().items()):
        if part.get("lcsc"):
            grouped.setdefault(part["lcsc"], []).append(reference)
    return grouped


def furniture():
    """{reference: {}} for every placed footprint that is not a part."""
    return {reference: {} for reference, part in sorted(_placed().items())
            if part["lib_id"] in FURNITURE_LIB_IDS}


def _mpn_by_part_number():
    return {part["lcsc"]: part["mpn"] for part in _placed().values()
            if part.get("lcsc")}


def records(parameters=None):
    """One process-requirements record per part number on the board."""
    parameters = parameters or rules.load_parameters()
    mpn = _mpn_by_part_number()
    out = {}
    for number in sorted(census()):
        stated = parameters["parts"][mpn[number]]["assembly"]
        record = {}
        for figure, field, kind in FIGURE_FIELDS:
            if figure in stated:
                record[field] = kind(stated[figure]["value"])
        if number in HAND_FITTED:
            # The reflow peak is not a requirement on a part the reflow
            # pass never reaches; what the part requires is to be kept
            # out of it, and that is what the record says.
            record.pop("peak_temp_max_c", None)
            record["process"] = "hand_solder_only"
        out[number] = record
    return out


def hand_soldered():
    """Every reference fitted by hand, from the part numbers that are."""
    grouped = census()
    return sorted(reference for number in HAND_FITTED
                  for reference in grouped[number])


def specification(parameters=None):
    return {
        "part_number_field": PART_NUMBER_FIELD,
        "process": {
            "reflow_passes": REFLOW_PASSES,
            "peak_temp_c": REFLOW_PEAK_C,
            "sides": list(POPULATED_SIDES),
            "cleaning": CLEANING,
            "hand_solder": hand_soldered(),
        },
        "parts": records(parameters),
        "furniture": furniture(),
        "paste": {
            "pads": [{"reference": "U1",
                      "pad": netlist.DRIVER_PINS["EPAD"],
                      "coverage": [libraries.MIN_PASTE_COVERAGE, 1.0]}],
        },
    }


if __name__ == "__main__":
    sys.stdout.write(json.dumps(specification(), indent=2,
                                sort_keys=True) + "\n")
