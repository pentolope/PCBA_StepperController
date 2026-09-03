from __future__ import annotations

import json
import math
import os
import re
import sys

from . import ksym, libraries, netlist

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMETERS_PATH = os.path.join(REPO_ROOT, "components", "parameters.json")
CATALOG_PATH = os.path.join(REPO_ROOT, "components", "jlcpcb.json")
TOOLKIT_ROOT = os.path.join(REPO_ROOT, "tooling", "PCBA_AutoDesignAndTest")
FOOTPRINT_ROOT = "/usr/share/kicad/footprints"
LOCAL_FOOTPRINT_ROOT = os.path.join(REPO_ROOT, "library")

if TOOLKIT_ROOT not in sys.path:
    sys.path.insert(0, TOOLKIT_ROOT)

from pcbqa import claim  # noqa: E402

DIRECT = "direct"
ASSUMED = "assumed"
DERIVED = "derived"

EVIDENCE_CLASSES = {
    DIRECT: "datasheet-behavioral",
    ASSUMED: "assumed-behavioral",
    DERIVED: "design-source",
}

BRIEF = "BRIEF.md"

ROOT2 = math.sqrt(2.0)


def load_parameters():
    with open(PARAMETERS_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_catalog():
    with open(CATALOG_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _mpn(reference):
    return netlist.PARTS[reference]["mpn"]


def _spec(parameters, reference):
    return parameters["parts"][_mpn(reference)]


def _evidence(basis, documents, phenomenon="device_electrical",
              assumptions=(), omissions=()):
    provenance = {"source": "components/parameters.json",
                  "documents": sorted(set(documents))}
    return claim.evidence(
        phenomenon, EVIDENCE_CLASSES.get(basis, "design-source"), provenance,
        assumptions=list(assumptions), omitted_contributions=list(omissions))


def _requirement(name, op, value, source=BRIEF):
    return claim.requirement(name, source, {"op": op, "value": value})


_BOUND_FOR_OPERATOR = {">=": claim.LOWER_BOUND, ">": claim.LOWER_BOUND,
                       "<=": claim.UPPER_BOUND, "<": claim.UPPER_BOUND}


def _claim(identity, units, significance, value, basis, documents,
           requirement, knowledge=None, scope_level="net", assumptions=(),
           omissions=(), phenomenon="device_electrical"):
    if value is None:
        return claim.claim(
            scope_level, identity, units, claim.UNKNOWN, {},
            _evidence(basis, documents, phenomenon, assumptions, omissions),
            significance, None, requirement)
    if knowledge is None:
        if basis == ASSUMED or omissions:
            knowledge = _BOUND_FOR_OPERATOR.get(
                requirement["assertion"]["op"], claim.APPROXIMATE)
        else:
            knowledge = claim.EXACT
    basis_record = None
    if knowledge != claim.EXACT:
        basis_record = claim.knowledge_basis(
            basis, "datasheet_limit" if basis == DIRECT else basis)
    return claim.claim(
        scope_level, identity, units, knowledge, {"value": value},
        _evidence(basis, documents, phenomenon, assumptions, omissions),
        significance, basis_record, requirement)


def _structural(identity, significance, violations, requirement_name,
                documents=(), basis=DERIVED, assumptions=(), omissions=()):
    return _claim(identity, "violations", significance, float(len(violations)),
                  basis, documents, _requirement(requirement_name, "<=", 0.0),
                  scope_level="board", assumptions=assumptions,
                  omissions=omissions)


_VALUE_SUFFIX = {"R": 1.0, "k": 1e3, "M": 1e6}


def _resistor_ohms(reference):
    value = netlist.PARTS[reference]["value"]
    if value == "100mR":
        return netlist.SENSE_RESISTANCE_OHM
    for suffix, scale in _VALUE_SUFFIX.items():
        if value.endswith(suffix):
            return float(value[:-len(suffix)]) * scale
    raise ValueError("resistor %s carries the unparsable value %r"
                     % (reference, value))


def _capacitance_farads(reference):
    value = netlist.PARTS[reference]["value"]
    for suffix, scale in (("uF", 1e-6), ("nF", 1e-9), ("pF", 1e-12)):
        if value.endswith(suffix):
            return float(value[:-len(suffix)]) * scale
    raise ValueError("capacitor %s carries the unparsable value %r"
                     % (reference, value))


def _tolerance(parameters, reference, block):
    entry = _spec(parameters, reference)[block].get("tolerance")
    return 0.0 if entry is None else entry["value"]


def _references(prefix):
    pattern = re.compile(r"^%s\d+$" % prefix)
    return sorted((reference for reference in netlist.PARTS
                   if pattern.match(reference)),
                  key=lambda name: int(name[len(prefix):]))


# ---------------------------------------------------------------------------

class Supply:
    """Worst-case rail values, from the parameters and the design source."""

    def __init__(self, parameters):
        self.parameters = parameters
        driver = _spec(parameters, "U1")
        regulator = _spec(parameters, "U3")["regulator"]
        fet = _spec(parameters, "Q1")["fet"]

        self.input_min_v = netlist.INPUT_SUPPLY["min_v"]
        self.input_max_v = netlist.INPUT_SUPPLY["max_v"]
        self.input_current_max_a = netlist.INPUT_CURRENT_RATING_A

        # The gate divider holds VGS at half the rail, so the on-resistance
        # is bounded by the lowest gate drive the datasheet characterises.
        self.blocking_rds_ohm = fet["rds_on_ohm"]["4.5"]["value"]
        self.blocking_gate_v = self.input_max_v / 2.0

        self.motor_rail_min_v = (self.input_min_v
                                 - self.input_current_max_a
                                 * self.blocking_rds_ohm)
        self.motor_rail_max_v = self.input_max_v

        reference = regulator["reference_v"]
        upper = _resistor_ohms("R5")
        lower = _resistor_ohms("R6")
        tolerance = _tolerance(parameters, "R5", "resistor")
        self.logic_rail_min_v = reference["min"]["value"] * (
            1.0 + upper * (1.0 - tolerance) / (lower * (1.0 + tolerance)))
        self.logic_rail_max_v = reference["max"]["value"] * (
            1.0 + upper * (1.0 + tolerance) / (lower * (1.0 - tolerance)))
        self.logic_current_max_a = netlist.LOGIC_CURRENT_MAX_A

        self.enable_rail_on_max_v = (
            regulator["enable_rising_v"]["max"]["value"]
            * (_resistor_ohms("R3") + _resistor_ohms("R4"))
            / _resistor_ohms("R4"))
        self.enable_rail_off_min_v = (
            regulator["enable_falling_v"]["min"]["value"]
            * (_resistor_ohms("R3") + _resistor_ohms("R4"))
            / _resistor_ohms("R4"))

        self.driver_vcc_io_min_v = driver["supply"]["vcc_io"]["min"]["value"]
        self.driver_vcc_io_max_v = driver["supply"]["vcc_io"]["max"]["value"]
        self.driver_vs_min_v = driver["supply"]["vs"]["min"]["value"]
        self.driver_vs_max_v = driver["supply"]["vs"]["max"]["value"]
        self.driver_vs_absolute_v = \
            driver["supply"]["vs_absolute_max"]["value"]

    def bulk_capacitance_min_f(self):
        total = 0.0
        for reference in netlist.BULK_REFERENCES:
            spec = _spec(self.parameters, reference)["capacitor"]
            total += spec["capacitance_f"]["value"] * (
                1.0 - spec["tolerance"]["value"])
        return total


def phase_current_rms_a(parameters, scale, sense_ohm=None, tolerance=0.0):
    """The driver's own current formula at one current-scale setting."""
    driver = _spec(parameters, "U1")["driver"]
    sense = netlist.SENSE_RESISTANCE_OHM if sense_ohm is None else sense_ohm
    internal = driver["sense_internal_resistance_ohm"]["value"]
    full_scale = driver["sense_full_scale_v"]["value"]
    return ((scale + 1.0) / 32.0 * full_scale / (sense + internal) / ROOT2
            * (1.0 + tolerance))


def programmed_scale(parameters):
    """The current-scale setting whose current is nearest the requirement."""
    best, distance = None, None
    for scale in range(netlist.CURRENT_SCALE_MIN,
                       netlist.CURRENT_SCALE_MAX + 1):
        error = abs(phase_current_rms_a(parameters, scale)
                    - netlist.PHASE_CURRENT_RMS_A)
        if distance is None or error < distance:
            best, distance = scale, error
    return best


# ---------------------------------------------------------------------------
# component selection

def _driver_requirements_failed(entry):
    failures = []
    if entry["continuous_rms_current_a"] < netlist.PHASE_CURRENT_RMS_A:
        failures.append("continuous phase current")
    if not entry["external_sense_resistors"]:
        failures.append("external sense resistors")
    if not entry["quiet_chopper"]:
        failures.append("quiet chopper")
    return failures


def evaluate_driver_selection(parameters):
    del parameters
    results = []
    selected = [name for name, entry in netlist.DRIVER_CANDIDATES.items()
                if entry["selected"]]
    documents = sorted(entry["document"]
                       for entry in netlist.DRIVER_CANDIDATES.values())
    results.append({
        "id": "exactly_one_driver_is_selected",
        "identity": "driver_selection",
        "measured": len(selected),
        "claim": _claim(
            "driver_selection", "devices", "component_selection",
            float(len(selected)), DERIVED, documents,
            _requirement("one_selected_driver", "<=", 1.0),
            scope_level="board")})
    for name, entry in sorted(netlist.DRIVER_CANDIDATES.items()):
        failures = _driver_requirements_failed(entry)
        if entry["selected"]:
            requirement = _requirement(
                "meets_every_selection_requirement", "<=", 0.0)
        else:
            requirement = _requirement(
                "fails_at_least_one_selection_requirement", ">=", 1.0)
        results.append({
            "id": "driver_candidate_against_the_selection_requirements",
            "identity": name,
            "measured": len(failures),
            "failed_requirements": failures,
            "continuous_rms_current_a": entry["continuous_rms_current_a"],
            "external_sense_resistors": entry["external_sense_resistors"],
            "claim": _claim(
                name, "requirements", "component_selection",
                float(len(failures)), DIRECT, (entry["document"],),
                requirement, scope_level="group",
                assumptions=(
                    "the requirements are the brief's own: at least %g A RMS "
                    "per phase continuously, external sense resistors, and "
                    "quiet microstepping" % netlist.PHASE_CURRENT_RMS_A,
                    "the continuous current figure is each device's own RMS "
                    "coil-current design guideline"))})
    return results


# ---------------------------------------------------------------------------
# phase current and current sensing

def evaluate_phase_current(parameters):
    driver = _spec(parameters, "U1")["driver"]
    tolerance = driver["current_full_scale_tolerance"]["value"]
    sense_tolerance = _tolerance(parameters, "RS1", "resistor")
    highest = phase_current_rms_a(
        parameters, netlist.CURRENT_SCALE_MAX,
        netlist.SENSE_RESISTANCE_OHM * (1.0 + sense_tolerance), -tolerance)
    lowest = phase_current_rms_a(
        parameters, netlist.CURRENT_SCALE_MIN,
        netlist.SENSE_RESISTANCE_OHM * (1.0 - sense_tolerance), tolerance)
    documents = ("tmc2226_trinamic", "shunt_1206_milliohm")
    tempco = (_spec(parameters, "RS1")["resistor"]["tempco_per_c"]["value"]
              * (netlist.SENSE_RESISTOR_TEMPERATURE_C - 25.0))
    budget = (tolerance + sense_tolerance + tempco
              + netlist.SENSE_INTERCONNECT_BUDGET)
    return [
        {"id": "the_driver_rating_covers_the_required_phase_current",
         "identity": "U1",
         "measured_a": driver["irms_continuous_max_a"]["value"],
         "claim": _claim(
             "U1", "A", "phase_current",
             driver["irms_continuous_max_a"]["value"], DIRECT,
             ("tmc2226_trinamic",),
             _requirement("covers_the_required_phase_current", ">=",
                          netlist.PHASE_CURRENT_RMS_A),
             assumptions=("the datasheet gives this as a continuous RMS "
                          "coil-current design guideline rather than a "
                          "tested limit",))},
        {"id": "the_sense_network_reaches_the_required_phase_current",
         "identity": "RS1,RS2",
         "measured_a": highest,
         "claim": _claim(
             "RS1,RS2", "A", "phase_current", highest, DIRECT, documents,
             _requirement("reaches_the_required_phase_current", ">=",
                          netlist.PHASE_CURRENT_RMS_A),
             scope_level="group",
             assumptions=("the shunt at the top of its tolerance and the "
                          "driver's full-scale current at the bottom of its "
                          "stated tolerance, which is the combination that "
                          "delivers least",),
             omissions=("the driver's internal 20 mohm sense path is stated "
                        "as a typical value with no tolerance, so its "
                        "contribution to the denominator is not bounded",))},
        {"id": "the_sense_network_programs_below_the_required_current",
         "identity": "RS1,RS2",
         "measured_a": lowest,
         "claim": _claim(
             "RS1,RS2", "A", "phase_current", lowest, DIRECT, documents,
             _requirement("programs_below_the_required_current", "<=",
                          netlist.PHASE_CURRENT_RMS_A),
             scope_level="group",
             assumptions=("the smallest current scale the driver offers, "
                          "with the shunt and the driver tolerance at the "
                          "combination that delivers most",),
             omissions=("the driver's internal sense path tolerance",))},
        {"id": "the_phase_current_accuracy_budget",
         "identity": "RS1,RS2",
         "measured": budget,
         "claim": _claim(
             "RS1,RS2", "fraction", "phase_current", budget, DIRECT,
             documents,
             _requirement("inside_the_recorded_accuracy_budget", "<=",
                          netlist.SENSE_ACCURACY_BUDGET),
             scope_level="group",
             assumptions=(
                 "the four terms are added rather than combined in "
                 "quadrature, which overstates the spread",
                 "the sense conductor's own resistance is carried at its "
                 "declared allowance of %g; the routed board's actual "
                 "figure is what the post-layout stage measures"
                 % netlist.SENSE_INTERCONNECT_BUDGET,
                 "the shunt's temperature coefficient is applied over the "
                 "span from its 25 degC tolerance reference to the declared "
                 "%g degC shunt temperature"
                 % netlist.SENSE_RESISTOR_TEMPERATURE_C),
             omissions=(
                 "the shunt's own temperature at full phase current, which "
                 "no thermal solve or measurement on this board "
                 "establishes",
                 "the tolerance of the driver's internal sense path"))},
    ]


def evaluate_sense_dissipation(parameters):
    spec = _spec(parameters, "RS1")["resistor"]
    resistance = netlist.SENSE_RESISTANCE_OHM * (
        1.0 + spec["tolerance"]["value"])
    dissipation = netlist.PHASE_CURRENT_PEAK_A ** 2 * resistance
    knee = spec["full_rating_ambient_max_c"]["value"]
    zero = spec["zero_power_ambient_c"]["value"]
    ambient = netlist.AMBIENT_MAX_C
    rating = spec["power_max_w"]["value"]
    if ambient > knee:
        rating *= (zero - ambient) / (zero - knee)
    return [
        {"id": "the_shunt_carries_the_peak_phase_current_continuously",
         "identity": "RS1,RS2",
         "measured_w": dissipation,
         "claim": _claim(
             "RS1,RS2", "W", "dissipation", dissipation, DIRECT,
             ("shunt_1206_milliohm", "tmc2226_trinamic"),
             _requirement("within_the_derated_power_rating", "<=", rating),
             scope_level="group",
             assumptions=(
                 "the worst case is standstill at a microstep position where "
                 "one phase carries the full sine peak, which the shunt then "
                 "carries continuously",
                 "the rating is the datasheet's own derating line evaluated "
                 "at the board's declared maximum ambient of %g degC"
                 % ambient))},
        {"id": "the_shunt_current_rating_covers_the_peak_phase_current",
         "identity": "RS1,RS2",
         "measured_a": netlist.PHASE_CURRENT_PEAK_A,
         "claim": _claim(
             "RS1,RS2", "A", "phase_current", netlist.PHASE_CURRENT_PEAK_A,
             DIRECT, ("shunt_1206_milliohm",),
             _requirement("within_the_shunt_current_rating", "<=",
                          spec["current_max_a"]["value"]),
             scope_level="group")},
        {"id": "the_shunt_is_a_low_inductance_type",
         "identity": "RS1,RS2",
         "measured": spec["low_inductance"]["value"],
         "claim": _claim(
             "RS1,RS2", "boolean", "phase_current",
             spec["low_inductance"]["value"], DIRECT,
             ("shunt_1206_milliohm",),
             _requirement("declared_low_inductance", ">=", 1.0),
             scope_level="group",
             assumptions=("the specification states low inductance as a "
                          "product feature and gives no figure, so the "
                          "requirement is met by declaration and not by a "
                          "bounded inductance",))},
    ]


# ---------------------------------------------------------------------------
# rails

def evaluate_rails(parameters):
    supply = Supply(parameters)
    driver = _spec(parameters, "U1")
    mcu = _spec(parameters, "U2")
    regulator = _spec(parameters, "U3")
    results = [
        {"id": "the_motor_rail_stays_inside_the_driver_supply_range",
         "identity": "VM",
         "measured_v": supply.motor_rail_min_v,
         "claim": _claim(
             "VM", "V", "rail", supply.motor_rail_min_v, DERIVED,
             ("tmc2226_trinamic", "si9407bdy_vishay"),
             _requirement("at_or_above_the_driver_minimum_supply", ">=",
                          supply.driver_vs_min_v),
             assumptions=(
                 "the lowest declared input less the reverse-blocking "
                 "device's drop at the board's rated input current, taken "
                 "at the on-resistance the datasheet states for the lowest "
                 "gate drive it characterises",))},
        {"id": "the_motor_rail_stays_inside_the_driver_supply_range",
         "identity": "VM_max",
         "measured_v": supply.motor_rail_max_v,
         "claim": _claim(
             "VM", "V", "rail", supply.motor_rail_max_v, DERIVED,
             ("tmc2226_trinamic",),
             _requirement("at_or_below_the_driver_maximum_supply", "<=",
                          supply.driver_vs_max_v))},
        {"id": "the_logic_rail_stays_inside_the_controller_supply_range",
         "identity": "+3V3_min",
         "measured_v": supply.logic_rail_min_v,
         "claim": _claim(
             "+3V3", "V", "rail", supply.logic_rail_min_v, DIRECT,
             ("lmr51430_ti", "res_0603_uniroyal"),
             _requirement("at_or_above_the_controller_minimum", ">=",
                          mcu["supply"]["min"]["value"]),
             assumptions=(
                 "the regulator's reference at the bottom of its stated "
                 "range with the feedback divider at the tolerance corner "
                 "that programs least",))},
        {"id": "the_logic_rail_stays_inside_the_controller_supply_range",
         "identity": "+3V3_max",
         "measured_v": supply.logic_rail_max_v,
         "claim": _claim(
             "+3V3", "V", "rail", supply.logic_rail_max_v, DIRECT,
             ("lmr51430_ti", "res_0603_uniroyal"),
             _requirement("at_or_below_the_controller_maximum", "<=",
                          mcu["supply"]["max"]["value"]))},
        {"id": "the_logic_rail_stays_inside_the_driver_io_supply_range",
         "identity": "VCC_IO_min",
         "measured_v": supply.logic_rail_min_v,
         "claim": _claim(
             "+3V3", "V", "rail", supply.logic_rail_min_v, DIRECT,
             ("lmr51430_ti", "tmc2226_trinamic"),
             _requirement("at_or_above_the_driver_io_minimum", ">=",
                          supply.driver_vcc_io_min_v))},
        {"id": "the_logic_rail_stays_inside_the_driver_io_supply_range",
         "identity": "VCC_IO_max",
         "measured_v": supply.logic_rail_max_v,
         "claim": _claim(
             "+3V3", "V", "rail", supply.logic_rail_max_v, DIRECT,
             ("lmr51430_ti", "tmc2226_trinamic"),
             _requirement("at_or_below_the_driver_io_maximum", "<=",
                          supply.driver_vcc_io_max_v))},
        {"id": "the_regulator_starts_below_the_declared_minimum_input",
         "identity": "BUCK_EN",
         "measured_v": supply.enable_rail_on_max_v,
         "claim": _claim(
             "BUCK_EN", "V", "rail", supply.enable_rail_on_max_v, DIRECT,
             ("lmr51430_ti", "res_0603_uniroyal"),
             _requirement("below_the_declared_minimum_input", "<=",
                          netlist.INPUT_SUPPLY["min_v"]),
             assumptions=("the enable threshold at the top of its stated "
                          "range with the divider at its nominal ratio",),
             omissions=("the divider resistors' tolerance, which moves the "
                        "threshold by at most the resistor tolerance",))},
        {"id": "the_regulator_input_rating_covers_the_declared_input",
         "identity": "U3",
         "measured_v": netlist.INPUT_SURVIVAL_MAX_V,
         "claim": _claim(
             "VM", "V", "rail", netlist.INPUT_SURVIVAL_MAX_V, DIRECT,
             ("lmr51430_ti",),
             _requirement("within_the_regulator_supply_range", "<=",
                          regulator["supply"]["max"]["value"]))},
        {"id": "the_driver_supply_current_is_inside_the_input_rating",
         "identity": "U1",
         "measured_a": driver["supply_current_max_a"]["value"],
         "claim": _claim(
             "VM", "A", "rail", driver["supply_current_max_a"]["value"],
             DIRECT, ("tmc2226_trinamic",),
             _requirement("within_the_board_input_current_rating", "<=",
                          netlist.INPUT_CURRENT_RATING_A),
             assumptions=("the driver's own quiescent draw; the current the "
                          "motor takes is the load's and is bounded by the "
                          "board's declared input rating instead",))},
    ]
    return results


# ---------------------------------------------------------------------------
# protection

def evaluate_reverse_polarity(parameters):
    fet = _spec(parameters, "Q1")["fet"]
    mapping = netlist.pin_to_net()
    drains = {mapping["Q1.%s" % pin] for pin in netlist.PFET_DRAIN_PINS}
    sources = {mapping["Q1.%s" % pin] for pin in netlist.PFET_SOURCE_PINS}
    orientation = []
    if drains != {"VM_IN"}:
        orientation.append("drain is not on the input conductor")
    if sources != {"VM"}:
        orientation.append("source is not on the protected rail")
    bridging = sorted(
        pin for pin in netlist.NETS["VM_IN"]
        if pin.split(".")[0] not in ("J1", "Q1")
        and not pin.startswith("#FLG"))
    gate_v = netlist.INPUT_SURVIVAL_MAX_V / 2.0
    return [
        {"id": "the_blocking_device_faces_the_input",
         "identity": "Q1",
         "measured": len(orientation),
         "claim": _structural(
             "Q1", "reverse_polarity", orientation,
             "the_body_diode_blocks_a_reversed_input",
             ("si9407bdy_vishay",),
             assumptions=("with the drain on the input conductor and the "
                          "source on the protected rail, a reversed input "
                          "reverse-biases the body diode",))},
        {"id": "nothing_else_bridges_the_input_conductor",
         "identity": "VM_IN",
         "measured": len(bridging),
         "claim": _structural(
             "VM_IN", "reverse_polarity", bridging,
             "no_component_other_than_the_terminal_and_the_blocking_device",
             ())},
        {"id": "the_blocking_device_stands_off_a_reversed_input",
         "identity": "Q1",
         "measured_v": netlist.INPUT_SURVIVAL_MAX_V,
         "claim": _claim(
             "Q1", "V", "reverse_polarity", netlist.INPUT_SURVIVAL_MAX_V,
             DIRECT, ("si9407bdy_vishay",),
             _requirement("within_the_drain_source_rating", "<=",
                          fet["vds_max_v"]["value"]))},
        {"id": "the_gate_divider_holds_the_gate_inside_its_rating",
         "identity": "Q1",
         "measured_v": gate_v,
         "claim": _claim(
             "Q1", "V", "reverse_polarity", gate_v, DERIVED,
             ("si9407bdy_vishay", "res_0603_uniroyal"),
             _requirement("within_the_gate_source_rating", "<=",
                          fet["vgs_max_v"]["value"]),
             assumptions=("the gate sits at half the rail because the two "
                          "divider resistors carry the same value, so the "
                          "gate-source voltage is half the rail at every "
                          "input",))},
        {"id": "the_gate_divider_turns_the_device_on_at_the_lowest_input",
         "identity": "Q1",
         "measured_v": netlist.INPUT_SUPPLY["min_v"] / 2.0,
         "claim": _claim(
             "Q1", "V", "reverse_polarity",
             netlist.INPUT_SUPPLY["min_v"] / 2.0, DIRECT,
             ("si9407bdy_vishay",),
             _requirement("above_the_gate_threshold", ">=",
                          fet["vgs_threshold_max_v"]["value"]))},
    ]


def evaluate_input_clamp(parameters):
    tvs = _spec(parameters, "D1")["tvs"]
    supply = Supply(parameters)
    return [
        {"id": "the_clamp_stands_off_the_declared_input",
         "identity": "D1",
         "measured_v": tvs["stand_off_v"]["value"],
         "claim": _claim(
             "VM", "V", "protection", tvs["stand_off_v"]["value"], DIRECT,
             ("smbj_littelfuse",),
             _requirement("at_or_above_the_declared_maximum_input", ">=",
                          netlist.INPUT_SUPPLY["max_v"]))},
        {"id": "the_clamp_conducts_below_the_driver_absolute_maximum",
         "identity": "D1",
         "measured_v": tvs["breakdown_max_v"]["value"],
         "claim": _claim(
             "VM", "V", "protection", tvs["breakdown_max_v"]["value"], DIRECT,
             ("smbj_littelfuse", "tmc2226_trinamic"),
             _requirement("below_the_driver_absolute_maximum_supply", "<=",
                          supply.driver_vs_absolute_v),
             assumptions=("the breakdown voltage is stated at 1 mA; above it "
                          "the clamping voltage rises with current, so this "
                          "bounds the rail only while the transient current "
                          "stays small",),
             omissions=("the clamping voltage at the transient currents this "
                        "board can produce, which the pre-layout hot-plug "
                        "scenario evaluates instead",))},
        {"id": "the_clamp_leaks_negligibly_at_the_declared_input",
         "identity": "D1",
         "measured_a": tvs["reverse_leakage_max_a"]["value"],
         "claim": _claim(
             "VM", "A", "protection", tvs["reverse_leakage_max_a"]["value"],
             DIRECT, ("smbj_littelfuse",),
             _requirement("negligible_against_the_input_rating", "<=",
                          netlist.INPUT_CURRENT_RATING_A / 1000.0))},
    ]


def evaluate_stored_energy(parameters):
    supply = Supply(parameters)
    bulk = supply.bulk_capacitance_min_f()
    start = netlist.INPUT_SUPPLY["max_v"]

    phase_energy = 0.5 * (netlist.MOTOR_PHASE_INDUCTANCE_MAX_H
                          * netlist.PHASE_CURRENT_PEAK_A ** 2)
    unmate_v = math.sqrt(start ** 2 + 2.0 * phase_energy / bulk)

    speed = 2.0 * math.pi * netlist.MOTOR_MAX_SPEED_RPS
    rotor_energy = 0.5 * netlist.MOTOR_ROTOR_INERTIA_MAX_KGM2 * speed ** 2
    regenerative_v = math.sqrt(start ** 2 + 2.0 * rotor_energy / bulk)

    documents = ("hybrid_ncc_hxc", "elcap_knscha_rvt", "tmc2226_trinamic")
    return [
        {"id": "unmating_the_motor_while_enabled_stays_inside_the_rail_limit",
         "identity": "VM",
         "measured_v": unmate_v,
         "claim": _claim(
             "VM", "V", "protection", unmate_v, ASSUMED, documents,
             _requirement("below_the_declared_rail_transient_ceiling", "<=",
                          netlist.MOTOR_RAIL_TRANSIENT_MAX_V),
             assumptions=(
                 "the two phase currents obey iA^2 + iB^2 = ipeak^2, so the "
                 "energy stored in the windings is half the declared phase "
                 "inductance times the square of the sine peak",
                 "all of that energy reaches the bulk capacitance through "
                 "the bridge body diodes and none of it is dissipated in the "
                 "winding resistance or the bridge",
                 "the declared maximum phase inductance of %g mH is an "
                 "assumption: the brief names no motor"
                 % (netlist.MOTOR_PHASE_INDUCTANCE_MAX_H * 1e3),
                 "the bulk capacitors are at the bottom of their tolerance"),
             omissions=("the clamp, which conducts above its breakdown "
                        "voltage and would hold the rail lower still",))},
        {"id": "regenerative_rise_stays_inside_the_rail_limit",
         "identity": "VM",
         "measured_v": regenerative_v,
         "claim": _claim(
             "VM", "V", "protection", regenerative_v, ASSUMED, documents,
             _requirement("below_the_declared_rail_transient_ceiling", "<=",
                          netlist.MOTOR_RAIL_TRANSIENT_MAX_V),
             assumptions=(
                 "the rotor's whole kinetic energy at the declared maximum "
                 "speed of %g rev/s returns to the rail, which no real "
                 "deceleration achieves because the winding resistance "
                 "dissipates part of it" % netlist.MOTOR_MAX_SPEED_RPS,
                 "the declared maximum rotor inertia of %g kg m^2 is an "
                 "assumption: the brief names no motor"
                 % netlist.MOTOR_ROTOR_INERTIA_MAX_KGM2,
                 "the bulk capacitors are at the bottom of their tolerance"),
             omissions=(
                 "the inertia of anything coupled to the shaft, which is the "
                 "integrator's budget and not this board's",
                 "the clamp, which conducts above its breakdown voltage"))},
        {"id": "the_declared_rail_ceiling_is_inside_the_driver_limit",
         "identity": "VM",
         "measured_v": netlist.MOTOR_RAIL_TRANSIENT_MAX_V,
         "claim": _claim(
             "VM", "V", "protection", netlist.MOTOR_RAIL_TRANSIENT_MAX_V,
             DIRECT, ("tmc2226_trinamic",),
             _requirement("below_the_driver_absolute_maximum_supply", "<=",
                          supply.driver_vs_absolute_v))},
    ]


def evaluate_bulk_ripple(parameters):
    spec = _spec(parameters, "C2")["capacitor"]
    count = len(netlist.RIPPLE_REFERENCES)
    multiplier = spec["ripple_frequency_multiplier_20k"]["value"]
    rating = spec["ripple_current_max_a"]["value"] * multiplier * count
    worst = netlist.PHASE_CURRENT_PEAK_A / 2.0
    return [
        {"id": "the_bulk_capacitors_carry_the_chopper_ripple",
         "identity": ",".join(netlist.RIPPLE_REFERENCES),
         "measured_a": worst,
         "claim": _claim(
             "VM", "A", "power_integrity", worst, DERIVED,
             ("hybrid_ncc_hxc", "tmc2226_trinamic"),
             _requirement("within_the_derated_ripple_rating", "<=", rating),
             scope_level="group", phenomenon="power_integrity",
             assumptions=(
                 "the supply current of a chopped bridge is the phase "
                 "current gated by the duty cycle, so its RMS ripple is "
                 "ipeak*sqrt(D(1-D)) and is largest at D = 1/2",
                 "the rating is the datasheet's own frequency multiplier at "
                 "20 kHz applied to the 100 kHz figure, and the chopper's "
                 "lowest tabulated frequency is %g kHz"
                 % (netlist.CHOPPER_FREQUENCY_MIN_HZ / 1e3),
                 "only the hybrid capacitors are counted, so the ceramics' "
                 "share of the ripple is credited to them and not to these"),
             omissions=(
                 "the ceramic capacitors on the same rail, which carry part "
                 "of the ripple and are left out, making this an upper bound "
                 "on what the hybrids carry",))},
    ]


# ---------------------------------------------------------------------------
# safe state, control and diagnostics

def evaluate_safe_state(parameters):
    supply = Supply(parameters)
    driver = _spec(parameters, "U1")
    mcu = _spec(parameters, "U2")
    leakage = (driver["input_leakage_max_a"]["value"]
               + mcu["input_leakage_max_a"]["value"])
    held_v = supply.logic_rail_min_v - leakage * _resistor_ohms("R13")
    threshold = (driver["digital_inputs"]["vih_min"]["fraction_of_supply"]
                 ["value"] * supply.logic_rail_min_v)
    mapping = netlist.pin_to_net()
    drivers_of_enn = sorted(
        pin for pin in netlist.NETS["DRV_ENN"]
        if pin.split(".")[0] not in ("U1", "R13")
        and not pin.startswith("TP"))
    del mapping
    return [
        {"id": "the_enable_input_is_held_disabled_with_nothing_driving_it",
         "identity": "DRV_ENN",
         "measured_v": held_v,
         "claim": _claim(
             "DRV_ENN", "V", "safe_state", held_v, DIRECT,
             ("tmc2226_trinamic", "stm32g030_st", "res_0603_uniroyal"),
             _requirement("at_or_above_the_driver_input_high_level", ">=",
                          threshold), phenomenon="digital_io",
             assumptions=(
                 "after reset every controller port is a floating input, so "
                 "the only current in the pull-up is the driver's and the "
                 "controller's own input leakage, both at their datasheet "
                 "maxima",))},
        {"id": "only_the_controller_and_the_pull_up_drive_the_enable_input",
         "identity": "DRV_ENN",
         "measured": len(drivers_of_enn),
         "claim": _structural(
             "DRV_ENN", "safe_state",
             [pin for pin in drivers_of_enn
              if not pin.startswith("U2.")],
             "nothing_but_the_controller_can_clear_a_latched_fault",
             ("tmc2226_trinamic",),
             assumptions=("the driver latches an error until ENN is driven "
                          "high, so a board with no automatic path to ENN "
                          "cannot retry into a fault on its own",))},
        {"id": "the_driver_is_in_reset_until_its_io_supply_is_up",
         "identity": "U1",
         "measured_v": driver["supply"]["vcc_io_uvlo_rising_max"]["value"],
         "claim": _claim(
             "U1", "V", "safe_state",
             driver["supply"]["vcc_io_uvlo_rising_max"]["value"], DIRECT,
             ("tmc2226_trinamic",),
             _requirement("below_the_logic_rail_minimum", "<=",
                          supply.logic_rail_min_v),
             assumptions=("below its IO undervoltage threshold the driver is "
                          "held in reset with the outputs off, so the rail "
                          "coming up is what releases it",))},
    ]


def _ring_claim(identity, net, supply, hysteresis_v):
    """What the routed conductor rings to when the controller drives it.

    Two models cover the conductor between them: as a lumped series loop it
    overshoots by its damping, and as a transmission line driven through a
    series element at or above its own impedance it does not overshoot at
    all. The larger of the two is reported, so the answer holds whether or
    not the edge is short enough to see the conductor as a line.
    """
    from . import geometry

    reference = netlist.SOURCE_TERMINATED[net]
    result = geometry.source_termination(
        geometry.snapshot(), net, _resistor_ohms(reference),
        supply.logic_rail_max_v)
    return {
        "id": identity,
        "identity": net,
        "measured_v": result["overshoot_v"],
        "claim": _claim(
            net, "V", "control", result["overshoot_v"], DERIVED,
            ("tmc2226_trinamic",),
            _requirement("below_the_driver_input_hysteresis", "<=",
                         hysteresis_v), phenomenon="interconnect_si",
            assumptions=(
                "%s stands between the controller and this conductor, and "
                "the conductor's own inductance and capacitance close the "
                "loop with it" % reference,
                "the loop is driven from the top of the logic rail, so the "
                "overshoot is the largest the rail can produce",
                "the series element is at or above the conductor's own "
                "impedance, which is what makes the lumped loop the larger "
                "of the two models and so the one reported"),
            omissions=(
                "the driver's input capacitance and the probe pad on the "
                "conductor, both of which damp the loop further",
                "the controller's own output resistance, which adds to the "
                "series element"))}


def evaluate_step_dir(parameters):
    driver = _spec(parameters, "U1")
    supply = Supply(parameters)
    clock_min = driver["driver"]["clock_hz"]["min"]["value"]
    filter_s = driver["driver"]["step_filter_max_s"]["value"]
    minimum_pulse_s = max(filter_s, 1.0 / clock_min
                          + driver["driver"]["step_setup_min_s"]["value"])
    timer_tick_s = 1.0 / 16.0e6
    producible_s = 2.0 * timer_tick_s
    hysteresis_v = (driver["digital_inputs"]["hysteresis"]
                    ["fraction_of_supply"]["value"] * supply.logic_rail_min_v)
    return [
        {"id": "the_controller_can_produce_the_drivers_minimum_step_pulse",
         "identity": "DRV_STEP",
         "measured_s": producible_s,
         "claim": _claim(
             "DRV_STEP", "s", "control", producible_s, DERIVED,
             ("tmc2226_trinamic", "stm32g030_st"),
             _requirement("at_or_above_the_driver_minimum_pulse", ">=",
                          minimum_pulse_s), phenomenon="digital_io",
             assumptions=(
                 "the step output is a compare channel of a timer clocked "
                 "from the controller's 16 MHz internal oscillator, so the "
                 "shortest pulse it can assert is two timer ticks",
                 "the driver's minimum is the larger of its input filter "
                 "time and one internal clock period plus 20 ns, evaluated "
                 "at the bottom of its clock tolerance"))},
        _ring_claim("the_step_input_ring_that_would_double_step",
                    "DRV_STEP", supply, hysteresis_v),
        _ring_claim("the_direction_input_ring_that_would_step_the_wrong_way",
                    "DRV_DIR", supply, hysteresis_v),
    ]


def evaluate_config_interface(parameters):
    supply = Supply(parameters)
    driver = _spec(parameters, "U1")
    mcu = _spec(parameters, "U2")
    pull_up = _resistor_ohms("R10")
    series = _resistor_ohms("R9")
    rail = supply.logic_rail_min_v

    idle_v = rail - driver["input_leakage_max_a"]["value"] * pull_up
    driver_vih = (driver["digital_inputs"]["vih_min"]["fraction_of_supply"]
                  ["value"] * rail)
    driver_vil = (driver["digital_inputs"]["vil_max"]["fraction_of_supply"]
                  ["value"] * rail)
    mcu_vil = (mcu["digital_inputs"]["vil_max"]["fraction_of_supply"]["value"]
               * rail)

    # The controller pulls the line low through its series element against
    # the pull-up; the controller's own low level is its output at the
    # current the network sources into it.
    mcu_low_v = 0.4
    low_v = ((rail / pull_up + mcu_low_v / series)
             / (1.0 / pull_up + 1.0 / series))

    reply_sink_a = (supply.logic_rail_max_v - mcu_low_v) / series \
        + supply.logic_rail_max_v / pull_up
    characterised_a = 0.002
    reply_low_v = (driver["digital_outputs"]["vol_max_v"]["value"]
                   * reply_sink_a / characterised_a)
    return [
        {"id": "the_configuration_line_idles_at_a_valid_high_level",
         "identity": "DRV_UART",
         "measured_v": idle_v,
         "claim": _claim(
             "DRV_UART", "V", "configuration", idle_v, DIRECT,
             ("tmc2226_trinamic", "res_0603_uniroyal"),
             _requirement("at_or_above_the_driver_input_high_level", ">=",
                          driver_vih), phenomenon="digital_io",
             assumptions=("the pull-up carries only the driver's own input "
                          "leakage at its datasheet maximum",))},
        {"id": "the_controller_reaches_a_valid_low_level_on_the_line",
         "identity": "DRV_UART",
         "measured_v": low_v,
         "claim": _claim(
             "DRV_UART", "V", "configuration", low_v, ASSUMED,
             ("tmc2226_trinamic", "res_0603_uniroyal"),
             _requirement("at_or_below_the_driver_input_low_level", "<=",
                          driver_vil), phenomenon="digital_io",
             assumptions=(
                 "the controller's output low level is taken as %g V, which "
                 "its datasheet states for a loaded output rather than for "
                 "the few hundred microamps this network draws" % mcu_low_v,
                 "the line is the divider formed by the pull-up and the "
                 "controller's series element"))},
        {"id": "the_driver_reaches_a_valid_low_level_when_it_replies",
         "identity": "DRV_UART",
         "measured_v": reply_low_v,
         "claim": _claim(
             "DRV_UART", "V", "configuration", reply_low_v, ASSUMED,
             ("tmc2226_trinamic", "res_0603_uniroyal"),
             _requirement("at_or_below_the_controller_input_low_level", "<=",
                          mcu_vil), phenomenon="digital_io",
             assumptions=(
                 "while the driver replies the controller's transmit output "
                 "idles high through its series element, so the driver sinks "
                 "%.2f mA rather than the 2 mA its output low level is "
                 "characterised at" % (reply_sink_a * 1e3),
                 "the output low level is scaled linearly with current from "
                 "that one characterised point, which treats the output as a "
                 "resistance"),
             omissions=("the driver's output on-resistance above the one "
                        "current its datasheet characterises",))},
        {"id": "the_configuration_line_is_reachable_from_outside",
         "identity": "CFG_UART",
         "measured": 1.0 if "CFG_UART" in netlist.entering_conductors()
                     else 0.0,
         "claim": _claim(
             "CFG_UART", "boolean", "configuration",
             1.0 if "CFG_UART" in netlist.entering_conductors() else 0.0,
             DERIVED, (),
             _requirement("reachable_for_read_back", ">=", 1.0))},
    ]


def evaluate_diagnostics(parameters):
    del parameters
    interrupt_capable = [
        name for name, (net, function) in netlist.MCU_FUNCTION.items()
        if net == "DRV_DIAG" and function.startswith("EXTI")]
    mapping = netlist.pin_to_net()
    diag_pins = [pin for pin in netlist.NETS["DRV_DIAG"]
                 if pin.startswith("U2.")]
    del mapping
    return [
        {"id": "the_fault_output_reaches_an_interrupt_capable_input",
         "identity": "DRV_DIAG",
         "measured": len(interrupt_capable),
         "claim": _claim(
             "DRV_DIAG", "pins", "diagnostics", float(len(interrupt_capable)),
             DERIVED, ("stm32g030_st",),
             _requirement("at_least_one_interrupt_capable_input", ">=", 1.0),
             phenomenon="digital_io",
             assumptions=("the pin assignment names the external-interrupt "
                          "line the fault output lands on",))},
        {"id": "the_fault_output_reaches_the_controller",
         "identity": "DRV_DIAG",
         "measured": len(diag_pins),
         "claim": _claim(
             "DRV_DIAG", "pins", "diagnostics", float(len(diag_pins)),
             DERIVED, (),
             _requirement("reaches_the_controller", ">=", 1.0),
             phenomenon="digital_io")},
        {"id": "the_index_output_reaches_the_controller",
         "identity": "DRV_INDEX",
         "measured": len([pin for pin in netlist.NETS["DRV_INDEX"]
                          if pin.startswith("U2.")]),
         "claim": _claim(
             "DRV_INDEX", "pins", "diagnostics",
             float(len([pin for pin in netlist.NETS["DRV_INDEX"]
                        if pin.startswith("U2.")])), DERIVED, (),
             _requirement("reaches_the_controller", ">=", 1.0),
             phenomenon="digital_io")},
    ]


# ---------------------------------------------------------------------------
# dissipation of the small parts

def _resistor_worst_case_a(parameters, reference, supply):
    """The largest steady current the topology can put through a resistor."""
    driver = _spec(parameters, "U1")
    mcu = _spec(parameters, "U2")
    tvs = _spec(parameters, "D2")["tvs"]
    led = _spec(parameters, "D10")["led"]
    rail = supply.logic_rail_max_v
    dividers = {"R1": ("R1", "R2", netlist.INPUT_SURVIVAL_MAX_V),
                "R2": ("R1", "R2", netlist.INPUT_SURVIVAL_MAX_V),
                "R3": ("R3", "R4", netlist.INPUT_SURVIVAL_MAX_V),
                "R4": ("R3", "R4", netlist.INPUT_SURVIVAL_MAX_V),
                "R5": ("R5", "R6", rail),
                "R6": ("R5", "R6", rail),
                "R7": ("R7", "R8", netlist.INPUT_SURVIVAL_MAX_V),
                "R8": ("R7", "R8", netlist.INPUT_SURVIVAL_MAX_V)}
    if reference in dividers:
        upper, lower, across = dividers[reference]
        return across / (_resistor_ohms(upper) + _resistor_ohms(lower))
    if reference in ("R9", "R22"):
        # one end at the rail, the other pulled to the reference by the
        # device at the far end of the single-wire line
        return rail / _resistor_ohms(reference)
    if reference == "R10":
        return rail / _resistor_ohms(reference)
    if reference == "R13":
        return rail / _resistor_ohms(reference)
    if reference in ("R20", "R21"):
        return ((rail - led["forward_voltage_min_v"]["value"])
                / _resistor_ohms(reference))
    if reference in ("R14", "R15"):
        # an external source held at the clamp's stand-off voltage while the
        # controller pin clamps to its own rail
        return max(0.0, (tvs["stand_off_v"]["value"]
                         - mcu["supply"]["max"]["value"])
                   / _resistor_ohms(reference))
    if reference in ("R11", "R12"):
        return driver["input_leakage_max_a"]["value"]
    if reference in ("R16", "R17", "R18", "R19"):
        return max(0.0, (tvs["stand_off_v"]["value"]
                         - mcu["supply"]["max"]["value"])
                   / _resistor_ohms(reference))
    raise KeyError("no worst-case current is declared for " + reference)


def evaluate_dissipation(parameters):
    supply = Supply(parameters)
    spec = _spec(parameters, "R1")["resistor"]
    rating = spec["power_max_w"]["value"]
    results = []
    for reference in _references("R"):
        current = _resistor_worst_case_a(parameters, reference, supply)
        watts = current ** 2 * _resistor_ohms(reference)
        results.append({
            "id": "resistor_dissipation_within_rating",
            "identity": reference,
            "measured_w": watts,
            "claim": _claim(
                reference, "W", "dissipation", watts, DERIVED,
                ("res_0603_uniroyal",),
                _requirement("within_the_resistor_power_rating", "<=",
                             rating),
                assumptions=("the current is the largest the topology can "
                             "hold through this element steadily",))})
    return results


def evaluate_indicators(parameters):
    led = _spec(parameters, "D10")["led"]
    supply = Supply(parameters)
    forward = led["forward_voltage_min_v"]["value"]
    current = ((supply.logic_rail_max_v - forward) / _resistor_ohms("R20"))
    return [
        {"id": "indicator_current_within_rating",
         "identity": "D10,D11",
         "measured_a": current,
         "claim": _claim(
             "PWR_LED_A", "A", "dissipation", current, DIRECT,
             ("kt0603r_kento", "res_0603_uniroyal"),
             _requirement("within_the_indicator_current_rating", "<=",
                          led["forward_current_max_a"]["value"]),
             scope_level="group",
             assumptions=("the rail at the top of its range and the diode at "
                          "the bottom of its forward-voltage range, which is "
                          "the combination that draws most",))},
    ]


# ---------------------------------------------------------------------------
# structural policy

def _net_maximum_v(supply):
    levels = {"GND": 0.0,
              "VM": netlist.INPUT_SURVIVAL_MAX_V,
              "VM_IN": netlist.INPUT_SURVIVAL_MAX_V,
              "VCP": netlist.INPUT_SURVIVAL_MAX_V + 5.25,
              "V5OUT": 5.25,
              "+3V3": supply.logic_rail_max_v}
    for name in netlist.NETS:
        if name not in levels:
            levels[name] = supply.logic_rail_max_v
    for name in ("PHASE_A1", "PHASE_A2", "PHASE_B1", "PHASE_B2",
                 "SENSE_A", "SENSE_B", "SW", "FB", "BUCK_EN", "VM_SENSE",
                 "PFET_G", "BOOT", "CP_OUT", "CP_IN", "DRV_VREF"):
        levels[name] = netlist.INPUT_SURVIVAL_MAX_V
    levels["BOOT"] = netlist.INPUT_SURVIVAL_MAX_V + 5.5
    return levels


def evaluate_absolute_maximum(parameters):
    supply = Supply(parameters)
    levels = _net_maximum_v(supply)
    mapping = netlist.pin_to_net()
    violations = []
    for reference, part in sorted(netlist.PARTS.items()):
        mpn = part["mpn"]
        if mpn is None:
            continue
        spec = parameters["parts"][mpn]
        rating = None
        for block, key in (("capacitor", "rated_voltage_v"),
                           ("resistor", "working_voltage_max_v"),
                           ("tvs", "stand_off_v")):
            entry = (spec.get(block) or {}).get(key)
            if entry is not None:
                rating = entry["value"]
                break
        if rating is None:
            continue
        for pin_ref, net in mapping.items():
            if pin_ref.split(".")[0] != reference:
                continue
            if levels.get(net, 0.0) > rating:
                violations.append("%s on %s sees %.2f V against a %.2f V "
                                  "rating" % (reference, net,
                                              levels[net], rating))
    return [
        {"id": "no_part_sees_more_than_its_rating",
         "identity": "board",
         "measured": len(violations),
         "claim": _structural(
             "board", "absolute_maximum", sorted(set(violations)),
             "every_part_is_rated_for_the_net_it_sits_on",
             ("mlcc_yageo_cc", "res_0603_uniroyal", "smbj_littelfuse",
              "tpd1e10b06_ti"),
             assumptions=(
                 "each net's ceiling is the declared input survival voltage "
                 "for the motor side, the regulator's own upper tolerance "
                 "for the logic side, and the bootstrap and charge-pump "
                 "nodes are taken as their rail plus the internal regulator "
                 "voltage",),
             omissions=(
                 "the capacitors' voltage coefficient: a ceramic's "
                 "capacitance falls with applied voltage and this checks "
                 "only the rating, not the value",))},
    ]


def evaluate_esd_coverage(parameters):
    del parameters
    entering = netlist.entering_conductors()
    clamped = set(netlist.ESD_CLAMP_NETS.values())
    unprotected = sorted(net for net in entering
                         if net not in clamped
                         and net not in netlist.ESD_EXEMPT)
    unused_exemptions = sorted(net for net in netlist.ESD_EXEMPT
                               if net not in entering)
    return [
        {"id": "every_entering_conductor_is_clamped_or_exempt",
         "identity": "board",
         "measured": len(unprotected),
         "claim": _structural(
             "board", "esd", unprotected,
             "no_entering_conductor_is_unaccounted_for",
             ("tpd1e10b06_ti",))},
        {"id": "no_exemption_names_a_conductor_that_does_not_enter",
         "identity": "board",
         "measured": len(unused_exemptions),
         "claim": _structural(
             "board", "esd", unused_exemptions,
             "every_exemption_describes_a_real_entering_conductor")},
    ]


def evaluate_injection_policy(parameters):
    del parameters
    entering = netlist.entering_conductors()
    field_nets = set()
    service_nets = set()
    for reference, functions in netlist.CONNECTOR_FUNCTION_NETS.items():
        target = field_nets if netlist.CONNECTOR_ROLE[reference] == "field" \
            else service_nets
        target.update(net for net in functions.values()
                      if net not in netlist.POWER_NETS)
    del entering

    mapping = netlist.pin_to_net()
    reachable = {}
    for pin_ref, net in mapping.items():
        reference, _, number = pin_ref.partition(".")
        if reference != "U2":
            continue
        reachable[number] = net

    def _reaches(net, targets):
        seen, frontier = set(), [net]
        while frontier:
            current = frontier.pop()
            if current in seen:
                continue
            seen.add(current)
            if current in targets:
                return True
            if current in netlist.POWER_NETS:
                continue
            for pin_ref in netlist.NETS[current]:
                owner = pin_ref.split(".")[0]
                if not owner.startswith("R"):
                    continue
                for other in netlist.NETS:
                    if other == current:
                        continue
                    if any(pin.split(".")[0] == owner
                           for pin in netlist.NETS[other]):
                        frontier.append(other)
        return False

    field_violations = []
    service_exposed = []
    for number, name in sorted(netlist.MCU_NO_NEGATIVE_INJECTION_PINS.items(),
                               key=lambda item: int(item[0])):
        net = reachable.get(number)
        if net is None:
            continue
        if _reaches(net, field_nets):
            field_violations.append("%s (pin %s) reaches a field conductor "
                                    "through %s" % (name, number, net))
        elif _reaches(net, service_nets):
            service_exposed.append("%s (pin %s) reaches a service conductor "
                                   "through %s" % (name, number, net))
    return [
        {"id": "no_field_conductor_reaches_a_zero_injection_pin",
         "identity": "U2",
         "measured": len(field_violations),
         "claim": _structural(
             "U2", "injection", field_violations,
             "field_conductors_avoid_the_pins_that_tolerate_no_negative_"
             "injection", ("stm32g030_st",),
             assumptions=("a field conductor is one an integrator wires and "
                          "may drive below this board's reference",))},
        {"id": "negative_injection_into_a_zero_injection_debug_pin",
         "identity": "U2",
         "measured": len(service_exposed),
         "claim": _claim(
             "U2", "A", "injection", None, ASSUMED,
             ("stm32g030_st",),
             _requirement("within_the_pins_negative_injection_allowance",
                          "<=", 0.0),
             scope_level="group",
             assumptions=(
                 "the debug pins are fixed by the controller and cannot be "
                 "moved, so the series element and the clamp are the whole "
                 "mitigation",
                 "the condition this rests on is that a service connector is "
                 "mated only by a probe sharing this board's reference"),
             omissions=(
                 "the current a probe driving below the reference would "
                 "inject, which the clamp bounds at its own breakdown "
                 "voltage and the series element divides, but which the "
                 "controller's datasheet gives no allowance for at all",))},
    ]


def evaluate_connector_contract(parameters):
    library = ksym.Library(netlist.SYMBOL_LIBRARY_PATHS)
    mapping = netlist.pin_to_net()
    results = []
    mismatched, unkeyed, underrated = [], [], []
    contract = netlist.CONNECTOR_FUNCTION_NETS
    for reference, functions in sorted(contract.items()):
        part = netlist.PARTS[reference]
        pins = library.pins(part["lib_id"])
        declared = set(functions.values())
        actual = {mapping["%s.%s" % (reference, number)] for number in pins}
        if declared != actual:
            mismatched.append("%s carries %s but declares %s"
                              % (reference, sorted(actual), sorted(declared)))
        spec = parameters["parts"][part["mpn"]]["connector"]
        if len(pins) != int(spec["positions"]["value"]):
            mismatched.append("%s has %d pins against a %d-position part"
                              % (reference, len(pins),
                                 int(spec["positions"]["value"])))
    motor = parameters["parts"][netlist.PARTS["J2"]["mpn"]]["connector"]
    if not motor["keyed"]["value"]:
        unkeyed.append("J2 is not keyed against reversed mating")
    if not motor["retained"]["value"]:
        unkeyed.append("J2 is not retained against vibration")
    if motor["current_max_a"]["value"] < netlist.PHASE_CURRENT_PEAK_A:
        underrated.append("J2 is rated below the phase current peak")
    supply_connector = parameters["parts"][
        netlist.PARTS["J1"]["mpn"]]["connector"]
    if supply_connector["current_max_a"]["value"] \
            < netlist.INPUT_CURRENT_RATING_A:
        underrated.append("J1 is rated below the board input current")

    results.append({
        "id": "every_connector_carries_the_functions_it_declares",
        "identity": "board",
        "measured": len(mismatched),
        "claim": _structural(
            "board", "connector", mismatched,
            "the_connector_contract_matches_the_netlist",
            ("jst_vh_connector", "kf128_cixikefa", "header1x5_kinghelm"))})
    results.append({
        "id": "the_motor_connector_is_keyed_and_retained",
        "identity": "J2",
        "measured": len(unkeyed),
        "claim": _structural(
            "J2", "connector", unkeyed,
            "keyed_against_reversed_mating_and_retained",
            ("jst_vh_connector",))})
    results.append({
        "id": "every_connector_is_rated_for_the_current_it_carries",
        "identity": "board",
        "measured": len(underrated),
        "claim": _structural(
            "board", "connector", underrated,
            "connector_current_ratings_cover_the_declared_currents",
            ("jst_vh_connector", "kf128_cixikefa"),
            assumptions=(
                "the motor connector's 10 A rating is stated including the "
                "temperature rise the applied current produces, up to the "
                "top of its 85 degC range",))})
    results.append({
        "id": "the_motor_connector_ambient_rating_covers_the_declared_maximum",
        "identity": "J2",
        "measured_c": motor["ambient_max_c"]["value"],
        "claim": _claim(
            "J2", "degC", "connector", motor["ambient_max_c"]["value"],
            DIRECT, ("jst_vh_connector",),
            _requirement("covers_the_declared_maximum_ambient", ">=",
                         netlist.AMBIENT_MAX_C))})
    return results


def evaluate_probe_access(parameters):
    del parameters
    mapping = netlist.pin_to_net()
    probed = {mapping["%s.1" % reference]
              for reference in netlist.PARTS if reference.startswith("TP")}
    missing = sorted(net for net in netlist.PROBE_REQUIRED_NETS
                     if net not in probed)
    return [
        {"id": "every_net_the_brief_requires_a_probe_on_has_one",
         "identity": "board",
         "measured": len(missing),
         "claim": _structural("board", "test_access", missing,
                              "every_required_net_reaches_a_probe")},
    ]


def _footprint_pad_numbers(footprint):
    library, _, name = footprint.partition(":")
    for base in (LOCAL_FOOTPRINT_ROOT, FOOTPRINT_ROOT):
        path = os.path.join(base, library + ".pretty", name + ".kicad_mod")
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            return {number for number in re.findall(r'\(pad "([^"]*)"', text)
                    if number}
    raise FileNotFoundError(footprint)


def evaluate_package_correspondence(parameters):
    del parameters
    library = ksym.Library(netlist.SYMBOL_LIBRARY_PATHS)
    mismatched = []
    for reference, part in sorted(netlist.PARTS.items()):
        if not part["footprint"]:
            continue
        symbol_pins = set(library.pins(part["lib_id"]))
        pads = _footprint_pad_numbers(part["footprint"])
        if reference.startswith("H"):
            continue
        if not symbol_pins <= pads:
            mismatched.append("%s: symbol pins %s are not pads on %s"
                              % (reference, sorted(symbol_pins - pads),
                                 part["footprint"]))
    return [
        {"id": "every_symbol_pin_lands_on_a_pad_of_its_footprint",
         "identity": "board",
         "measured": len(mismatched),
         "claim": _structural(
             "board", "package", mismatched,
             "symbol_pin_numbers_and_footprint_pad_numbers_agree",
             assumptions=("a mounting hole carries no pin and no pad and is "
                          "excluded",))},
        {"id": "the_contested_controller_pins_carry_no_connection",
         "identity": "U2",
         "measured": len([number for number in netlist.MCU_CONTESTED_PINS
                          if "U2.%s" % number not in netlist.NO_CONNECT]),
         "claim": _structural(
             "U2", "package",
             [number for number in netlist.MCU_CONTESTED_PINS
              if "U2.%s" % number not in netlist.NO_CONNECT],
             "no_design_decision_rests_on_a_contested_pin",
             ("stm32g030_st",),
             assumptions=("the datasheet pinout and the symbol disagree "
                          "about what package pins %s are; both are left "
                          "unconnected so neither reading matters"
                          % ", ".join(sorted(netlist.MCU_CONTESTED_PINS)),))},
    ]


def evaluate_thermal_pad(parameters):
    del parameters
    return [
        {"id": "the_exposed_pad_carries_the_declared_via_array",
         "identity": "U1",
         "measured": len(libraries.thermal_via_positions_mm()),
         "claim": _claim(
             "U1", "vias", "thermal",
             float(len(libraries.thermal_via_positions_mm())), DERIVED,
             ("tmc2226_trinamic",),
             _requirement("at_least_the_declared_via_count", ">=",
                          float(netlist.THERMAL_VIA_COUNT)),
             scope_level="group", phenomenon="interconnect_geometry")},
        {"id": "no_thermal_via_lies_under_solder_paste",
         "identity": "U1",
         "measured_mm": libraries.thermal_via_to_mask_clearance_mm(),
         "claim": _claim(
             "U1", "mm", "thermal",
             libraries.thermal_via_to_mask_clearance_mm(), DERIVED, (),
             _requirement("clear_of_every_mask_opening", ">=", 0.15),
             scope_level="group", phenomenon="interconnect_geometry",
             assumptions=("the exposed pad's mask and paste are cut into "
                          "windows and every via sits on a dam between "
                          "them, so the clearance is half the dam less the "
                          "via's own radius",))},
        {"id": "the_exposed_pad_keeps_a_usable_paste_coverage",
         "identity": "U1",
         "measured": libraries.paste_coverage_fraction(),
         "claim": _claim(
             "U1", "fraction", "thermal",
             libraries.paste_coverage_fraction(), DERIVED, (),
             _requirement("at_or_above_half_the_pad_area", ">=", 0.50),
             scope_level="group", phenomenon="interconnect_geometry")},
    ]


def evaluate_supply_availability(parameters):
    del parameters
    catalog = load_catalog()["parts"]
    counts = {}
    for reference, part in netlist.PARTS.items():
        if not part["in_bom"]:
            continue
        counts[part["lcsc"]] = counts.get(part["lcsc"], 0) + 1
    limits = {code: catalog[code]["stock"] // count
              for code, count in counts.items()}
    tightest = min(limits, key=limits.get)
    return [
        {"id": "catalogue_stock_covers_the_planned_build",
         "identity": tightest,
         "measured": limits[tightest],
         "claim": _claim(
             tightest, "boards", "supply", float(limits[tightest]), DIRECT,
             (),
             _requirement("covers_the_planned_build_quantity", ">=",
                          float(netlist.PLANNED_BUILD_QUANTITY)),
             scope_level="board",
             assumptions=("stock is a reading taken when the catalogue was "
                          "frozen and is not a commitment",))},
    ]


def _footprint_is_through_hole(footprint):
    """What the land pattern declares itself to be, not what pads it holds.

    A surface-mount package with thermal vias under its exposed pad carries
    plated holes and is still placed by the machine.
    """
    library, _, name = footprint.partition(":")
    for base in (LOCAL_FOOTPRINT_ROOT, FOOTPRINT_ROOT):
        path = os.path.join(base, library + ".pretty", name + ".kicad_mod")
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            match = re.search(r"\(attr ([^)]*)\)", text)
            return bool(match) and "through_hole" in match.group(1)
    raise FileNotFoundError(footprint)


def evaluate_assembly(parameters):
    del parameters
    through_hole = sorted(
        reference for reference, part in netlist.PARTS.items()
        if part["in_bom"] and part["footprint"]
        and _footprint_is_through_hole(part["footprint"]))
    return [
        {"id": "the_through_hole_count_matches_the_assembly_policy",
         "identity": "board",
         "measured": len(through_hole),
         "claim": _claim(
             "board", "parts", "assembly", float(len(through_hole)), DERIVED,
             (),
             _requirement("matches_the_declared_hand_soldered_count", "<=",
                          float(netlist.ASSEMBLY_POLICY[
                              "through_hole_soldered_parts"])),
             scope_level="board",
             assumptions=("the driver's exposed-pad thermal vias are "
                          "footprint pads rather than fitted parts and are "
                          "not counted",))},
    ]


# ---------------------------------------------------------------------------

PRODUCERS = (
    evaluate_driver_selection,
    evaluate_phase_current,
    evaluate_sense_dissipation,
    evaluate_rails,
    evaluate_reverse_polarity,
    evaluate_input_clamp,
    evaluate_stored_energy,
    evaluate_bulk_ripple,
    evaluate_safe_state,
    evaluate_step_dir,
    evaluate_config_interface,
    evaluate_diagnostics,
    evaluate_dissipation,
    evaluate_indicators,
    evaluate_absolute_maximum,
    evaluate_esd_coverage,
    evaluate_injection_policy,
    evaluate_connector_contract,
    evaluate_probe_access,
    evaluate_package_correspondence,
    evaluate_thermal_pad,
    evaluate_supply_availability,
    evaluate_assembly,
)


def evaluate_all():
    from . import geometry, thermal
    parameters = load_parameters()
    results = []
    for producer in PRODUCERS:
        results.extend(producer(parameters))
    results.extend(thermal.evaluate_all(parameters))
    results.extend(geometry.evaluate_all(parameters))
    for result in results:
        result["verdict"] = claim.verdict(result["claim"])
    return results


REPORT_PATH = os.path.join(REPO_ROOT, "generated", "requirements.json")


def write_report():
    evaluated = evaluate_all()
    document = {
        "kind": "board-requirement-evidence",
        "summary": summarise(evaluated),
        "results": [
            {"id": result["id"], "identity": result["identity"],
             "claim": result["claim"], "verdict": result["verdict"]}
            for result in sorted(evaluated,
                                 key=lambda item: (item["id"],
                                                   item["identity"]))],
    }
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return REPORT_PATH


def summarise(results):
    counts = {}
    for result in results:
        counts[result["verdict"]["result"]] = counts.get(
            result["verdict"]["result"], 0) + 1
    return counts


if __name__ == "__main__":
    evaluated = evaluate_all()
    write_report()
    for result in sorted(evaluated, key=lambda item: (
            item["verdict"]["result"], item["id"], item["identity"])):
        value = result["claim"]["quantity"].get("value")
        rendered = "-" if value is None else "%.6g" % value
        sys.stdout.write("%-8s %-62s %-16s %12s %s\n" % (
            result["verdict"]["result"], result["id"], result["identity"],
            rendered, result["claim"]["units"]))
    sys.stdout.write("\n" + json.dumps(summarise(evaluated), sort_keys=True)
                     + "\n")
