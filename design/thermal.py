from __future__ import annotations

import json
import os
import sys

from . import netlist, rules

REPO_ROOT = rules.REPO_ROOT
REPORT_PATH = os.path.join(REPO_ROOT, "generated", "thermal.json")


def driver_conduction_w(parameters, current_a=None):
    """Both bridges conducting the phase current through their own silicon.

    A lower bound on the driver's dissipation: it counts the on-resistance
    the datasheet states at 25 degC and nothing else.
    """
    driver = rules._spec(parameters, "U1")["driver"]
    current = netlist.PHASE_CURRENT_RMS_A if current_a is None else current_a
    resistance = (driver["rds_on_low_side_max_ohm"]["value"]
                  + driver["rds_on_high_side_max_ohm"]["value"])
    return 2.0 * current ** 2 * resistance


def driver_dissipation_w(parameters, current_a=None):
    """The datasheet's own measured dissipation, scaled to this current.

    The measurement is a whole-device figure at one current: conduction,
    switching, gate charge and the internal regulator together. Only the
    conduction term scales with the square of the current, so the rest is
    separated out at the datasheet's own operating point and carried across
    unchanged.
    """
    driver = rules._spec(parameters, "U1")["driver"]
    measured = driver["typical_dissipation_w"]["value"]
    at_current = driver["typical_dissipation_current_a"]["value"]
    current = netlist.PHASE_CURRENT_RMS_A if current_a is None else current_a
    conduction = driver_conduction_w(parameters, at_current)
    remainder = max(0.0, measured - conduction)
    return driver_conduction_w(parameters, current) + remainder


def regulator_dissipation_w(parameters):
    regulator = rules._spec(parameters, "U3")["regulator"]
    supply = rules.Supply(parameters)
    duty = supply.logic_rail_max_v / supply.motor_rail_max_v
    high = regulator["rds_on_high_side_ohm"]["value"]
    low = regulator["rds_on_low_side_ohm"]["value"]
    current = supply.logic_current_max_a
    return current ** 2 * (duty * high + (1.0 - duty) * low)


def blocking_dissipation_w(parameters):
    supply = rules.Supply(parameters)
    return supply.input_current_max_a ** 2 * supply.blocking_rds_ohm


def sense_dissipation_w(parameters):
    spec = rules._spec(parameters, "RS1")["resistor"]
    resistance = netlist.SENSE_RESISTANCE_OHM * (
        1.0 + spec["tolerance"]["value"])
    return netlist.PHASE_CURRENT_PEAK_A ** 2 * resistance


def inventory(parameters):
    supply = rules.Supply(parameters)
    resistors = sum(
        rules._resistor_worst_case_a(parameters, reference, supply) ** 2
        * rules._resistor_ohms(reference)
        for reference in rules._references("R"))
    indicators = sum(entry["measured_a"]
                     * rules._spec(parameters, "D10")["led"][
                         "forward_voltage_max_v"]["value"]
                     for entry in rules.evaluate_indicators(parameters)) * 2.0
    return {
        "driver": {
            "watts": driver_dissipation_w(parameters),
            "documents": ["tmc2226_trinamic"]},
        "sense_resistors": {
            "watts": 2.0 * sense_dissipation_w(parameters),
            "documents": ["shunt_1206_milliohm"]},
        "reverse_blocking_device": {
            "watts": blocking_dissipation_w(parameters),
            "documents": ["si9407bdy_vishay"]},
        "logic_regulator": {
            "watts": regulator_dissipation_w(parameters),
            "documents": ["lmr51430_ti"]},
        "resistor_networks": {
            "watts": resistors,
            "documents": ["res_0603_uniroyal"]},
        "indicators": {
            "watts": indicators,
            "documents": ["kt0603r_kento"]},
    }


def total_w(parameters):
    return sum(entry["watts"] for entry in inventory(parameters).values())


def driver_reference_board_rise_c(parameters):
    driver = rules._spec(parameters, "U1")
    return (driver_dissipation_w(parameters)
            * driver["theta_ja_c_per_w"]["value"])


def driver_ambient_ceiling_c(parameters):
    driver = rules._spec(parameters, "U1")
    return (driver["junction_max_c"]["value"]
            - driver_reference_board_rise_c(parameters))


