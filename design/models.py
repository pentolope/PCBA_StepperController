from __future__ import annotations

import json
import os
import sys

from . import rules

REPO_ROOT = rules.REPO_ROOT
MODELS_PATH = os.path.join(REPO_ROOT, "sim", "models.json")

INPUT_CLAMP = "input_clamp_smbj26a"

#: The temperature the clamp's breakdown limits are stated at.
CLAMP_SPEC_TEMPERATURE_C = 25.0


def fit(parameters):
    """The weakest clamp the datasheet's own limits still permit.

    Two points bound the part: breakdown at the top of its stated range,
    where the device conducts the test current, and the clamping voltage at
    the stated peak pulse current. The straight line between them is the
    highest voltage a conforming device can hold at any current between
    them, because breakdown may not exceed the first point and the clamping
    voltage may not exceed the second.
    """
    tvs = rules._spec(parameters, "D1")["tvs"]
    breakdown_v = tvs["breakdown_max_v"]["value"]
    test_a = 0.001
    clamp_v = tvs["clamping_v"]["value"]
    clamp_a = tvs["clamping_current_a"]["value"]
    series_ohm = (clamp_v - breakdown_v) / (clamp_a - test_a)
    return breakdown_v, test_a, series_ohm


def spice_text(parameters):
    breakdown_v, test_a, series_ohm = fit(parameters)
    return "\n".join((
        ".subckt %s a k" % INPUT_CLAMP,
        "D1 a k %s_junction" % INPUT_CLAMP,
        ".model %s_junction D(IS=1.000000e-14 N=1 RS=%.6f BV=%.6f "
        "IBV=%.6e TNOM=%g)"
        % (INPUT_CLAMP, series_ohm, breakdown_v, test_a,
           CLAMP_SPEC_TEMPERATURE_C),
        ".ends %s" % INPUT_CLAMP,
    ))


def input_clamp(parameters):
    tvs = rules._spec(parameters, "D1")["tvs"]
    breakdown_v, test_a, series_ohm = fit(parameters)
    return {
        "identity": INPUT_CLAMP,
        "kind": "diode",
        "ports": ["a", "k"],
        "spice": spice_text(parameters),
        "evidence": [{
            "phenomenon": "device_electrical",
            "evidence_class": "datasheet-behavioral",
            "provenance": {"source": "components/parameters.json",
                           "documents": ["smbj_littelfuse"]},
            "applicability": {
                "status": "applicable",
                "detail": "reverse breakdown between %g A and %g A, where "
                          "the fitted line runs between the two limits the "
                          "datasheet states and so lies at or above every "
                          "conforming device"
                          % (test_a, tvs["clamping_current_a"]["value"])},
            "assumptions": [
                "the datasheet's maximum breakdown voltage and its clamping "
                "voltage at the stated peak pulse current are both limits a "
                "conforming device may not exceed",
                "the device's reverse characteristic between those two "
                "currents is no steeper than the line joining them, so the "
                "line bounds the voltage from above",
            ],
            "omitted_contributions": [
                "the breakdown voltage's temperature coefficient, stated as "
                "%g per degC, so the model describes the part at %g degC "
                "only" % (tvs["breakdown_tempco_per_c"]["value"],
                          CLAMP_SPEC_TEMPERATURE_C),
                "junction capacitance, which the datasheet states for the "
                "bidirectional variants only",
                "the thermal limit on how long the device may hold the "
                "clamping current, which is a pulse rating rather than a "
                "continuous one",
            ],
        }],
        "conditions": {
            "temperature_c": {
                "kind": "fixed-reference",
                "value": CLAMP_SPEC_TEMPERATURE_C,
                "units": "degC",
                "source": "the ambient the datasheet states its breakdown "
                          "and clamping limits at",
            },
        },
        "derivation": {
            "method": "two-point line between the datasheet's maximum "
                      "breakdown voltage at its test current and its "
                      "clamping voltage at its peak pulse current",
            "fitted_through": [
                {"current_a": test_a, "max_voltage_v": breakdown_v},
                {"current_a": tvs["clamping_current_a"]["value"],
                 "max_voltage_v": tvs["clamping_v"]["value"]}],
            "series_resistance_ohm": round(series_ohm, 9),
            "breakdown_voltage_v": breakdown_v,
            "valid_current_range_a": [test_a,
                                      tvs["clamping_current_a"]["value"]],
            "bound_direction": "upper_bound",
            "bound_argument": "a device that conducts its test current at or "
                              "below the stated maximum breakdown voltage, "
                              "and its peak pulse current at or below the "
                              "stated clamping voltage, holds the rail at or "
                              "below the line between those two points",
        },
        "notes": "not a vendor model: an upper-bound envelope of the two "
                 "reverse limits the datasheet states. The series resistance "
                 "it carries is a fit artefact, not a measured dynamic "
                 "resistance.",
    }


def records(parameters=None):
    parameters = parameters or rules.load_parameters()
    return [input_clamp(parameters)]


def check(parameters=None):
    parameters = parameters or rules.load_parameters()
    sys.path.insert(0, rules.TOOLKIT_ROOT)
    from pcbqa.sim import model_registry
    for record in records(parameters):
        model_registry.validate_model(record)
    return True


def write():
    parameters = rules.load_parameters()
    check(parameters)
    os.makedirs(os.path.dirname(MODELS_PATH), exist_ok=True)
    with open(MODELS_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(records(parameters), handle, indent=2, sort_keys=True)
        handle.write("\n")
    return MODELS_PATH


if __name__ == "__main__":
    parameters = rules.load_parameters()
    breakdown_v, test_a, series_ohm = fit(parameters)
    sys.stdout.write("breakdown %.3f V at %g A, series %.4f ohm\n"
                     % (breakdown_v, test_a, series_ohm))
    sys.stdout.write(write() + "\n")
