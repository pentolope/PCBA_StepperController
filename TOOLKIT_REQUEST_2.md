# Toolkit request 2 — sizing a heatsink

`TOOLKIT_REQUEST.md` asked for a thermal capability and Phase 3 delivered it.
This board declared it, `THERMAL.BOARD_RISE` failed at 90.8 °C against a
45 °C budget, and the response was to add a heatsink. Sizing one exposed five
things the toolkit cannot express or cannot resolve. All five are
board-agnostic; none is specific to a stepper driver.

Every number below was produced by the toolkit's own `pcbqa.thermal`
physics — `SpreadingSolve`, `via_array_resistance_c_per_w`,
`spreading_resistance_c_per_w` — over this board's real copper coverage.
Only the extra heatsink node is board-side, and it is exactly what item 1
asks the toolkit to own.

---

## 1. A heat-removal device the solve can be told about

**Observed.** `thermal.board_rise` takes a single `convection_w_per_m2k`
applied to both faces of every cell, and nothing else removes heat. There is
no way to declare a heatsink, a chassis mount, a cold plate, or a fan.

A board that adds a heatsink therefore has exactly two options, and one of
them is dishonest:

* leave the gate failing forever, because the design change it was supposed
  to drive cannot be recorded; or
* raise `convection_w_per_m2k` until the number comes out — inventing an
  environment to pass a check, which is the failure mode this whole toolkit
  is built to prevent.

This board took the first. The heatsink is sized and specified and the gate
still says 90.8 °C, because the manifest has no vocabulary for the part that
fixes it.

**Ask.** A declaration for a device that removes heat at declared cells:

```
thermal.heat_removal: [
  { id, attached_to: {reference | cells | net+area},
    contact_area_mm2,
    interface_resistance_m2k_per_w,     # the TIM, per unit area
    resistance_c_per_w: {value, measured_at_rise_c, source, document} }
]
```

and in the solve, one isothermal node per device coupled to its covered
cells through the interface conductance and to ambient through its own
resistance. That is a dozen lines in `SpreadingSolve` — I wrote them
board-side to get the numbers in this document, and they should not live
here.

The gate should then refuse the two ways this can be faked: a device with no
`source` for its resistance, and a device attached to a reference that is
not on the board (the same refusal `THERMAL.BOARD_RISE` already makes for a
dissipator off the outline).

**Unblocks.** Any board that cools something with hardware rather than with
copper. On this one it is the difference between a permanent red gate and a
verified design.

---

## 2. A dissipating part is not a point

**Observed.** `THERMAL.BOARD_RISE` puts a part's whole dissipation into the
single cell its footprint origin lands in, whatever size that cell is and
whatever size the part is. U1 is an HTSSOP-28 whose exposed pad is
2.75 × 6.2 mm = 17.1 mm². At the 40 × 32 grid this board declares, a cell is
4.1 mm² — a quarter of the pad — so 3.04 W is injected into a quarter of the
area it actually enters the copper through.

The peak the gate judges moves with a grid the board chooses freely:

| grid | cell area | peak rise | mean rise |
|---|---|---|---|
| 16 × 13 | 25.1 mm² | 92.0 °C | 45.6 °C |
| 20 × 16 | 16.3 mm² | 96.1 °C | 45.6 °C |
| 26 × 21 | 9.6 mm² | 98.0 °C | 45.6 °C |
| 40 × 32 | 4.1 mm² | 104.2 °C | 45.6 °C |
| 52 × 42 | 2.4 mm² | 106.8 °C | 45.6 °C |

The mean is grid-independent, as it must be — the physics of total heat in
and out does not care about discretisation. The peak is not, and the peak is
what the budget is judged against. Worse, the *design consequence* moves
with it: the heatsink resistance this board needs to reach 45 °C is
17.3 K/W at a pad-sized grid and 9.3 K/W at the grid it declared. A board
can halve its own heatsink requirement by declaring a coarser grid, and
nothing refuses it.

To be fair to the solve: the hot spot is real, not an artefact. It is 2× the
mean at every resolution. But its magnitude, and therefore the hardware it
demands, is currently a declaration rather than a measurement.

**Ask.** Spread each source over its own area — the courtyard, or better the
sum of its pads — across whatever cells that area covers, weighted by
overlap. The geometry is already available: `pcbqa.geom.BoardGeometry`
carries every pad polygon, and `copper_coverage` already rasterises polygons
onto this exact grid. Then a finer grid converges instead of diverging, and
`grid` becomes a resolution choice rather than an answer choice.

Where a part's area is genuinely unknown, injecting at a point is the
conservative direction — but it should say so, and the claim should carry it
as an assumption rather than leave the reader to discover it.

---

## 3. A thermal resistance is quoted at a temperature rise

**Observed.** `theta_record` carries `measured_on` for the copper a junction
figure was measured over, which is the right discipline — `THERMAL.JUNCTION`
correctly downgrades to a conditional margin when this board's copper does
not match. Natural-convection heatsinks need the same discipline on a
different axis: their resistance is a function of the rise they are working
at, roughly θ ∝ ΔT^−0.25, because the convection coefficient is.

