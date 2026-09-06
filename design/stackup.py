"""The board's physical stackup, from the catalogue it was selected under.

KiCad's board file carries no (stackup ...) block for this project, so the
materials come from the same place the fabrication selection came from: the
approved catalogue entry `fab/selection.json` names, pinned by its own
digest. Every number here is quoted from that catalogue rather than typed,
and the permittivity is the lowest the catalogue states for the material,
which is the bound every impedance on this board is argued against.
"""
from __future__ import annotations

import json
import os
import sys

from . import build, geometry

REPO_ROOT = geometry.rules.REPO_ROOT

DOCUMENT_PATH = os.path.join(REPO_ROOT, "generated", "stackup.json")

#: Catalogue copper layer labels, outer first, against this board's own
#: copper layer names. The order is the catalogue's; the names are KiCad's.
COPPER_LAYER_NAMES = tuple(name for name, _ in build.LAYER_ROLES)


def _selection():
    with open(geometry.SELECTION_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _permittivity(materials, entry):
    """The lowest permittivity the catalogue states for this dielectric."""
    values = [record["dk"] for record in materials.values()
              if record.get("kind") == entry["form"]
              and record.get("name") == entry.get("material", entry["form"])]
    if not values:
        raise RuntimeError("the catalog states no permittivity for %s %s"
                           % (entry["form"], entry.get("material")))
    return min(values)


def document():
    selection = _selection()
    approved = geometry._approved()
    normalized = approved["normalized"]
    catalog = normalized["stackups"][selection["stackup"]]
    materials = normalized["materials"]

    layers, copper_index = [], 0
    for index, entry in enumerate(catalog["layers"]):
        if entry["role"] == "copper":
            layers.append({
                "name": COPPER_LAYER_NAMES[copper_index],
                "kind": "copper",
                "thickness_mm": entry["thickness_mm"],
                "source": "stackups.%s.layers[%d]" % (selection["stackup"],
                                                      index)})
            copper_index += 1
            continue
        material = entry.get("material", entry["form"])
        described = entry["form"] if material == entry["form"] \
            else "%s %s" % (entry["form"], material)
        layers.append({
            "name": "%s %s-%s" % (described,
                                  COPPER_LAYER_NAMES[copper_index - 1],
                                  COPPER_LAYER_NAMES[copper_index]),
            "kind": "dielectric",
            "type": entry["form"],
            "material": material,
            "thickness_mm": entry["thickness_mm"],
            "epsilon_r": _permittivity(materials, entry),
            "source": "stackups.%s.layers[%d]" % (selection["stackup"],
                                                  index)})
    if copper_index != len(COPPER_LAYER_NAMES):
        raise RuntimeError(
            "the catalog stackup has %d copper layers and this board has %d"
            % (copper_index, len(COPPER_LAYER_NAMES)))
    return {
        "schema": 1,
        "stackup": selection["stackup"],
        "layers": layers,
        "provenance": {
            "source": "JLCPCB approved catalogue",
            "catalog_normalized_sha256": approved["normalized_sha256"],
            "selected_by": "fab/selection.json",
            "permittivity_basis": "the lowest dk the catalogue states for "
                                  "the material, so every impedance derived "
                                  "from it is an upper bound",
        },
    }


def write(path=None):
    target = path or os.environ.get("PCBQA_OUT") or DOCUMENT_PATH
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    text = json.dumps(document(), indent=2, sort_keys=True) + "\n"
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return target


if __name__ == "__main__":
    sys.stdout.write(write() + "\n")
