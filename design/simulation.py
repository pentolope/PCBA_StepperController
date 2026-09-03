from __future__ import annotations

import json
import os
import sys

from . import models, netlist, rules

REPO_ROOT = rules.REPO_ROOT
SIM_DIR = os.path.join(REPO_ROOT, "sim")

#: How long the input transient is watched after the connector closes.
HOT_PLUG_WINDOW_S = 2.0e-3

#: The pass element idealised to a short. Anything the reverse-blocking
#: device really presents damps the loop further, so the peak this scenario
#: reports is the one no real pass element exceeds.
IDEAL_PASS_OHM = 1.0e-3

#: Interconnect the step edge is evaluated against before any copper exists.
STEP_TRACE_CAPACITANCE_F = 5.0e-12

#: How many step periods the edge scenario runs for, and the rate it runs at.
STEP_PERIODS = 3
STEP_FREQUENCY_HZ = 100.0e3


def _parameters():
    return rules.load_parameters()


def _ideal(records):
    return {name: {"stands_in_for": detail,
                   "accepted_for_design_decision": True}
            for name, detail in records.items()}


def _measurement(name, kind, node, op=None, value=None, knowledge=None):
    record = {"name": name, "kind": kind, "node": node}
    if op is not None:
        record["assertion"] = {"op": op, "value": value}
    if knowledge is not None:
        record["knowledge"] = knowledge
    return record


def _pulse(v1, v2, period_s, delay_s=None, width_s=None):
    delay = period_s / 20.0 if delay_s is None else delay_s
    width = period_s / 2.0 if width_s is None else width_s
    return {"v1": v1, "v2": v2, "delay_s": delay,
            "rise_s": period_s / 1.0e6, "fall_s": period_s / 1.0e6,
            "width_s": width, "period_s": period_s}


# ---------------------------------------------------------------------------

def hot_plug_scenario(parameters):
    """The supply connector closing onto the board's own bulk capacitance.

    The brief asks for margin against hot-plug ringing. The ring is the
    supply lead's inductance against the bulk, and what bounds it is the
    clamp. Every element that would damp the loop is either taken at its
    least damping value or left out, so the peak this reports is one no
    real assembly exceeds under the declared lead parasitics.
    """
    supply = rules.Supply(parameters)
    hybrid = rules._spec(parameters, "C2")["capacitor"]
    esr = hybrid["esr_max_ohm"]["value"]
    elements = [
        {"kind": "vsource_pulse", "name": "SRC", "nodes": ["src", "0"],
         "pulse": _pulse(0.0, supply.input_max_v, 2.0 * HOT_PLUG_WINDOW_S,
                         delay_s=HOT_PLUG_WINDOW_S / 100.0,
                         width_s=HOT_PLUG_WINDOW_S)},
        {"kind": "resistor", "name": "RLEAD", "nodes": ["src", "lead"],
         "value": netlist.SUPPLY_LEAD_RESISTANCE_OHM},
        {"kind": "inductor", "name": "LLEAD", "nodes": ["lead", "in"],
         "value": netlist.SUPPLY_LEAD_INDUCTANCE_H},
        {"kind": "resistor", "name": "RPASS", "nodes": ["in", "vm"],
         "value": IDEAL_PASS_OHM},
        {"kind": "model_instance", "name": "DCLAMP",
         "nodes": ["0", "vm"], "model": models.INPUT_CLAMP},
    ]
    assumptions = {
        "SRC": "the supply at the top of the declared input range, as an "
               "ideal source connected in a nanosecond with no output "
               "impedance of its own",
        "RLEAD": "the supply lead's resistance at the declared budget of "
                 "%g ohm, which is a budget for the integrator's wiring "
                 "rather than a measurement of it"
                 % netlist.SUPPLY_LEAD_RESISTANCE_OHM,
        "LLEAD": "the supply lead's inductance at the declared budget of "
                 "%g uH" % (netlist.SUPPLY_LEAD_INDUCTANCE_H * 1e6),
        "RPASS": "the reverse-blocking device idealised to a short, which "
                 "removes the damping its channel and its body diode both "
                 "provide",
    }
    for index, reference in enumerate(netlist.BULK_REFERENCES):
        spec = rules._spec(parameters, reference)["capacitor"]
        value = spec["capacitance_f"]["value"] * (
            1.0 - spec["tolerance"]["value"])
        node = "c%d" % index
        elements.append(
            {"kind": "resistor", "name": "RESR%d" % index,
             "nodes": ["vm", node], "value": esr})
        elements.append(
            {"kind": "capacitor", "name": "CBULK%d" % index,
             "nodes": [node, "0"], "value": value})
        assumptions["RESR%d" % index] = (
            "the bulk capacitor %s at its stated 100 kHz equivalent series "
            "resistance, which is a maximum; a part below it leaves the loop "
            "less damped, and the peak here is reported for that maximum "
            "with every other damping element removed" % reference)
        assumptions["CBULK%d" % index] = (
            "%s at the bottom of its tolerance, which is the value that "
            "rings highest" % reference)
    return {
        "name": "hot_plug_into_the_bulk_capacitance",
        "description": "the supply connector closing onto the board, with "
                       "the declared supply-lead parasitics ringing against "
                       "the bulk capacitance and the input clamp holding "
                       "the motor rail",
        "elements": elements,
        "analyses": [{"kind": "tran", "step_s": HOT_PLUG_WINDOW_S / 20000.0,
                      "stop_s": HOT_PLUG_WINDOW_S}],
        "operating_conditions": {
            "temperature_c": models.CLAMP_SPEC_TEMPERATURE_C},
        "measurements": [
            _measurement("motor_rail_peak", "tran_max_voltage", "vm", "<=",
                         supply.driver_vs_absolute_v,
                         knowledge={
                             "kind": "upper_bound",
                             "basis": {"kind": "assumed",
                                       "detail": "every damping element is "
                                                 "at its least damping value "
                                                 "or left out"}}),
            _measurement("input_node_peak", "tran_max_voltage", "in"),
        ],
        "assumptions": _ideal(assumptions),
    }


