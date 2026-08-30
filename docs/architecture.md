# Architecture — Quiet Stepper Motor Controller

**A worksheet, not a design.** Every line below is a question this board has to
answer, and none of them is answered here. Nothing in this file is a
recommendation, and the order of the sections carries no preference.

The questions were derived from [the brief](../BRIEF.md) and from what this
board is meant to stress in the benchmark:

- motor-current routing
- driver thermal pad
- sense resistors
- mixed-signal grounding

Those are the places where a wrong answer shows up in copper.

Answer them in this file as the design is made, each answer carrying the
evidence that supports it, and record the corresponding choice against its
`OPEN-nn` entry in [board/requirements.md](../board/requirements.md). An answer
without evidence is a guess wearing a document's clothes — and this benchmark is
allowed to refuse an unsupported claim rather than invent one.

## Supply input and rail generation

- What is the worst-case input condition the board must survive across the stated 12–24 V range, and does that include supply transients or only steady state?
- How are logic rails derived from the motor supply, and what topology is justified by the logic current budget and the input range?
- What is the total logic current draw, and does the chosen regulator's dissipation at the top of the 12–24 V range fit the thermal plan?
- Where does bulk capacitance sit relative to the driver supply pins, and what ripple current does it actually see at the target phase current?
- Does the input rail need reverse-polarity or overvoltage handling for the intended installation, and what is the cost of that decision in voltage drop and board area?

## Driver selection and current capability

- Which driver device is chosen, and what evidence shows it delivers at least 1.5 A RMS per phase across the stated 12–24 V input range, under what stated duty-cycle and thermal assumptions?
- What derating does the driver's datasheet impose between peak, RMS and continuous ratings, and which of those does the 1.5 A RMS/phase figure map to?
- By what mechanism does the chosen driver satisfy the brief's 'quiet' requirement, and what does relying on that mechanism cost in torque or maximum step rate?
- What microstep resolution is selected, and what constrains it — driver capability, step-rate source, or acoustic behaviour?
- What motor winding resistance and inductance range is the design assumed to work with, and is that assumption recorded as an assumption rather than a requirement?

## Current sensing

- What sense-resistor value follows from the driver's sense-voltage specification at the 1.5 A RMS/phase target, and what headroom remains to the driver's regulation limit?
- What is the peak and RMS power in each sense resistor, and what package and rating cover it with margin?
- What tolerance and TCR are required so that phase-current accuracy holds over the expected temperature rise, and does self-heating of the resistor itself matter?
- What sense-connection scheme is used — Kelvin or otherwise — what justifies it at the resulting sense-voltage level, and where exactly does the sense return meet the power ground?
- How far, and along what path, does the sense trace run relative to the phase switching nodes — and what physically enforces that separation in the layout?

## High-current phase loops and motor-current routing

- Which loops carry the fast di/dt current, and what is each loop's enclosed area in the actual layout?
- What conductor width, copper weight and via count carry the phase current from driver to connector at an acceptable temperature rise, and against what data is that sized?
- Where are the phase-current return paths, and do they overlap the sense or logic regions at any point?
- How is the motor connector's per-contact rating reconciled with the required phase current, including derating for temperature and adjacent energised contacts?
- What in the layout keeps the switching nodes' copper area small enough to limit radiated coupling without violating the current-carrying requirement?

## Driver thermal pad, grounding and heat path

- The brief calls out driver thermal-pad grounding: how is the chosen device's exposed pad tied to ground, what does its datasheet require of that connection, and how does that requirement interact with the pad's role in the heat path?
- What is the complete heat path from junction to ambient, and what thermal resistance is claimed at each stage?
- By what structure does heat leave the pad into the spreading copper — a thermal-via array or something else — and if vias, how many, at what diameter and pitch, into which layer, and what conduction do they actually contribute?
- What copper area on which layer is dedicated to spreading, and does it conflict with the grounding scheme or with routing?
- What ambient temperature, airflow and duty cycle is the thermal result computed at, and are those assumptions stated as assumptions?
- What is the estimated driver dissipation at 1.5 A RMS/phase over the stated supply range, and what components (conduction, switching, quiescent) make it up?

## Mixed-signal grounding and stackup

- What is the ground partitioning scheme — one pour, partitioned regions, or a defined single-point tie — and what is the argument for it?
- Where does return current from the phase loops physically flow, and does any of it cross under the sense or MCU regions?
- What layer count is finally chosen, what does each layer carry, and how does that follow from the routing and thermal demands rather than from the metadata preference?
- Where is the reference plane for the logic and configuration-bus signals, and is it continuous beneath them?
- How is the driver's thermal-pad ground tied to the rest of the ground system without injecting power-ground noise into the sense reference?

## MCU, control and configuration interfaces

- Which MCU is chosen, and what peripheral generates or receives STEP/DIR at the required step rate?
- Is STEP/DIR generated on-board, accepted from an external host, or both, and what does the connector pinout imply about that choice?
- Are both UART and SPI configuration paths implemented, or is one selected — and what determines that?
- What logic level does each interface operate at, and does level translation exist anywhere between MCU, driver and connector?
- How is the MCU programmed and debugged after assembly, and what does that add to the board?
- What is the state of the driver's control inputs during MCU reset and before firmware runs?

## Fault, status and safe-state behaviour

- What fault conditions does the chosen driver report, and by which mechanism — a dedicated pin, register readback, or both?
- How is a fault surfaced off-board, and does that satisfy 'fault/status signals' for a host that has no configuration bus attached?
- What is the board's behaviour on overtemperature or overcurrent — latched off, auto-retry, or host-decided — and who clears it?
- Is there an enable/disable path that puts the motor into a defined state independent of firmware?
- What happens to the motor and the driver if the host disappears mid-motion?

## Connectors, mechanical and assembly

- What board outline, mounting scheme and connector placement does the intended installation imply, given that the brief fixes none of them?
- Which connector family serves the 4-pin motor interface, and does its current rating cover the phase current with derating?
- Are connectors positioned so that motor wiring does not run over sense or logic areas?
- Is the board single- or double-sided assembly, and what does the thermal plan require of the layer opposite the driver?
- What test points are needed to verify phase current, sense voltage and rail integrity during bring-up?

## Protection, EMC and robustness

- What transient environment does the motor cable represent, and what handles energy fed back from the winding on abrupt disconnection?
- Is any protection needed on the exposed control and motor connector pins, and what is the justification either way?
- What filtering, if any, sits on the supply input, and how is it kept from resonating with the bulk capacitance?
- How does the chosen quiet-mode and current-regulation behaviour affect conducted and radiated emissions, and what layout choices address that?
- What happens if the motor connector is unplugged while energised, or a phase is shorted to ground?

## Verification and bring-up

- What measurements will confirm actual phase current versus the 1.5 A RMS/phase target, and where are they taken?
- How is the driver's junction or case temperature verified against the thermal claim, and under what load?
- What test proves the quiet-mode behaviour is real rather than assumed from the datasheet?
- How is sense-path integrity checked — for example, that switching-node coupling does not corrupt the regulated current?
- What sequence brings the board up safely the first time, and what limits are set before a motor is attached?

## Answers still owed

All of them. See [status.md](status.md).