Catalogue parts are quoted at 50–75 °C rise. This board's heatsink works at
about 20 °C rise, where the same part is roughly 25% worse. A board that
reads 5 K/W off a datasheet and declares it will be optimistic by that much,
and nothing would catch it.

**Ask.** If item 1 lands, make `resistance_c_per_w` a record with
`measured_at_rise_c` required, and have the solve either correct it to the
rise it actually converges at, or refuse when the two differ by more than a
declared tolerance. This is the same shape as `current.basis.validity`
refusing outside its fitted window, and for the same reason: a number
outside the conditions it was measured under is not a conservative number,
it is an unmeasured one.

---

## 4. Convection is not one number for the whole board

**Observed.** `SpreadingSolve` applies one coefficient to both faces of every
cell. Real boards are not uniform: this one would have a heatsink over part
of the bottom face (which is then not convecting to open air at all), the
rest of the bottom in still air, and the top populated with parts. An
enclosure wall, a chassis mount, or a fan blowing across one region all
break the assumption in the same way.

Verified on this board, holding everything else fixed: the heatsink
resistance required to reach the 45 °C budget is 6.9 K/W if the board's own
faces convect at 5 W/m²K and 9.3 K/W if they convect at 10. A factor of two
in a single global input the board declares once, with no way to say that it
is not the same everywhere.

**Ask.** Let `convection_w_per_m2k` be either a scalar (as now) or a list of
regions — `{cells | rectangle_mm, coefficient, why}` — with a declared
default for everything not covered. Same evidence discipline, finer subject.

---

## 5. The path from a junction into the copper

**Observed.** `pcbqa.thermal` has the two primitives — a plated via array in
parallel, and a disc-form constriction into a plane — and nothing composes
them. `THERMAL.BOARD_RISE` solves the copper; `THERMAL.JUNCTION` judges the
package. Neither owns what joins them, so the board is left to decide
whether a junction sits on top of the copper the solve reports or 50 °C
above it.

On this board, with the toolkit's own functions:

| segment | resistance |
|---|---|
| junction to exposed pad (datasheet θJC) | 6.0 K/W |
| pad to F.Cu, disc constriction over 17.1 mm² | 0.3 K/W |
| pad to the inner layers, 9 × Ø0.3 mm barrels, 18 µm wall | 27.2 K/W |
| the same, through the 0.2104 mm prepreg in parallel | 41.1 K/W |
| **pad to inner layers, the two in parallel** | **16.4 K/W** |

The 16.4 K/W is why the one-node-deep model is optimistic for a part like
this: it treats all four copper layers as one node the exposed pad reaches
for free, when three of them are behind a barrier that costs 3.04 W × 16.4 =
50 °C. It is also the number that decides whether a bottom-side heatsink is
worth fitting — and it turns out that it is, because most of U1's heat
crosses to B.Cu over the whole board area (about 1 K/W through 1.6 mm of
FR4 over 52 cm²) rather than through the nine vias.

**Ask.** A `junction_to_copper` composition — θJC plus the declared via
array plus the constriction — that `THERMAL.JUNCTION` adds to the solved
cell rise, so a board with a solve gets a junction *temperature* instead of
a conditional margin. The inputs are all declared already: `theta_jc` is a
`theta_record`, the via array is on the board, and
`current.physical_inputs` states the plating.

While that path is unmodelled, the honest reading of a passing
`THERMAL.JUNCTION` is narrower than it looks: it says the package can shed
its heat into an ideal board, not that this one does.

---

## What the sizing came out at

Target: **≤ 6 K/W sink-to-ambient**, bonded to the bottom copper under U1
over at least 20 × 20 mm with a thermal pad of 1 K·cm²/W or better. The
whole bottom face is free — this board places nothing on it.

| | max copper rise | J2, the 85 °C part | U1 junction |
|---|---|---|---|
| no heatsink | 104.2 °C | 46.5 °C | 162 °C |
| 9 K/W | 44.5 °C | 19.9 °C | 103 °C |
| **6 K/W** | **39.1 °C** | **15.6 °C** | **97 °C** |
| 4 K/W | 34.4 °C | 11.9 °C | 93 °C |

9 K/W is the bare minimum and only at the most optimistic convection
assumption; 6 K/W holds across the range in item 4 and across every grid in
item 2.

At the natural-convection optimum fin spacing for a 30 mm fin at a 20 °C
rise — 5.9 mm, Bar-Cohen and Rohsenow, giving 6.3 W/m²K on fin area — that
is about 265 cm² of surface: **60 × 60 × 30 mm, eight fins**, or any
catalogue part rated 4 K/W or better at its own quoted rise (item 3).

Two alternatives were checked and both fail. Derating reaches 45 °C only at
0.5 A RMS per phase, a third of the design current, even on the most
forgiving grid. Forced air over the whole board leaves 62.5 °C at
50 W/m²K. Neither works because the constraint is a local constriction at
one package, and only something attached to that package relieves it.