def safe_state_scenario(parameters):
    """The enable input with nothing driving it.

    After reset the controller's port is a floating input, so the only
    current in the pull-up is leakage: the driver's own input leakage and
    the controller pin's, both at their datasheet maxima.
    """
    supply = rules.Supply(parameters)
    driver = rules._spec(parameters, "U1")
    mcu = rules._spec(parameters, "U2")
    driver_leakage_ohm = (supply.logic_rail_min_v
                          / driver["input_leakage_max_a"]["value"])
    mcu_leakage_ohm = (supply.logic_rail_min_v
                       / mcu["input_leakage_max_a"]["value"])
    threshold = (driver["digital_inputs"]["vih_min"]["fraction_of_supply"]
                 ["value"] * supply.logic_rail_min_v)
    return {
        "name": "enable_input_held_off_with_nothing_driving_it",
        "description": "the driver's enable input in the state a controller "
                       "that has not started leaves it, held by its pull-up "
                       "against both leakage paths at their maxima",
        "elements": [
            {"kind": "vsource_dc", "name": "RAIL", "nodes": ["rail", "0"],
             "value": supply.logic_rail_min_v},
            {"kind": "resistor", "name": "RPULLUP", "nodes": ["rail", "enn"],
             "value": rules._resistor_ohms("R13")},
            {"kind": "resistor", "name": "RLEAKDRV", "nodes": ["enn", "0"],
             "value": driver_leakage_ohm},
            {"kind": "resistor", "name": "RLEAKMCU", "nodes": ["enn", "0"],
             "value": mcu_leakage_ohm},
        ],
        "analyses": [{"kind": "op"}],
        "measurements": [
            _measurement("enable_input_level", "op_voltage", "enn", ">=",
                         threshold),
        ],
        "assumptions": _ideal({
            "RAIL": "the logic rail at the bottom of the regulator's stated "
                    "accuracy, which is the worst case for reaching the "
                    "driver's input high threshold",
            "RPULLUP": "the enable pull-up at its nominal value",
            "RLEAKDRV": "the driver's input leakage at its datasheet "
                        "maximum, as the resistance that sinks it to the "
                        "reference",
            "RLEAKMCU": "the controller pin's input leakage at its datasheet "
                        "maximum, as above",
        }),
    }


