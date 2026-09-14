# 07 — Designing so first power-up is possible

Bring-up is a design constraint, not a phase that happens later. Almost everything in this file costs
**¥0 and a few square millimetres while the layout is open**, and is impossible once the board is
fabricated.

The reference project's electrical audit produced 26 findings on a board that was already routed,
DRC-clean and released. None was fatal. Nine were serious, and every one of them was *"a value
change, a part change, or a small net stub — free now, impossible after the coupon is spent."*

---

## 1. Flash it with the product's own connector

Assume the user owns no USB-serial adapter, no programmer and no debug probe. If the product has a
USB-C socket, that socket is the programming interface.

### The modern case: it may already work

Many current MCUs contain a hardware USB-serial/JTAG peripheral that **puts the chip into download
mode by itself**. Establish this from the silicon vendor's own documentation and the module vendor's
guide, and record what you established:

| claim | source | tag |
|---|---|---|
| download mode entered with `STRAP_A = 0` and `STRAP_B = 1` | module vendor's user guide, boot-mode table | VERIFIED |
| strapping defaults: `STRAP_B` floating, `STRAP_A` weak pull-up = 1 | same page | VERIFIED |
| "The USB Serial/JTAG Controller is able to put the chip into download mode automatically" | silicon vendor's own docs | VERIFIED |
| which pins carry the USB pair | silicon vendor's GPIO reference | VERIFIED |
| those pins stop being USB if firmware reconfigures them as GPIO | same | VERIFIED |

**One thing on the board is mandatory** for that to work: the second strap must be held at its
required level by a real resistor, not by hope. On the reference board a 100 kΩ pull-up on
`STRAP_B` is what makes a virgin or crash-looping chip enumerate with nothing but a cable.

### Documentation gaps are normal — settle them from a second source

