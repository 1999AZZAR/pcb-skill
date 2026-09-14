# 06 — Proving the board can actually be assembled

A board that passes DRC, routes cleanly and costs nothing can still be impossible to build. The
reference project's released fabrication package was **withdrawn** after a mechanical pass found
three FATALs: a capacitor underneath a module body, a battery connector that could not be mated, and
a battery that had no way to connect to it at all.

None of those is visible in a 2D layout view. All of them are visible in ten minutes if you measure
solids.

---

## 1. Build the 3D from the EDA's own export — and measure solids, not courtyards

**Do this.** Export the board as a solid model (STEP) *and* as a tessellated mesh (OBJ), in board
coordinates with z = 0 at the top copper. Then write three small tools:

| tool | what it does |
|---|---|
| assembly → world bounding boxes | every product in the STEP assembly, in board coordinates |
| true cross-section | slice the solid at an arbitrary x or y and render it |
| mesh reader | vertices/triangles, to answer "what protrudes past the back face" |

The reference project's model was 39 MB of STEP / 95 507 vertices / 232 998 triangles, and the tools
to interrogate it were a few hundred lines each. There is no reason to skip this step.

### Courtyard ≠ body

A courtyard is a documentation rectangle an author drew. A body is a solid. They disagree in both
directions and both disagreements are dangerous.

- **Courtyard too small:** one audio jack footprint had **no assembly outline at all**; its silk body
  reached x = 0.000 while its pads only reached x = 3.05, so every clearance check understated the
  part by **3.05 mm on one side**. Nothing collided that day — but the collision checker was blind
  there, so the next move of any neighbour would have collided silently.
- **Courtyard wrong shape:** a connector footprint built as the union of two candidate parts kept the
  *spare* part's body (19.42 × 5.98 mm) while the *fitted* part is 20.61 × 5.20 — understating the
  real width by 0.60 mm per side and overstating the depth by 0.78 mm. The DRC was checking the wrong
  box.

**Guard:** run the containment test on **real 3D bodies**, then use courtyards only for the
clearance-to-neighbours question. Test every declared body over some threshold area against every
other part, not just neighbours.

### The tool will lie to you about the 3D too

The single tallest object in the reference project's exported 3D model — an 8.477 mm header with pins
protruding 1.40 mm out of the **back** face, into the battery area — **did not exist**. The part had
been converted to three bare SMD pads; the copper was correct (3 pads, 0 drills, confirmed against
the shipped drill files); but the footprint document's title still read `HDR-TH_3P-P2.54-V-M-1`, and
the EDA resolves the 3D model from that title.

**Guard:** cross-check every 3D-derived claim against the fabrication data.

- A hole exists if and only if it is in a drill file.
- A pad exists if and only if it is in the copper Gerber.
- A mask opening exists if and only if it is in the mask Gerber (as a flash **or** a `G36` region).

And when you find a metadata lie like this, **fix the metadata**, because the next reviewer and the
enclosure designer will both read it. An enclosure built from that model would have had a 10 mm boss
and a hole under the battery.

---

## 2. Heights against the enclosure gap

Build one table. It is the most-consulted artefact in the whole mechanical pass.

```
| part | height above the PCB | source (3D model / datasheet / ESTIMATE) |
```

Rules that make it trustworthy:

- **The tallest part sets the gap.** Everything else is then automatically fine — which means the
  only number you must get right is the maximum. In the reference project the gap was believed to be
  5.00 mm set by the audio jack, and was actually **5.501 mm set by a battery connector nobody had
  measured** (its datasheet says 5.5; the 3D model says 5.501). An enclosure drawn to the old table
  would have pressed the panel onto the connector.
- **Mark every ESTIMATE.** Three parts in that table had no 3D model and no published height. One of
  them was a module whose "2.7 mm" is a reseller's claim that was never measured; another was a
  connector for which no height is published anywhere.
- **A mated connector is taller than its socket.** The core module was 2.20 mm — plus a mated
  coaxial plug at 2.4 mm nominal / 2.5 mm max, so **4.70 mm locally**, against a 5.50 mm gap. That
  0.80 mm of clearance is the whole story for whether the antenna pigtail fits, and it is the
  difference between the module's height and the assembly's height.
