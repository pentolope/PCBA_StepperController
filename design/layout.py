"""The board: outline, placement, planes and silkscreen, from the source.

Board coordinates run x right and y UP from the lower-left corner, which is
the frame every dimension here is stated in. KiCad's own y runs down, so the
mapping is applied once, in `to_board`.

The arrangement follows the current. Field wiring enters on the left edge,
the bulk sits along the bottom, and the motor leaves through a connector
directly above the bridge outputs, so the phase conductors are the shortest
structures on the board. The driver sits between them with its exposed pad
on the reference plane, its supply pins taken straight down to the rail
plane, and one sense resistor immediately outside each bridge return.
"""
from __future__ import annotations

import json
import math
import os
import sys

from . import ksym, netlist

_TOOLKIT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tooling", "PCBA_AutoDesignAndTest")
if _TOOLKIT not in sys.path:
    sys.path.insert(0, _TOOLKIT)

from pcbqa import headless  # noqa: E402

headless.suppress_blocking_ui()

import pcbnew  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD_PATH = os.path.join(REPO_ROOT, netlist.PROJECT_NAME + ".kicad_pcb")
PLACEMENT_PATH = os.path.join(REPO_ROOT, "constraints", "placement.json")

FOOTPRINT_SEARCH_PATHS = (
    os.path.join(REPO_ROOT, "library"),
    "/usr/share/kicad/footprints",
)

ORIGIN_MM = (30.0, 110.0)

BOARD_W_MM = 80.0
BOARD_H_MM = 65.0

EDGE_WIDTH_MM = 0.1
TRACK_WIDTH_MM = 0.25
SENSE_TRACK_WIDTH_MM = 1.2
#: The driver's reference pins reach the pad under the device between their
#: neighbours, so this is narrower than anything a search would draw.
DRIVER_GROUND_TRACK_MM = 0.2
CLEARANCE_MM = 0.15
EDGE_CLEARANCE_MM = 0.3
VIA_DIAMETER_MM = 0.6
VIA_DRILL_MM = 0.3
ZONE_INSET_MM = 0.5
STITCH_TRACK_WIDTH_MM = 0.4
STITCH_GAP_MM = 0.35

MOUNTING_HOLES_MM = {
    "H1": (3.5, 3.5),
    "H2": (76.5, 3.5),
    "H3": (3.5, 61.5),
    "H4": (76.5, 61.5),
}

#: Parts a placement search may not move, and why.
#:
#: The connectors and the fasteners are the board's mechanical contract. The
#: test points are its service contract. The driver's position is what the
#: exposed pad's connections are generated from, and the two sense resistors
#: are the pair whose position IS the topology they create.
LOCKED_REFERENCES = tuple(sorted(
    [reference for reference in netlist.PARTS
     if reference[0] in ("J", "H") and reference[1:].isdigit()]
    + [reference for reference in netlist.PARTS
       if reference.startswith("TP")]
    + ["U1"] + list(netlist.SENSE_RESISTOR_REFERENCES.values())))