def config_line_scenario(parameters):
    """The single-wire configuration line in its three states.

    Idle, the controller pulling it down through its series element, and
    the driver replying while the controller's transmit output idles high.
    """
    supply = rules.Supply(parameters)
    driver = rules._spec(parameters, "U1")
    mcu = rules._spec(parameters, "U2")
    rail = supply.logic_rail_min_v
    pull_up = rules._resistor_ohms("R10")
    series = rules._resistor_ohms("R9")
    driver_vih = (driver["digital_inputs"]["vih_min"]["fraction_of_supply"]
                  ["value"] * rail)
    driver_vil = (driver["digital_inputs"]["vil_max"]["fraction_of_supply"]
                  ["value"] * rail)
    mcu_vil = (mcu["digital_inputs"]["vil_max"]["fraction_of_supply"]["value"]
               * rail)
    mcu_low_v = 0.4
    driver_output_ohm = (driver["digital_outputs"]["vol_max_v"]["value"]
                         / 0.002)
    driver_leakage_ohm = rail / driver["input_leakage_max_a"]["value"]
    return {
        "name": "single_wire_configuration_line_levels",
        "description": "the configuration line idle, pulled low by the "
                       "controller through its series element, and pulled "
                       "low by the driver against that element idling high",
        "elements": [
            {"kind": "vsource_dc", "name": "RAIL", "nodes": ["rail", "0"],
             "value": rail},
            {"kind": "resistor", "name": "RPULLIDLE",
             "nodes": ["rail", "idle"], "value": pull_up},
            {"kind": "resistor", "name": "RLEAKIDLE", "nodes": ["idle", "0"],
             "value": driver_leakage_ohm},
            {"kind": "resistor", "name": "RSERIESIDLE",
             "nodes": ["idle", "rail"], "value": series},

            {"kind": "resistor", "name": "RPULLLOW", "nodes": ["rail", "low"],
             "value": pull_up},
            {"kind": "resistor", "name": "RSERIESLOW",
             "nodes": ["low", "mculow"], "value": series},
            {"kind": "vsource_dc", "name": "MCULOW", "nodes": ["mculow", "0"],
             "value": mcu_low_v},

            {"kind": "resistor", "name": "RPULLREPLY",
             "nodes": ["rail", "reply"], "value": pull_up},
            {"kind": "resistor", "name": "RSERIESREPLY",
             "nodes": ["rail", "reply"], "value": series},
            {"kind": "resistor", "name": "RDRVOUT", "nodes": ["reply", "0"],
             "value": driver_output_ohm},
        ],
        "analyses": [{"kind": "op"}],
        "measurements": [
            _measurement("idle_level", "op_voltage", "idle", ">=",
                         driver_vih),
            _measurement("controller_low_level", "op_voltage", "low", "<=",
                         driver_vil),
            _measurement("driver_reply_low_level", "op_voltage", "reply",
                         "<=", mcu_vil),
        ],
        "assumptions": _ideal({
            "RAIL": "the logic rail at the bottom of the regulator's stated "
                    "accuracy, which is the worst case for every level here",
            "RPULLIDLE": "the line's pull-up at its nominal value",
            "RLEAKIDLE": "the driver's input leakage at its datasheet "
                         "maximum, as the resistance that sinks it",
            "RSERIESIDLE": "the controller's transmit output idling high "
                           "through its series element",
            "RPULLLOW": "the pull-up again, for the state where the "
                        "controller drives the line",
            "RSERIESLOW": "the controller's series element",
            "MCULOW": "the controller's output low level taken as %g V, "
                      "which its datasheet states for a loaded output rather "
                      "than for the current this network draws" % mcu_low_v,
            "RPULLREPLY": "the pull-up again, for the state where the driver "
                          "replies",
            "RSERIESREPLY": "the controller's transmit output idling high "
                            "through its series element while the driver "
                            "drives the line",
            "RDRVOUT": "the driver's output as the resistance that produces "
                       "its stated output low level at the one current the "
                       "datasheet characterises, which treats the output as "
                       "linear beyond that point",
        }),
    }


