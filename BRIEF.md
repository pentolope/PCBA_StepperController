# PCBA_StepperController — Quiet Stepper Motor Controller
## Design brief

Create a single-axis stepper controller using a modern quiet microstepping driver (for example a Trinamic-class device) and a small MCU. Input supply: 12–24 V. Motor current target: 1.5 A RMS/phase minimum. Include current-sense resistors, bulk/ceramic decoupling, STEP/DIR and UART/SPI configuration access, fault/status signals, and a 4-pin motor connector. Pay particular attention to driver thermal-pad grounding, high-current phase loops, and keeping current-sense routing away from switching nodes.

## Functional and electrical requirements

- 1.5 A RMS/phase sustained continuously across the whole 12-24 V range.
- Low-noise microstepping usable as assembled; current, microstep resolution and chopper mode settable over the interface.
- Outputs off at power-up and reset; no phase current until the driver is explicitly enabled.

## Motor drive and current sensing

- One external sense resistor per phase, non-inductive, rated for peak and RMS dissipation, tempco and tolerance inside the recorded accuracy budget.
- Sense value puts 1.5 A RMS/phase (about 2.1 A sine peak) inside the driver's sense-voltage range, with programmable headroom either side.
- Kelvin sensing at the resistor pads, returning only to the driver's sense reference and sharing no copper with phase or supply return current.

## Interfaces and connectors

- 4-pin motor connector A+/A-/B+/B-, keyed against reversed mating, rated for phase current at temperature and retained against vibration.
- STEP/DIR meet the driver's pulse width and setup/hold limits and do not ring enough to double-step.
- Configuration interface carries the pulls and idle states the driver needs and is reachable externally for read-back; diagnostics reach the MCU, at least one interrupt-capable.

## Layout, grounding and thermal

- Exposed pad soldered to copper that is both power-ground connection and heat path, tied through a via array, not a neck or a sense return.
- Phase loops - output, connector, motor, return, sense resistor, ground - as tight as layout allows, enclosing no sense or logic routing.
- Sense pairs routed together, away from output nodes, phase copper and charge-pump nodes; decoupling for the shortest supply-to-ground loop.
- Copper area, plane tie and airflow hold junction temperature under the driver's limit with both phases at full current at 24 V.

## Protection and robustness

- Motor-supply parts rated above 24 V with margin for hot-plug ringing and regenerative rise; reversed polarity does no damage.
- Survives unmating the motor while enabled, and a phase shorted pin-to-pin, to ground or to supply.
- Driver short, open-load and overtemperature detection enabled and reported; drive latches off rather than retrying into a fault.

## Test and bring-up

- Test points with local ground on motor supply, logic rail, STEP, DIR, enable, fault/status and each sense node.
- Rails, register read-back and faults verifiable with no motor fitted; MCU debug accessible.

## Open choices

- Driver device and MCU, subject to quiet microstepping with external sense resistors at 1.5 A RMS/phase or more over 12-24 V and an interrupt-capable fault input.
- UART or SPI for configuration, and whether the logic rail is made on-board or taken from outside.
- Whether STEP/DIR are also exposed to an external motion source, and whether fault/status is surfaced to a human.
- Connector families, board outline and layer count.
