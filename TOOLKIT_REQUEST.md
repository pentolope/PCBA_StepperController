# Toolkit request

What the board-agnostic toolkit should own, drawn from designing
`08_PCBA_StepperController`. Every item below was either a blocker that cost
real time, a board-side implementation of something no board should own, or a
gap that keeps this board's remaining claims unknown.

Each item states what was observed, what to add, and what it unblocks.
Board-side workarounds are named by path so the code can be lifted.

Priority 1-5 cost this board the most time or block its remaining evidence.
6-11 are smaller, but each one is a trap a later board will fall into too.

---

## 1. Safe board mutation — a `pcbqa.board` module

**Observed.** `pcbnew`'s SWIG bindings corrupt themselves on removal. After
`board.Remove(track)`, when the removed proxy is garbage-collected, the
bindings' type registry is damaged: a later `board.GetTracks()` returns an
unwrapped `SwigPyObject` (`'SwigPyObject' object is not iterable`), and
`track.m_Uuid` on *other, still-live* tracks degrades the same way. The
failure surfaces far from its cause, and the object it surfaces on is not the
object that was removed. `RemoveNative` is worse: it broke after 20 removals
in a stress test where `Remove` survived 120.

Three separate consequences, all discovered the hard way:

- a removed proxy's own fields stop answering, so a uuid must be read
  *before* `Remove`;
- a removed proxy cannot be handed back to `board.Add`, so the
  remove-then-restore idiom for "would this removal break the net?" is
  unusable — the decision has to be made before the board is touched;
- `pcbnew.LoadBoard` a second time in one process returns a degraded object,
  so a transform cannot re-read its own input.

**Ask.** A `pcbqa.board` module owning these primitives:

```python
class Copper:                      # the board's track list, read once, owned
    def __init__(self, board): ...
    def tracks(self); def vias(self)
    def discard(self, item) -> str  # uuid read first, thisown cleared,
                                    # proxy retained, then Remove
class Session:                     # one board per process, or process-isolated
    def phases(self, names, state) # resumable: each phase in a fresh
                                   # interpreter, checkpointed to disk
```

plus a documented contract: *what may be mutated in one process, and what
must not*. The retention trick (`item.thisown = False` and keep a reference)
is the entire fix and it is not discoverable from any error message.

**Board-side workaround.** `design/route.py` — `_Copper`, `run_tidy_phase`,
`TIDY_PHASES`, and `design/tidy.py` as the per-phase entry point. Roughly 250
lines that are not about this board at all.

**Unblocks.** Any board whose flow includes a post-router transform. This cost
more time than every other item here combined, twice: once before the context
break and once after.

---

## 2. The routing search loop — a `pcbqa.route` module

`pcbqa/krt.py` resolves *which* router runs and records its provenance. The
loop that actually produces an accepted candidate is left to each board, and
every part of it is board-agnostic.

**Observed, in the order it bit:**

1. **The search adopts copper the design owns.** KRT auto-registers any
   pre-existing net with ≤30 segments and ≤6 vias as a rip candidate
   (`py_router/route.py`, the `KICAD_RIP_PREEXISTING` block ~line 1766) and
   excludes it from the base obstacle map (`base_map_exclusions`, ~line 1837).
   The generated phase conductors were ripped and other nets routed straight
   through the vacated corridor; reinstating the design's copper afterwards
   produced 13 shorting-items violations. Two mechanisms fix it and both are
   needed: write design-owned copper **locked** (`protected_nets.py:230`,
   "locked means never") and pass `KICAD_RIP_PREEXISTING=0`.
2. **The search adds copper on reserved nets anyway.** Its finalize pass
   excludes only the plane nets, so reserved-net copper has to be discarded
   from the routed board and reinstated from the source. In KiCad 10 the
   segment and via blocks carry `(net "NAME")`, not a net number, and the
   block header is `\n\t(segment\n` — the format detail that made a
   first attempt silently a no-op.
3. **The grid loses fine-pitch escapes.** At the default 0.1 mm grid, four
   nets around a 0.65 mm-pitch HTSSOP failed with "the start/target pads are
   boxed in by static obstacles ... not by congestion". `--grid-step 0.05`
   fixed all four, because an escape can then sit on the pad's own centre
   line. The router's own hint says this; nothing derives it.
