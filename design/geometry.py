from __future__ import annotations

import json
import math
import os

from . import layout, netlist, rules

PHYSICAL_PATH = os.path.join(rules.REPO_ROOT, "fab", "physical_inputs.json")
SELECTION_PATH = os.path.join(rules.REPO_ROOT, "fab", "selection.json")
CATALOG_ROOT = os.path.join(rules.REPO_ROOT, "tooling",
                            "PCBA_AutoDesignAndTest", "profiles", "jlcpcb")

FREE_SPACE_IMPEDANCE_OHM = 376.730313668

#: IPC-2221 conductor current curves, I = k * rise**0.44 * area**0.725 with
#: the area in square mils and the current in amperes.
IPC_AREA_EXPONENT = 0.725
IPC_RISE_EXPONENT = 0.44
IPC_CONSTANT = {True: 0.048, False: 0.024}
MIL_MM = 0.0254

EXTERNAL_LAYERS = ("F.Cu", "B.Cu")

TOUCH_MM = 0.001

IPC_CURVE = ("the IPC-2221 conductor current curve, which is drawn for a "
             "long conductor in still air with no other heat path")
PLATING = ("a plated hole wall of at least %.0f um, which is the class the "
           "fabricator's process is taken to hold to"
           % netlist.VIA_PLATING_MIN_UM)
NO_SPREADING = ("the copper each conductor runs into at both ends, which "
                "the curve does not credit")
NO_PLANES = ("the planes beneath, which the curve does not credit")


def _approved():
    import sys as _sys
    if rules.TOOLKIT_ROOT not in _sys.path:
        _sys.path.insert(0, rules.TOOLKIT_ROOT)
    from pcbqa.fabricators.store import CatalogStore

    approved = CatalogStore(CATALOG_ROOT).approved()
    if approved is None:
        raise RuntimeError("no approved fabricator catalog")
    return approved


def signal_dielectric():
    """The dielectric an outer conductor sees, from approved evidence.

    The selected stackup's first dielectric is the one between an outer
    conductor and the plane next to it; its permittivity is the lowest the
    catalog states for that material, because a lower permittivity raises
    the impedance and every use of it here is an upper bound.
    """
    import sys as _sys
    if rules.TOOLKIT_ROOT not in _sys.path:
        _sys.path.insert(0, rules.TOOLKIT_ROOT)
    from pcbqa import extract

    with open(SELECTION_PATH, "r", encoding="utf-8") as handle:
        selection = json.load(handle)
    approved = _approved()
    digest = approved["normalized_sha256"]
    stackup = approved["normalized"]["stackups"][selection["stackup"]]
    layers = stackup["layers"]
    first = next(index for index, layer in enumerate(layers)
                 if layer["role"] == "dielectric")
    dielectric = layers[first]
    materials = approved["normalized"]["materials"]
    permittivity = [record["dk"] for record in materials.values()
                    if record.get("kind") == dielectric["form"]
                    and record.get("name") == dielectric["material"]]
    if not permittivity:
        raise RuntimeError("the catalog states no permittivity for %s %s"
                           % (dielectric["form"], dielectric["material"]))
    return {
        "height_mm": extract.validate_parameter(
            {"value": dielectric["thickness_mm"], "units": "mm",
             "source_type": "approved-evidence",
             "source": "stackups.%s.layers[%d]" % (selection["stackup"],
                                                   first),
             "digest": digest,
             "applicability": "the dielectric between an outer conductor "
                              "and the plane next to it"},
            "dielectric height"),
        "permittivity": extract.validate_parameter(
            {"value": min(permittivity), "units": "1",
             "source_type": "approved-evidence",
             "source": "materials.%s %s" % (dielectric["form"],
                                            dielectric["material"]),
             "digest": digest,
             "applicability": "the lowest permittivity the catalog states "
                              "for this material"},
            "relative permittivity"),
    }


