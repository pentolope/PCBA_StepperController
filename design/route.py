"""Routing: the search draws ordinary connectivity, nothing else.

Four nets are withheld from it. The reference and the motor rail are planes
with a via at every surface pad, and which plane a pad joins is a property of
its net rather than of a search. The two sense conductors are withheld
because their topology is the requirement: each runs from one bridge return
to its own resistor and shares copper with nothing.

The search is also confined to the outer layers, so the two inner planes stay
unbroken under everything it draws.

A candidate is judged, not trusted: it is adopted, the board is measured, and
if it does not come back clean the placed board is restored so no failing
copper stays in the tree.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys

import pcbnew

from . import build, layout, netlist

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tooling", "PCBA_AutoDesignAndTest"))

from pcbqa import routing_record  # noqa: E402

REPO_ROOT = layout.REPO_ROOT
CANDIDATE_ROOT = os.path.join(REPO_ROOT, "candidates")
CANDIDATE_NAME = "route-current"
PROVENANCE_PATH = os.path.join(REPO_ROOT, "generated", "routing.json")

#: Nets the search may not draw, and the copper that already carries them.
RESERVED_NETS = tuple(layout.PLANE_NETS) + tuple(
    "SENSE_%s" % phase for phase in netlist.PHASES) + tuple(
    "PHASE_%s" % function for function in sorted(
        netlist.MOTOR_CONNECTOR_PINS))

#: Layers the search may use. The two inner layers are reference and rail;
#: a signal routed through either would be a hole in the plane that every
#: conductor above it returns through.
ROUTING_LAYERS = ("F.Cu", "B.Cu")




def routed_nets():
    return tuple(sorted(name for name in netlist.NETS
                        if name not in RESERVED_NETS))


#: The router is given a wider clearance than the rule the board is judged by.
#: It takes the figure from the project's Default net class, and its diagonal
#: segments then land short of it, so the candidate is routed against a
#: project carrying this margin and judged against the authoritative one,
#: which `_adopt` restores.
ROUTER_CLEARANCE_MM = 0.30

#: The clearances a candidate may be searched at, widest first. Each is a
#: preference above the rule the board is judged by, not a relaxation of it:
#: whichever one produced a candidate, that candidate is judged against the
#: board's own constraints, which `_adopt` restores.
ATTEMPT_CLEARANCES_MM = (0.30, 0.25, 0.20)

#: The search grid. A pad row at 0.65 mm pitch leaves each escape a lane
#: only as wide as the pad, and a grid that cannot put a track on the pad's
#: own centre line loses the lane to the neighbours' clearance.
ROUTER_GRID_STEP_MM = 0.05

ROUTER_OPTIONS = (
    ("--track-width", str(layout.TRACK_WIDTH_MM),
     "--via-size", str(layout.VIA_DIAMETER_MM),
     "--via-drill", str(layout.VIA_DRILL_MM),
     "--board-edge-clearance", "0.45",
     "--hole-to-hole-clearance", "0.3",
     "--same-net-pad-clearance", "0.3",
     "--grid-step", str(ROUTER_GRID_STEP_MM),
     "--no-power-tap-neckdown",
     "--layers") + ROUTING_LAYERS)

# The router is deterministic for a fixed input, so a bare retry explores
# nothing. Each attempt varies the net-ordering strategy instead, which is
# what actually produces a different candidate.
#: The search is repeated over the same orderings because the router is not
#: deterministic: the same board and the same ordering can come back with a
#: different set of vias, and a candidate carrying one sub-clearance item is
#: rejected rather than patched. Each repeat is a distinct candidate, and
#: every one of them is recorded whether it was accepted or not.
ROUTER_ENVIRONMENT = {"KICAD_RIP_PREEXISTING": "0"}
ATTEMPT_ORDERINGS = ("inside_out", "original", "mps", "bus")

#: The search is deterministic for a fixed input, so every attempt has to
#: differ in something the search reads.
ATTEMPT_PLANS = tuple({"ordering": ordering, "clearance_mm": clearance}
                      for clearance in ATTEMPT_CLEARANCES_MM
                      for ordering in ATTEMPT_ORDERINGS)
MAX_ATTEMPTS = len(ATTEMPT_PLANS)

#: A track end is pulled onto a via's centre only when it already stands on
#: that via's own copper. A larger reach would move copper the clearance
#: check has already accepted; this one cannot, because the destination is
#: inside the annulus the end is already touching.
SNAP_WITHIN_VIA = True
#: The shortest track fragment the board accepts away from a pad or a via.
#: A router turning a diagonal lands it as a staircase of pieces far below
#: this; each one is a manufacturing risk rather than a connection, so the
#: pieces are collapsed into their neighbours.
MIN_SEGMENT_MM = 0.1
TOUCH_TOLERANCE_MM = 0.01


def _krt():
    from pcbqa import krt
    return krt


def digest(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _summary(text):
    for line in text.splitlines():
        if line.strip().startswith("JSON_SUMMARY_MIN:"):
            return json.loads(line.split("JSON_SUMMARY_MIN:", 1)[1])
    return {}


def _write_routing_project(path, clearance_mm=ROUTER_CLEARANCE_MM):
    """The project the router sees: the design's, with the clearance margin."""
    document = build.project_document(
        str(build.schematic._uuid("sheet", netlist.PROJECT_NAME)))
    document["board"]["design_settings"]["rules"]["min_clearance"] = \
        clearance_mm
    for entry in document["net_settings"]["classes"]:
        if entry["name"] == "Default":
            entry["clearance"] = clearance_mm
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, indent=2)
        handle.write("\n")
    return path