The silicon vendor's own page for this chip had an **unfilled placeholder** where the manual-download
pin should be printed (*"you need to manually put the chip into download mode by pulling low
`[Not Updated!]` and resetting"*), in both the stable and the versioned docs. The pin was established
from two other sources instead — the module vendor's boot-mode table and the flashing tool's own
boot-mode page — and the gap was written into the report so nobody re-derives it.

---

## 2. Recovery from bricked firmware

The documented way to lose the port is one sentence: *if the application reconfigures the USB pins or
disables the USB peripheral, the device disappears.* Deep sleep also drops the device — that is a
replug, not a brick.

Recovery needs exactly two things: **the boot strap held low**, and **a reset while it is held**.

### Get both without adding a button

**Reset:** you may already have one. On the reference board the master power slide switch drives the
buck converter's enable pin, with the load-share network upstream of the buck — so switching it off
removes the 3.3 V rail from the main MCU *and* the co-processor, with or without USB attached and
with or without a cell. **That is a genuine hard reset**, verified from the schematic rather than
assumed, and it costs nothing.

**Strap low:** a test pad, bridged with tweezers or a solder blob.

The recovery gesture is then: `power OFF → bridge BOOT to GND → power ON → run the flashing tool →
remove the bridge`.

### Put a GND pad **next to** the strap pad

This is the single cheapest bring-up fix in this file.

On the reference board `TP201` (BOOT) and `TP208` (GND) were **7.80 mm apart with three signal pads
physically in between**. A slipped tweezer lands on a signal pad instead of ground. Nothing is
damaged — but **the recovery attempt silently fails and you cannot see why**, at exactly the moment
you are already debugging something else.

Fix: one more GND pad directly above the strap pad, **pad-edge gap 0.40 mm, deliberately bridgeable
by tweezer or solder blob**. ¥0.00, and the band around it was empty anyway.

Do the same for every strap you might ever need to hold: pair it with its own ground.

### A button is usually the wrong answer

On a device whose front face is entirely covered by a panel and whose back carries a glued cell,
**any button fitted to the board is unreachable once the device is assembled**. A pad pair is
strictly better: cheaper (¥0 vs a part plus 3.5 mm of a 5.5 mm gap), does not consume a key position,
and works with the case open — which is the only state in which you would ever need it.

### External pulls on strapping pins

A strapping pin that relies only on the die's weak internal pull-up, on a long trace, next to an
exposed test pad, is the classic cause of an intermittent "boots into download mode". Fit an external
10 kΩ. It draws **zero standby current** (the pin is a high-Z input), and the module vendor's own
reference carrier fits one for exactly this reason.

---

## 3. Bridging a co-processor through the main MCU

If the board carries a second processor with no USB of its own, it is unflashable without an adapter
— which is precisely the thing the user does not own. Three options; the numbers decide.

### (a) Bridge it through the main MCU — chosen

Wire the co-processor's UART RX/TX and its boot strap to three spare main-MCU pins through **1 kΩ
series resistors**, keep its reset on the pin that already drives it, and keep the existing test pads
in parallel.

```
C6_BR_TX    MCU pad 88 (GPIO0)  --1k--  co-proc U0RXD  (+ existing test pad)
C6_BR_RX    MCU pad 81 (GPIO53) --1k--  co-proc U0TXD  (+ existing test pad)
C6_BR_BOOT  MCU pad 16 (GPIO1)  --1k--  co-proc IO9    (+ existing test pad)
```

**Topology rule, and it matters:** the series resistor goes **between the main MCU's pin and the
co-processor's pad**, so the test pads stay directly on the co-processor. An external dongle applied
to a test pad then always wins over the MCU, and a contention is limited to ~3.3 mA.

Cost: **3 nets, 3 × 1 kΩ (already bought), 1 DNP 0 Ω, 2 test pads, ≈ 48 mm of track, ≈ 21 mm² of
copper, 6 hand joints, ¥0.00 BOM delta, no new IC, no re-placement.**

**Verify the firmware side before committing the copper.** A vendor library exists that lets one MCU
of this family flash another over UART, taking an explicit `reset_pin` and `boot_pin` — exactly the
two lines this design provides. That is what makes the option real, and it means the USB peripheral's
unreadable CDC control lines never matter.

**Verify the pins you are about to spend.** Read the free list off the **live schematic**, not off an
architecture document. The reference project's architecture table and the built schematic disagreed
in three places — one pin was already spent, two had been freed by later decisions. And check that
none of your three is a strapping pin, so an idle co-processor driving them is harmless.

### (b) Add a hub and a second USB-serial bridge — rejected

Needs no firmware at all and gives the co-processor a permanent console. Costs: **¥8.48**, three more
hand-soldered actives plus a crystal, **~246 mm² (5.9 % of the board face)**, a new high-speed USB
link on a board with no impedance control, and a full re-place / re-route / re-verify cycle on a
layout that was already certified.

Note *why* it lost: **not price** — it still cleared the budget. Board area and re-spinning a
certified layout.

### (c) Rely on over-the-air co-processor update — rejected

The honest reading: an **interrupted** transfer is safe, because the sequence ends with "set boot
partition" and a reboot, so the old image stays selected. What it does not protect against is a
**complete but wrong image** — wrong transport, wrong pins, a crash before the entry point. Then the
link the update rides on is gone, and the update cannot fix what the update broke. The documented
recovery is *"flash it directly via its UART port"* — i.e. buy the adapter the user does not have.

**Rule of thumb:** an in-band update path is a convenience, never a recovery path. Recovery must not
depend on the thing that broke.

---

## 4. Test pads

- **Put them on a board edge, in a row, on a known pitch.** The reference board carries six at
  1.6 × 2.5 mm on a 1.95 mm pitch along the bottom edge: BOOT, UART TX, UART RX, co-processor reset,
  GND, 3V3.
- **Include a rail and a ground**, so a programmer has a reference and a meter has somewhere to sit.
- **Pair every strap pad with its own ground pad** (§2).
- **Keep them out of every mechanical corridor.** Those six pads ended **0.95 mm clear** of the folded
  flex-cable corridor — and the panel's tail presents a *grounded steel stiffener* toward the PCB in
  exactly that band. One millimetre further along and the 3.3 V pad would have had a grounded steel
  plate lying on it.
- **They are meant to be bare.** On an OSP finish they are bare copper; on ENIG they are gold. Check
  the vertical budget above them: on the reference board, tail-root block → 3.62 mm of air → tallest
  part 1.51 mm → **2.11 mm of clearance**. Not a contact risk as built, and that had to be measured.
- **Keep a probe point on any line a bridge takes over.** When the co-processor's reset line got a
  fitted 0 Ω link, its test pad became a live probe point — which is what makes the settling test in
  §6 possible.

---

## 5. What must be configured before a part is soldered down

Walk the whole BOM and ask of every part: *does this have a programmable memory, a config register,
a one-time setting, or a physical jumper?* Then ask *can it still be reached after assembly?*

The reference project's sweep of 44 part types produced exactly one one-way door, and it is a good
example of the class:

> The Bluetooth module's **TX/RX mode is a 3-pad solder jumper on the module's own top face**, and it
> needs a reset after a change. After assembly that face sits under the panel in a 5.5 mm gap, with
> the module cantilevered over its pad row. **Set that jumper before soldering the module to the
> board.**

That belongs in the **build checklist**, not in the BOM and not in a code comment.

The same sweep also produced useful negatives, worth recording so nobody re-checks them: the DAC is
fully pin-strapped in hardware (no register writes at all); the amplifier has no shutdown pin; the
charger's current is set by one resistor; the panel's touch controller's firmware lives inside the
panel.

And one genuinely undecidable strap: the panel's ID pin wants 10 kΩ to **either** ground **or** the
I/O rail and the datasheet does not say which. The board fits both footprints — one populated, one
DNP — so it is a hand swap rather than a re-spin. **When a datasheet leaves a choice open, put both
pads on the board.**

---

## 6. Hedge the unknowns with DNP pads

The cheapest insurance in hardware is an unpopulated footprint.

The reference project's largest open risk was whether a 4-lane display panel negotiates 2-lane
operation with the unused lanes floating — genuinely unestablished, and the board **had no way to try
anything about it**. Fix: four DNP 0 Ω / 10 kΩ pads from the unused lane pins to ground, plus a probe
pad on each. **¥0, and impossible after fabrication.**

Other hedges from the same audit, all of them a footprint or a value:

| unknown | hedge |
|---|---|
| module's supply floor may be above a flat cell's voltage | DNP 0 Ω pads to feed it from the regulated rail instead |
| module may bond its analogue and power grounds internally | a DNP link, and a meter check on arrival |
| a sense-line threshold depends on a leakage current nobody measured | choose the firmware threshold conservatively and say why |

**The pattern:** if a question can only be answered with the physical part in hand, put the *answer's
implementation* on the board now, unpopulated, and write the arrival test that decides it.

---

## 7. The electrical checks that decide whether first power-up works

Run a sceptical audit of the design *before* the fabrication package is final. Scope it to the things
the routing, placement and mechanical reviews did not cover: power-up sequencing and straps, every
IC's mandatory-pin sweep against its own datasheet, recomputation of every value that decides
behaviour, thermal, battery safety, and part ratings versus actual use.

The reference project's found nine serious issues on a board that everyone believed was finished.
The three that mattered most are worth stating as patterns:

**An input that is DC-connected to an output.** A headphone-detect pin was tied to a jack's
normally-closed blade, which rests on the tip — so with no plug inserted the detect pin *is* the
amplifier output. Computed: the pin is driven to **−1.04 V** on every negative half-cycle, against a
−0.3 V absolute maximum, through ~0.3 Ω of source impedance. That is tens of milliamps of substrate
injection every time audio plays with the jack empty — which is the normal case for a Bluetooth
device. Fix: 100 kΩ in series and a bigger filter cap, then read it as an analogue voltage rather
than a digital level. **Pattern: trace what a mechanical switch contact connects in *both* states.**

**A value that is right in the datasheet's own example and wrong in your thermal environment.** The
charger's programming resistor was exactly the datasheet's 500 mA value. With θJA = 250 °C/W and
TJ(max) = 110 °C, the allowed dissipation is 0.34 W, so the real current limit is **262 mA at a 3.7 V
cell and 170 mA at 3.0 V** — and inside a sealed case at 40 °C ambient, 215 / 140 mA. The part would
have sat in thermal regulation for the entire charge, delivering a third of the programmed current,
while raising the whole case and therefore the cell. Fix: one resistor value, ¥0. **Pattern: check
every current-setting value against the package's own dissipation limit, in the enclosure the product
actually has.**

**A part operated outside its specified supply.** An analogue mux run at 3.3 V, where the datasheet
specifies on-resistance only at 5 V and above and states "performance degrades below 3 V". Its own
distortion figure (0.3 % at 5 V, worse below) would then dominate an audio chain whose DAC is
0.005 %. Fix: a different part number with an **identical pinout and land pattern**, specified 2–6 V.
¥0, no schematic change, no PCB change. **Pattern: when a datasheet's electrical table does not
contain your operating point, you have no specification at all.**

Six more from the same list that generalise cleanly:

- **Nothing analogue may float.** All four mux inputs had no DC path except through the switch
  itself; the deselected node drifts on leakage and can go below the negative rail. Fix: 1 MΩ from
  each input to the bias node, ≈ 0.1 % shunt loss.
- **Check every rail against the *maximum* of what it feeds**, using worst-case tolerances. A 3.3 V
  rail computed at 3.315 V typical / **3.437 V worst** against a panel whose datasheet maximum is
  3.3 V. Fix: re-centre the feedback divider.
- **Coupling capacitors set the bandwidth, and ceramics lose capacitance under DC bias.** 100 µF
  X5R at 1.65 V bias is 60–75 µF effective, giving −3 dB at **133–166 Hz into 16 Ω** on a music
  player. Fix: a part family with no DC-bias derating — and check the replacement fits the height
  budget (see `06-mechanical.md`); most 5 × 5.4 mm aluminium cans did not fit a 4.741 mm gap.
- **A signal from a device on a different rail can exceed your MCU's rail.** Two module outputs idled
  ~1.2 V above the MCU's supply, pushing 0.5 mA per pin continuously into the ESD clamp. Note the
  rejected fix: a resistive divider to ground would have dropped the level below the MCU's input-high
  threshold at a flat cell — **check the low end of the range before adding a divider.**
- **Give any unkeyed power input reverse-polarity protection you can see.** Silk `+` / `−` **and**
  visually different pad shapes, plus a "meter the leads before soldering" gate.
- **Two things you can only settle with the part in hand** get a 60-second arrival test each, written
  down: continuity checks for whether a module bonds two grounds internally, and whether a switch's
  metal shell is common with a contact.

Finally, record what you checked and found **correct**, with the evidence — the reference audit's
"do not re-audit these" list ran to eleven items including the full mandatory-pin sweep of six ICs,
the power-up ordering, the off-state current budget and the load-share bias in both states. That list
is what stops the next pass from spending a day re-deriving it.

---

## 8. Bring-up runbook template

Write this **during design**, not after. It is what tells you whether the design is actually
bring-up-able — every step that would need a tool the user does not own is a design finding.

```markdown
# Bring-up runbook — <board>

Tools assumed: soldering iron, hot air, tweezers, multimeter, <storage media>, one USB-C cable.
No USB-serial adapter is needed at any step.

## 0. Before anything is soldered
a. Set <the one-way-door jumper> on <module>'s top face. After assembly that face is
   unreachable under the panel.
b. Confirm the strap-resistor population: R303 fitted (ID → GND), R304 not fitted.
   If <symptom> later, swap them.
c. Build the firmware with <the config option the stock SDK needs for this silicon revision>.

## 1. Power section only
Fit: input connector, protection, charger, load share, master switch, regulator + inductor +
divider, and the MCU's decoupling. **Do not fit the expensive module yet.** No cell yet —
the board runs from USB alone.

## 2. Prove the rail before you risk the module
Switch OFF → plug in → switch ON. Measure TP209 (+3V3) against TP208 (GND):
expect 3.30 V ± 0.10. **If it is wrong, stop here.**

## 3. Fit the module, repeat step 2
Expect ~3.3 V at 30–160 mA.

## 4. First flash — no button
A USB serial/JTAG device appears. Run <tool> --chip <x> flash_id, then flash.
*If it never enumerates:* switch OFF → bridge TP201 (BOOT) ↔ TP211 (GND) → switch ON →
flash → remove the bridge. This is also the recovery for firmware that later kills the port.
*If it enumerates and then vanishes:* the app is entering deep sleep — documented, not a brick.

## 5. Prove the co-processor and its link
Run <the host build> and do a wireless scan. One test proves the co-processor's shipped
firmware, the inter-chip bus and the module's own reset network at once.
Read and **write down** the co-processor firmware version.

## 6. Settle the open inference — 30 seconds, no adapter
Drive <the suspected reset pin> low for 10 ms, release, and watch the co-processor's TX line
at 115200. A ROM banner on release proves the pin.

## 7. Flash the co-processor with only the USB-C cable
Run the serial-flasher on the main MCU with reset_pin / boot_pin as designed.
*Fallback if step 6 failed:* fit the DNP 0 Ω that grounds the co-processor's boot strap, or
bridge TP206 ↔ TP210, power-cycle, flash, then remove it. Still no adapter.

## 8. Configure the peripherals that need it
<AT command sequence, and the ordering constraint: enable power first, fill the pairing table
before enabling transmit>

## 9. Backlight before pixels
Fit the display connector, insert the flex with pin 1 at the LEFT when the socket opens toward
the board's bottom edge. Enable the panel rail, then PWM the backlight at ~1 kHz, low duty.
Measure VLED_P: expect 22.4–26.4 V at ≈ 20 mA. If dark, check the sense resistor and the
boost before suspecting the panel.

## 10. Panel and touch
<interface, reset lines, the fact that the touch bus pull-ups ride the switched panel rail, so
the rail must be up before probing the bus>

## 11. Audio
<signal path, the pin that boots muted, the detect pin's expected level>

## 12. Keys, fader, cell
Solder the cell's leads **last**, after everything above passes — a connected cell means the
master switch no longer removes power from a charging board.
```

**Two structural properties of that template worth copying:**

1. **Every step that would need a missing tool is marked.** In the reference runbook the steps that
   would need a USB-serial adapter *without* the bridge edit are flagged `[needs the edit]`. That is
   how a runbook becomes a design review.
2. **The order is "prove the cheap thing before you risk the expensive thing".** Rail before module;
   module before panel; backlight before pixels; cell last.

---

## 9. Firmware obligations and accepted defects

Some things are not board problems and must be handed over explicitly, or they will be rediscovered
as bugs.

- **Accepted defects, with the reason.** A power-off thump: the amplifier has no shutdown pin and the
  rail is cut mechanically, so at switch-off the bias collapses while the output cap still holds
  half-rail. No cheap hardware fix; recorded as expected behaviour.
- **Firmware mitigations for things the board cannot fix.** No series damping on a fast memory-card
  bus: reduce the MCU's drive strength, and drop the clock if cards misbehave.
- **Firmware obligations created by the hardware.** Keep the backlight PWM above 20 kHz, and never
  let the control pin sit low for more than 160 µs inside the first millisecond after enable, or the
  part enters a one-wire dimming mode; more than 2.5 ms low shuts it down entirely. Threshold the
  USB-present sense well above a volt, because a Schottky's reverse leakage floats that node.
- **Bring-up measurements that are not banked results.** Real battery runtime (the capacity estimate
  had 4 % margin), and RF range with a metal pouch 10.5 mm from the antenna region — with a named
  fallback (a shorter cell at −25 % capacity) if the measurement disappoints.

Write all four categories down in the same place as the runbook. The board is finished; the project
is not.
