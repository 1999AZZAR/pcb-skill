# Case study — one board, honestly

This skill was written from a single real project. Everything in `SKILL.md` and in `references/` is
either a rule that project needed or a rule it learned by not having it.

This page is the evidence. It says what the board was, what the process caught, what each catch
would have cost, what it cost to run, and what it did not solve.

**One thing up front, because it changes how you should read the rest:** the board has been released
to fabrication and staged for purchase, but at the time of writing it **has not been fabricated,
assembled or powered on**. Every defect below is a design-stage catch, verified against the design
data, the exported Gerbers and the exported 3D solids — not against a physical failure. That is a
weaker claim than "we built it and it worked", and the page is written to be honest about which one
it is.

---

## 1. The board

A slim, bar-shaped programmable music player. Hardware only; firmware was out of scope from the
first sentence.

| | |
|---|---|
| outline | **41.40 × 100.00 mm**, 4 layers, 1.6 mm |
| components | **149**, all on the panel-facing side; the battery cell is glued flat to the bare back |
| nets | **108** routed nets, each one island |
| copper | **1 882 track segments**, 5 344 mm |
| drills | 406 vias → **584 total holes** after the final prune |
| assembly | **100 % hand-soldered.** No machine placement at all |
| final DRC | **0 clearance errors, 0 connection errors** |

What is on it: an ESP32-P4 + C6 core module on 88 castellated pads, a 3.99" 400×960 MIPI-DSI panel
with in-cell touch on a 30-pin 0.5 mm flex, a Bluetooth transmit/receive module, an I²S DAC with a
headphone amplifier and an analogue source mux, a 3.5 mm jack, a microSD slot, four side keys, a
45 mm slide fader, USB-C charging with load-share, a boost converter for an 8-LED backlight string,
and a Li-Po pouch.

The stack is: panel in front, PCB behind it, all components on the PCB's panel-facing side, cell on
the back. That single decision — taken in Phase 1, from an area calculation — set the constraint that
later caught three of the defects below.

---

## 2. The constraints that shaped it

Written down at the start as hard (`H`) and soft (`S`), with the soft ones **ranked**, and that
ranking then resolved perhaps thirty later decisions without another round trip to the owner.

**Hard:**

- **The PCB must be free.** The vendor's free-prototype coupon has hard limits: both edges ≤ 100 mm,
  5 pieces, 1.6 mm, green mask, a specific surface finish, single-board shipping, "regular process"
  only. The board is 100.00 mm on its long edge. That is not a coincidence; it is the constraint
  driving the outline from the first sketch. The panel is 102.15 mm long and simply overhangs.
- **The feature list**, including Bluetooth **both** transmit and receive — which is one question,
  asked in Phase 0, that added a module, an analogue mux, three nets and about ¥12.
- **Never place an order, pay, enter a credential, or accept terms.**

**Soft, ranked:** `S1 price > S2 hand-solder count > S3 speed`, against a **¥350 hard red line**.

**And one package rule that re-priced the whole BOM:** no QFN, DFN, VQFN, bottom-terminated or
exposed-pad-only ICs. The owner had been burned by two of them on a previous board. Lead *pitch* was
explicitly **not** a criterion — a later clarification that mattered, because it re-opened parts the
first pass had excluded.

That rule alone changed the codec, the charger and the amplifier, and it interacts with `S1` in a
way worth stating: at quantity **one**, a per-part machine-placement fee (¥20 per part type on this
vendor) dwarfs every part price, so hand-assembly wins on cost — which then inverts the entire
part-selection rule, because library class stops mattering and solderability starts.

---

## 3. What the process caught

Nine, ordered by how badly each one would have ended.

| # | defect | found by | would have cost |
|---|---|---|---|
| 1 | five nets silently shorted, DRC = 0 | netlist assertions | a fabricated, populated, dead board |
| 2 | flex socket rotated 180° | adversarial forensic review | the display could never be connected |
| 3 | 0805 capacitor under a module body | 3D solid check | the wireless module cannot be fitted |
| 4 | battery connector the plug cannot reach | 3D solid check | no way to connect the battery |
| 5 | antenna keep-out that was only a drawing | Gerber raster | 93.8 % copper under the antenna |
| 6 | power rails 2.5× over rating under the cell | route review | 25–31 °C of buried copper against a lithium pouch |
| 7 | detect pin driven 1 V below absolute minimum | electrical audit | abs-max violation on the core module, continuously |
| 8 | charger set beyond its package's dissipation | electrical audit | die at its 110 °C limit for every charge |
| 9 | three checkers measuring the wrong thing | tool re-validation | every gate green on a board with real defects |