#: The router carries its own fab-capability floor and is free to escalate
#: below the nominal clearance to fit tight geometry, recording the tighter
#: value so the board is graded against it. This board is graded against its
#: own declared constraints instead, so the router is given those constraints
#: as its floor: copper it emits is then legal by the same rule the checker
#: applies, rather than legal only against a floor the router lowered.
def _write_fab_floor(path):
    floors = (("clearance", build.DESIGN_RULES["min_clearance"]),
              ("track_width", build.DESIGN_RULES["min_track_width"]),
              ("via_diameter", layout.VIA_DIAMETER_MM),
              ("via_drill", layout.VIA_DRILL_MM),
              ("hole_to_hole", build.DESIGN_RULES["min_hole_to_hole"]),
              ("board_edge", build.DESIGN_RULES["min_copper_edge_clearance"]))
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("# generated from the board's declared constraints\n")
        for key, value in floors:
            handle.write("%s = %s\n" % (key, value))
    return path


def _router_environment():
    """The search may not adopt copper this repository placed.

    Its pre-existing-rip candidacy would otherwise take a short conductor
    off the base obstacle map and route another net through it, and the
    reserved copper is reinstated afterwards on top of whatever went there.
    """
    environment = dict(os.environ)
    environment.update(ROUTER_ENVIRONMENT)
    return environment


def _route_once(resolved, candidate, attempt, placed_pcb):
    stage_dir = os.path.join(candidate, "attempt-%02d" % attempt)
    os.makedirs(stage_dir, exist_ok=True)
    source_pcb = os.path.join(stage_dir, "source.kicad_pcb")
    shutil.copy(placed_pcb, source_pcb)
    routed_pcb = os.path.join(stage_dir, "routed.kicad_pcb")
    plan = ATTEMPT_PLANS[attempt - 1]
    _write_routing_project(os.path.join(stage_dir, "source.kicad_pro"),
                           plan["clearance_mm"])
    floor = _write_fab_floor(os.path.join(stage_dir, "fab-floor.txt"))
    command = [sys.executable,
               os.path.join(resolved["path"], "py_router", "route.py"),
               source_pcb, "--output", routed_pcb, "--nets"] \
        + list(routed_nets()) + list(ROUTER_OPTIONS) \
        + ["--fab-overrides", floor,
           "--ordering", plan["ordering"],
           "--clearance", str(plan["clearance_mm"])]
    completed = subprocess.run(command, capture_output=True, text=True,
                               env=_router_environment())
    summary = _summary(completed.stdout)
    if completed.returncode != 0:
        raise RuntimeError("routing failed: rc=%s summary=%s stderr=%s"
                           % (completed.returncode, summary,
                              completed.stderr[-2000:]))
    tidied_pcb = os.path.join(stage_dir, "tidied.kicad_pcb")
    shutil.copy(routed_pcb, tidied_pcb)
    transform = tidy(tidied_pcb, source_pcb, stage_dir)
    return {
        "attempt": attempt,
        "source_sha256": digest(source_pcb),
        "accepted": False,
        "stages": [
            {"stage": "routed", "produced_by": "router",
             "sha256": digest(routed_pcb)},
            {"stage": "tidied", "produced_by": "transform",
             "sha256": digest(tidied_pcb),
             "transform": "snap a track end standing on a same-net via "
                          "onto that via's centre; "
                          "pull a track end that stopped inside a same-net "
                          "pad's outline onto that pad's anchor; "
                          "drop tracks the snap collapsed to a point; "
                          "restore the declared width on any track and the "
                          "declared size on any via the search narrowed "
                          "below them; prune dangling track ends, "
                          "keeping any removal only while connectivity is "
                          "unchanged; refill the zones so the pours are "
                          "knocked out around the copper the router added",
             "effects": transform,
             "parameters": {"snap_within_via_annulus": SNAP_WITHIN_VIA,
                            "touch_tolerance_mm": TOUCH_TOLERANCE_MM}},
        ],
        "context": {"router_summary": summary,
                    "ordering": plan["ordering"],
                    "clearance_mm": plan["clearance_mm"]},
        "board": tidied_pcb,
    }


