# Requirements — Quiet Stepper Motor Controller

Two lists. The difference between them is the whole point of this file.

A **fixed requirement** is something [BRIEF.md](../BRIEF.md) asks for. Each one
below quotes the brief text that substantiates it; if a statement cannot be
quoted, it is not a requirement here. An **open decision** is a choice the brief
deliberately left to whoever designs this board.

> Missing details are design freedom, not permission to fabricate unstated user
> requirements.

Promoting a decision into a requirement is the failure this file exists to
prevent. Record a choice under the decision it answers, with the reasoning that
made it — never by adding it to the list above.

Bound to `BRIEF.md` SHA-256 `eb32e622a2161815c687ef267615287b89c1135211a0c5d5494930910a460444`.

## Fixed by the brief

### REQ-01 — The board is a single-axis stepper controller.

Brief text:

> Create a single-axis stepper controller using a modern quiet microstepping driver

### REQ-02 — The motor driver must be a modern quiet microstepping driver. The brief cites a Trinamic-class device only as an example; no specific part is mandated.

Brief text:

> a modern quiet microstepping driver (for example a Trinamic-class device) and a small MCU

### REQ-03 — The board includes a small MCU.

Brief text:

> (for example a Trinamic-class device) and a small MCU. Input supply: 12–24 V.

### REQ-04 — The board operates from a 12–24 V input supply.

Brief text:

> Input supply: 12–24 V. Motor current target: 1.5 A RMS/phase minimum.

### REQ-05 — The motor current target is 1.5 A RMS per phase as a minimum.

Brief text:

> Motor current target: 1.5 A RMS/phase minimum. Include current-sense resistors

### REQ-06 — Current-sense resistors must be included.

Brief text:

> Include current-sense resistors, bulk/ceramic decoupling, STEP/DIR and UART/SPI configuration access

### REQ-07 — Bulk and ceramic decoupling must be included.

Brief text:

> Include current-sense resistors, bulk/ceramic decoupling, STEP/DIR and UART/SPI configuration access

### REQ-08 — A STEP/DIR interface must be provided.

Brief text:

> bulk/ceramic decoupling, STEP/DIR and UART/SPI configuration access, fault/status signals

### REQ-09 — UART/SPI configuration access must be provided.

Brief text:

> STEP/DIR and UART/SPI configuration access, fault/status signals, and a 4-pin motor connector.

### REQ-10 — Fault/status signals must be provided.

Brief text:

> fault/status signals, and a 4-pin motor connector.

### REQ-11 — A 4-pin motor connector must be provided.

Brief text:

> fault/status signals, and a 4-pin motor connector.

### REQ-12 — The design must give particular attention to driver thermal-pad grounding.

Brief text:

> Pay particular attention to driver thermal-pad grounding, high-current phase loops, and keeping current-sense routing away from switching nodes.

### REQ-13 — The design must give particular attention to the high-current phase loops.

Brief text:

> Pay particular attention to driver thermal-pad grounding, high-current phase loops, and keeping current-sense routing away from switching nodes.

### REQ-14 — The design must give particular attention to keeping current-sense routing away from switching nodes.

Brief text:

> Pay particular attention to driver thermal-pad grounding, high-current phase loops, and keeping current-sense routing away from switching nodes.

### REQ-15 — The repository stays a consumer of the shared PCBA_AutoDesignAndTest toolkit; board-specific logic must not accumulate in the toolkit.

Brief text:

> The repository should remain a consumer of the shared `PCBA_AutoDesignAndTest` toolkit rather than accumulating board-specific logic in the toolkit.

### REQ-16 — Stated requirements are authoritative; open choices must be made and documented as engineering decisions, not invented as hidden user requirements.

Brief text:

> Treat stated requirements as authoritative; where the brief leaves choices open, make and document reasonable engineering decisions rather than inventing hidden user requirements.

## Open — the design agent decides

### OPEN-01 — Which stepper driver device to use, and in which package.

The brief requires 'a modern quiet microstepping driver' and offers a Trinamic-class device only as an example; it names no part, vendor or package.

*Decision:* **not yet made.**

### OPEN-02 — Which MCU to use, in which package, and with what memory/peripheral set.

The brief says only 'a small MCU' — no family, architecture, package or peripheral requirement is stated.

*Decision:* **not yet made.**

### OPEN-03 — How many current-sense resistors are used and on which phases, what sensing topology they sit in, and what resistance, tolerance, TCR, power rating and sense-connection scheme (Kelvin or otherwise) they use.

The brief fixes that current-sense resistors are included (REQ-06), but fixes no value, tolerance, package, count per phase or sensing topology.

*Decision:* **not yet made.**

### OPEN-04 — How the driver is configured for microstep resolution, quiet-mode and current-regulation behaviour, decay and current scaling.

The brief asks for a 'quiet' microstepping driver and for configuration access, but states no microstep count, quiet-mode mechanism or current-regulation settings.

*Decision:* **not yet made.**

### OPEN-05 — How logic rails are generated from the 12–24 V input: regulator topology, rail voltage(s), and current budget.

The brief fixes only the input supply range. It says nothing about logic voltage, regulator type or efficiency/thermal targets.

*Decision:* **not yet made.**

### OPEN-06 — Whether STEP/DIR is generated by the on-board MCU, driven from an external host connector, or both, and who owns motion profiling.

The brief lists STEP/DIR as an interface to include without saying which side of the board drives it or where motion planning lives.