def required_theta_ja_c_per_w(parameters):
    driver = rules._spec(parameters, "U1")
    budget = (driver["junction_max_c"]["value"]
              - netlist.CONTINUOUS_RATING_AMBIENT_C)
    return budget / driver_dissipation_w(parameters)


# ---------------------------------------------------------------------------
# what the toolkit's thermal domain is told

#: Copper's thermal conductivity, the only material property the spreading
#: solve reads that no catalogue on this board publishes.
COPPER_CONDUCTIVITY_W_PER_MK = 385.0

#: Still air, board mounted with no enclosure and no forced flow. It is an
#: environment statement, not a measurement, and the solve it feeds says so.
NATURAL_CONVECTION_W_PER_M2K = 10.0

#: Cells about 2 mm across on this outline.
BOARD_RISE_GRID = {"columns": 40, "rows": 32}


def _theta_record(spec, key, conditions_key=None):
    record = spec[key]
    # regime is stated, not assumed: every figure this board records
    # under a theta_ja key is a junction-to-ambient thermal RESISTANCE,
    # which is defined at thermal equilibrium; a transient figure would
    # be a Zth curve and lives under no such key in the frozen
    # parameters. The toolkit refuses a record that does not say.
    entry = {"value": record["value"], "units": "C/W",
             "regime": "steady_state",
             "source": record.get("document") or "datasheet"}
    document = record.get("document")
    if document:
        entry["document"] = document
    conditions = record.get("conditions")
    if conditions:
        entry["conditions"] = conditions
    return entry


def junction_parts(parameters=None):
    """Every part whose junction path this board's evidence can judge.

    A dissipating part with no stated junction-to-ambient resistance is
    not on this list: the toolkit reports an undeclared junction path as
    unjudged rather than as passing, and none of the passives' frozen
    datasheets state one. What they dissipate is therefore outside the
    spreading solve, and `omitted_dissipation_w` says how much.
    """
    parameters = parameters or rules.load_parameters()
    driver = rules._spec(parameters, "U1")
    regulator = rules._spec(parameters, "U3")
    blocking = rules._spec(parameters, "Q1")["fet"]
    clamp = rules._spec(parameters, "D1")
    clamp_w = (clamp["tvs"]["reverse_leakage_max_a"]["value"]
               * netlist.INPUT_SURVIVAL_MAX_V)
    return {
        "U1": {
            "dissipation_w": driver_dissipation_w(parameters),
            "junction_max_c": driver["junction_max_c"]["value"],
            "theta_ja": _theta_record(driver, "theta_ja_c_per_w"),
            "documents": ["tmc2226_trinamic"],
        },
        "U3": {
            "dissipation_w": regulator_dissipation_w(parameters),
            "junction_max_c": regulator["junction_max_c"]["value"],
            "theta_ja": _theta_record(regulator, "theta_ja_c_per_w"),
            "documents": ["lmr51430_ti"],
        },
        "Q1": {
            "dissipation_w": blocking_dissipation_w(parameters),
            "junction_max_c": blocking["junction_max_c"]["value"],
            "theta_ja": _theta_record(blocking, "theta_ja_max_c_per_w"),
            "documents": ["si9407bdy_vishay"],
        },
        "D1": {
            "dissipation_w": clamp_w,
            "junction_max_c": clamp["junction_max_c"]["value"],
            "theta_ja": _theta_record(clamp, "theta_ja_c_per_w"),
            "documents": ["smbj_littelfuse"],
        },
    }


def omitted_dissipation_w(parameters=None):
    """Heat the spreading solve is not given, because it has no junction."""
    parameters = parameters or rules.load_parameters()
    return total_w(parameters) - sum(
        entry["dissipation_w"]
        for entry in junction_parts(parameters).values())


def lowest_stated_ambient_rating_c(parameters=None):
    """The least tolerant part's own stated ambient ceiling."""
    parameters = parameters or rules.load_parameters()
    ceilings = []
    for reference, part in sorted(netlist.PARTS.items()):
        mpn = part["mpn"]
        if mpn is None:
            continue
        spec = parameters["parts"][mpn]
        for holder in (spec, spec.get("connector") or {},
                       spec.get("led") or {}, spec.get("capacitor") or {},
                       spec.get("resistor") or {},
                       spec.get("inductor") or {}, spec.get("tvs") or {}):
            record = holder.get("ambient_max_c")
            if record is not None:
                ceilings.append(record["value"])
                break
    return min(ceilings)