---

### 1. Net ports silently shorted five nets, and DRC read zero

**What happened.** The schematic page carried **256 net ports**. The EDA's own netlist export
mis-resolved five of them:

```
BL_SW     →  merged into TF_PWR       (L301.2, U301.3, D301.2 all landed on the TF card rail)
BL_COMP   →  merged into GND
I2S_DOUT  →  merged into GND
U0TXD     →  merged into GND
SD_D3     →  merged into BT_CON
```

A backlight switching node — a 0 to 27 V, roughly 1 MHz node — tied to the 3.3 V TF card rail. The
I²S data line tied to ground. **The design data was never wrong. The drawing primitive was.**

**Why nothing caught it.** DRC returned zero errors. A visual check of the page shows correct-looking
labels next to correct-looking wires. The board is *electrically consistent with what the netlist
says* — it is the netlist that is wrong.

**What did catch it.** A generated set of assertions, run against the EDA's **own exported netlist**:

| assertion class | count |
|---|---|
| must-connect (pin → net) | 203 |
| must-not-connect (net ≠ net) | 37 |
| must-be-open (pin has no net) | 18 |
| per-net pin count equals the generator's intent | every net |

That last row is the one that finds a *silent merge*: a merged net has more pins than intended, a
split net has fewer, and neither shows up as a missing connection.

**The diagnosis, which mattered as much as the catch.** Everything geometric was ruled out by
measurement, in this order: coincident wire endpoints (0), stubs crossing foreign stubs (0), stubs
through foreign pins (0), coincident terminators (0), stale back-references (all empty), sheet-frame
overflow (enlarging the frame to 3400 × 9000 changed nothing) — and then geometry in general, by
rebuilding the identical netlist at 12 columns instead of 6 and getting **exactly the same five
broken nets**. It is scale-dependent: small pages are unaffected, and the threshold sits between
**180 and 263 terminators**, which is why a band-by-band build had looked clean the whole time.

**The fix** was to replace every net port with a net flag. All 109 nets then resolve and all 258
assertions pass.

**If it had shipped:** five wrong nets on a fabricated, hand-populated board. The backlight short is
a converter switching node into a load rail — you find that with a scope after you have soldered 149
parts.

---

### 2. The flex socket was rotated 180°, so the panel could never be connected

**What happened.** The display's 30-pin flex tail folds 180° behind the panel. The socket on the
board was placed at `angle 180`, which put **its mouth at board y 52.67 facing +Y** — toward the
USB-C end. The folded tail arrives from **−Y** and its tip stops at **y 49.255, on top of the
socket's 2.00 mm body.** There is no connection to make. Not a tight fit — no fit.

**How it was established**, because this is the part worth copying. The socket's mouth is not stated
anywhere in words, so it was derived three independent ways from the connector vendor's own PDF:

1. The PDF's content stream was decompressed and `SECTION A-A` read **as vectors**: one tuning-fork
   contact per position, whose free tips sit at the **opposite** end from the 0.085 mm solder foot.
   The flex can only enter at the free-tip end, so the mouth is opposite the solder tails.
2. The footprint's `Component Shape` ends **0.845 mm short** of the 3D bounding box at +y — exactly
   the drawing's `0.85` tail protrusion. So the tails are at footprint +y.
3. The +y face's central recess measures **15.05 mm** against a **15.50 mm** flex. It cannot be a
   mouth.

**The earlier call had been an inference with a sign error.** A previous review had reasoned from the
"flip-lock silk bar" — but that bar is the **drawer**, and the drawer sits on the *mouth* side. It
had honestly flagged its own call as *inferred*; the gate written from it, and the parts manifest,
both repeated it.

**And then the trap inside the fix.** The 30-pin map was, as it stood, **correct** — pad *n* carried
exactly the net panel pin *n* needs, all 30, with pad 1 (ground) at x 13.450. Which means
**correcting the rotation alone would have mirrored it**: pad 1 lands at x 27.950, and the backlight
rail — **22.4 to 26.4 V** — drops onto the panel's ground finger.