4. **Retries that cannot differ.** The router is deterministic for a fixed
   input, so my first attempt table (four orderings repeated three times) was
   two thirds waste. Attempts must differ in something the search reads.

**Ask.**

```python
pcbqa.route.search(
    board, reserved_nets, attempts, accept,   # accept(metrics) -> bool
    grid_step=None,                           # else derived from finest pitch
) -> RoutingRecord                            # already schema'd in routing_record.py
```

with: reserved copper locked and restored by the toolkit (a text splice, not a
`pcbnew` round trip — see item 1); `KICAD_RIP_PREEXISTING=0` set and recorded
in the provenance context; a default attempt matrix that varies ordering ×
clearance × grid and refuses two identical attempts; and a grid derived from
the board's finest pad pitch with a warning when the caller overrides it
upward.

**Board-side workaround.** `design/route.py` — `restore_generated`,
`_router_environment`, `ATTEMPT_PLANS`, `ROUTER_GRID_STEP_MM`, the
route→transform→adopt→DRC→accept loop in `run()`.

**Unblocks.** Every routed board. Item 1 of this list is a prerequisite for
doing it well.

---

## 3. Conductor physics primitives

**Observed.** The toolkit has no current-capacity model and no characteristic
impedance. `propagation.py` computes Hammerstad's effective permittivity
(`propagation.py:317`) and stops there — it derives delay but not Z0, which is
an odd place to stop, because Z0 is what decides whether a series element
terminates a conductor.

I had to write, board-side: IPC-2221 rise-versus-area (external and internal
constants), Hammerstad microstrip Z0, via-barrel copper area, and the
lumped-loop damping/overshoot that follows from Z0 and a series element.

**Ask.** In the toolkit, as functions producing claim-shaped values with their
own assumptions attached:

```python
pcbqa.conductor.temperature_rise_k(current_a, area_mm2, external=True)
pcbqa.conductor.microstrip_impedance_ohm(width_mm, height_mm, epsilon_r)
pcbqa.conductor.barrel_area_mm2(drill_mm, plating_mm)
pcbqa.conductor.damping(series_ohm, impedance_ohm)   # and overshoot fraction
```

and a board snapshot to feed them — tracks, vias and pads as plain numbers, in
millimetres, read once. `extract.py` already walks the board this way
internally; it is not exposed.

**Unblocks.** Two general classes of claim every board wants and none can
currently state: *does this conductor carry its current*, and *does this
conductor's layer change narrow it*. On this board they became 8 claims
(`design/geometry.py`), and the second one found a real defect: the first
phase via I drew carried less copper in its barrel wall than the conductor it
joined.

---

## 4. Extraction beyond resistance

**Observed.** `extract.interconnect_model_from_path` (`extract.py:744`) emits
`.subckt … R1 a b {value}` — resistance only, stated plainly at
`extract.py:32`. That is honest, and it means no board can build a post-layout
signal-integrity scenario: to say anything about ringing you need L and C.