def board_rise_budget_c(parameters=None):
    """What the copper may rise before a part sits above its own rating.

    Not a target chosen for the answer: it is the headroom the least
    tolerant part on this board has above the declared maximum ambient.
    """
    return lowest_stated_ambient_rating_c(parameters) - netlist.AMBIENT_MAX_C


def manifest_block(parameters=None):
    parameters = parameters or rules.load_parameters()
    return {
        "ambient_c": netlist.AMBIENT_MAX_C,
        "conductivity_w_per_mk": COPPER_CONDUCTIVITY_W_PER_MK,
        "parts": junction_parts(parameters),
        "board_rise": {
            "grid": dict(BOARD_RISE_GRID),
            "convection_w_per_m2k": NATURAL_CONVECTION_W_PER_M2K,
            "copper_thickness_mm": layout_copper_thickness_mm(),
            "budget_c": board_rise_budget_c(parameters),
        },
    }


def layout_copper_thickness_mm():
    """The per-layer thickness the solve's one node should carry.

    The spreading solve is one node deep and multiplies what it is given
    by the copper layer count, so the figure that reproduces this board's
    real copper is the mean of the four finished thicknesses, not the
    outer foil: the inner layers are less than half the outer ones and
    quoting the outer figure would give the board copper it does not have.
    """
    from . import geometry
    thicknesses = list(geometry.copper_thickness_mm().values())
    return sum(thicknesses) / len(thicknesses)


# ---------------------------------------------------------------------------

def evaluate_driver_junction(parameters):
    driver = rules._spec(parameters, "U1")
    conduction = driver_conduction_w(parameters)
    dissipation = driver_dissipation_w(parameters)
    budget_c = (driver["junction_max_c"]["value"]
                - netlist.CONTINUOUS_RATING_AMBIENT_C)
    rise_c = driver_reference_board_rise_c(parameters)
    conditions = driver["theta_ja_c_per_w"]["conditions"]
    return [
        {"id": "driver_conduction_loss_at_the_required_phase_current",
         "identity": "U1",
         "measured_w": conduction,
         "claim": rules._claim(
             "U1", "W", "thermal", conduction, rules.DIRECT,
             ("tmc2226_trinamic",),
             rules._requirement("below_the_whole_device_estimate", "<=",
                                dissipation),
             scope_level="group",
             assumptions=(
                 "both bridges carry the required RMS phase current through "
                 "the sum of the datasheet's maximum high-side and low-side "
                 "on-resistances at 25 degC",),
             omissions=(
                 "switching loss, gate charge, the internal regulator and "
                 "the rise of on-resistance with junction temperature, so "
                 "this is a lower bound on the driver's dissipation",))},
        {"id": "driver_dissipation_at_the_required_phase_current",
         "identity": "U1",
         "measured_w": dissipation,
         "claim": rules._claim(
             "U1", "W", "thermal", dissipation, rules.DIRECT,
             ("tmc2226_trinamic",),
             rules._requirement("within_the_reference_board_budget", "<=",
                                budget_c
                                / driver["theta_ja_c_per_w"]["value"]),
             scope_level="group",
             assumptions=(
                 "the datasheet's own measured %g W at %g A RMS two-phase "
                 "sine at 24 V is separated into the conduction term, which "
                 "scales with the square of the current, and a remainder "
                 "that is carried across unchanged"
                 % (driver["driver"]["typical_dissipation_w"]["value"],
                    driver["driver"]["typical_dissipation_current_a"]
                    ["value"]),
                 "the budget is the junction headroom above the declared "
                 "%g degC continuous-rating ambient divided by the "
                 "datasheet's junction-to-ambient figure"
                 % netlist.CONTINUOUS_RATING_AMBIENT_C),
             omissions=(
                 "this board's own junction-to-ambient path, which is "
                 "neither the datasheet's board nor its copper",))},
        {"id": "driver_junction_margin_on_the_datasheet_reference_board",
         "identity": "U1",
         "measured_factor": budget_c / rise_c,
         "claim": rules._claim(
             "U1", "x", "thermal", budget_c / rise_c, rules.DIRECT,
             ("tmc2226_trinamic",),
             rules._requirement("at_or_above_the_reference_board", ">=", 1.0),
             scope_level="group",
             assumptions=(
                 "the factor is how many times worse this board's "
                 "junction-to-ambient path could be than the datasheet's "
                 "before the junction limit is reached at the declared "
                 "continuous-rating ambient",
                 "the datasheet figure is measured on %s, which is neither "
                 "this board nor this copper" % conditions.split(" as ")[0]))},
        {"id": "ambient_where_the_reference_board_reaches_the_limit",
         "identity": "U1",
         "measured_c": driver_ambient_ceiling_c(parameters),
         "claim": rules._claim(
             "U1", "degC", "thermal", driver_ambient_ceiling_c(parameters),
             rules.DIRECT, ("tmc2226_trinamic",),
             rules._requirement("at_or_above_the_continuous_rating_ambient",
                                ">=", netlist.CONTINUOUS_RATING_AMBIENT_C),
             scope_level="group",
             assumptions=("the same reference-board thermal path, solved for "
                          "the ambient rather than for the junction",))},
        {"id": "board_thermal_resistance_to_ambient",
         "identity": "U1",
         "measured_c_per_w": None,
         "claim": rules._claim(
             "U1", "degC/W", "thermal", None, rules.ASSUMED,
             ("tmc2226_trinamic",),
             rules._requirement("at_or_below_the_required_path", "<=",
                                required_theta_ja_c_per_w(parameters)),
             scope_level="group",
             assumptions=(
                 "the requirement is the junction headroom above the "
                 "declared continuous-rating ambient divided by the "
                 "estimated dissipation",
                 "the board carries four copper layers, two of them "
                 "unbroken reference, and the exposed pad reaches them "
                 "through a via array; none of that is a number until it is "
                 "solved or measured"),
             omissions=(
                 "the junction-to-ambient resistance of this board: "
                 "THERMAL.BOARD_RISE solves the copper's own spreading and "
                 "not the package's path into it, so the junction "
                 "temperature at the required phase current is still not "
                 "established and physical test is what would establish it",
                 "airflow: still air is neither assumed nor established, "
                 "and the mounting orientation is not specified"))},
    ]