PLACEMENT = {
    # the input: terminal on the left edge, then the reverse-blocking
    # device, its gate divider and the clamp
    "J1": (7.0, 25.0, 90.0),
    "Q1": (20.0, 25.0, 0.0),
    "R1": (18.0, 31.0, 0.0),
    "R2": (22.0, 31.0, 0.0),
    "D1": (26.0, 24.0, 90.0),
    "TP1": (26.0, 30.5, 0.0),
    "TP9": (30.0, 30.5, 0.0),

    # the bulk row along the bottom, feeding the rail plane
    "C1": (14.0, 9.0, 0.0),
    "C2": (28.0, 9.0, 0.0),
    "C20": (42.0, 9.0, 0.0),
    "C21": (56.0, 9.0, 0.0),

    # the driver, its decoupling, its charge pump and its sense resistors
    "U1": (46.0, 24.0, 0.0),
    "RS2": (36.0, 27.575, 180.0),
    "RS1": (56.0, 27.575, 0.0),
    "C5": (32.0, 24.2, 0.0),
    "C6": (60.0, 24.5, 0.0),
    "C3": (32.0, 17.5, 0.0),
    "C4": (60.0, 21.0, 0.0),
    "C7": (36.5, 24.2, 0.0),
    "C8": (32.0, 21.0, 0.0),
    "C9": (36.5, 21.5, 180.0),
    "C10": (56.0, 24.0, 0.0),
    "C11": (56.0, 21.0, 0.0),
    "TP7": (54.5375, 30.5, 0.0),
    "TP8": (37.4625, 30.5, 0.0),
    "TP10": (34.0, 33.0, 0.0),
    "TP13": (54.5375, 33.5, 0.0),

    # the motor connector, directly above the bridge outputs
    "J2": (57.88, 40.0, 180.0),

    # the logic regulator
    "U3": (66.0, 20.0, 0.0),
    "L1": (72.0, 25.0, 0.0),
    "C12": (66.0, 15.0, 0.0),
    "C13": (71.0, 15.0, 0.0),
    "C14": (66.0, 25.0, 0.0),
    "C15": (66.0, 29.0, 0.0),
    "C16": (70.0, 29.0, 0.0),
    "R3": (76.0, 20.0, 90.0),
    "R4": (76.0, 16.0, 90.0),
    "R5": (61.0, 29.0, 0.0),
    "R6": (61.0, 32.0, 0.0),
    "TP2": (76.0, 25.0, 0.0),
    "TP11": (76.0, 29.0, 0.0),

    # the controller and everything referenced to the logic rail
    "U2": (30.0, 46.0, 0.0),
    "C17": (20.0, 42.0, 0.0),
    "C18": (20.0, 45.0, 0.0),
    "C19": (20.0, 48.0, 0.0),
    "R7": (14.0, 42.0, 0.0),
    "R8": (14.0, 45.0, 0.0),
    "R13": (14.0, 48.0, 0.0),
    "R9": (40.0, 45.0, 0.0),
    "R10": (40.0, 48.0, 0.0),
    "R11": (40.0, 51.0, 0.0),
    "R12": (44.0, 51.0, 0.0),
    "TP3": (10.0, 37.0, 0.0),
    "TP4": (17.0, 37.0, 0.0),
    "TP5": (24.0, 37.0, 0.0),
    "TP6": (31.0, 37.0, 0.0),
    "TP12": (10.0, 41.0, 0.0),

    # the indicators
    "D10": (9.0, 60.0, 0.0),
    "R20": (13.0, 60.0, 0.0),
    "D11": (9.0, 57.0, 0.0),
    "R21": (13.0, 57.0, 0.0),

    # the headers along the top edge, each conductor's series element and
    # clamp between the header and what it reaches
    "R16": (20.0, 60.0, 0.0),
    "R17": (24.0, 60.0, 0.0),
    "R14": (28.0, 60.0, 0.0),
    "R15": (32.0, 60.0, 0.0),
    "R18": (36.0, 60.0, 0.0),
    "R19": (40.0, 60.0, 0.0),
    "R22": (44.0, 60.0, 0.0),
    "D2": (20.0, 57.0, 0.0),
    "D3": (24.0, 57.0, 0.0),
    "D4": (28.0, 57.0, 0.0),
    "D5": (32.0, 57.0, 0.0),
    "D6": (36.0, 57.0, 0.0),
    "D7": (40.0, 57.0, 0.0),
    "D8": (44.0, 57.0, 0.0),
    "D9": (48.0, 57.0, 0.0),
    "J4": (55.0, 61.0, 0.0),
    "J3": (62.0, 61.0, 0.0),
    "J5": (69.0, 61.0, 0.0),
}


def to_board(x_mm, y_mm):
    return (ORIGIN_MM[0] + x_mm, ORIGIN_MM[1] - y_mm)


def _point(x_mm, y_mm):
    bx, by = to_board(x_mm, y_mm)
    return pcbnew.VECTOR2I(pcbnew.FromMM(bx), pcbnew.FromMM(by))


def accepted_placement():
    if not os.path.isfile(PLACEMENT_PATH):
        return {}
    with open(PLACEMENT_PATH, encoding="utf-8") as handle:
        document = json.load(handle)
    return {reference: tuple(pose)
            for reference, pose in document["placement"].items()
            if reference not in LOCKED_REFERENCES}


def seed_placement():
    placed = dict(PLACEMENT)
    for reference, (x, y) in MOUNTING_HOLES_MM.items():
        placed[reference] = (x, y, 0.0)
    return placed


def fixed_placements():
    placed = seed_placement()
    for reference, pose in accepted_placement().items():
        if reference not in placed:
            raise KeyError("accepted placement names an unknown part: "
                           + reference)
        placed[reference] = pose
    missing = sorted(reference for reference, part in netlist.PARTS.items()
                     if part["footprint"] and reference not in placed)
    if missing:
        raise KeyError("no placement for " + ", ".join(missing))
    return placed