def measure(path):
    """What the board says about itself: violations, and what is still open."""
    report = os.path.join(CANDIDATE_ROOT, CANDIDATE_NAME, "adopted-drc.json")
    os.makedirs(os.path.dirname(report), exist_ok=True)
    completed = subprocess.run(
        ["kicad-cli", "pcb", "drc", "--output", report, "--format", "json",
         "--severity-error", "--severity-warning", path],
        capture_output=True, text=True)
    if completed.returncode != 0 and not os.path.isfile(report):
        raise RuntimeError("DRC did not run: " + completed.stderr[-2000:])
    with open(report, encoding="utf-8") as handle:
        document = json.load(handle)
    counted = document.get("violations") or []
    return {
        "errors": sum(1 for entry in counted
                      if entry.get("severity") == "error"),
        "warnings": sum(1 for entry in counted
                        if entry.get("severity") != "error"),
        "unconnected": len(document.get("unconnected_items") or []),
        "schematic_parity": len(document.get("schematic_parity") or []),
    }


def _accepts(metrics):
    """What a candidate has to be before it replaces the board in the tree.

    Everything the board's own severities call a finding, because the gate
    that judges the routed board counts warnings too: a candidate that leaves
    one is a candidate the release would reject.
    """
    return (metrics["errors"] == 0 and metrics["warnings"] == 0
            and metrics["unconnected"] == 0
            and metrics["schematic_parity"] == 0)


