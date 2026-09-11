"""The reviewed library-zero registry, built from the frozen evidence.

Every placement angle a release ships is the board's own angle plus a
correction that belongs to the part number rather than to the board: where the
assembly library's zero orientation differs from the footprint's, every
instance is fitted turned by the difference.

The corrections are not written here. They are derived from the library
responses frozen in fabrication/jlc_orientation by the toolkit deriver this
board pins by digest, and this module only assembles what that derivation
produced into the registry the manifest carries - refusing any part whose
evidence did not decide an offset, because an entry with a number nothing
established is exactly what a registry is supposed to make impossible.

The derivation runs again during validation, from the same committed files and
the same pinned bytes, and the gate fails if it disagrees with what the
manifest records. So the manifest block is a cache of a computation, not a
table of opinions, and it is regenerated rather than edited.
"""
from __future__ import annotations

import json
import os
import sys

from . import netlist, rules

sys.path.insert(0, rules.TOOLKIT_ROOT)

from pcbqa import derivers  # noqa: E402

REPO_ROOT = rules.REPO_ROOT
FIXTURE_DIR = os.path.join(REPO_ROOT, "fabrication", "jlc_orientation")
BOARD_PATH = os.path.join(REPO_ROOT, "stepper_controller.kicad_pcb")

PART_NUMBER_FIELD = "LCSC"

#: The scoring algorithm, pinned to the bytes that produced this registry.
#: The digest is the pin: the gate refuses to run anything else, so an
#: edited or replaced deriver cannot silently re-score the evidence, and
#: a new version is adopted here deliberately or not at all.
DERIVER_ID = "jlc-pad-pairing-v1"
DERIVER_SHA256 = \
    "58c93007981ad5e0522f2b3a1d29f20caf36c2720757ebc6c76d11bf91bb1a57"

#: What this registry's review status is allowed to mean: a script
#: re-deriving each offset from the frozen response on every release,
#: not a person comparing parts by eye.
REVIEW_BASIS = "evidence_rederivation"


def _deriver():
    return derivers.load(DERIVER_ID, DERIVER_SHA256)


def _package_name(tool, lcsc):
    """The library's own name for the package, from the frozen response."""
    with open(tool.raw_path(FIXTURE_DIR, lcsc), "rb") as handle:
        document = json.loads(handle.read().decode("utf-8"))
    head = document["result"]["packageDetail"]["dataStr"]["head"]
    return head.get("c_para", {}).get("package", "")


def _mpn_by_part_number():
    return {part["lcsc"]: part["mpn"]
            for part in netlist.PARTS.values() if part.get("lcsc")}


def _relative(path):
    return os.path.relpath(path, REPO_ROOT).replace("\\", "/")


def registry():
    """One row per part number, or a refusal naming what is not established."""
    tool = _deriver()
    derived = tool.derive(PART_NUMBER_FIELD, BOARD_PATH, FIXTURE_DIR)
    mpn = _mpn_by_part_number()
    rows, refused = [], []
    for lcsc, record in sorted(derived.items()):
        if record.get("error"):
            refused.append({"lcsc": lcsc, "issue": record["error"]})
            continue
        if record.get("evidence_problems"):
            refused.append({"lcsc": lcsc,
                            "issue": "the frozen evidence does not check out",
                            "problems": record["evidence_problems"]})
            continue
        if not record.get("decisive"):
            refused.append({
                "lcsc": lcsc,
                "issue": "the evidence does not decide an offset",
                "best_worst_deg": record.get("best_worst_deg"),
                "margin_deg": record.get("margin_deg")})
            continue
        rows.append({
            "lcsc": lcsc,
            "mpn": mpn.get(lcsc, ""),
            "package": _package_name(tool, lcsc),
            "kicad_footprint": record["kicad_footprint"],
            "offset_deg": record["best_offset_deg"],
            "review_status": "reviewed",
            "review_basis": REVIEW_BASIS,
            "evidence_file": _relative(tool.extract_path(FIXTURE_DIR, lcsc)),
            "raw_file": _relative(tool.raw_path(FIXTURE_DIR, lcsc)),
            "evidence_sha256": record["evidence_sha256"],
            "x_pairing": record["pairing"],
            "x_worst_pad_disagreement_deg": record["best_worst_deg"],
            "x_margin_over_runner_up_deg": record["margin_deg"],
            "x_references": record["references"],
        })
    return rows, refused


def specification():
    rows, refused = registry()
    if refused:
        raise ValueError(
            "the orientation evidence does not establish an offset for %d "
            "part number(s): %s"
            % (len(refused), json.dumps(refused, indent=2)))
    return {
        "deriver": {"id": DERIVER_ID, "sha256": DERIVER_SHA256},
        "part_number_field": PART_NUMBER_FIELD,
        "normalize_range_deg": [0, 360],
        "angle_decimals": 4,
        "evidence": {
            "fixtures": "fabrication/jlc_orientation/*.json",
            "note": "the raw library response and a normalised extract of it "
                    "are both committed; the extract is re-derived from the "
                    "body whenever it is read, and the offsets are scored "
                    "from the body rather than from the extract",
        },
        "reproduction_inputs": {
            "required_globs": [
                "fabrication/jlc_orientation/*.json",
                "fabrication/jlc_orientation/raw/*.json",
            ],
        },
        "registry": rows,
    }


if __name__ == "__main__":
    rows, refused = registry()
    for row in rows:
        sys.stdout.write("%-10s %-24s %-46s %5.0f deg  %s\n" % (
            row["lcsc"], row["mpn"][:24], row["kicad_footprint"][:46],
            row["offset_deg"], row["x_pairing"]))
    for entry in refused:
        sys.stdout.write("REFUSED %s\n" % json.dumps(entry))