def evaluate_ambient_coverage(parameters):
    stated, unstated, violations = [], [], []
    for reference, part in sorted(netlist.PARTS.items()):
        mpn = part["mpn"]
        if mpn is None:
            continue
        spec = parameters["parts"][mpn]
        ceiling, document = None, None
        for holder in (spec, spec.get("connector") or {},
                       spec.get("led") or {}, spec.get("capacitor") or {},
                       spec.get("resistor") or {},
                       spec.get("inductor") or {}, spec.get("tvs") or {}):
            record = holder.get("ambient_max_c")
            if record is not None:
                ceiling, document = record["value"], record.get("document")
                break
            record = (holder.get("ambient_temperature_c") or {}).get("max")
            if record is not None:
                ceiling, document = record["value"], record.get("document")
                break
        if ceiling is None:
            if "junction_max_c" in spec or "junction_max_c" in (
                    spec.get("fet") or {}):
                continue
            unstated.append(mpn)
            continue
        stated.append((reference, mpn, ceiling, document))
        if ceiling < netlist.AMBIENT_MAX_C:
            violations.append("%s (%s) is rated to %g degC"
                              % (reference, mpn, ceiling))
    documents = sorted({row[3] for row in stated if row[3]})
    results = [{
        "id": "every_stated_ambient_rating_covers_the_declared_maximum",
        "identity": "board",
        "measured": len(violations),
        "claim": rules._structural(
            "board", "thermal", violations,
            "covers_the_declared_maximum_ambient", documents,
            basis=rules.DIRECT)}]
    if unstated:
        results.append({
            "id": "parts_whose_datasheet_states_no_ambient_rating",
            "identity": "board",
            "measured": len(sorted(set(unstated))),
            "claim": rules._claim(
                "board", "degC", "thermal", None, rules.ASSUMED, (),
                rules._requirement("an_ambient_rating_is_established", ">=",
                                   netlist.AMBIENT_MAX_C),
                scope_level="board",
                omissions=("the ambient rating of %s, whose frozen "
                           "datasheet states none"
                           % ", ".join(sorted(set(unstated))),))})
    return results