def microstrip_impedance_ohm(width_mm, height_mm, epsilon_r):
    """Hammerstad's microstrip impedance for a zero-thickness conductor."""
    import sys as _sys
    if rules.TOOLKIT_ROOT not in _sys.path:
        _sys.path.insert(0, rules.TOOLKIT_ROOT)
    from pcbqa import propagation

    effective = propagation.hammerstad_effective_permittivity(
        epsilon_r, width_mm, height_mm)
    ratio = width_mm / height_mm
    root = math.sqrt(effective)
    if ratio <= 1.0:
        return (FREE_SPACE_IMPEDANCE_OHM / (2.0 * math.pi * root)) \
            * math.log(8.0 / ratio + ratio / 4.0)
    return (FREE_SPACE_IMPEDANCE_OHM / root) \
        / (ratio + 1.393 + 0.667 * math.log(ratio + 1.444))


def damping_ratio(series_ohm, impedance_ohm):
    """The series element against the conductor's own L and C.

    A conductor short enough to be lumped is a series RLC whose L and C are
    the line's own, so LC is the square of its delay and the damping falls
    out as the series element over twice the impedance.
    """
    return series_ohm / (2.0 * impedance_ohm)


def overshoot_fraction(damping):
    if damping >= 1.0:
        return 0.0
    return math.exp(-math.pi * damping / math.sqrt(1.0 - damping * damping))


def narrowest_conductor(board, net):
    widths = [track["width_mm"] for track in board["tracks"]
              if track["net"] == net]
    if not widths:
        raise RuntimeError("no copper on %s" % net)
    return min(widths)


def source_termination(board, net, series_ohm, swing_v):
    """What the routed conductor does to an edge driven through a series
    element: the narrowest section, its impedance, and the overshoot the
    lumped loop would produce."""
    dielectric = signal_dielectric()
    width = narrowest_conductor(board, net)
    impedance = microstrip_impedance_ohm(
        width, dielectric["height_mm"]["value"],
        dielectric["permittivity"]["value"])
    damping = damping_ratio(series_ohm, impedance)
    return {"width_mm": width, "impedance_ohm": impedance,
            "damping": damping,
            "overshoot_v": overshoot_fraction(damping) * swing_v,
            "dielectric": dielectric}


def temperature_rise_k(current_a, area_mm2, external=True):
    area_mil2 = area_mm2 / (MIL_MM ** 2)
    capacity = IPC_CONSTANT[bool(external)] * area_mil2 ** IPC_AREA_EXPONENT
    return (current_a / capacity) ** (1.0 / IPC_RISE_EXPONENT)


def barrel_area_mm2(drill_mm):
    return math.pi * drill_mm * netlist.VIA_PLATING_MIN_UM * 1e-3


def copper_thickness_mm():
    with open(PHYSICAL_PATH, "r", encoding="utf-8") as handle:
        document = json.load(handle)
    return {layer: record["value"]
            for layer, record in document["copper_thickness_mm"].items()}


_SNAPSHOTS = {}


def snapshot(path=None, reread=False):
    """Every conductor, via and pad the board carries, as plain numbers.

    Kept per board file and stamp, because several producers ask for the
    same board in one run and reading it again would be the only cost.
    """
    target = path or layout.BOARD_PATH
    status = os.stat(target)
    key = (target, status.st_mtime_ns, status.st_size)
    if not reread and key in _SNAPSHOTS:
        return _SNAPSHOTS[key]
    _SNAPSHOTS.clear()
    _SNAPSHOTS[key] = _read(target)
    return _SNAPSHOTS[key]