The fix had to be one commit of four changes: renumber the footprint 1↔30, mirror the silk pin-1
triangle, set the socket to `angle 0` at origin `(20.700, 51.000)`, and extend the 30 tracks 4.45 mm
north under the body. Because the renumber undoes the rotation's end-swap, the whole thing is a
**translation, not a permutation** — net order and the differential-pair geometry survive. Insertion
depth afterwards: 2.12 mm against the part's measured 1.45–2.75 mm window. No BOM change.

**If it had shipped:** a board that cannot drive its only display, and a plausible "obvious fix" that
puts 26 V on the panel's ground.

---

### 3. A capacitor placed under a module body

**What happened.** A 0805 capacitor sat **wholly inside** the wireless module's body rectangle
(x 25.55–41.05, y 76.30–100.00 — a 15.5 × 23.7 mm block). That module solders on 11 castellated pads
along **one** edge and cantilevers 23.7 mm over the rest of the board. With a 1.300 mm part under the
overhang it tilts about 22° or crushes the cap.

**Why the earlier gates passed it.** Because they checked **courtyards**, and courtyards do not
describe a cantilevered body. The board had 0 courtyard overlaps and 0 pairs under 0.30 mm.

**What caught it** was exporting the board as solid geometry — STEP and OBJ — and measuring the
solids. The fix moved the part to `(24.050, 82.350, 270°)`, 0.875 mm clear of the nearest module
body, and added a permanent gate: **all 149 parts against every module body ≥ 20 mm² — 8 bodies ×
148 parts = 1 184 pairs, 0 violations.**

**If it had shipped:** the module cannot be fitted, and it is the Bluetooth radio.

---

### 4. A battery connector whose plug could not physically reach

**What happened.** Sectioning the solid at x = 4.70 showed the connector's cavity mouth facing −Y at
y 75.600 with a 5.00 mm cavity. The mating housing is 6.85 mm and protrudes **1.85 mm** — but two
0.80 mm capacitors start at y 74.27, leaving only **1.33 mm** of clear corridor. A **0.52 mm
shortfall**, plus 0.25 mm of vertical interference. And even with those caps moved, the microSD
socket's own body caps the corridor at 4.80 mm.

**And a second, independent problem found at the same time:** the battery that had been staged for
purchase ships with **bare leads and no plug**, and no housing or crimp contacts were in any cart. So
there was nothing to plug in either.

**The fix collapsed all of it.** Delete the connector; replace it with **two bare Ø1.5 mm pads at
2.00 mm pitch** on the component side. The cell's two wires solder directly. That removed the
connector, the corridor problem and the missing-plug problem in one move, and took **0.76 mm off the
device thickness** — the connector had been the tallest part on the board, not the headphone jack as
recorded.

**If it had shipped:** a board with a battery connector nobody can plug a battery into, and a battery
with no plug on it.

---

### 5. An "antenna keep-out" that was only a drawing layer

**What happened.** The design declared a keep-out under the wireless module's antenna end. It existed
**only as a polygon on the Document layer** — a drawing, not copper. Rastering the shipped Gerbers
showed **93.8 % ground pour on all four layers, plus 10 stitching vias**, directly under the antenna.

**Why it passed.** An earlier review had closed this item — but on a **component** keep-out. Nothing
had ever asked whether *copper* respected it, because nothing had looked at the Gerbers.

**The fix** cut real copper keep-outs on all four layers and deleted 14 ground stitching vias. Proof
was taken the same way the defect was found: re-raster the regenerated Gerbers at 10 µm and measure
**0.0000 % copper over x 25.550–41.050 / y 92.000–100.000 on L1, L2, L3 and L4 — 0 of 1 240 000
pixels per layer.**

**If it had shipped:** a 2.4 GHz antenna radiating into a solid ground plane 0.2 mm away. Not a dead
board — a board whose Bluetooth and Wi-Fi range are mysteriously terrible, which is among the most
expensive classes of bug to chase after assembly.

---

### 6. Power rails 2.5× over their current rating, buried under a lithium pouch

**What happened.** Both main rails ran on **0.30 mm wide, 0.5 oz *inner* copper**.

Solving each rail as a resistor network (1 oz = 0.035 mm, 0.5 oz = 0.0152 mm, ρ = 1.72 × 10⁻⁸ Ω·m):

| rail | length | on inner layer | series section carrying full current | load | IPC-2221 ΔT |
|---|---|---|---|---|---|
| system rail | 171.89 mm | 135.1 mm | **24.84 mm** | 451 mA typical | **25.4 °C** |
| " | | | | 1.01 A worst case | **179 °C** |
| USB rail | 127.50 mm | 74.1 mm | | 450 mA | **31.2 °C**, plus 141.2 mV of IR drop |