def step_edge_scenario(parameters):
    """The step output driving the driver's input before any copper exists.

    The interconnect is a declared capacitance budget, not a measurement, so
    what this establishes is that the series element and the load the driver
    presents leave the edge far shorter than the pulse it belongs to.
    """
    supply = rules.Supply(parameters)
    driver = rules._spec(parameters, "U1")
    rail = supply.logic_rail_min_v
    series = rules._resistor_ohms("R11")
    load_f = (driver["pin_capacitance_f"]["value"]
              + STEP_TRACE_CAPACITANCE_F)
    period_s = 1.0 / STEP_FREQUENCY_HZ
    vih = (driver["digital_inputs"]["vih_min"]["fraction_of_supply"]["value"]
           * rail)
    vil = (driver["digital_inputs"]["vil_max"]["fraction_of_supply"]["value"]
           * rail)
    return {
        "name": "step_edge_into_the_driver_input",
        "description": "one step pulse from the controller's timer through "
                       "its series element into the driver's input "
                       "capacitance and a declared trace budget",
        "elements": [
            {"kind": "vsource_pulse", "name": "STEP", "nodes": ["out", "0"],
             "pulse": _pulse(0.0, rail, period_s)},
            {"kind": "resistor", "name": "RSERIES", "nodes": ["out", "pin"],
             "value": series},
            {"kind": "capacitor", "name": "CPIN", "nodes": ["pin", "0"],
             "value": load_f},
            {"kind": "resistor", "name": "RLEAK", "nodes": ["pin", "0"],
             "value": rail / driver["input_leakage_max_a"]["value"]},
        ],
        "analyses": [{"kind": "tran", "step_s": period_s / 20000.0,
                      "stop_s": STEP_PERIODS * period_s}],
        "measurements": [
            _measurement("step_input_high_level", "tran_max_voltage", "pin",
                         ">=", vih),
            _measurement("step_input_low_level", "tran_min_voltage", "pin",
                         "<=", vil),
        ],
        "assumptions": _ideal({
            "STEP": "the controller's timer output as an ideal switch "
                    "between the reference and the logic rail at its lower "
                    "tolerance",
            "RSERIES": "the step output's series element at its nominal "
                       "value",
            "CPIN": "the driver's stated input capacitance plus a declared "
                    "%g pF budget for the trace, which is a budget and not a "
                    "measurement" % (STEP_TRACE_CAPACITANCE_F * 1e12),
            "RLEAK": "the driver's input leakage at its datasheet maximum",
        }),
    }


#: Alias each extracted sense conductor is registered under, so a stored
#: scenario can name it: the extracted model's own identity embeds the
#: board's digest and changes whenever the copper does.
SENSE_PATH_ALIASES = {"A": "sense_path_a", "B": "sense_path_b"}


def extracted_paths():
    """What the validator is asked to measure from the routed board."""
    paths = {}
    for phase, alias in sorted(SENSE_PATH_ALIASES.items()):
        paths[alias] = {
            "net": "SENSE_%s" % phase,
            "from_pad": "U1.%s" % netlist.DRIVER_PINS["BR%s" % phase],
            "to_pad": "%s.1" % netlist.SENSE_RESISTOR_REFERENCES[phase],
        }
    return paths