def evaluate_junction_paths(parameters):
    supply = rules.Supply(parameters)
    results = []
    clamp = rules._spec(parameters, "D1")
    clamp_w = (clamp["tvs"]["reverse_leakage_max_a"]["value"]
               * netlist.INPUT_SURVIVAL_MAX_V)
    for identity, spec, watts, document, detail in (
            ("Q1", rules._spec(parameters, "Q1")["fet"],
             blocking_dissipation_w(parameters), "si9407bdy_vishay",
             "carrying the board's rated input current at the on-resistance "
             "the gate divider's drive gives it"),
            ("D1", clamp, clamp_w, "smbj_littelfuse",
             "conducting its stated maximum reverse leakage at the declared "
             "input survival voltage, which is all it carries until it "
             "clamps"),):
        budget_c = spec["junction_max_c"]["value"] - netlist.AMBIENT_MAX_C
        theta = spec.get("theta_ja_max_c_per_w") or spec["theta_ja_c_per_w"]
        rise_c = watts * theta["value"]
        results.append({
            "id": "junction_margin_on_the_datasheet_reference_board",
            "identity": identity,
            "measured_factor": budget_c / rise_c,
            "claim": rules._claim(
                identity, "x", "thermal", budget_c / rise_c, rules.DIRECT,
                (document,),
                rules._requirement("at_or_above_the_reference_board", ">=",
                                   1.0),
                scope_level="group",
                assumptions=(
                    "the part is %s" % detail,
                    "the factor is how many times worse this board's "
                    "junction-to-ambient path could be than the datasheet's "
                    "test board before the junction limit is reached at the "
                    "declared maximum ambient"))})
    del supply
    return results


def evaluate_all(parameters):
    results = []
    for producer in (evaluate_driver_junction, evaluate_ambient_coverage,
                     evaluate_junction_paths):
        results.extend(producer(parameters))
    return results


# ---------------------------------------------------------------------------

def document(parameters=None):
    parameters = parameters or rules.load_parameters()
    return {
        "kind": "thermal-estimate",
        "estimate_class": "a dissipation inventory and package-limit "
                          "derating at declared ambients. No thermal solve, "
                          "no copper spreading model, no airflow assumption, "
                          "and therefore no board temperature and no "
                          "junction temperature.",
        "declared_max_ambient_c": netlist.AMBIENT_MAX_C,
        "continuous_rating_ambient_c": netlist.CONTINUOUS_RATING_AMBIENT_C,
        "dissipation_w": inventory(parameters),
        "total_w": total_w(parameters),
        "driver": {
            "conduction_w": driver_conduction_w(parameters),
            "estimated_w": driver_dissipation_w(parameters),
            "reference_board_rise_c":
                driver_reference_board_rise_c(parameters),
            "reference_board_ambient_ceiling_c":
                driver_ambient_ceiling_c(parameters),
            "required_theta_ja_c_per_w":
                required_theta_ja_c_per_w(parameters),
        },
        "not_established": [
            "board temperature rise above ambient",
            "junction temperature of any part",
            "airflow and mounting orientation",
            "the temperature of the sense resistors at full phase current",
        ],
        "context": {"generated_by": "design/thermal.py"},
    }


def write(path=None):
    target = path or os.environ.get("PCBQA_OUT") or REPORT_PATH
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    return target


if __name__ == "__main__":
    parameters = rules.load_parameters()
    for name, entry in sorted(inventory(parameters).items(),
                              key=lambda item: -item[1]["watts"]):
        sys.stdout.write("  %-28s %8.4f W\n" % (name, entry["watts"]))
    sys.stdout.write("  %-28s %8.4f W\n" % ("total", total_w(parameters)))
    sys.stdout.write(
        "\ndriver conduction %.3f W, estimated %.3f W, reference-board rise "
        "%.1f K\nreference-board ambient ceiling %.1f degC, required "
        "theta_JA %.1f K/W\n"
        % (driver_conduction_w(parameters), driver_dissipation_w(parameters),
           driver_reference_board_rise_c(parameters),
           driver_ambient_ceiling_c(parameters),
           required_theta_ja_c_per_w(parameters)))
    sys.stdout.write(write() + "\n")