IPC-2221 wants **0.60 mm at 0.45 A** and **1.80 mm at 1.0 A** on 0.5 oz internal copper. The board
had 0.30 mm. (0.30 mm on *outer* 1 oz would have been about right for 1 A — an earlier phase had
promised "38 mV at 2 A over 75 mm of 2 mm-wide 1 oz copper", and that width was simply never routed.)

**And 48.1 mm of that hot copper lay directly over the Li-Po pouch** (cell rectangle x 0.70–40.70,
y 0.50–61.50), 0.25 mm beneath a glued lithium cell.

A companion finding: every rail changed layer through a **single 0.30 mm via**. One via carried the
entire system rail — 411 mA typical, **970 mA worst**. A 0.30 mm barrel at 25 µm plating is rated
0.95 A for a 10 °C rise, and at the vendor's 18 µm plating floor only **0.74 A**. One void in that
barrel and the board is dead or intermittent, which is the hardest failure mode to find after
assembly.

**The reviewer's own caveat, kept because it is the honest form of the finding:** every temperature
above is IPC-2221, which is conservative for internal layers — it assumes a worse thermal environment
than a plane-adjacent inner layer really has. An IPC-2152 number was **not** computed and was **not**
presented. *"What is not in doubt is the current density."*

**The fix:** widen those runs to ≥ 0.60 mm on the inner layer (0.80 preferred) or move them to 1 oz
outer copper; three vias in parallel at every rail layer change (about 8 extra vias, against a drill
budget that had room).

---

### 7. A detect pin driven 1 V below its absolute minimum

**What happened.** The headphone jack's pin 3 is a **normally-closed blade resting on the tip** —
established from the connector vendor's own schematic block, re-rendered at 6× to read it. So with no
plug inserted, the detect net **is** the left audio output.

The amplifier therefore drives the core module's pad 32 to **0.30 − 1.34 = −1.04 V** through about
0.3 Ω, on every negative half-cycle of ordinary Bluetooth playback. The absolute maximum on that pin
is **−0.3 V**.

Not an edge case. Not a fault condition. Normal operation, continuously, for as long as music is
playing with no headphones plugged in — which is the device's default state.

**The fix:** 100 kΩ in series at the jack, the detect capacitor raised to 1 µF, and the pin read on an
ADC channel instead of a digital input.

**If it had shipped:** an absolute-maximum violation on the most expensive part on the board, on
every unit, from first power-on.

---

### 8. A charger programmed for a current its package could not dissipate

**What happened.** The linear charger's program resistor was set for **500 mA**. Its own absolute-
maximum table gives θJA = **250 °C/W** and TJmax = **110 °C**, which caps dissipation at **0.34 W**.
500 mA is simply unreachable: the real current is **140–260 mA** with the die pinned at 110 °C for
the entire charge.

**The fix cost nothing:** change one resistor from 2 kΩ to 4.7 kΩ. It was already a line in the BOM.

**And it closed a second problem.** A separate thermal analysis had put the battery pouch at **48 °C
while playing and charging at 500 mA**, against a lithium charge window that ends at **45 °C**.
Dropping the charge current is what fixes that; the enclosure does the rest. The same analysis
established that the heat is *not* a layout problem — no rail runs on the face touching the cell, and
the module's own junction sits at 41 °C idle / 52 °C playing / 79 °C at the absolute worst case
against a 125 °C limit.

**If it had shipped:** a charger running at its thermal limit for every charge cycle, charging slower
than specified, warming the cell past its own safe charge window.

---

### 9. Three checkers that measured the wrong thing

This is the finding that changes how you should build everything else. In the final two passes, the
project's **own verification tools** were re-validated, and five of them were wrong. Three mattered:

**a. The 3D interference gate was measuring the previous release.** The mesh loader hard-coded the
prior package's OBJ path and cached the mesh in a pickle. It therefore read **95 430 vertices instead
of this board's 107 775** and reported **0 interferences on a board that had three** — a capacitor
and two resistors sitting inside the headphone jack's moulded body. Re-pointed at the right file, it
found all three immediately.

**b. A pad was modelled as its bounding rectangle.** A tantalum's land **swallowed** an 0805 pad
whole and the sweep still reported **0.22 mm of clearance**, because the pad's centre was inside the
rectangle and the geometry was never actually intersected. Fixed with a point-in-polygon test. (The
same class of error, on rounded and oval lands, had earlier produced 16 *false* violations in the
other direction.)

