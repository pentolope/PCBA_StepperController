# PCBA_StepperController — Quiet Stepper Motor Controller

**Benchmark ID:** 08  
**Difficulty:** 3/5  
**Brief detail:** 3/5  
**Category:** motor-control  
**Likely layer count:** 4 preferred  
**Primary stressors:** motor-current routing, driver thermal pad, sense resistors, mixed-signal grounding

## Design brief

Create a single-axis stepper controller using a modern quiet microstepping driver (for example a Trinamic-class device) and a small MCU. Input supply: 12–24 V. Motor current target: 1.5 A RMS/phase minimum. Include current-sense resistors, bulk/ceramic decoupling, STEP/DIR and UART/SPI configuration access, fault/status signals, and a 4-pin motor connector. Pay particular attention to driver thermal-pad grounding, high-current phase loops, and keeping current-sense routing away from switching nodes.

## Benchmark intent

This brief is intentionally one member of a heterogeneous PCBA-autodesign benchmark. Treat stated requirements as authoritative; where the brief leaves choices open, make and document reasonable engineering decisions rather than inventing hidden user requirements. The repository should remain a consumer of the shared `PCBA_AutoDesignAndTest` toolkit rather than accumulating board-specific logic in the toolkit.