- **Recompute the device total whenever anything changes**, and publish the arithmetic:

  ```
  device = panel 2.350 + gap 5.501 + PCB 1.600 + cell 4.000 = 13.451 mm
  after deleting the tallest connector:  gap 4.741  →  12.691 mm
  ```

- **Apply the height rule to every part, not just the tall ones.** A 6.0 mm through-hole header
  mid-board, under a full-face panel, set the device thickness to 13.95 mm *and* was unreachable
  after assembly. Deleting it and replacing it with three bare Ø1.5 mm pads at 2.54 mm pitch — wires
  soldered flat — removed both problems for ¥0. The generalised ruling that came out of it:

  > **Nothing under the panel may be taller than the gap the enclosure can afford.** Apply the test
  > to every remaining part.

- **Local height budgets exist too.** A folded flex tail carried its own 1.5 mm component block that
  hangs down over the bottom 15 mm of the board, so parts in that band had their own ceiling. The
  reference board's tallest part there was 1.510 mm against a 3.62 mm allowance — 2.11 mm spare, and
  that had to be measured rather than assumed.

---

## 3. Connectors: mating volume and entry direction

**A connector's footprint tells you where it solders. It tells you nothing about where the plug
goes.** Two questions must be answered separately for every connector:

1. **Which way does the mouth face?** and
2. **What volume does the mating plug sweep, and what is in it?**

### The battery connector that could not be mated

Measured by cutting the solid model at the connector's centreline:

```
cavity mouth faces           −Y  (at board y = 75.600)
cavity depth                 5.00 mm
connector height             5.501 mm     (matches the JST PH datasheet exactly)
mating plug (PHR-2) length   6.85 mm      (datasheet)
  → plug protrudes           6.85 − 5.00 = 1.85 mm in front of the mouth

free corridor in front of the mouth   75.60 − 74.27 = 1.33 mm
plug body needs                                     ≥ 1.85 mm
shortfall                                             0.52 mm   → will not seat
vertical interference: 0.80 mm cap vs 0.55 mm cavity floor = 0.25 mm
```

Two 0805 capacitors, 0.80 mm tall, sat in the corridor. Moving them opened it to only 4.80 mm before
another socket's *body* blocked it — and two AWG-26 leads exiting the plug's rear face need ≈ 4 mm to
turn 90°.

**The lesson generalises past this part:** for a **side-entry** connector, the plug occupies board
area *outside* the footprint, in a direction the footprint does not encode. Draw the plug's swept
volume in plan and check it like a keep-out.

### And check that the mating half exists

The same review's third FATAL was purely a purchasing fact: the chosen cell ships with **two bare
tinned leads and no plug**, and no housing and no crimp contacts appeared anywhere in the BOM, the
manifest or the ledger. The suggested workaround in the documents — "just solder the wires to the
socket" — is impossible for a side-entry SMT header, whose posts sit inside a 5 mm plastic cavity
with no accessible metal.

**Ask of every connector: what mates with it, is it in the cart, and can the user physically join
the two halves?**

### The fix that closed four findings at once

> **Delete the connector and give the cell two bare Ø1.5 mm top-layer pads at 2.00 mm pitch.**

That removed the connector, the corridor problem and the missing-plug problem together, took 0.76 mm
off the device, and cost nothing — the same trade already accepted for the fader wires. **On a
one-off hand-built board, a connector is often worse than two pads.**

Its one new risk was recorded and mitigated: two unkeyed pads with a bare-lead cell means a reversed
cell forward-biases the charger's substrate diode straight to ground and short-circuits an
unprotected lithium pouch. Fix: unmistakable `+` / `−` silk, **and** make the two pads visually
different in size or shape so polarity is readable without the silk, **and** a hard "meter the leads
before soldering" gate in the assembly checklist.

### User-facing openings

Tabulate every opening against the outline, measured on the solid:

| part | edge | opening | note |
|---|---|---|---|
| USB-C | top | y = 99.976, effectively flush | needs a zero-setback cutout |
| slide switch | top | **0.490 mm proud** | must protrude through the wall |
| audio jack | right | flush at x = 41.400 | barrel axis at z ≈ 2.55, bore ≈ 3.7 mm — **the cutout must be cut down to the board's top surface**, not just above it |
| microSD | left | flush at x = 0.000 | |
| side keys | right | **0.145 mm proud** | see below |