**c. Clearance was being measured on merged copper labels.** The Gerber rasteriser leaked through a
plane's own zero-width keyhole cut-ins, so two electrically separate pieces of copper were labelled as
one — a ground-island via read as **shorted to the plane**. Every Gerber clearance number on the
project had been measured that way.

Two more, for completeness: a placement checker that only tested module bodies ≥ 20 mm², so an 0603
was legally placed **underneath** a 3.5 × 2.8 mm tantalum (9.8 mm²); and a clearance sweep that
skipped same-net pairs — correct for copper, **wrong for holes**, so three stacked vias on one node
(two 0.02 mm apart, two coincident) passed the sweep and failed the real DRC.

**The general fact that came out of it:**

> **A footprint's courtyard is not the part.**

The headphone jack's courtyard stops at x 38.350; its actual solid reaches x 41.400. **The jack
overhangs its own courtyard by 3.05 mm**, and everything placed in that strip is unbuildable. The
same class of error is what the flex socket in defect 2 turned on.

Placement is now checked against per-part **solid boxes taken from the 3D export**, not courtyards.

**If these had not been caught:** every gate would have been green on a board with three physical
interferences, one pad overlap, three illegal hole spacings and unverifiable clearance numbers. The
gates would have said "release", and they would have been lying.

---

## 4. Two more, worth a paragraph each

**A four-layer board that was electrically two layers.** The design rules said four layers. The
physical stack-up record said four layers. The inner layers' `layerStatus` was `0` — copper cannot
exist on them. Nothing in the rule set or the stack-up record showed it. Routing had been running on
it. Read the layer status directly before you route.

**33 mm of abandoned copper on ten nets.** Track chains ending in a via that connects to nothing,
carrying 7 extra drill hits. Every gate passed over it because the nets **are** connected — the
abandoned stub is just extra. It took a defect class nobody had looked for, in the last pass, to find
it. And the first attempt to prune it **deleted a real route**, because two segments on the bottom
layer *cross* in mid-span and carry the net while both far ends look free.

---

## 5. The cost, honestly

### Money

| | |
|---|---|
| parts, distributor cart | **¥102.45** (27 lines) |
| parts, marketplace carts | **¥157.25** (goods ¥129.25 + ¥28.00 shipping) |
| PCB, on the free coupon | **¥0** |
| **staged total** | **¥259.70** against a ¥350 red line |

The budget also has a stated failure mode, which is more useful than the total. The same board quotes
**¥54** through the vendor's desktop ordering client without any coupon — so even a failed coupon
lands at about **¥314**, still inside the line. But through the vendor's **web order form** the same
board is **¥162**, which puts the project at about **¥422** and breaks it. The operational rule that
came out of that is one sentence: *never order this board through the web form.*

Those two numbers are also a small lesson in themselves. An earlier live reading of the *same*
specification, two days before, gave **¥64.80** and **¥172.80** — the vendor's pricing moved about
15 % in 48 hours. That is exactly why the skill insists a price is either **VERIFIED with a source
and a date** or labelled an **ESTIMATE**. A number read once and then remembered is an estimate, and
the memory does not know it.

Eighteen BOM lines came to ¥0 because they were netted against leftover stock from a previous
project. That netting is worth about ¥122 and it is why the ledger exists.

### Time

- **Two full iterations.** The first one reached a complete schematic (264 components, 170 nets) and
  then died in routing at **11 % of nets connected**, with 300 island-merges left, because the
  placement had been designed to a 0.55 mm gap that holds one track and never a via. It was restarted
  from zero on the owner's instruction. **That is the honest headline cost: one entire iteration, and
  it was a placement decision made before any copper existed that killed it.**
- **The second iteration ran two days** — 2026-09-06 to the release-to-fabrication pass late on
  2026-09-07, with the ordering handoff the following morning — and took **22 numbered work
  packages** plus 6 research packages. Most of those 22 were not new design; they were the
  consequence of a gate declared closed on evidence that turned out to be an assumption.
- **Two fabrication packages were released and then withdrawn**, each moved to `superseded/` with a
  note saying exactly why. The second withdrawal came from the 3D check that found defects 3, 4 and 5.
- **One run sat silent for 10 h 53 m.** The autorouter's worker thread died with a
  `StackOverflowError` while the JVM sat at 0 % CPU and never exited. The wait condition was "output
  file appears OR process exits", so neither fired. The error was in the log the whole time and
  nothing was watching for it. That is where the standing rule comes from: *a wait condition must
  answer — if this crashed right now, would my filter emit a line?*