def _read(path):
    import pcbnew

    import sys as _sys
    if rules.TOOLKIT_ROOT not in _sys.path:
        _sys.path.insert(0, rules.TOOLKIT_ROOT)
    from pcbqa import headless

    headless.suppress_blocking_ui()
    board = pcbnew.LoadBoard(path)
    tracks, vias = [], []
    for item in board.GetTracks():
        net = item.GetNetname()
        if item.Type() == pcbnew.PCB_VIA_T:
            position = item.GetPosition()
            vias.append({
                "net": net,
                "at": (pcbnew.ToMM(position.x), pcbnew.ToMM(position.y)),
                "diameter_mm": pcbnew.ToMM(item.GetWidth(pcbnew.F_Cu)),
                "drill_mm": pcbnew.ToMM(item.GetDrill())})
            continue
        tracks.append({
            "net": net,
            "start": (pcbnew.ToMM(item.GetStart().x),
                      pcbnew.ToMM(item.GetStart().y)),
            "end": (pcbnew.ToMM(item.GetEnd().x),
                    pcbnew.ToMM(item.GetEnd().y)),
            "width_mm": pcbnew.ToMM(item.GetWidth()),
            "layer": board.GetLayerName(item.GetLayer())})
    pads = {}
    for footprint in board.GetFootprints():
        reference = footprint.GetReference()
        for pad in footprint.Pads():
            box = pad.GetBoundingBox()
            pads["%s.%s" % (reference, pad.GetNumber())] = {
                "net": pad.GetNetname(),
                "at": (pcbnew.ToMM(pad.GetPosition().x),
                       pcbnew.ToMM(pad.GetPosition().y)),
                "box": (pcbnew.ToMM(box.GetLeft()), pcbnew.ToMM(box.GetTop()),
                        pcbnew.ToMM(box.GetRight()),
                        pcbnew.ToMM(box.GetBottom()))}
    return {"tracks": tracks, "vias": vias, "pads": pads}


def _distance(one, other):
    return math.hypot(one[0] - other[0], one[1] - other[1])


def _in_box(box, point):
    return (box[0] - TOUCH_MM <= point[0] <= box[2] + TOUCH_MM
            and box[1] - TOUCH_MM <= point[1] <= box[3] + TOUCH_MM)


def _current_nets():
    """Every net that carries a coil's current, and how much of it."""
    current = netlist.PHASE_CURRENT_RMS_A
    nets = {"PHASE_%s" % function: current
            for function in netlist.MOTOR_CONNECTOR_PINS}
    nets.update({"SENSE_%s" % phase: current for phase in netlist.PHASES})
    return nets


def evaluate_conductor_rise(parameters, board=None):
    """What each coil conductor's narrowest section does to its own heat."""
    del parameters
    board = board or snapshot()
    thickness = copper_thickness_mm()
    results = []
    for net, current in sorted(_current_nets().items()):
        sections = [(track["width_mm"], track["layer"])
                    for track in board["tracks"] if track["net"] == net]
        if not sections:
            raise RuntimeError("no copper on %s" % net)
        width_mm, layer = min(sections)
        rise = temperature_rise_k(current, width_mm * thickness[layer],
                                  layer in EXTERNAL_LAYERS)
        results.append({
            "id": "the_temperature_rise_of_%s_at_its_narrowest" % net.lower(),
            "identity": net,
            "measured": rise,
            "claim": rules._claim(
                net, "K", "conductor_heating", rise, rules.DERIVED, (),
                rules._requirement(
                    "every_coil_conductor_carries_the_phase_current_within_"
                    "the_declared_rise",
                    "<=", netlist.PHASE_CONDUCTOR_RISE_MAX_K),
                phenomenon="interconnect_dc",
                assumptions=(IPC_CURVE,
                             "the finished copper the approved fabricator "
                             "catalog states for %s" % layer,
                             "the whole coil current in the narrowest "
                             "section the net carries anywhere"),
                omissions=(NO_SPREADING, NO_PLANES))})
    return results


def _touching_tracks(board, via):
    reach = via["diameter_mm"] / 2.0 + TOUCH_MM
    return [track for track in board["tracks"]
            if track["net"] == via["net"]
            and (_distance(track["start"], via["at"]) <= reach
                 or _distance(track["end"], via["at"]) <= reach)]