def _footprint_dir(footprint):
    library, _, name = footprint.partition(":")
    for base in FOOTPRINT_SEARCH_PATHS:
        candidate = os.path.join(base, library + ".pretty")
        if os.path.isfile(os.path.join(candidate, name + ".kicad_mod")):
            return candidate, name
    raise FileNotFoundError(footprint)


_PIN_NAMES = {}


def _pin_name(lib_id, number):
    if lib_id not in _PIN_NAMES:
        library = ksym.Library(netlist.SYMBOL_LIBRARY_PATHS)
        _PIN_NAMES[lib_id] = {
            key: pins[0].name for key, pins in library.pins(lib_id).items()}
    return _PIN_NAMES[lib_id].get(number, "")


def _floating_net(board, reference, number):
    lib_id = netlist.PARTS[reference]["lib_id"]
    name = "unconnected-(%s-%s-Pad%s)" % (
        reference, _pin_name(lib_id, number).replace("/", "{slash}"), number)
    existing = board.GetNetInfo().GetNetItem(name)
    if existing is not None and existing.GetNetCode() != 0:
        return existing
    net = pcbnew.NETINFO_ITEM(board, name)
    board.Add(net)
    return net


def _load(board, reference, part, x, y, rotation, pin_net, nets):
    library_dir, name = _footprint_dir(part["footprint"])
    footprint = pcbnew.FootprintLoad(library_dir, name)
    if footprint is None:
        raise RuntimeError("could not load " + part["footprint"])
    library = part["footprint"].partition(":")[0]
    footprint.SetFPID(pcbnew.LIB_ID(library, name))
    footprint.SetPosition(_point(x, y))
    footprint.SetOrientationDegrees(rotation)
    footprint.SetReference(reference)
    footprint.SetValue(part["value"])
    footprint.Reference().SetLayer(pcbnew.F_Fab)
    footprint.Value().SetLayer(pcbnew.F_Fab)
    for key, value in (("MPN", part["mpn"]), ("LCSC", part["lcsc"]),
                       ("Manufacturer", part["manufacturer"])):
        if not value:
            continue
        footprint.SetField(key, value)
        for field in footprint.GetFields():
            if field.GetName() == key:
                field.SetLayer(pcbnew.F_Fab)
                field.SetVisible(False)
    if not part["in_bom"]:
        footprint.SetExcludedFromBOM(True)
    if reference in LOCKED_REFERENCES:
        footprint.SetLocked(True)
    for pad in footprint.Pads():
        number = pad.GetNumber()
        if not number:
            continue
        net_name = pin_net.get("%s.%s" % (reference, number))
        if net_name:
            pad.SetNet(nets[net_name])
        else:
            pad.SetNet(_floating_net(board, reference, number))
    board.Add(footprint)
    return footprint


def _nets(board):
    created = {}
    for name in sorted(netlist.NETS):
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
        created[name] = net
    return created


def _design_settings(board):
    from . import build
    board.SetCopperLayerCount(build.COPPER_LAYERS)
    settings = board.GetDesignSettings()
    settings.m_TrackMinWidth = pcbnew.FromMM(
        build.DESIGN_RULES["min_track_width"])
    settings.m_ViasMinSize = pcbnew.FromMM(
        build.DESIGN_RULES["min_via_diameter"])
    settings.m_MinThroughDrill = pcbnew.FromMM(
        build.DESIGN_RULES["min_through_hole_diameter"])
    settings.m_CopperEdgeClearance = pcbnew.FromMM(EDGE_CLEARANCE_MM)
    settings.m_HoleClearance = pcbnew.FromMM(
        build.DESIGN_RULES["min_hole_clearance"])
    settings.m_HoleToHoleMin = pcbnew.FromMM(
        build.DESIGN_RULES["min_hole_to_hole"])
    settings.m_ViasMinAnnularWidth = pcbnew.FromMM(
        build.DESIGN_RULES["min_via_annular_width"])
    settings.m_MinClearance = pcbnew.FromMM(CLEARANCE_MM)
    default_class = settings.m_NetSettings.GetDefaultNetclass()
    default_class.SetClearance(pcbnew.FromMM(CLEARANCE_MM))
    default_class.SetTrackWidth(pcbnew.FromMM(TRACK_WIDTH_MM))
    default_class.SetViaDiameter(pcbnew.FromMM(VIA_DIAMETER_MM))
    default_class.SetViaDrill(pcbnew.FromMM(VIA_DRILL_MM))


#: Nets carried by a plane rather than by a conductor a search draws.
PLANE_NETS = ("GND", "VM")


