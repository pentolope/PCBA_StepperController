# PCBA_StepperController — Quiet Stepper Motor Controller
## Design brief

Create a single-axis stepper controller using a modern quiet microstepping driver (for example a Trinamic-class device) and a small MCU. Input supply: 12–24 V. Motor current target: 1.5 A RMS/phase minimum. Include current-sense resistors, bulk/ceramic decoupling, STEP/DIR and UART/SPI configuration access, fault/status signals, and a 4-pin motor connector. Pay particular attention to driver thermal-pad grounding, high-current phase loops, and keeping current-sense routing away from switching nodes.
