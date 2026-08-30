# Quiet Stepper Motor Controller

Single-axis stepper controller using a modern quiet microstepping driver and a small MCU, from a 12–24 V supply at 1.5 A RMS/phase minimum.

`PCBA_StepperController` is a single-axis stepper motor controller built around a modern quiet microstepping driver (the brief offers "a Trinamic-class device" as an example, not a mandate) and a small MCU. The brief fixes the supply range (12–24 V), the phase current target (1.5 A RMS/phase minimum), the presence of current-sense resistors and bulk/ceramic decoupling, STEP/DIR plus UART/SPI configuration access, fault/status signals, and a 4-pin motor connector; it also directs specific attention to driver thermal-pad grounding, high-current phase loops, and keeping current-sense routing away from switching nodes. Everything else — the actual driver and MCU parts, the logic rail, sense-resistor values, connector families, board outline, stackup details, protection and thermal strategy — is left to the design agent. At detail 3/5 this is a mid-specificity brief: the electrical envelope and the layout hazards are named, the implementation is not.

> **This board has not been designed.** There is no schematic, no layout and no
> part selection here — only the brief, a reading of the brief, and the
> scaffolding a design run needs. That is the intended state of this repository,
> not a gap in it.

## What the brief fixes, and what it leaves open

The brief pins down 16 requirements and deliberately leaves
19 decisions to whoever designs the board. The `Source` column says
which is which: `brief` is quoted from [BRIEF.md](BRIEF.md), `metadata` comes
from the benchmark catalogue, and `open` means the brief does not fix it.

| Aspect | Value | Source |
|---|---|---|
| Function | Single-axis stepper controller | brief |
| Motor driver | A modern quiet microstepping driver; a Trinamic-class device is given as an example only, not a mandated part | brief |
| Controller | A small MCU on the board | brief |
| Input supply | 12–24 V | brief |
| Motor current target | 1.5 A RMS/phase minimum | brief |
| Sensing and decoupling | Current-sense resistors plus bulk/ceramic decoupling (values and technologies not fixed) | brief |
| Control and configuration interfaces | STEP/DIR, and UART/SPI configuration access | brief |
| Fault/status | Fault/status signals present (form not fixed) | brief |
| Motor connector | 4-pin (family, pitch and rating not fixed) | brief |
| Layout emphasis called out by the brief | Driver thermal-pad grounding, high-current phase loops, current-sense routing kept away from switching nodes | brief |
| Likely layer count | 4 preferred | metadata |
| Category / difficulty / brief detail | motor-control, difficulty 3, detail 3 | metadata |
| Primary stressors | motor-current routing, driver thermal pad, sense resistors, mixed-signal grounding | metadata |
| Board outline, size, mounting and power-input connector | Not fixed by the brief — design agent's choice | open |

The full split, with the verbatim brief text substantiating every fixed
requirement, is in [board/requirements.md](board/requirements.md) and
machine-readably in [board/requirements.json](board/requirements.json).

**Missing details are design freedom, not permission to fabricate unstated user
requirements.** A choice the brief left open is recorded as a decision, with its
reasoning — never promoted into a requirement.

## Benchmark position

| | |
|---|---|
| Benchmark id | 8 of 32 |
| Category | motor-control |
| Difficulty | 3 / 5 |
| Brief detail | 3 / 5 |
| Likely layer count | 4 preferred |
| Primary stressors | motor-current routing, driver thermal pad, sense resistors, mixed-signal grounding |

This is a motor-control board at difficulty 3/5 and detail 3/5: it tests whether an agent can carry a modest power stage from a stated current and supply envelope through conductor sizing, sense-resistor design and a defensible thermal path, rather than drawing a schematic that only looks right. The four named stressors — motor-current routing, driver thermal pad, sense resistors, mixed-signal grounding — are all layout-and-substantiation problems, so what separates a strong result from a plausible-looking one is whether the physical implementation and its supporting calculations agree. Because the brief names an example device class rather than a part, it also probes whether the agent treats an illustrative example as a requirement.

This repository is one of thirty-two. The suite, the protocol and the results
live in [PCBA_AutoDesignAndTest_Bench](https://github.com/pentolope/PCBA_AutoDesignAndTest_Bench).

## Repository layout

| Path | Contents |
|---|---|
| `BRIEF.md` | the supplied brief — authoritative, preserved byte for byte, never edited |
| `board/requirements.md` | what the brief fixes, what it leaves open, and where decisions get recorded |
| `board/requirements.json` | the same split, machine-readable, each fixed requirement bound to brief text |
| `board/manifest.template.json` | the toolkit's minimum manifest, pre-filled for this board |
| `board/toolchain.json` | where this board's build finds KiCad and the router |
| `benchmark/metadata.json` | the supplied catalogue entry — category, difficulty, detail, stressors |
| `docs/architecture.md` | the decisions this board must make, as questions, unanswered |
| `docs/sources.md` | the classes of evidence the design will have to cite |
| `docs/status.md` | what exists, what does not, and what is deliberately absent |
| `candidates/` | disposable search output, ignored by Git |
| `.claude/skills/` | the accountability-review skill [CLAUDE.md](CLAUDE.md) requires before a push |
| `tooling/PCBA_AutoDesignAndTest` | the shared verification/routing/release toolkit, as a pinned submodule |

## Getting the repository

The toolkit is a submodule and carries KiCad Routing Tools as a submodule of its
own, so clone recursively:

```bash
git clone --recursive https://github.com/pentolope/PCBA_StepperController.git
```

```bash
git submodule update --init --recursive
```

## Designing the board

Generic verification, routing and release logic is **not** written here. It is
consumed from `tooling/PCBA_AutoDesignAndTest`, which is board-agnostic by
construction and must stay that way; this repository owns the board and nothing
else. Start from
[the toolkit's onboarding guide](tooling/PCBA_AutoDesignAndTest/examples/onboarding.md),
and see [CLAUDE.md](CLAUDE.md) for the rules a design run works under.

```bash
python3 tooling/PCBA_AutoDesignAndTest/run.py preflight
```

## Brief integrity

`BRIEF.md` SHA-256 `eb32e622a2161815c687ef267615287b89c1135211a0c5d5494930910a460444`

Every quotation in `board/requirements.json` is bound to those exact bytes. If
the brief ever changes, the bindings are stale by construction — which is the
point of recording the digest.