def copper_layers():
    from . import build
    lookup = {"F.Cu": pcbnew.F_Cu, "In1.Cu": pcbnew.In1_Cu,
              "In2.Cu": pcbnew.In2_Cu, "B.Cu": pcbnew.B_Cu}
    return [(lookup[name], net) for name, net in build.LAYER_ROLES]


def _add_outline(board):
    corners = [(0.0, 0.0), (BOARD_W_MM, 0.0), (BOARD_W_MM, BOARD_H_MM),
               (0.0, BOARD_H_MM)]
    closed = corners + [corners[0]]
    for start, end in zip(closed, closed[1:]):
        shape = pcbnew.PCB_SHAPE(board)
        shape.SetShape(pcbnew.SHAPE_T_SEGMENT)
        shape.SetStart(_point(*start))
        shape.SetEnd(_point(*end))
        shape.SetLayer(pcbnew.Edge_Cuts)
        shape.SetWidth(pcbnew.FromMM(EDGE_WIDTH_MM))
        board.Add(shape)


def _rectangle(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _pour(board, net, corners, layers, priority=0):
    zone = pcbnew.ZONE(board)
    layer_set = pcbnew.LSET()
    for layer in layers:
        layer_set.addLayer(layer)
    zone.SetLayerSet(layer_set)
    outline = zone.Outline()
    outline.NewOutline()
    for x, y in corners:
        bx, by = to_board(x, y)
        outline.Append(pcbnew.FromMM(bx), pcbnew.FromMM(by))
    zone.SetNet(net)
    zone.SetAssignedPriority(priority)
    zone.SetLocalClearance(pcbnew.FromMM(CLEARANCE_MM))
    zone.SetMinThickness(pcbnew.FromMM(0.2))
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    zone.SetThermalReliefGap(pcbnew.FromMM(0.3))
    zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.4))
    board.Add(zone)
    return zone


def _add_pours(board, nets):
    inset = ZONE_INSET_MM
    full = _rectangle(inset, inset, BOARD_W_MM - inset, BOARD_H_MM - inset)
    for layer, net_name in copper_layers():
        if net_name not in PLANE_NETS:
            continue
        _pour(board, nets[net_name], full, (layer,))


def _add_track(board, start, end, layer, net, width_mm):
    # Locked, because this conductor is the design's rather than a search
    # result: a router reading the board treats locked copper as fixed and
    # never routes through the corridor it occupies.
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(start)
    track.SetEnd(end)
    track.SetLayer(layer)
    track.SetNet(net)
    track.SetWidth(pcbnew.FromMM(width_mm))
    track.SetLocked(True)
    board.Add(track)
    return track


def _add_via(board, position, net, diameter_mm=None, drill_mm=None):
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(position)
    via.SetWidth(pcbnew.F_Cu,
                 pcbnew.FromMM(VIA_DIAMETER_MM if diameter_mm is None
                               else diameter_mm))
    via.SetDrill(pcbnew.FromMM(VIA_DRILL_MM if drill_mm is None
                               else drill_mm))
    via.SetNet(net)
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetLocked(True)
    board.Add(via)
    return via


def _box_distance(box, x, y):
    """Distance from a point to an axis-aligned box, zero inside it."""
    dx = max(box.GetLeft() - x, 0, x - box.GetRight())
    dy = max(box.GetTop() - y, 0, y - box.GetBottom())
    return math.hypot(dx, dy)


def _segment_box_distance(box, start, end, samples=24):
    """Distance from a segment to a box, sampled along the segment."""
    closest = None
    for index in range(samples + 1):
        t = index / float(samples)
        x = start.x + (end.x - start.x) * t
        y = start.y + (end.y - start.y) * t
        distance = _box_distance(box, x, y)
        if closest is None or distance < closest:
            closest = distance
    return closest


def _obstacles(board):
    """Every pad and via as a box the generated copper must stay clear of."""
    found = []
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            found.append((pad.GetBoundingBox(), pad.GetNetCode()))
    for item in board.GetTracks():
        if item.Type() == pcbnew.PCB_VIA_T:
            found.append((item.GetBoundingBox(), None))
        else:
            found.append((item.GetBoundingBox(), item.GetNetCode()))
    return found


