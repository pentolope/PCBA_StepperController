# Benchmark entry — board 8 of 32

[metadata.json](metadata.json) is the supplied catalogue entry for this board,
preserved byte for byte from the seed pack. It is the same record that appears
in `boards_index.json` in
[PCBA_AutoDesignAndTest_Bench](https://github.com/pentolope/PCBA_AutoDesignAndTest_Bench), and the two must agree.

| | |
|---|---|
| Repository | `PCBA_StepperController` |
| Board id | `stepper_controller` |
| Category | motor-control |
| Difficulty | 3 / 5 |
| Brief detail | 3 / 5 |
| Likely layer count | 4 preferred |
| Primary stressors | motor-current routing, driver thermal pad, sense resistors, mixed-signal grounding |

`difficulty` is how hard the board is. `detail` is how much of it the brief
states — and a low `detail` is not a low bar. A detail-1 brief leaves the
architecture open on purpose, and an agent that fills the silence with invented
user requirements has failed the board more thoroughly than one that designs it
badly.

This is a motor-control board at difficulty 3/5 and detail 3/5: it tests whether an agent can carry a modest power stage from a stated current and supply envelope through conductor sizing, sense-resistor design and a defensible thermal path, rather than drawing a schematic that only looks right. The four named stressors — motor-current routing, driver thermal pad, sense resistors, mixed-signal grounding — are all layout-and-substantiation problems, so what separates a strong result from a plausible-looking one is whether the physical implementation and its supporting calculations agree. Because the brief names an example device class rather than a part, it also probes whether the agent treats an illustrative example as a requirement.

## What goes here

Compact results only: metrics, verdicts, and the commit each was measured at.
The evidence for a result is the artefact the toolkit recomputes, not a summary
of it.

Routing search output, candidate pools, build trees and field-solver dumps do
**not** go here. They are ignored by [.gitignore](../.gitignore) and are
regenerated from what is committed. Thirty-two repositories share one benchmark
clone; weight here is paid thirty-two times.

## Protocol

The attempt protocol is defined once, in the umbrella repository, so that
thirty-two boards cannot drift into thirty-two protocols. See
[PCBA_AutoDesignAndTest_Bench/BENCHMARK.md](https://github.com/pentolope/PCBA_AutoDesignAndTest_Bench/blob/main/BENCHMARK.md).