### What the reviews actually returned

| review | findings |
|---|---|
| placement, adversarial | 2 FATAL, 10 SERIOUS, 3 MINOR |
| routing, adversarial | 7 SERIOUS, 8 accepted with the reason recorded |
| 3D / mechanical release check | 3 FATAL, 4 SERIOUS, 8 MINOR |
| flex-socket forensic | 2 FATAL, one of them new |
| broad electrical audit | 0 FATAL, 9 SERIOUS, 17 MINOR |
| under-module signals and thermal | 3 SERIOUS, 4 MINOR |

**Every one of those reviews was a different worker from the builder, read-only, single-pass, with
its termination criterion written before it started.** The one time that criterion was not written
first, on an earlier project, 22 candidate findings produced zero deliverables because the review
looped.

---

## 6. What this does not prove

- **The board has not been built.** No fabrication, no assembly, no bring-up. The catches are real
  and measured; the *absence* of further defects is not established.
- **Some things are deliberately deferred to a physical measurement**, and the design carries hedges
  for each: whether the panel runs on 2 lanes (four unpopulated pads exist so it can be terminated
  either way); the actual capacity of the cell (labelled 1000 mAh, judged at **780–910 mAh** on
  energy density, which clears the requirement by 4 % at the pessimistic end); Bluetooth range with
  the pouch ending 10.5 mm from the antenna keep-out; and whether a low-profile antenna plug really
  fits a **0.041 mm** corner clearance.
- **One coupon condition was never fully established** — whether the ordering route honours the free
  prototype for this design. The mitigation is the ¥54 fallback above, not a claim that it will work.
- **The final ordering clicks are the owner's**, and were left to him: the desktop ordering client
  renders a stale image to screen capture so its GUI cannot be driven by sight, the web order page has
  no file-upload control at all (measured: zero file inputs), and the EDA's own menus do not open for
  synthetic clicks. Three routes, three measured dead ends, and the honest answer was to stage
  everything and hand over the click.

---

## 7. What we would do differently

**1. Measure the mechanical fit before the schematic is finished, not after the board is routed.**
Defects 2, 3 and 4 are all one class — *a part's real solid does not match the abstraction the layout
tool uses* — and all three were found after 5 344 mm of copper existed. The socket's mouth, the
module's cantilever and the connector's insertion corridor were all knowable from vendor drawings on
day one. **Read every connector and module datasheet for its solid geometry and its mating direction
during part selection, and write the result into the parts manifest as a measured field.**

**2. Design the placement to the via lane, not to the clearance rule.** The first iteration died
because its shelves were 0.55 mm apart — enough for one 0.20 mm track, never for a via, so the
router's islands sealed themselves into 4 mm² pockets. The second iteration designed shelves at
0.76 mm against a 0.704 mm via lane and routed 108 of 108 nets. **The placement gate is routability,
not legality**, and it is derived by sweeping free spans against `(via pad + 2 × clearance)`.

**3. Calibrate every checker against a known asymmetric object before trusting one number it emits.**
Five tools on this project silently measured the wrong thing, and each one was *reporting a pass*.
The cheapest version of this discipline: build one deliberately-wrong test case per checker — a part
that overlaps, a hole pair that violates, a net that is genuinely split — and require the checker to
fail on it before you believe it when it passes. **Never let a gate read a cached or hard-coded input
path.**

**4. Write the netlist assertions before drawing the schematic, not after.** They were written after,
and they immediately found a defect that no other instrument on the project could see. Generated from
the same source as the schematic, they cost almost nothing and they are the only thing standing
between you and a silently merged net.

**5. Take the shopping session's health as a precondition, not a discovery.** Two work packages were
lost to browser state — one to an expired marketplace session that still rendered a signed-in
homepage, one to a domain the browser extension had not been granted. Both are 30-second checks at
the start of a run and 40-minute detours in the middle of one.

**6. Fix everything free while the board is open.** The re-open is the expensive part; the fixes are
not. The final pass closed twelve findings in one commit because they all rode on one re-open — and
every one of them would have been impossible after the coupon was spent.

**7. Keep the superseded packages, and mark them.** Two packages were withdrawn. Both were moved to
`superseded/` with a README stating the four numbers that made them unbuildable. A withdrawn package
sitting next to the current one, unlabelled, will eventually get ordered.