Two things to check: **no two openings collide on the same face** (the reference project's top face
carried the USB-C mouth and a switch actuator separated by a 0.98 mm rib at one point — flagged), and
**every actuator protrudes enough to be driven through a wall.** A tact switch 0.145 mm proud with
~0.2 mm of travel gives the enclosure no self-alignment at all: the boss has to reach past the board
line and then travel further, and wall-thickness variation swallows the whole margin. Moving four
keys 0.35 mm bought 0.495 mm of protrusion — matching the switch on the other face — at the cost of
eight short re-routes.

---

## 4. Flex-cable folds

A folded FPC is the highest-risk mechanical feature on a small board, because everything about it is
*inferred* from a drawing unless you force it not to be. The reference project got it wrong twice —
once by 25 mm of reach, once by 180° of rotation — and the second one was FATAL.

Settle these five things, in order, each with evidence:

### 4a. The datum

**Which edge is a dimension measured from?** The panel's fold diagram gives the folded tip position
as `(50.33)`, and the "maximum protrusion" of the fold as `max 0.80`. An early pass subtracted one
from the other. They are **two different quantities sharing one datum** — both measured from the
panel's bottom edge — as the front view's unfolded reach confirms:

```
52.00 (unfolded reach from the panel's bottom edge) − 2 × 0.835 (the fold) = 50.33   ✓
```

Getting that wrong moved the acceptance window by 0.80 mm on a budget of 1.30 mm.

### 4b. The reach

Convert the tip position into **board** coordinates, including the panel's own overhang, and state
the answer as a tolerance on the mechanical assembly:

```
y_tip = 50.33 + y_panel_bottom
panel 102.15 long on a 100.00 board  →  y_panel_bottom ∈ [−2.15, 0]
centring the panel gives y_panel_bottom = −1.075  →  y_tip = 49.255
```

**Output a build instruction, not just a number:** *"the panel overhangs the board's bottom end by
0.45–1.75 mm; centring leaves +0.67 / −0.63 mm of margin."*

The first placement missed this by **24–26 mm of surplus tail**, which would have had to be absorbed
as a Z-fold inside a ≤ 6 mm gap, lying on top of a boost converter and a microSD socket. Nothing in
the design reserved that volume.

### 4c. Which face the contacts are on after the fold

This decides **top-contact vs bottom-contact socket**, and getting it wrong is a dead panel.

Establish it, do not assume it. The method that worked:

1. **Identify each view of the mechanical drawing** by its own content — a front view carries the
   polariser and active-area dimensions; a back view carries the metal bezel tabs and the grounding
   stiffeners.
2. **The finger dimensions appear only in the back view**, as a comb of 30 dimensioned bars; the
   front view draws the same area as a plain cross-hatched block that is *larger* than the finger
   field — that block is the stiffener.
3. **Determine whether the fold diagram is a same-side or opposite-side view** by reading its text.
   A fold about a horizontal axis viewed from the *same* side mirrors text top-to-bottom but
   preserves glyph order; viewed from the *opposite* side it rotates the text 180°, reversing glyph
   order and turning each glyph over. The reference drawing showed the second — so the fold diagram
   is a back view.
4. **Apply the transform.** `(x, y, z) → (x, 2y_f − y, −z)`: it **swaps the faces** and does **not**
   mirror left/right.
5. **Cross-check physically.** The tail's steel stiffeners carry *double-sided conductive* adhesive
   labelled "reinforce + ground", on the same face as the fingers. Their only possible job is to bond
   the tail to the module's metal back frame — which requires that face to end up against the panel.
   Two independent routes, same answer.

### 4d. Where the mouth is

**This is the one that was FATAL.** The socket was the correct top-contact type, at the wrong
rotation: its mouth faced the far end of the board and the tail arrived from the opposite side, rode
up onto the 2.00 mm body and stopped. **No electrical connection to the panel at all.**

The earlier pass had flagged its own mouth call as *inferred* — "inferred from the flip-lock silk bar
sitting on the far side of the body from the solder tails". The inference had a sign error: **that
silk bar is the drawer, and the drawer is on the mouth side.**

How the mouth was finally settled — three independent measurements:

1. **Read the manufacturer's section as vectors**, not as a raster. Decompressing the drawing PDF's
   content stream and extracting the geometry showed one tuning-fork contact per position, whose free
   tips sit at the **opposite** end from the 0.085 mm flat solder foot. *A beam pair anchored and
   closed by a curl at the far end has nowhere for a cable to go — the mouth is the free-tip end.*
2. **Compare the footprint's component shape against the 3D bounding box.** They agreed at one end
   and differed by **0.845 mm** at the other — exactly the drawing's 0.85 ± 0.05 solder-tail
   protrusion. So the tails are unambiguously at that end.
3. **Measure the candidate mouth.** The recess on the tail end spans **15.05 mm** against a
   **15.50 mm** cable. It cannot be a mouth; it is where the contact tails emerge.

**Guard:** never let "which way does it open" stay inferred. It is settleable in an hour from the
manufacturer's own section, and it is worth an hour.

### 4e. The trap that the fix creates

For this connector family, **mouth direction and pin-1 end are rigidly coupled**: the same flat cable
flipped over to suit the other contact type presents pin 1 at the other end. So:

| what you do | mouth | pad 1 | result |
|---|---|---|---|
| leave it | wrong | correct | open circuit — panel dead but safe |
| rotate only | correct | **wrong** | **26 V on the panel's ground — panel destroyed** |
| rotate **and** renumber 1↔30 | correct | correct | correct |

**The rotation fix and the footprint renumber must be one commit, never two.** And because the
renumber undoes the rotation's end-swap, the net at each physical x is unchanged — the re-route is a
**translation, not a permutation**, so the differential-pair geometry survives. (The rejected
alternative — flip the panel instead — makes the pin map genuinely mirrored and turns the re-route
into a 30-net permutation that wrecks the pair routing.)

Also fix the **pin-1 marker**. The reference project's silk triangle pointed at the pad carrying the
backlight anode at 22.4–26.4 V, and the parts manifest still named the *other* candidate part as the
default. Either of those alone would put 26 V on the panel's ground on the bench.

### 4f. Insertion window and bend radius

- **Insertion window.** From the connector's section: contact dimple at 1.45 mm, hard stop at
  2.75 mm — a **1.30 mm window**. The corrected placement achieved 2.124 mm, dead centre. The whole
  tolerance budget is where the panel sits, ±0.65 mm, which is why the socket's y had to be right to
  ~0.5 mm.
- **The bend radius is not the tail's stated thickness.** The 0.3 ± 0.03 mm figure is the **tail tip
  with its stiffener**, not the fold region. The panel maker put a single-layer, coverlay-free zone
  exactly at the fold precisely so a thin web tolerates a static bend far below the usual
  6 × thickness guideline. **Do not apply a thickness-based radius rule at the fold.**
- **Add no bend of your own.** Check the run from the fold to the socket: in the reference project it
  descends ≈ 4.7 mm over 35 mm — a 7.6° ramp, no second bend of any consequence.
- **Reserve the fold's protrusion in the enclosure** (here, 0.80 mm below the panel's bottom edge).
- **Check the mated pair's dimensions.** The socket's recommended cable was 4.00 mm fingers /
  6.00 mm stiffener; the panel gives 3.00 / 5.00. Width, pitch, contact span and thickness match
  exactly; the tail is simply 1 mm shorter in both directions. It still works — the dimple is only
  1.45 mm in — but it removes 1 mm of wipe and retention margin, which is worth knowing at bring-up
  if a lane is intermittent.

---

## 5. Parts under module bodies

**FATAL, and invisible in 2D.** An 0805 capacitor (body 26.253–28.248 × 77.850–79.150, 1.300 mm tall)
lay wholly inside a Bluetooth module's body rectangle. The module solders on 11 pads along one edge
and **cantilevers 23.7 mm**. A castellated module lands flat on its pads with ~0.1 mm of standoff. So
the capacitor either holds the module's underside 1.15 mm off its pads — tilting the far end 9.6 mm,
a **22° tilt**, straight into the panel — or is crushed. Either way the 11 joints do not form and the
module cannot be fitted.

**The permanent gate that came out of it:**

> **No part may sit under any module body.** Test every declared body over ~20 mm² against every
> other part's real 3D body, not against courtyards.

That test found exactly one such pair on a 149-part board, and it was the one that stopped the build.

### The copper version of the same question