def evaluate_layer_changes(parameters, board=None):
    """A layer change may not be the narrowest part of the conductor."""
    del parameters
    board = board or snapshot()
    thickness = copper_thickness_mm()
    carried = _current_nets()
    violations = []
    for via in board["vias"]:
        if via["net"] not in carried:
            continue
        barrel = barrel_area_mm2(via["drill_mm"])
        for track in _touching_tracks(board, via):
            section = track["width_mm"] * thickness[track["layer"]]
            if barrel < section:
                violations.append(
                    "%s at %.3f,%.3f carries %.4f mm2 of wall where the "
                    "conductor it joins carries %.4f mm2"
                    % (via["net"], via["at"][0], via["at"][1], barrel,
                       section))
    return [
        {"id": "no_layer_change_narrows_a_coil_conductor",
         "identity": "board",
         "measured": len(violations),
         "claim": rules._structural(
             "board", "conductor_heating", sorted(set(violations)),
             "every_layer_change_on_a_coil_conductor_carries_at_least_the_"
             "conductor_it_joins",
             assumptions=(PLATING,
                          "the finished copper the approved fabricator "
                          "catalog states for each layer"))},
    ]


def _surface_group(board, pad_name):
    """What the pad reaches on the component layer without leaving it."""
    pad = board["pads"][pad_name]
    tracks = [track for track in board["tracks"]
              if track["net"] == pad["net"] and track["layer"] == "F.Cu"]
    reached = [track for track in tracks
               if _in_box(pad["box"], track["start"])
               or _in_box(pad["box"], track["end"])]
    group = {id(track) for track in reached}
    frontier = list(reached)
    while frontier:
        track = frontier.pop()
        for other in tracks:
            if id(other) in group:
                continue
            for one in (track["start"], track["end"]):
                if min(_distance(one, other["start"]),
                       _distance(one, other["end"])) <= TOUCH_MM:
                    group.add(id(other))
                    frontier.append(other)
                    break
    return [track for track in tracks if id(track) in group]


def _group_vias(board, group):
    ends = [point for track in group for point in (track["start"],
                                                   track["end"])]
    return [via for via in board["vias"]
            if any(_distance(via["at"], point)
                   <= via["diameter_mm"] / 2.0 + TOUCH_MM for point in ends)]


def evaluate_sense_returns(parameters, board=None):
    """Each shunt's reference end reaches the plane on its own."""
    del parameters
    board = board or snapshot()
    results = []
    groups = {}
    for phase, reference in sorted(netlist.SENSE_RESISTOR_REFERENCES.items()):
        name = "%s.2" % reference
        groups[reference] = _surface_group(board, name)
        count = len(_group_vias(board, groups[reference]))
        results.append({
            "id": "the_%s_shunt_reference_reaches_the_plane_by_its_own_vias"
                  % phase.lower(),
            "identity": name,
            "measured": count,
            "claim": rules._claim(
                name, "vias", "sense_accuracy", float(count), rules.DERIVED,
                (), rules._requirement(
                    "each_shunt_reference_end_reaches_the_plane_by_the_"
                    "declared_number_of_vias",
                    ">=", float(netlist.SENSE_RETURN_VIA_COUNT)),
                scope_level="path", phenomenon="interconnect_geometry")})
    shared = []
    references = sorted(groups)
    for index, reference in enumerate(references):
        for other in references[index + 1:]:
            common = {id(track) for track in groups[reference]} \
                & {id(track) for track in groups[other]}
            if common:
                shared.append("%s and %s stand on the same surface copper"
                              % (reference, other))
    results.append({
        "id": "the_shunt_references_share_no_surface_conductor",
        "identity": "board",
        "measured": len(shared),
        "claim": rules._structural(
            "board", "sense_accuracy", shared,
            "no_two_shunt_reference_ends_share_copper_before_the_plane")})
    return results