def _stitch(board, footprint, pad, net):
    """Drop a via just outside a surface pad and bond it to its plane.

    The direction is searched rather than assumed: on a board where a
    passive row steps by little more than its own courtyard, the obvious
    direction is often occupied, and a via that lands on a neighbour's mask
    opening is a bridge, not a connection.
    """
    position = pad.GetPosition()
    size = pad.GetSize()
    angle = math.radians(footprint.GetOrientationDegrees())
    along = (math.cos(angle), math.sin(angle))
    across = (-math.sin(angle), math.cos(angle))
    half_along = pcbnew.ToMM(size.x) / 2.0
    half_across = pcbnew.ToMM(size.y) / 2.0
    keep_out = pcbnew.FromMM(VIA_DIAMETER_MM / 2.0 + CLEARANCE_MM)
    track_keep_out = pcbnew.FromMM(STITCH_TRACK_WIDTH_MM / 2.0 + CLEARANCE_MM)
    obstacles = _obstacles(board)
    candidates = []
    # Axis-aligned first, and closest first: a stitch that runs square to
    # its pad keeps the copper it adds predictable, and only a pad with no
    # square way out falls back to a diagonal.
    for directions in (4, 16):
        for step in range(13):
            extra = 0.25 * step
            for index in range(directions):
                turn = 2.0 * math.pi * index / directions
                axis = (math.cos(angle + turn), math.sin(angle + turn))
                half = (abs(math.cos(turn)) * half_along
                        + abs(math.sin(turn)) * half_across)
                reach = half + VIA_DIAMETER_MM / 2.0 + STITCH_GAP_MM + extra
                candidates.append((axis[0] * reach, axis[1] * reach))
    for dx, dy in candidates:
        centre = pcbnew.VECTOR2I(int(position.x + pcbnew.FromMM(dx)),
                                 int(position.y + pcbnew.FromMM(dy)))
        x_mm = pcbnew.ToMM(centre.x) - ORIGIN_MM[0]
        y_mm = ORIGIN_MM[1] - pcbnew.ToMM(centre.y)
        margin = ZONE_INSET_MM + VIA_DIAMETER_MM / 2.0
        if not margin <= x_mm <= BOARD_W_MM - margin:
            continue
        if not margin <= y_mm <= BOARD_H_MM - margin:
            continue
        clear = True
        for box, net_code in obstacles:
            if net_code is not None and net_code == net.GetNetCode():
                continue
            if _box_distance(box, centre.x, centre.y) < keep_out:
                clear = False
                break
            # the via is reached by a track, and that track has to be clear
            # of everything the via itself was tested against
            if _segment_box_distance(box, position, centre) < track_keep_out:
                clear = False
                break
        if not clear:
            continue
        _add_via(board, centre, net)
        _add_track(board, position, centre, pcbnew.F_Cu, net,
                   STITCH_TRACK_WIDTH_MM)
        return centre
    raise RuntimeError(
        "no clear stitch position for %s pad %s"
        % (footprint.GetReference(), pad.GetNumber()))


def _pad(footprints, reference, number):
    return next(pad for pad in footprints[reference].Pads()
                if pad.GetNumber() == number)


def _driver_reference_pins(board, footprints, nets):
    """Every reference pin of the driver, joined to its own exposed pad.

    The datasheet asks for exactly this: the ground pins connected directly
    to the pad under the device, which is where the star point is and where
    the via field takes the heat and the return current down to the planes.
    """
    exposed = _pad(footprints, "U1", netlist.DRIVER_PINS["EPAD"])
    half_width = pcbnew.ToMM(exposed.GetSize().x) / 2.0
    half_height = pcbnew.ToMM(exposed.GetSize().y) / 2.0
    centre = exposed.GetPosition()
    for number in sorted(set(netlist.DRIVER_PINS.values()), key=int):
        if number == netlist.DRIVER_PINS["EPAD"]:
            continue
        pad = _pad(footprints, "U1", number)
        if pad.GetNetname() != "GND":
            continue
        position = pad.GetPosition()
        sign = -1.0 if position.x < centre.x else 1.0
        edge_x = int(centre.x + sign * pcbnew.FromMM(half_width - 0.1))
        corner = pcbnew.VECTOR2I(edge_x, position.y)
        _add_track(board, position, corner, pcbnew.F_Cu, nets["GND"],
                   DRIVER_GROUND_TRACK_MM)
        # A pin beyond the pad's own extent needs a second leg to reach it.
        reach = pcbnew.FromMM(half_height - 0.1)
        if abs(position.y - centre.y) > reach:
            step = reach if position.y > centre.y else -reach
            _add_track(board, corner,
                       pcbnew.VECTOR2I(edge_x, int(centre.y + step)),
                       pcbnew.F_Cu, nets["GND"], DRIVER_GROUND_TRACK_MM)