Under a castellated module, only **top-layer copper and via pads** can touch anything — inner and
bottom layers are irrelevant to that failure mode. But the underside is not featureless. On the
reference module it presented **20 discrete bare gold squares, 21.93 mm² in total**, in two arrays
sitting under the two dice.

What the board had under them: four 0.100 mm top-layer tracks running straight through four land
columns, and — worse — **two vias whose drill centres were inside bare gold lands**, i.e. a tented-via
membrane pressed under bare metal, holding at every ±0.3 mm placement offset, so structural rather
than a near miss.

Consequences were bounded honestly: nothing powered was under the gold (the nearest 3.3 V net was
3.359 mm away, the 26 V nets 13 mm), so it capped at SERIOUS rather than FATAL. But the worst case
was concrete: one of the affected nets ran through a 0 Ω link to a USB data line, so grounding it
would have killed enumeration, flashing and USB host mode at once.

**Fix, targeted rather than total:** keep non-ground top-layer copper and vias out of the two land
envelopes **plus 0.40 mm** — 8 segments, 23.90 mm of track and 4 vias moved. Clearing the *whole*
centre would have cost 27 segments, 122.63 mm and 11 vias **and bought nothing**, because only
top-layer copper can touch the module.

### Should you connect the module's centre lands?

Measure it before deciding. For the reference module: die-to-ambient was **28.2 K/W**, of which the
sealed case is 9.42 and the module's own internals 14.4; the 11 electrically-connected perimeter pads
alone give 0.40 K/W and the module simply lying on the board adds 1.3–6.5 K/W in parallel. **Soldering
all 20 centre lands would drop the junction by 0.2–0.5 K.** Not worth a joint a hand-solderer cannot
inspect.

And the real thermal constraint turned out to be elsewhere entirely: the lithium pouch reaches 40 °C
playing, 43 °C streaming and **48 °C playing while charging at 500 mA**, against a 45 °C charge
window. The fix was a resistor value that reduces the charge current, plus the enclosure — not
anything about the module.

---

## 6. The back face, and through-hole joints over a battery

If a cell is glued to the bare back of the board, the back face is a mechanical surface, not just a
routing layer.

**The rule:** **a plated through-hole's solder joint protrudes onto the back face.** So through-hole
parts must be confined to the region the cell does not occupy. In the reference project:

> Through-hole parts are limited to three components and all sit above y = 62.5 mm — off the Li-Po
> cell — because a plated hole's solder joint protrudes onto the back face where the pouch is glued.
> Any future part change must respect this.

Verify it on the fabrication data, not on intent:

