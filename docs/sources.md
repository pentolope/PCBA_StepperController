# Sources — Quiet Stepper Motor Controller

The evidence this board's design will have to cite. **Classes of document, not
documents:** the specific parts are not chosen yet, so naming a datasheet here
would be choosing one.

A number that reaches the board carries its provenance: source, document id or
URL, retrieval date, units, and the condition it applies under. A number without
that is not evidence, and no live network lookup may change a validation or
release result.

| Kind of source | What the design needs from it |
|---|---|
| Stepper driver datasheet and its layout/application section | Sets sense-voltage and sense-resistor equations, RMS/peak current ratings and derating, the device's quiet-mode and current-regulation behaviour, exposed-pad grounding requirements and the vendor's own layout guidance for the phase loops. |
| MCU datasheet | Pin capabilities, timer/serial peripherals available for STEP/DIR generation and UART/SPI configuration, logic levels, and package thermal data. |
| Current-sense resistor datasheet | Resistance tolerance, TCR, power and pulse-power ratings, self-heating, and the recommended footprint that the chosen sensing scheme's accuracy depends on. |
| Capacitor characterisation data (bulk and ceramic) | Ripple-current rating, ESR versus frequency and DC-bias derating are what decide whether the required bulk/ceramic decoupling actually holds the rail at the target phase current. |
| Voltage regulator datasheet for whichever logic-rail topology is chosen | Confirms operation across the stated 12–24 V input, and supplies the dissipation and thermal data for the logic rail. |
| Connector datasheet (motor, power, control) | Per-contact current rating with temperature and adjacent-contact derating, wire gauge accommodation and retention — required to justify the 4-pin motor interface at the phase current. |
| Stepper motor characteristics for the intended class of motor | Winding resistance, inductance, rated current and back-EMF drive the achievable step rate, current-regulation behaviour and driver dissipation; must be recorded as a stated assumption, not a requirement. |
| PCB fabricator capability and stackup documentation | Minimum trace/space, available copper weights, via geometry and stackup options for the chosen layer count constrain both the high-current routing and any thermal via structure. |
| IPC conductor sizing / temperature-rise data | The evidence base for phase and supply conductor widths at 1.5 A RMS/phase for a chosen copper weight and permitted rise. |
| Thermal design reference data (copper spreading area, via thermal resistance) | Needed to turn the driver's dissipation estimate into a junction temperature rather than an assertion that the thermal pad is 'adequately grounded'. |
| Assembly and DFM guidance for exposed-pad packages | Paste aperture design, void limits and stencil rules determine whether the thermal path claimed in the design is achieved in the built board. |
| Transient and ESD protection component data and applicable immunity standards | If any input or connector protection is added, its clamping level, standoff voltage and energy rating must be tied to a stated environment. |

## Recording a source, once one is chosen

Replace the class with the actual document — manufacturer, part number, revision
and date — and state the fact taken from it, in the units the document uses.
Keep the class row: it says why the document was needed.

JLCPCB-wide process limits are **not** recorded here. They live in the toolkit's
`profiles/jlcpcb/`, with their own provenance; this board records only its own
tighter targets and its own selected options. A limit copied into two places is
a rival threshold, and the toolkit has a gate that says so.