def _driver_thermal_vias(board, footprints, nets):
    """The exposed pad's via field, at the positions the land pattern's mask
    dams were cut for."""
    from . import libraries
    footprint = footprints["U1"]
    centre = footprint.GetPosition()
    angle = math.radians(-footprint.GetOrientationDegrees())
    for x_mm, y_mm in libraries.thermal_via_positions_mm():
        dx = x_mm * math.cos(angle) - y_mm * math.sin(angle)
        dy = x_mm * math.sin(angle) + y_mm * math.cos(angle)
        position = pcbnew.VECTOR2I(int(centre.x + pcbnew.FromMM(dx)),
                                   int(centre.y + pcbnew.FromMM(dy)))
        _add_via(board, position, nets["GND"])


#: Where each of the driver's supply pins reaches the rail plane. Placed
#: rather than searched: the pin sits between its own coil's sense conductor
#: and one bridge output, and the one position that clears both is a
#: property of those two conductors.
#: Each supply pin's own way to the rail plane. The escape steps clear of
#: its own sense conductor's row before the via, which will not fit in the
#: gap between that row and the bridge output's.
SUPPLY_ROUTES = {"VS_A": [(51.5, 26.925, 0.4), (51.5, 25.5, 0.4)],
                 "VS_B": [(40.5, 26.925, 0.4), (40.5, 25.5, 0.4)]}


def _driver_supply_pins(board, footprints, nets):
    """The driver's supply pins, taken straight down to the rail plane."""
    for name, waypoints in sorted(SUPPLY_ROUTES.items()):
        pad = _pad(footprints, "U1", netlist.DRIVER_PINS[name])
        end = _polyline(board, nets["VM"], pad.GetPosition(), waypoints)
        _add_via(board, end, nets["VM"])


#: Each phase conductor's itinerary from the bridge output to its connector
#: position, as (x, y, width) waypoints in board coordinates. A `None` entry
#: is where the conductor changes layer: the two inner outputs cannot reach
#: the connector on the component layer without crossing their own coil's
#: sense conductor, so each takes one via and finishes underneath. That via
#: stands beside the pad it serves rather than out along the flank, so the
#: copper below it runs above the pin row instead of across the corridor the
#: logic pins leave the package through.
#:
#: Every conductor leaves the pad field narrow. A wide conductor at a pad's
#: own row would stand inside its neighbours' clearance, so the width the
#: current needs is taken only once the copper is clear of the package.
#: The width a bridge output leaves the pad row at, and the width it runs at
#: once clear of it. The escape is as wide as the pad pitch allows beside its
#: neighbours; the run is what the conductor's own temperature rise asks for.
PHASE_ESCAPE_WIDTH_MM = 0.5
PHASE_RUN_WIDTH_MM = 0.8

#: The layer change on a bridge output carries the whole phase current, so
#: it is drilled wider than the board's signal via: a barrel wall thinner
#: than the conductor it joins would be the conductor's narrowest point.
PHASE_VIA_DIAMETER_MM = 0.9
PHASE_VIA_DRILL_MM = 0.6

PHASE_ROUTES = {
    "B1": [(41.2, 28.225, PHASE_ESCAPE_WIDTH_MM),
           (41.2, 30.0, PHASE_ESCAPE_WIDTH_MM),
           (41.2, 34.5, PHASE_RUN_WIDTH_MM),
           (49.96, 34.5, PHASE_RUN_WIDTH_MM),
           (49.96, 40.0, PHASE_RUN_WIDTH_MM)],
    "B2": [(42.3, 26.275, PHASE_ESCAPE_WIDTH_MM),
           (41.5, 26.0, PHASE_ESCAPE_WIDTH_MM), None,
           (41.5, 38.0, PHASE_RUN_WIDTH_MM),
           (46.0, 38.0, PHASE_RUN_WIDTH_MM),
           (46.0, 40.0, PHASE_RUN_WIDTH_MM)],
    "A1": [(50.8, 28.225, PHASE_ESCAPE_WIDTH_MM),
           (50.8, 30.5, PHASE_ESCAPE_WIDTH_MM),
           (52.5, 30.5, PHASE_RUN_WIDTH_MM),
           (52.5, 36.5, PHASE_RUN_WIDTH_MM),
           (57.88, 36.5, PHASE_RUN_WIDTH_MM),
           (57.88, 40.0, PHASE_RUN_WIDTH_MM)],
    "A2": [(49.7, 26.275, PHASE_ESCAPE_WIDTH_MM),
           (50.5, 26.0, PHASE_ESCAPE_WIDTH_MM), None,
           (50.5, 38.0, PHASE_RUN_WIDTH_MM),
           (53.92, 38.0, PHASE_RUN_WIDTH_MM),
           (53.92, 40.0, PHASE_RUN_WIDTH_MM)],
}