def _write_record(placed_pcb, attempts, accepted, krt, resolved):
    record = {
        "kind": routing_record.KIND,
        "source_sha256": digest(placed_pcb),
        "attempts": attempts,
        "accepted_attempt": accepted["attempt"] if accepted else None,
        "adopted_sha256": (digest(layout.BOARD_PATH) if accepted else None),
        "context": {
            "router": krt.provenance(resolved["path"], sys.executable),
            "resolution": resolved,
            "routed_nets": list(routed_nets()),
            "reserved_nets": list(RESERVED_NETS),
            "options": list(ROUTER_OPTIONS),
            "environment": dict(ROUTER_ENVIRONMENT),
            "acceptance": "a candidate is adopted only when a fresh DRC over "
                          "the adopted board reports no violation, nothing "
                          "unconnected and no disagreement with the "
                          "schematic",
            "reproducibility": "the router is not bit-reproducible; "
                               "candidates are generated until one is "
                               "accepted and every attempt is recorded here",
        },
    }
    routing_record.validate(record)
    os.makedirs(os.path.dirname(PROVENANCE_PATH), exist_ok=True)
    with open(PROVENANCE_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
    return record


def _adopt(candidate_board):
    """Install a candidate, then rewrite everything derived from the board.

    The router writes its own project file beside the candidate - loosening a
    track width, pinning an edge clearance, silencing severities - so the
    authoritative project is regenerated from the design source rather than
    inherited from whatever the search left behind.
    """
    shutil.copy(candidate_board, layout.BOARD_PATH)
    build.write_project()


def run():
    krt = _krt()
    resolved = krt.resolve()
    candidate = os.path.join(CANDIDATE_ROOT, CANDIDATE_NAME)
    shutil.rmtree(candidate, ignore_errors=True)
    os.makedirs(candidate, exist_ok=True)
    layout.write()
    placed_pcb = os.path.join(candidate, "placed.kicad_pcb")
    shutil.copy(layout.BOARD_PATH, placed_pcb)

    attempts = []
    accepted = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = _route_once(resolved, candidate, attempt, placed_pcb)
        entry = {key: value for key, value in result.items() if key != "board"}
        _adopt(result["board"])
        metrics = measure(layout.BOARD_PATH)
        entry["context"]["adopted_metrics"] = metrics
        entry["accepted"] = _accepts(metrics)
        _write_record(placed_pcb, attempts + [entry],
                      entry if entry["accepted"] else None, krt, resolved)
        attempts.append(entry)
        if entry["accepted"]:
            accepted = entry
            break

    if accepted is None:
        _adopt(placed_pcb)
        _write_record(placed_pcb, attempts, None, krt, resolved)
        raise RuntimeError(
            "no routing candidate was accepted in %d attempts; the placed, "
            "unrouted board has been restored so no failing copper stays in "
            "the tree" % MAX_ATTEMPTS)
    return layout.BOARD_PATH, PROVENANCE_PATH


def _net_copper(board, net_code, copper=None):
    tracks = [item for item in (board.GetTracks() if copper is None
                                else copper)
              if item.GetNetCode() == net_code]
    pads = [pad for footprint in board.GetFootprints()
            for pad in footprint.Pads() if pad.GetNetCode() == net_code]
    return tracks, pads


def _via_touches(via, item, epsilon):
    centre = via.GetPosition()
    radius = via.GetWidth(pcbnew.F_Cu) / 2.0
    if item.Type() == pcbnew.PCB_VIA_T:
        other = item.GetPosition()
        return math.hypot(centre.x - other.x,
                          centre.y - other.y) <= radius + epsilon
    if not item.IsOnLayer(pcbnew.F_Cu) and not item.IsOnLayer(pcbnew.B_Cu):
        return False
    for point in _endpoints(item):
        if math.hypot(point.x - centre.x, point.y - centre.y) <= radius:
            return True
    return item.HitTest(centre, int(epsilon))


def _tracks_touch(one, other, epsilon):
    if one.GetLayer() != other.GetLayer():
        return False
    for point in _endpoints(one):
        if other.HitTest(point, int(epsilon)):
            return True
    for point in _endpoints(other):
        if one.HitTest(point, int(epsilon)):
            return True
    return False


def _pad_touches(pad, item, epsilon):
    if item.Type() == pcbnew.PCB_VIA_T:
        return pad.HitTest(item.GetPosition(), int(epsilon))
    if not pad.IsOnLayer(item.GetLayer()):
        return False
    return any(pad.HitTest(point, 0) for point in _endpoints(item))


def net_islands(board, net_code, epsilon, skip=None, copper=None):
    """Connected groups of one net's copper, counted over pads only.

    KiCad's own connectivity object is not used here: repeated rebuilds in
    one process eventually hand back an untyped wrapper, and a prune
    decision must not depend on a binding artefact.
    """
    tracks, pads = _net_copper(board, net_code, copper)
    if skip is not None:
        tracks = [item for item in tracks
                  if item.m_Uuid.AsString() != skip]
    items = tracks + pads
    parent = list(range(len(items)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left, right):
        left, right = find(left), find(right)
        if left != right:
            parent[right] = left

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            one, other = items[i], items[j]
            one_pad = i >= len(tracks)
            other_pad = j >= len(tracks)
            if one_pad and other_pad:
                continue
            if one_pad:
                touching = _pad_touches(one, other, epsilon)
            elif other_pad:
                touching = _pad_touches(other, one, epsilon)
            elif one.Type() == pcbnew.PCB_VIA_T:
                touching = _via_touches(one, other, epsilon)
            elif other.Type() == pcbnew.PCB_VIA_T:
                touching = _via_touches(other, one, epsilon)
            else:
                touching = _tracks_touch(one, other, epsilon)
            if touching:
                union(i, j)
    groups = set()
    for index in range(len(tracks), len(items)):
        groups.add(find(index))
    return len(groups)


def _endpoints(track):
    return (track.GetStart(), track.GetEnd())


def _supported(point, track, board, vias, tracks, epsilon):
    for via in vias:
        if via.GetNetCode() != track.GetNetCode():
            continue
        if not via.IsOnLayer(track.GetLayer()):
            continue
        centre = via.GetPosition()
        if math.hypot(point.x - centre.x, point.y - centre.y) <= epsilon:
            return True
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.GetNetCode() != track.GetNetCode():
                continue
            # A pad only holds a track end up on a layer it is actually on:
            # an SMD pad on the far side is not a connection, and treating it
            # as one used to leave the end dangling for the checker to find.
            if not pad.IsOnLayer(track.GetLayer()):
                continue
            if pad.HitTest(point, 0):
                return True
    for other in tracks:
        if other.m_Uuid.AsString() == track.m_Uuid.AsString():
            continue
        if other.GetNetCode() != track.GetNetCode():
            continue
        if other.Type() == pcbnew.PCB_VIA_T:
            continue
        if other.GetLayer() != track.GetLayer():
            continue
        if other.HitTest(point, int(epsilon)):
            return True
    return False


def _entry_geometry(track, board, vias):
    """True when an end of the track sits on a via or in a pad: copper that
    short is how a route enters one, not a route in its own right."""
    for point in _endpoints(track):
        for via in vias:
            centre = via.GetPosition()
            if math.hypot(point.x - centre.x, point.y - centre.y) \
                    <= via.GetWidth(pcbnew.F_Cu) / 2:
                return True
        for footprint in board.GetFootprints():
            for pad in footprint.Pads():
                if pad.IsOnLayer(track.GetLayer()) and pad.HitTest(point, 0):
                    return True
    return False


def _absorption(fragment, board, vias, tracks, epsilon):
    """The one neighbour a fragment can be folded into, or None.

    A fold is only offered where exactly one same-net track on the same layer
    meets the fragment at that end and no via or pad stands there, so a
    junction and a terminal are both left alone."""
    for point, other in ((fragment.GetStart(), fragment.GetEnd()),
                         (fragment.GetEnd(), fragment.GetStart())):
        for via in vias:
            centre = via.GetPosition()
            if math.hypot(point.x - centre.x, point.y - centre.y) <= epsilon:
                break
        else:
            touching = []
            for candidate in tracks:
                if candidate.m_Uuid.AsString() == fragment.m_Uuid.AsString():
                    continue
                if candidate.GetNetCode() != fragment.GetNetCode():
                    continue
                if candidate.GetLayer() != fragment.GetLayer():
                    continue
                for get, set_ in ((candidate.GetStart, candidate.SetStart),
                                  (candidate.GetEnd, candidate.SetEnd)):
                    end = get()
                    if math.hypot(end.x - point.x, end.y - point.y) <= epsilon:
                        touching.append((candidate, set_, end))
            if len(touching) == 1:
                candidate, set_, end = touching[0]
                return (fragment, candidate, set_, end, other)
    return None


def _generated(track, board):
    """Copper this repository drew rather than the search."""
    del board
    return track.GetNetname() in RESERVED_NETS


def _top_level_blocks(text, keyword):
    """Every top-level `(keyword ...)` block in a board file, as text.

    A board file is edited here as text rather than through the bindings:
    removing and re-adding objects through them leaves the interpreter
    handing back untyped wrappers, and the copper being replaced is copper
    this repository generated, so its exact text is what belongs.
    """
    blocks = []
    needle = "\n\t(%s\n" % keyword
    index = text.find(needle)
    while index != -1:
        depth = 0
        cursor = index + 1
        while True:
            character = text[cursor]
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    break
            elif character == '"':
                cursor += 1
                while text[cursor] != '"':
                    cursor += 2 if text[cursor] == "\\" else 1
            cursor += 1
        blocks.append((index + 1, cursor + 1))
        index = text.find(needle, cursor)
    return blocks


def _block_net(body):
    marker = body.rfind('(net "')
    if marker == -1:
        return None
    return body[marker + 6:body.index('"', marker + 6)]


def restore_generated(routed_path, source_path):
    """Put every reserved net's copper back exactly as the source drew it.

    The router completes nets outside its own selection during its final
    pass, and the reserved nets' topology is a requirement rather than a
    result, so whatever it drew on them is discarded and the source copper
    reinstated.
    """
    with open(routed_path, encoding="utf-8") as handle:
        routed = handle.read()
    with open(source_path, encoding="utf-8") as handle:
        source = handle.read()
    cuts = []
    for keyword in ("segment", "via"):
        for start, end in _top_level_blocks(routed, keyword):
            if _block_net(routed[start:end]) in RESERVED_NETS:
                cuts.append((start, end))
    kept = []
    previous = 0
    for start, end in sorted(cuts):
        kept.append(routed[previous:start])
        previous = end
    kept.append(routed[previous:])
    trimmed = "".join(kept)

    additions = []
    for keyword in ("segment", "via"):
        for start, end in _top_level_blocks(source, keyword):
            body = source[start:end]
            if _block_net(body) not in RESERVED_NETS:
                continue
            additions.append(body)

    closing = trimmed.rindex(")")
    rebuilt = (trimmed[:closing] + "\t"
               + "\n\t".join(additions) + "\n" + trimmed[closing:])
    with open(routed_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(rebuilt)
    return {"reserved_removed": len(cuts),
            "reserved_restored": len(additions)}


TIDY_PHASES = ("snap", "pad_snap", "collapse", "absorb", "widen", "resize",
               "prune", "fill")
TIDY_CHECKPOINT = 20
TIDY_RESTART_LIMIT = 60


class Degraded(RuntimeError):
    """The bindings stopped answering for the objects already in hand."""


def _degraded(exc):
    return (isinstance(exc, (TypeError, AttributeError))
            and "SwigPyObject" in str(exc))


def _uuid(track):
    return track.m_Uuid.AsString()


class _Copper:
    """The board's track list, read once and owned here.

    Asking the board for it again after enough proxies have come and gone
    hands back an untyped wrapper, which is a fact about the bindings and
    not about this board.
    """

    def __init__(self, board):
        self.board = board
        self.items = list(board.GetTracks())
        self.retired = []

    def vias(self):
        return [item for item in self.items
                if item.Type() == pcbnew.PCB_VIA_T]

    def tracks(self):
        return [item for item in self.items
                if item.Type() != pcbnew.PCB_VIA_T]

    def discard(self, track):
        # The uuid is read first: a removed track's own fields stop
        # answering the moment the board lets go of it. The wrapper is then
        # kept, and kept disowned, because collecting one the board has let
        # go of takes the bindings' type table down with it.
        uuid = _uuid(track)
        track.thisown = False
        self.retired.append(track)
        self.board.Remove(track)
        for index, item in enumerate(self.items):
            if item is track:
                del self.items[index]
                break
        return uuid


def _phase_snap(copper, epsilon, state, save):
    """A track end standing on a same-net via is pulled to that via."""
    snapped = 0
    pending = 0
    for _ in range(4):
        vias = copper.vias()
        moved = 0
        for track in copper.tracks():
            if _generated(track, copper.board):
                continue
            for get, set_ in ((track.GetStart, track.SetStart),
                              (track.GetEnd, track.SetEnd)):
                point = get()
                for via in vias:
                    if via.GetNetCode() != track.GetNetCode():
                        continue
                    centre = via.GetPosition()
                    distance = math.hypot(point.x - centre.x,
                                          point.y - centre.y)
                    if epsilon < distance <= via.GetWidth(pcbnew.F_Cu) / 2:
                        set_(centre)
                        moved += 1
                        pending += 1
                        break
            if pending >= TIDY_CHECKPOINT:
                save()
                pending = 0
        snapped += moved
        if not moved:
            break
    return {"endpoints_snapped": snapped}


def _phase_pad_snap(copper, epsilon, state, save):
    """A track end inside a same-net pad's outline is pulled to its anchor.

    An end that stops inside the outline but outside the shape the pad
    presents - the cut corner of a rounded rectangle - reads as connected to
    the board's connectivity and as a bare end to anything that asks what
    copper touches it. The anchor is the one point on a pad every reader
    agrees is on it.
    """
    board = copper.board
    pad_snapped = 0
    pending = 0
    for track in copper.tracks():
        if _generated(track, board):
            continue
        vias = copper.vias()
        tracks = copper.tracks()
        for get, set_ in ((track.GetStart, track.SetStart),
                          (track.GetEnd, track.SetEnd)):
            point = get()
            if _supported(point, track, board, vias, tracks, epsilon):
                continue
            for footprint in board.GetFootprints():
                for pad in footprint.Pads():
                    if pad.GetNetCode() != track.GetNetCode():
                        continue
                    if not pad.IsOnLayer(track.GetLayer()):
                        continue
                    if not pad.GetBoundingBox().Contains(point):
                        continue
                    set_(pad.GetPosition())
                    pad_snapped += 1
                    pending += 1
                    break
                else:
                    continue
                break
        if pending >= TIDY_CHECKPOINT:
            save()
            pending = 0
    return {"endpoints_snapped_to_pads": pad_snapped}


def _phase_collapse(copper, epsilon, state, save):
    """Snapping can leave a track whose two ends became the same point.

    It connects nothing, and DRC reports it crossing whatever it lies on, so
    it goes before anything else is judged - and before the pruning pass,
    which can decide to keep a track and then never look at it again.
    """
    collapsed = 0
    while True:
        degenerate = next((track for track in copper.tracks()
                           if track.GetLength() == 0), None)
        if degenerate is None:
            break
        copper.discard(degenerate)
        collapsed += 1
        if collapsed % TIDY_CHECKPOINT == 0:
            save()
    if collapsed:
        save()
    return {"collapsed_tracks_removed": collapsed}


def _phase_absorb(copper, epsilon, state, save):
    """The router cuts a corner with a chamfer a few tens of microns long.

    Copper that short is below anything the fab resolves and reads as a
    fragment rather than as a route, so each one is folded into the
    neighbour it meets - and only where a single neighbour meets it away
    from any pad or via, so a junction is never collapsed, and only while
    connectivity is unchanged.
    """
    board = copper.board
    keep_short = set(state.get("keep_short", ()))
    absorbed = 0
    while True:
        vias = copper.vias()
        tracks = copper.tracks()
        move = None
        for track in tracks:
            if _uuid(track) in keep_short:
                continue
            if _generated(track, board):
                continue
            if track.GetLength() >= pcbnew.FromMM(MIN_SEGMENT_MM):
                continue
            if _entry_geometry(track, board, vias):
                continue
            move = _absorption(track, board, vias, tracks, epsilon)
            if move is not None:
                break
            keep_short.add(_uuid(track))
        state["keep_short"] = sorted(keep_short)
        if move is None:
            break
        fragment, neighbour, setter, previous, target = move
        del neighbour
        uuid = _uuid(fragment)
        net_code = fragment.GetNetCode()
        baseline = net_islands(board, net_code, epsilon, copper=copper.items)
        setter(target)
        # The fold is judged before the board is changed: a track the board
        # has already let go of cannot be put back.
        if net_islands(board, net_code, epsilon, skip=uuid,
                       copper=copper.items) > baseline:
            setter(previous)
            keep_short.add(uuid)
            state["keep_short"] = sorted(keep_short)
            continue
        copper.discard(fragment)
        absorbed += 1
        save()
    return {"fragments_absorbed": absorbed}


def _phase_widen(copper, epsilon, state, save):
    """The search falls back to a 5 mil track where the width will not fit.

    That is below the floor this board declares, so it is brought up to the
    floor - not to the net class's width, which is a preference rather than
    a limit, and widening to it would move copper the clearance check has
    already accepted.
    """
    floor = pcbnew.FromMM(build.DESIGN_RULES["min_track_width"])
    widened = 0
    for track in copper.tracks():
        if track.GetWidth() >= floor:
            continue
        track.SetWidth(floor)
        widened += 1
    if widened:
        save()
    return {"narrow_tracks_widened": widened}


def _phase_resize(copper, epsilon, state, save):
    """Every via the search added is the board's own via.

    The router narrows one where it cannot fit the declared size, which
    produces a hole the declared fabrication process does not offer; the
    declared size is restored, and if that no longer fits, the clearance
    check that runs next is what says so.
    """
    wide = pcbnew.FromMM(layout.VIA_DIAMETER_MM)
    drill = pcbnew.FromMM(layout.VIA_DRILL_MM)
    resized = 0
    for item in copper.vias():
        if item.GetWidth(pcbnew.F_Cu) >= wide and item.GetDrill() >= drill:
            continue
        item.SetWidth(pcbnew.F_Cu, wide)
        item.SetDrill(drill)
        resized += 1
    if resized:
        save()
    return {"undersized_vias_restored": resized}


def _phase_prune(copper, epsilon, state, save):
    """Prune what the router left unattached.

    A track whose removal would break the net is kept and skipped rather
    than ending the pass, because one such track used to hide every dangling
    end behind it.
    """
    board = copper.board
    keep = set(state.get("keep", ()))
    removed = 0
    while True:
        vias = copper.vias()
        tracks = copper.tracks()
        victim = None
        for track in tracks:
            if _uuid(track) in keep:
                continue
            if _generated(track, board):
                continue
            if all(_supported(point, track, board, vias, tracks, epsilon)
                   for point in _endpoints(track)):
                continue
            victim = track
            break
        if victim is None:
            break
        uuid = _uuid(victim)
        net_code = victim.GetNetCode()
        baseline = net_islands(board, net_code, epsilon, copper=copper.items)
        if net_islands(board, net_code, epsilon, skip=uuid,
                       copper=copper.items) > baseline:
            keep.add(uuid)
            state["keep"] = sorted(keep)
            continue
        copper.discard(victim)
        removed += 1
        save()
    return {"dangling_tracks_removed": removed}


def _phase_fill(copper, epsilon, state, save):
    """The router adds copper the pours were not knocked out around."""
    layout.fill_zones(copper.board)
    save()
    return {"zones_refilled": len(list(copper.board.Zones()))}


TIDY_HANDLERS = {
    "snap": _phase_snap,
    "pad_snap": _phase_pad_snap,
    "collapse": _phase_collapse,
    "absorb": _phase_absorb,
    "widen": _phase_widen,
    "resize": _phase_resize,
    "prune": _phase_prune,
    "fill": _phase_fill,
}


def run_tidy_phase(path, phase, state):
    """One phase of the transform, in a process that has not run one before.

    Every phase is idempotent, and the ones that remove copper save after
    each removal, so a phase the bindings cut short is resumed from the
    board on disk rather than restarted from the router's output.
    """
    board = pcbnew.LoadBoard(path)
    copper = _Copper(board)

    def save():
        pcbnew.SaveBoard(path, board)

    try:
        effects = TIDY_HANDLERS[phase](
            copper, pcbnew.FromMM(TOUCH_TOLERANCE_MM), state, save)
    except Exception as exc:  # noqa: BLE001 - re-raised unless it is the one
        if not _degraded(exc):
            raise
        return {"effects": {}, "state": state, "complete": False}
    save()
    return {"effects": effects, "state": state, "complete": True}


def tidy(path, source_path, workdir):
    effects = dict(restore_generated(path, source_path))
    state = {}
    state_path = os.path.join(workdir, "transform-state.json")
    result_path = os.path.join(workdir, "transform-phase.json")
    for phase in TIDY_PHASES:
        for _ in range(TIDY_RESTART_LIMIT):
            with open(state_path, "w", encoding="utf-8",
                      newline="\n") as handle:
                json.dump(state, handle, indent=2, sort_keys=True)
            completed = subprocess.run(
                [sys.executable, "-m", "design.tidy", path, phase,
                 state_path, result_path],
                cwd=REPO_ROOT, capture_output=True, text=True)
            if completed.returncode != 0:
                raise RuntimeError("transform phase %s failed: rc=%s stderr=%s"
                                   % (phase, completed.returncode,
                                      (completed.stderr or "")[-2000:]))
            with open(result_path, encoding="utf-8") as handle:
                outcome = json.load(handle)
            for key, value in outcome["effects"].items():
                effects[key] = effects.get(key, 0) + value
            state = outcome["state"]
            if outcome["complete"]:
                break
        else:
            raise RuntimeError("transform phase %s never ran to completion"
                               % phase)
    return effects


if __name__ == "__main__":
    for path in run():
        sys.stdout.write(path + "\n")