def evaluate_probe_reference(parameters, board=None):
    """No probe stands further from a ground probe than a lead reaches."""
    del parameters
    board = board or snapshot()
    pin_net = netlist.pin_to_net()
    probes = {reference: board["pads"]["%s.1" % reference]["at"]
              for reference in netlist.PARTS if reference.startswith("TP")}
    grounds = [position for reference, position in probes.items()
               if pin_net["%s.1" % reference] == "GND"]
    worst = 0.0
    for reference, position in sorted(probes.items()):
        net = pin_net["%s.1" % reference]
        if net == "GND" or net not in netlist.PROBE_REQUIRED_NETS:
            continue
        worst = max(worst, min(_distance(position, ground)
                               for ground in grounds))
    return [
        {"id": "the_furthest_a_probe_stands_from_a_ground_probe",
         "identity": "board",
         "measured": worst,
         "claim": rules._claim(
             "board", "mm", "test_access", worst, rules.DERIVED, (),
             rules._requirement(
                 "every_required_probe_has_a_ground_probe_within_reach",
                 "<=", netlist.PROBE_GROUND_REACH_MM),
             scope_level="board", phenomenon="interconnect_geometry")},
    ]


def evaluate_thermal_pad_vias(parameters, board=None):
    """The exposed pad's heat path, counted on the board rather than meant."""
    del parameters
    board = board or snapshot()
    pad = board["pads"]["U1.%s" % netlist.DRIVER_PINS["EPAD"]]
    count = sum(1 for via in board["vias"]
                if via["net"] == pad["net"] and _in_box(pad["box"],
                                                        via["at"]))
    return [
        {"id": "the_vias_standing_in_the_exposed_pad",
         "identity": "U1.%s" % netlist.DRIVER_PINS["EPAD"],
         "measured": count,
         "claim": rules._claim(
             "U1.%s" % netlist.DRIVER_PINS["EPAD"], "vias", "thermal",
             float(count), rules.DERIVED, (),
             rules._requirement(
                 "the_exposed_pad_reaches_the_plane_through_the_declared_"
                 "via_array",
                 ">=", float(netlist.THERMAL_VIA_COUNT)),
             scope_level="path", phenomenon="interconnect_geometry")},
    ]


def evaluate_source_termination(parameters, board=None):
    """The series element at the controller against what it drives.

    A conductor driven through a series element at or above its own
    impedance cannot deliver an edge to the far end that stands above the
    driven level; the element is the design's, the impedance is the routed
    conductor's.
    """
    del parameters
    board = board or snapshot()
    dielectric = signal_dielectric()
    results = []
    for net, reference in sorted(netlist.SOURCE_TERMINATED.items()):
        series = rules._resistor_ohms(reference)
        width = narrowest_conductor(board, net)
        impedance = microstrip_impedance_ohm(
            width, dielectric["height_mm"]["value"],
            dielectric["permittivity"]["value"])
        results.append({
            "id": "the_impedance_%s_presents_to_its_series_element"
                  % net.lower(),
            "identity": net,
            "measured": impedance,
            "claim": rules._claim(
                net, "ohm", "signal_integrity", impedance, rules.DERIVED, (),
                rules._requirement(
                    "the_series_element_is_at_least_the_conductor_impedance",
                    "<=", series),
                phenomenon="characteristic_impedance",
                assumptions=(
                    "Hammerstad's microstrip impedance at the narrowest "
                    "width the net carries, which is the highest impedance "
                    "any of its sections presents",
                    "the plane next to the conductor's layer is its return "
                    "path, and the rail plane is a return at the "
                    "frequencies an edge carries because the decoupling "
                    "ties it to the reference",
                    "the dielectric between an outer conductor and that "
                    "plane, at the lowest permittivity the catalog states "
                    "for it"),
                omissions=(
                    "the conductor's own thickness and the mask over it, "
                    "both of which lower the impedance",))})
    return results


PRODUCERS = (
    evaluate_conductor_rise,
    evaluate_source_termination,
    evaluate_layer_changes,
    evaluate_sense_returns,
    evaluate_probe_reference,
    evaluate_thermal_pad_vias,
)


def evaluate_all(parameters):
    board = snapshot()
    results = []
    for producer in PRODUCERS:
        results.extend(producer(parameters, board))
    return results