#: Where each sense conductor stops being a pad escape and becomes the wide
#: conductor its own resistance budget asks for.
SENSE_WIDEN_X_MM = {"A": 52.8, "B": 39.2}
SENSE_ESCAPE_WIDTH_MM = 0.5

#: The probe on each sense conductor, taken off the resistor's own end so
#: the probe stub carries no part of the measured drop.
SENSE_PROBES = {"A": "TP7", "B": "TP8"}


def _polyline(board, net, start, waypoints, via_diameter_mm=None,
              via_drill_mm=None):
    """Draw one conductor, changing layer where the itinerary says to."""
    layer = pcbnew.F_Cu
    previous = start
    for waypoint in waypoints:
        if waypoint is None:
            _add_via(board, previous, net, via_diameter_mm, via_drill_mm)
            layer = pcbnew.B_Cu
            continue
        x_mm, y_mm, width = waypoint
        point = _point(x_mm, y_mm)
        if point != previous:
            _add_track(board, previous, point, layer, net, width)
        previous = point
    return previous


def _route_phases(board, footprints, nets):
    """The four phase conductors, generated rather than searched.

    Each carries the whole coil current, its loop is the requirement, and
    the order the connector presents its positions in leaves a search no
    freedom worth having.
    """
    for function, waypoints in sorted(PHASE_ROUTES.items()):
        start = _pad(footprints, "U1",
                     netlist.DRIVER_PINS["O%s" % function]).GetPosition()
        _polyline(board, nets["PHASE_%s" % function], start, waypoints,
                  PHASE_VIA_DIAMETER_MM, PHASE_VIA_DRILL_MM)


def _route_sense(board, footprints, nets):
    """Each bridge return to its own resistor, and nothing else on the way.

    The conductor leaves the pad field at the width the pad pitch allows and
    widens as soon as it is clear, because its resistance is added to the
    shunt's by the driver's own comparator.
    """
    for phase, reference in sorted(netlist.SENSE_RESISTOR_REFERENCES.items()):
        net = nets["SENSE_%s" % phase]
        start = _pad(footprints, "U1",
                     netlist.DRIVER_PINS["BR%s" % phase]).GetPosition()
        end = _pad(footprints, reference, "1").GetPosition()
        row_mm = ORIGIN_MM[1] - pcbnew.ToMM(start.y)
        widen_mm = SENSE_WIDEN_X_MM[phase]
        end_mm = pcbnew.ToMM(end.x) - ORIGIN_MM[0]
        corner = _polyline(board, net, start, [
            (widen_mm, row_mm, SENSE_ESCAPE_WIDTH_MM),
            (end_mm, row_mm, SENSE_TRACK_WIDTH_MM)])
        probe = _pad(footprints, SENSE_PROBES[phase], "1").GetPosition()
        _add_track(board, corner, probe, pcbnew.F_Cu, net,
                   SENSE_ESCAPE_WIDTH_MM)


def _stitch_planes(board, footprints, nets):
    """Every surface pad on a plane net reaches its plane by its own via.

    Doing it here rather than leaving it to the router keeps how a pad joins
    a plane a property of the pad, not of a search - which is what the two
    sense resistors need, since each of their reference ends must reach the
    plane without sharing copper with the other.
    """
    sense = set(netlist.SENSE_RESISTOR_REFERENCES.values())
    for reference, footprint in sorted(footprints.items()):
        if reference == "U1":
            continue
        for pad in footprint.Pads():
            name = pad.GetNetname()
            if name not in PLANE_NETS:
                continue
            if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            count = netlist.SENSE_RETURN_VIA_COUNT if reference in sense else 1
            for _ in range(count):
                _stitch(board, footprint, pad, nets[name])


def fill_zones(board):
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    return board


def build(with_copper=True):
    """The board.

    `with_copper=False` produces the same placement with no planes: a
    placement search refuses a board that already carries copper, because
    moving a footprint would leave its copper behind. Everything conductive
    is generated from the accepted poses afterwards, so the two forms cannot
    disagree about where a part is.
    """
    board = pcbnew.CreateEmptyBoard()
    _design_settings(board)
    nets = _nets(board)
    pin_net = netlist.pin_to_net()

    footprints = {}
    placed = fixed_placements()
    for reference, (x, y, rotation) in sorted(placed.items()):
        part = netlist.PARTS[reference]
        if not part["footprint"]:
            continue
        footprints[reference] = _load(
            board, reference, part, x, y, rotation, pin_net, nets)

    _add_outline(board)
    if with_copper:
        _add_pours(board, nets)
        _route_phases(board, footprints, nets)
        _route_sense(board, footprints, nets)
        _driver_thermal_vias(board, footprints, nets)
        _driver_reference_pins(board, footprints, nets)
        _driver_supply_pins(board, footprints, nets)
        _stitch_planes(board, footprints, nets)
    _add_silkscreen(board, footprints)
    return board, footprints