*Decision:* **not yet made.**

### OPEN-07 — Whether both UART and SPI configuration paths are implemented, or one is selected, and how that path is exposed off-board.

The brief writes 'UART/SPI configuration access' without resolving whether the slash means both, either, or a build-time option.

*Decision:* **not yet made.**

### OPEN-08 — The host/control connector: family, pin count, pinout, and signal levels.

The brief fixes a pin count only for the motor connector; the control-side connector is unspecified.

*Decision:* **not yet made.**

### OPEN-09 — The power-input connector: family, current rating, polarity keying and mounting style.

The brief states the supply voltage range but nothing about how power enters the board.

*Decision:* **not yet made.**

### OPEN-10 — The 4-pin motor connector's family, pitch, per-contact current rating, orientation and retention.

Only the pin count is fixed by the brief; everything about the connector's physical and electrical spec is left open.

*Decision:* **not yet made.**

### OPEN-11 — The form of the fault/status signalling: visual indicator, digital output pin, driver register readback over the configuration bus, or a combination — and what conditions it reports.

The brief requires 'fault/status signals' without defining the medium, the fault set, or the latching/clearing behaviour.

*Decision:* **not yet made.**

### OPEN-12 — Board outline, dimensions, mounting-hole pattern, connector edge placement and any keepouts.

The brief is silent on mechanical constraints entirely.

*Decision:* **not yet made.**

### OPEN-13 — Stackup specifics: final layer count, layer assignment, copper weights and dielectric thicknesses.

Metadata records '4 preferred' as a preference rather than a fixed requirement, and neither brief nor metadata states copper weight or layer roles.

*Decision:* **not yet made.**

### OPEN-14 — The thermal strategy for driver dissipation: copper area, whether a thermal-via array is used and in what pattern, whether heat leaves through the pad into an internal or bottom plane, and the assumed ambient and airflow.

The brief directs attention to thermal-pad grounding but states no ambient, junction-temperature limit, airflow assumption or duty cycle, and prescribes no via or plane structure.

*Decision:* **not yet made.**

### OPEN-15 — Input protection strategy: reverse-polarity, overvoltage/transient handling on a 12–24 V rail, and ESD handling on exposed connectors.

The brief neither requires nor forbids protection; no environment, standard or immunity level is named.

*Decision:* **not yet made.**

### OPEN-16 — The grounding architecture — how power ground, sense return and MCU/logic ground relate (single pour, partitioned regions, stitching strategy) and where the single-point tie sits.

Mixed-signal grounding is listed as a stressor and thermal-pad grounding is called out, but no ground scheme is prescribed.

*Decision:* **not yet made.**

### OPEN-17 — Bulk capacitance value, technology, ripple-current rating and placement, and the ceramic decoupling set per rail.

The brief requires bulk/ceramic decoupling without specifying values, technologies or placement rules.

*Decision:* **not yet made.**

### OPEN-18 — Additional board features: enable/sleep/reset control, limit or endstop inputs, encoder or index inputs, test points, and programming/debug access for the MCU.

The brief lists no such features and does not exclude them; whether they are needed is a design judgement.

*Decision:* **not yet made.**

### OPEN-19 — Manufacturing and assembly constraints: fabricator and process class, single- vs double-sided assembly, and minimum trace/space and via geometry.

Neither the brief nor the metadata names a fabricator, process class or DFM ruleset.

*Decision:* **not yet made.**

## Where a decision gets recorded

1. Set `chosen` and `rationale` on the matching entry in
   [requirements.json](requirements.json). **That file is the authoritative
   record**, and the only one the benchmark's scripts read: a decision written
   only in prose is invisible to `board_status.py` and to any result that
   counts how many decisions an attempt actually made.
2. Answer it under its `OPEN-nn` heading here as well, with the reasoning and
   the evidence that made the choice. This file is the readable copy; where the
   two disagree, the JSON is what happened.
3. Cite the datasheet or standard in [docs/sources.md](../docs/sources.md).

A choice recorded this way stays visibly a choice. That is what lets a later
reader tell this board's engineering apart from its brief.

## Where this board is most likely to be faked

Places where a design run would be tempted to assert something it cannot
substantiate:

- Treating the brief's example ('a Trinamic-class device') as a mandated part, and then justifying the whole architecture — including the mechanism that makes the driver 'quiet' — from that part rather than from the stated requirements.
- Asserting that the driver's thermal pad is 'well grounded' or 'thermally adequate' without a dissipation estimate, a junction-to-ambient path, and stated ambient/airflow assumptions.
- Claiming 1.5 A RMS/phase capability without conductor sizing, connector current derating, and sense-resistor power calculations to back it — an easy number to assert and not substantiate.
- Inventing electrical context the brief never gives: a logic rail voltage, a motor inductance, a step rate, a duty cycle, or an ambient temperature presented as a requirement instead of an assumption.
- Drawing a sense-resistor value backwards from a convenient E-series part rather than from the chosen driver's sense-voltage specification and headroom.
- Describing Kelvin sensing, a star ground, or sense-away-from-switching-node separation in prose while the actual layout does none of it.
- Reading metadata's '4 preferred' as a fixed four-layer requirement, or conversely ignoring the routing and thermal reasons the preference exists.
- Adding features the brief never asked for (endstops, encoders, indicators, protection) and then presenting them as brief requirements rather than as documented design decisions.