This board's two ringing claims said, at pre-layout, that they could not be
established "until measured from extracted geometry". With only R available I
could not simulate them. I closed them analytically instead — Z0 from the
routed width and the approved stackup, then the larger of two models (lumped
RLC overshoot 0.080 V versus a source-terminated line's zero) against the
driver's 0.387 V hysteresis. That is defensible, but it is an argument, not a
simulation, and every board will have to repeat it.

**Ask.** The same path traversal, same provenance chain, returning
`(R, L, C)` or equivalently `(Z0, delay)`, and a SPICE model that is a
transmission line rather than a resistor. The traversal already knows length
per layer; the missing inputs are the dielectric height and permittivity,
which item 6 supplies.

**Unblocks.** Post-layout SI as a real simulated stage rather than an
analytic aside; `SIM.STAGE_COVERAGE` then means something stronger. Combined
with `coupling_geometry.parallelism_inventory`, it would also let a board turn
"sense routing kept away from switching copper" from a structural claim into a
simulated one.

---

## 5. Thermal

**Observed.** Nothing in `pcbqa/` addresses heat. Two of this board's three
remaining UNKNOWNs are thermal, and they are the two that matter most for
reliability:

- `board_thermal_resistance_to_ambient` — no solve, no measurement;
- `board_temperature_rise_above_ambient` — follows from it.

The board states the requirement it would have to meet (θJA ≤ 32.9 K/W at the
25 °C continuous-rating ambient, from 3.044 W estimated driver dissipation)
and then has to say it cannot establish it. The inputs are all present and all
board-agnostic: copper polygons per layer, the stackup, which footprints
dissipate how much, an ambient and a convection assumption.

**Ask.** In rough order of value per unit of work:

1. `pcbqa.thermal.via_array_resistance(pad, vias, stackup)` — the closed-form
   spreading path from an exposed pad through its via array into the plane. It
   would bound the pad-to-plane leg of every power part without a solver.
2. A coarse 2-D copper-spreading finite-difference solve over the actual
   copper, with declared boundary conditions, producing θJA with its
   assumptions and omissions attached.
3. A `THERMAL.JUNCTION_HEADROOM` gate over the result.

**Unblocks.** The largest remaining evidence gap on this board, and on every
board that dissipates more than a logic rail's worth.

---

## 6. The physical stackup from the approved catalog

**Observed.** Two half-connected paths. `stackup_physical.py` wants the
physical stackup from the board's own `(setup (stackup …))` block or from a
board-owned declaration, and refuses to assume FR-4 — correctly. Meanwhile the
approved fabricator catalog already carries the selected stackup layer by
layer (`normalized.stackups["JLC-4L-no-requirement"].layers`: prepreg 7628,
0.2104 mm) and the material's permittivity (`normalized.materials`, dk 4.4).
Nothing bridges them, so a board that has *selected* a stackup still has an
incomplete physical one.

I reached into the catalog directly and minted approved-evidence parameter
records by hand (`design/geometry.py: signal_dielectric`), taking the lowest
stated permittivity because every use of it was an upper bound on impedance.

**Ask.**

```python
stackup_physical.from_approved_catalog(selection, approved) -> PhysicalStackup
```

with per-field provenance in the existing parameter-record shape, and a
documented rule for choosing among several stated permittivities for one
material.

**Unblocks.** `STACK.PHYSICAL` and the `TIMING.*` gates become reachable
without hand-declaring what the catalog already states — this board leaves
five gates NOT_APPLICABLE partly for want of it. Also the dielectric inputs
item 4 needs.

---

## 7. Plated-hole wall thickness in the approved catalog

**Observed.** `extract.approved_finished_copper` resolves finished copper per
layer from the `copper-finished` capability category, with exactly-one-match
discipline. There is no equivalent for the plated wall of a hole, so the
via-current and via-neck claims on this board rest on a declared assumption
(18 µm, stated in the claim as assumed) rather than on approved evidence.

**Ask.** A `copper-plated-hole` capability category resolved the same way, so
`barrel_area_mm2` can be fed approved evidence.

**Unblocks.** Turns "the layer change carries at least the conductor it joins"
from a bounded-under-assumption claim into an evidenced one, on every board
that carries current through a via.

---

## 8. The orientation registry belongs in the toolkit

**Observed.** `tools/jlc_orientation.py` is 486 lines copied verbatim from
board 03 with exactly one line changed (the board filename). The gate loads it
*from the board* on purpose (`g_orientation.py`, `_rederive`) — "the board's
own derivation script is not toolkit code" — but the effect is that a fix to
the scorer has to be pasted into every board that ever ships, and no board can
tell whether its copy is current.

The freeze step also hit HTTP 403 rate limiting twice, at 18 and 24 parts of
26. The tool anticipates this in its docstring but the caller has to build the
backoff and resume loop by hand.

**Ask.** Ship the deriver as versioned toolkit code that the board *pins* — a
digest in the manifest, so the gate still checks the exact script that ran and
the board still owns the choice of version. Plus a freeze helper with backoff,
resume, and the existing rule that the response actually served is the one
committed.

**Unblocks.** The seven turned part numbers on this board (the driver, the
controller, the regulator, the P-FET, both header types, the indicators) were
found by evidence, not by a table — that machinery is too valuable to be
copy-pasted.

---

## 9. Build-time coherence

**Observed, two ways a correct-looking manifest silently does nothing:**

1. `release_generation.cpl_orientation` has no effect unless
   `release_generation.fab_format` is also declared, because `orient_cpl` is
   only called from inside the `fab_format` step (`build.py:228`, guarded by
   `build.py:188`). I declared the registry, rebuilt, and shipped uncorrected
   angles; the failure appeared two steps later as nine CPL rotation
   mismatches. A registry declared with nowhere to apply it should be a build
   error.
2. Nothing checks that a board's *derived documents* are current. Reports are
   covered by `PROV.REPORT_FRESHNESS`, but `generated/requirements.json`,
   `generated/thermal.json` and `sim/*.json` are only as fresh as the operator
   remembered to make them. I wrote per-board tests for exactly this
   (`test_the_committed_report_is_the_generated_one`, three times over).

**Ask.** A manifest-declared regeneration order the toolkit can run
(`run.py regenerate <manifest>`), and a `PROV.DERIVED_DOCUMENTS` gate that
re-runs each declared generator and compares. Plus a build-time refusal when a
declared feature has no step that consumes it.

---

## 10. Discoverability

**Observed.** The toolkit already contains things I did not find and
re-implemented, or did not find and worked around:

- `pcbqa/connectivity.py` — shape-based copper connectivity. I wrote a
  union-find `net_islands` in `design/route.py` because I did not know this
  existed, and mine is weaker (endpoint proximity, not real intersection).
- `pcbqa/coupling_geometry.py` — measured parallel-run inventory between named
  nets. This board's brief asks for sense conductors kept away from switching
  copper, and I claimed it structurally when this module would have let me
  measure it.
- `pcbqa/geom.py` — effective pad and mask polygons, which is what my board
  snapshot approximates with bounding boxes.

Separately, completeness is invisible: I found `CPL.ORIENTATION` only by
diffing my gate matrix against board 03's. `validate` says *why* a gate is
NOT_APPLICABLE, which is good; there is no view of what declaring a key would
turn on.

**Ask.** `run.py gates --missing <manifest>`, listing every NOT_APPLICABLE
gate with the manifest key that would enable it and what evidence that key
needs. And a short module index in the toolkit README grouped by question
answered ("what copper touches what", "how close do two nets run", "what shape
is this pad really"), because the module names do not suggest their contents.

---

## 11. Smaller things that still cost time

- **DRC without the sibling project silently uses KiCad's defaults.** Running
  `kicad-cli pcb drc` on a board copied to a scratch directory applied 0.2 mm
  clearance and 0.2 mm minimum track instead of this board's declared 0.15,
  producing 108 phantom violations I spent time diagnosing. A
  `pcbqa.drc(board, project)` helper that carries the authoritative project
  would make that misreading impossible.
- **No fast placement pre-check.** Courtyard overlaps and silkscreen
  collisions cost several regenerate-and-DRC cycles while positioning three
  test points. An in-process courtyard/silk check over a proposed placement,
  without a full DRC run, would tighten that loop considerably.
- **No mask-dam capability.** The catalog states
  `plugged_via_to_mask_opening_mm` but nothing for minimum dam width, so the
  segmented mask on this board's exposed pad (1.0 mm dams, 0.516 paste
  coverage, computed by hand in `design/libraries.py`) is unevidenced against
  the process. An `ASSY.PASTE_COVERAGE`-style check over an exposed pad —
  coverage within declared bounds, no via under paste — would be board-
  agnostic and directly reliability-relevant.

---

## What this board still cannot establish

| Unknown | Closed by |
|---|---|
| `board_thermal_resistance_to_ambient` | item 5 |
| `board_temperature_rise_above_ambient` | item 5 |
| `negative_injection_into_a_zero_injection_debug_pin` | nothing in the toolkit — the STM32G030 datasheet states no injection limit for those pins. It is a component-evidence gap, correctly reported as unknown. |

Items 3, 4 and 7 do not close an unknown on this board, but each converts a
claim that currently rests on an assumption or an analytic argument into one
that rests on evidence or on simulation.