# ---------------------------------------------------------------------------
# silkscreen

SILK_LAYER = pcbnew.F_SilkS
SILK_TEXT_MM = 1.2
SILK_THICKNESS_MM = 0.2
PROBE_LABEL_OFFSET_MM = 1.7
RATING_Y_MM = 2.5

#: What each motor connector position carries, marked because a plug that
#: mates mechanically in the wrong order reverses one phase.
MOTOR_PIN_MARKS = {"A1": "A+", "A2": "A-", "B1": "B+", "B2": "B-"}


def _text(board, value, x, y, size_mm=SILK_TEXT_MM, layer=None):
    item = pcbnew.PCB_TEXT(board)
    item.SetText(value)
    item.SetPosition(_point(x, y))
    item.SetLayer(SILK_LAYER if layer is None else layer)
    item.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size_mm),
                                     pcbnew.FromMM(size_mm)))
    item.SetTextThickness(pcbnew.FromMM(SILK_THICKNESS_MM))
    item.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    item.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    board.Add(item)
    return item


def rating_text():
    """What the board is marked with, from what it claims."""
    return "%g-%gV  %gA MAX  %.1fArms/PHASE" % (
        netlist.INPUT_SUPPLY["min_v"], netlist.INPUT_SUPPLY["max_v"],
        netlist.INPUT_CURRENT_RATING_A, netlist.PHASE_CURRENT_RMS_A)


def probe_labels():
    pin_net = netlist.pin_to_net()
    return {reference: pin_net["%s.1" % reference]
            for reference in netlist.PARTS if reference.startswith("TP")}


def motor_order_text(footprints):
    """The connector's positions in the order the assembled board shows them.

    Read off the placed pads rather than the pin numbers: the connector is
    rotated, so the numeric order and the order a hand sees run opposite
    ways, and the marking has to be the one a hand can follow.
    """
    marks = {}
    for function, pin in netlist.MOTOR_CONNECTOR_PINS.items():
        pad = _pad(footprints, "J2", str(pin))
        marks[pad.GetPosition().x] = "%d%s" % (pin, MOTOR_PIN_MARKS[function])
    return " ".join(marks[x] for x in sorted(marks))


def _add_silkscreen(board, footprints):
    _text(board, rating_text(), BOARD_W_MM / 2.0, RATING_Y_MM, size_mm=1.0)
    placed = fixed_placements()
    centre = sum(_pad(footprints, "J2", str(pin)).GetPosition().x
                 for pin in netlist.MOTOR_CONNECTOR_PINS.values()) / 4.0
    _text(board, motor_order_text(footprints),
          pcbnew.ToMM(centre) - ORIGIN_MM[0], placed["J2"][1] + 6.5,
          size_mm=0.9)
    for reference, net in sorted(probe_labels().items()):
        x, y, _ = placed[reference]
        _text(board, net, x, y + PROBE_LABEL_OFFSET_MM, size_mm=0.8)
    for reference, label, dx, dy, size in (("J1", "12-24V", 0.0, 9.0, 1.0),
                                           ("J3", "CTRL", 0.0, 2.9, 0.8),
                                           ("J4", "SWD", 0.0, 2.9, 0.8),
                                           ("J5", "CFG", 0.0, 2.9, 0.8)):
        x, y, _ = placed[reference]
        _text(board, label, x + dx, y + dy, size_mm=size)


def write(path=None):
    """Write the board, then rewrite the project it belongs to.

    Saving a board rewrites the project file beside it with KiCad's own
    defaults, which is how rule severities a board declares as warnings turn
    into ignores. The project is therefore regenerated from the design
    source afterwards, every time.
    """
    from . import build as _build
    board, _ = build()
    fill_zones(board)
    target = BOARD_PATH if path is None else path
    pcbnew.SaveBoard(target, board)
    if path is None:
        _build.write_project()
    return target


def write_placement_board(path):
    board, _ = build(with_copper=False)
    pcbnew.SaveBoard(path, board)
    return path


if __name__ == "__main__":
    sys.stdout.write(write() + "\n")