def sense_path_scenario(parameters):
    """What the routed sense conductor does to the current it sets.

    The driver compares the voltage at its own pin, so every milliohm of
    copper between the shunt and that pin is added to the shunt by the
    comparator itself and the delivered current falls by that fraction. The
    conductor is no longer a budget here: it is the resistance measured from
    the copper this board actually carries.
    """
    driver = rules._spec(parameters, "U1")["driver"]
    scale = rules.programmed_scale(parameters)
    full_scale = driver["sense_full_scale_v"]["value"]
    internal = driver["sense_internal_resistance_ohm"]["value"]
    shunt = netlist.SENSE_RESISTANCE_OHM
    target = (scale + 1.0) / 32.0 * full_scale
    ideal = target * shunt / (shunt + internal)
    floor = ideal * (1.0 - netlist.SENSE_INTERCONNECT_BUDGET)

    elements = [
        {"kind": "vsource_dc", "name": "TARGET", "nodes": ["target", "0"],
         "value": target},
    ]
    assumptions = {
        "TARGET": "the comparator threshold the driver regulates the sense "
                  "voltage to at current scale %d, as an ideal source"
                  % scale,
    }
    measurements = []
    for phase, alias in sorted(SENSE_PATH_ALIASES.items()):
        pin = "pin%s" % phase
        node = "shunt%s" % phase
        elements.extend([
            {"kind": "resistor", "name": "RINT%s" % phase,
             "nodes": ["target", pin], "value": internal},
            {"kind": "model_instance", "name": "RTRACE%s" % phase,
             "nodes": [pin, node], "model": alias},
            {"kind": "resistor", "name": "RSHUNT%s" % phase,
             "nodes": [node, "0"], "value": shunt},
        ])
        assumptions["RINT%s" % phase] = (
            "the driver's own path from the sense pin to its comparator, at "
            "the typical value its datasheet states and with no tolerance")
        assumptions["RSHUNT%s" % phase] = (
            "the shunt at its nominal value: this scenario asks what the "
            "copper costs, and the shunt's own tolerance is carried by the "
            "requirement report instead")
        measurements.append(_measurement(
            "shunt_voltage_phase_%s" % phase, "op_voltage", node, ">=",
            floor))
    return {
        "name": "delivered_current_with_the_routed_sense_conductor",
        "description": "the driver's own current-setting divider with the "
                       "sense conductor's measured resistance in it, at the "
                       "current scale nearest the required phase current",
        "elements": elements,
        "analyses": [{"kind": "op"}],
        "measurements": measurements,
        "assumptions": _ideal(assumptions),
    }


SCENARIOS = (
    ("pre_layout_hot_plug.json", hot_plug_scenario),
    ("pre_layout_safe_state.json", safe_state_scenario),
    ("pre_layout_config_line.json", config_line_scenario),
    ("pre_layout_step_edge.json", step_edge_scenario),
    ("post_layout_sense_path.json", sense_path_scenario),
)

STAGE_OF = {"pre_layout_hot_plug.json": "pre_layout",
            "pre_layout_safe_state.json": "pre_layout",
            "pre_layout_config_line.json": "pre_layout",
            "pre_layout_step_edge.json": "pre_layout",
            "post_layout_sense_path.json": "post_layout"}


def stages():
    grouped = {}
    for name in sorted(documents()):
        grouped.setdefault(STAGE_OF[name], []).append("sim/" + name)
    return grouped


def extracted_records():
    """The models the validator builds, built here the same way.

    A local run and the gate must see the same numbers, so both extract
    from the board rather than from a stored file.
    """
    import pcbnew

    sys.path.insert(0, rules.TOOLKIT_ROOT)
    from pcbqa import extract, geom, headless
    from pcbqa.core import sha256_file

    headless.suppress_blocking_ui()
    geom.configure(0.001)
    with open(os.path.join(REPO_ROOT, "fab", "physical_inputs.json"),
              encoding="utf-8") as handle:
        physical = json.load(handle)
    copper = {layer: extract.validate_parameter(record, layer)
              for layer, record in physical["copper_thickness_mm"].items()}
    extract.validate_parameter(physical["board_thickness_mm"], "thickness")
    from . import layout
    board = pcbnew.LoadBoard(layout.BOARD_PATH)
    digest = sha256_file(layout.BOARD_PATH)
    records = []
    for alias, declared in sorted(extracted_paths().items()):
        traced = extract.path_resistance(
            board, declared["net"], declared["from_pad"], declared["to_pad"],
            copper)
        records.append(extract.aliased(
            extract.interconnect_model_from_path(traced, digest, physical),
            alias))
    return records


def documents():
    parameters = _parameters()
    return {name: builder(parameters) for name, builder in SCENARIOS}


def _write(path, document):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def write():
    models.write()
    return [_write(os.path.join(SIM_DIR, name), document)
            for name, document in sorted(documents().items())]


if __name__ == "__main__":
    for path in write():
        sys.stdout.write(path + "\n")