| check | reference result |
|---|---|
| plated component holes inside the cell rectangle | **0** (all 9 at the far end) |
| bottom solder-mask openings | 9 on the whole board, all 31 mm clear of the cell |
| bottom silkscreen | completely empty |
| vias passing through the cell area | 297, **all tented** |
| things protruding past the back face in the solid model | 2 — one real (a switch's pins, outside the cell), one phantom (§1) |

**Non-plated holes are a lesser but real issue.** Eleven NPTH holes fell inside the cell rectangle;
measured on the solid, none of the locating pegs reaches through. Accepted, with a mitigation
(a small Kapton square over the two largest holes when gluing the cell) rather than a board change —
adhesive wicks into an open hole, and a Ø1.2 mm hole is a place for the pouch to be pressed in over
time.

**Battery lead routing is a design item.** With no pass-through in the board, the leads must wrap an
edge. Find the free window and measure it: the reference project's only one was 4.85 mm wide, and it
put the wires directly over the parts that already blocked the plug. That problem disappeared when
the connector became two pads — but it would not have been found without asking.

---

## 7. A keep-out that exists only on a documentation layer does not exist

**A `Document`-layer polygon does not constrain a pour.**

The reference project declared an antenna keep-out as a document-layer polygon and recorded the
finding as fixed on the strength of a *component* keep-out — which measures nothing about copper.
Rastered at 0.5 mm straight out of the shipped Gerbers:

| layer | ground pour coverage inside the declared keep-out |
|---|---|
| L1 | **93.8 %** |
| L2 | **93.8 %** |
| L3 | **93.8 %** |
| L4 | **93.8 %** |

Plus **10 ground stitching vias inside it**. A 2.4 GHz module antenna sitting on a stitched
four-layer solid ground plane 0.394 mm beneath it is detuned and largely shorted — a metre or two of
range instead of ten — and it cannot be fixed after fabrication.

**The fix, and the proof.** Cut real copper keep-outs on all four layers, delete the stitching vias,
regenerate the Gerbers, and **re-raster** — the same method that disproved the original claim:

> copper inside the keep-out is **0.0000 % on L1, L2, L3 and L4 — 0 of 1 240 000 pixels per layer**
> (was 93.8 % on every layer).

**Generalise it:** for every keep-out, exclusion zone, courtyard or "reserved channel" in the design,
ask *which layer is it on, and what does that layer actually constrain?* Then verify from the
fabrication output, not from the canvas.

The same logic applies to non-copper obstacles: an enclosure requirement that a metal battery pouch
must stop ≥ 10 mm short of the antenna region is a *purchase and assembly* constraint, and it has to
be written into the enclosure spec, because nothing in the EDA will ever check it.

---

## 8. Assembly order

Tall parts and walls block the iron. Derive the order from the geometry rather than guessing.

**Method.** Compute every (pad, neighbouring body) pair closer than ~0.8 mm and read the ordering
constraints off the list. The reference project had **205 such pairs**; the ones that imposed an order
were a handful:

```
C412 → BT501  0.000 mm   (this was the FATAL)
C501 → BT501  0.350
R410 → BT501  0.418
C420 → J401   0.350      (and J401 is 4.74 mm tall)
R413 → J401   0.744
L301 → U301   0.300
C304 → D301   0.300
```

The resulting order:

1. all passives and small ICs;
2. the large castellated module — it has 1.80 mm of clear board around it and 0.557 mm of land
   exposed past the body on all four sides, so every pad is reachable with a fine tip;
3. the remaining ICs, then the fine-pitch connectors (measure the exposed land in front of each body:
   1.10 mm and 1.30 mm here) while nothing tall is in the way;
4. the tall blocks — jack, USB-C, switch;
5. the cantilevered module (the easiest joint on the board once the part underneath it is gone);
6. flying leads — fader wires, battery leads — **last**.

Two more assembly facts that belong in the build instructions rather than the BOM:

- **Anything that must be configured before a part is soldered down.** The Bluetooth module's TX/RX
  mode is a solder jumper **on the module's own top face**; after assembly that face sits under the
  panel in a 5.5 mm gap. *Set it before soldering the module.* This is a one-way door and it must be
  written where the builder will read it. (See `07-bringup.md`.)
- **Hand-solder hazards that are accepted rather than fixed.** An 0603 pad 0.118 mm from a SOIC's
  plastic body gives the iron tip nowhere to sit, and a bridge to the neighbouring pin is easy to
  make and hard to see. Accepted — with the ordering constraint written down, which costs nothing.

Also worth flagging to the builder: **vias inside pads**. On the reference board 88 of 517 vias had
their barrel inside a mask opening; 68 of those were fully inside a top pad on the *same* net —
deliberate via-in-pad under decoupling caps and the inductors, electrically correct. For hand
assembly it means solder wicks down those vias: on the four true via-in-pad joints, use a little
extra solder and expect a slightly starved fillet.

---

## Mechanical checklist

```
[ ] 3D solid exported from the EDA, in board coordinates, z = 0 at top copper
[ ] every 3D claim cross-checked against the drill / copper / mask Gerbers
[ ] height table, with the source and the ESTIMATE flags, and the device total recomputed
[ ] the gap set by a measured tallest part — including mated plugs, not just sockets
[ ] every connector: mouth direction established (not inferred) and mating volume drawn
[ ] every connector: the mating half exists, is in the cart, and can be joined by hand
[ ] flex fold: datum, reach, contact face, mouth, insertion window, bend region — each with evidence
[ ] pin-1 marker and the parts manifest agree with the fitted part, not a spare
[ ] no part inside any module body (real bodies, not courtyards)
[ ] no non-ground top copper or via drills under a module's exposed lands
[ ] through-hole joints confined off any glued cell; back face verified from the Gerbers
[ ] every keep-out verified on the layer that actually constrains copper, by re-rastering
[ ] every user-facing opening measured; actuators proud enough to drive through a wall
[ ] assembly order derived from pad-to-body pairs, and the one-way doors written down
```
