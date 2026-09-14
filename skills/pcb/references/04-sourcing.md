# 04 — Sourcing: 性价比 and hand assembly

Choosing parts for a one-off board is a different problem from choosing parts for production, and
most part-selection advice is written for production. This file is the one-off version.

---

## The rule that inverts everything: quantity one

At quantity one, **fees dominate part prices**. A ¥20 per-part-type machine-placement fee is larger
than almost every component on a small board. So the usual preference order flips:

> basic-library, machine-placed (fee ¥0)
> **>** *leaded extended-library part, hand-soldered (fee ¥0)*
> **>** extended-library part, machine-placed (fee ¥20/type)

The middle option — pay more for the part, pay nothing for the placement — wins far more often at
qty 1 than at volume.

**Worked example.** A QFN audio codec at ¥3.37 versus a leaded TSSOP-20 DAC at ¥8.56. At volume the
codec wins by ¥5. At qty 1:

```
codec:  3.37 + 20.00 (loading fee) = 23.37   and it is a QFN the user cannot hand-solder
DAC:    8.56 +  0.00               =  8.56   TSSOP-20, leads outside, hand-solderable
```

The break-even loading fee was computed as ¥5–8 *before* the fee was known; the measured fee was ¥20;
the decision then took no judgement at all. **Compute the break-even before you have the number, so
that when the number arrives the decision is arithmetic.**

And once the user decides to hand-assemble everything, the library class stops mattering entirely and
parts are chosen on price and solderability alone. Ask which world you are in before optimising.

---

## Basic vs extended library

The vendor's "basic library" is the set of parts already loaded on the pick-and-place machine. Basic
parts carry no loading fee and no material-loss charge; extended parts carry both (see
`03-jlc-manufacturing.md` §8).

**Enumerate the basic library once, completely, and then absence is proof.** The reference project
paged through the whole thing: **351 part numbers**, cross-validated against 37 parts a previous
iteration had independently labelled basic (37/37 present). That turns "I could not find a basic X"
into "no basic X exists".

What it actually contained:

- **282 chip passives** — 0603 (118), 0805 (88), 0402 (51), 1206 (25)
- **69 everything else** — 18 SOT-23 transistors/MOSFETs, 7 SOIC-8, 5 SMA diodes, 3 crystals,
  2 SOT-223 / 2 SOT-89 LDOs, 2 tact switches, 2 optocouplers, 3 resistor arrays, 2 tantalums, and a
  handful of logic/interface/converter ICs.

What it contained **zero** of — measured, not inferred:

| role | basic option? |
|---|---|
| any connector at all — USB-C, microSD, 3.5 mm jack, FPC, JST | **none** |
| Li-ion charger IC | **none** |
| buck/boost that runs from a single Li-ion cell | **none** |
| audio codec or I²S DAC | **none** |
| analogue switch / mux | **none** |
| NTC thermistor, any size | **none** |
| power inductor (2.2 / 4.7 / 22 µH at 1.6–3 A) | **none** |
| **side-actuated** tact switch | **none** — both basic tact switches are top-actuated |

That last row is the kind of thing that only shows up as a *mechanical* problem three phases later:
a top-actuated switch cannot serve a side key without redesigning the enclosure.

**Consequence:** on any board with connectors and power conversion, the question is almost never
"basic or extended". It is "which extended parts do I pay to machine-place, and which do I
hand-solder for free".

**Do not trust the class field from a secondary API.** A previous iteration recorded a middle tier
("preferred", fee ¥15). Measured directly on the vendor's own retail pages, three charger ICs that
the international API called "Preferred" all read **`SMT扩展库`** — extended. Budget them at the
extended rate. The authoritative field is the one on the page the vendor bills against.

**Also verify part numbers themselves.** Two part numbers carried through several documents in the
reference project were simply wrong: one pointed at a 2512 resistor instead of a DAC, another at an
MCU instead of a codec. Resolve every part number to a live product page and check the MPN matches
what you think you are buying.

---

## Netting the BOM against stock the user already owns

Leftovers from a previous build are free parts, and they are usually worth more than people expect.
In the reference project the leftover stock was a **paid 42-line order of ¥279.63** plus a same-day
marketplace order — ≈ **¥122 of usable stock** against a ¥350 project ceiling.

### "Bought minus used" is an upper bound, not an inventory

The previous project's own workbook defined its leftover column as `购买数量 − 单板用量 × 2` —
"bought minus two boards' worth" — which is exactly the number you want, **and it assumes zero solder
scrap.** Every quantity derived that way is an upper bound. Treat it as one:

- Say so, in the ledger, on every row: *"upper bound, assumes zero scrap; count before ordering."*
- **Flag every line whose margin lands at 0 or 1** and add a minimum-pack insurance line for it. The
  reference project had exactly two such lines — a 1 µF 0805 (need 8, have 8) and a 10 µF 0805
  (need 3, have 4) — and bought insurance for both, ¥7.63 combined. One dropped part on a line with
  margin 0 stops the build.
- If a design change frees up stock, re-check: a later value change released two of those eight 1 µF
  parts and the margin problem went away.

### How to find the stock in the first place

The reference project's stock inventory had been "not found" by a previous iteration because a
source document was searched for on the wrong drive. The path to it was written in plain text on
line 4 of that iteration's own mission file. **Before concluding a record does not exist, grep the
project's own documents for the filename.**

---

## Order granularity: a ¥0.01 part is a ¥1 line

Distributors sell in packs. A resistor at ¥0.0149 each that you need two of is a **100-piece,
¥1.49 line** — not ¥0.03.

From the reference project's staged cart, needed quantity → bought quantity:

| part | need | buy | unit ¥ | line ¥ |
|---|---|---|---|---|
| 470 Ω 0603 | 2 | **100** | 0.0149 | 1.49 |
| 220 nF 0603 | 1 | **50** | 0.111 | 5.55 |
| 2N7002 SOT-23 | 4 | **50** | 0.1078 | 5.39 |
| 10 µF 0603 | 4 | **20** | 0.352 | 7.04 |
| TSSOP-20 DAC | 1 | **1** | 8.64 | 8.64 |

The cheap passives are not free; five of them are a ¥20 line. And the expensive IC is a ¥8.64 line.
**Budget on line totals, never on unit price × quantity needed.**

**How to discover the real granularity without assuming it:**

> Paste the part numbers with their **needed** quantities — deliberately, so the vendor's own tool
> rounds them up and reveals the actual minimum-buy and pack-step, rather than your assumption
> confirming itself.

Then read the cart back and check that every predicted quantity came back unchanged. In the
reference project all 27 lines did, which is what turned "order granularity was respected" into a
measurement rather than a claim.

---

## Sanity-check a rating against physics, not against the label

Marketplace listings inflate. The way to filter them is to compute what the claim implies and ask
whether physics allows it.

**Worked example — the method that killed an inflated cell.**

The requirement was ≈ 750 mAh. Method: `energy (Wh) = capacity (Ah) × 3.7 V`, `density = energy / volume`.
Small budget lithium-polymer pouch cells realistically land at **300–350 Wh/L**, with well-made ones
approaching 400. Anything implying > 450 Wh/L at this size is inflated.

| format (T×W×L mm) | volume | claim | implied Wh/L | verdict | realistic at 300–350 Wh/L | clears 750 mAh? |
|---|---|---|---|---|---|---|
| **403080** | 9.6 cm³ | 1000 mAh | **385** | optimistic but achievable | **780–910 mAh** | **yes** |
| 403080 (other sellers) | 9.6 cm³ | 1300 mAh | 501 | inflated ~1.3× | same cell | yes |
| 403080 (other sellers) | 9.6 cm³ | 1500 mAh | 578 | inflated ~1.5× | same cell | yes |
| 303080 | 7.2 cm³ | 1200 mAh | 617 | inflated ~1.8× | 585–680 mAh | **no** |
| 303080 | 7.2 cm³ | 700 mAh | 360 | **honest** | 585–680 mAh | **no** |
| 503080 | 12.0 cm³ | 1300 mAh | 401 | credible | 975–1135 mAh | yes |

Then invert it — **the break-even density needed to deliver the requirement** is the sharper form:

- `403080` needs **289 Wh/L** — below typical, so it should clear.
- `303080` needs **385 Wh/L** — the top of the achievable band, and thin cells do *worse*, not
  better. **The 3.0 mm format cannot meet the requirement at any price**, which closes off "just
  fall back to a thinner cell" permanently.
- `503080` needs **231 Wh/L** — trivial.

Three things fall out of this that generalise well past batteries:

1. **The physically credible claim is a seller-quality signal.** In that search, exactly one listing
   made a claim physics allowed — and *"a seller who does not measure capacity probably does not
   measure dimensions either, and width is what decides whether this device assembles."*
2. **Say what is still not banked.** At the pessimistic 300 Wh/L end the chosen cell yields 780 mAh
   against a 750 mAh need — 4 % margin. That was written down as *"3 h of playback is a bring-up
   measurement, not a banked result"*, not as a solved requirement.
3. **Read the part code, not the search result.** A generic search for "1000 mAh 4 mm-class cell"
   keeps returning `803040` — the same capacity at **twice the thickness**. The code is
   thickness/width/length; reject anything whose middle pair is not what you asked for. The same
   trap exists for every coded part family.

Apply the same discipline elsewhere: a claimed dropout voltage against the input range you actually
have; a claimed switch current against the inductor's saturation rating; a claimed module supply
floor against a flat cell. The reference project caught a basic-library op-amp recommendation that
required ±5 V rails on a board whose highest rail was 3.3 V, purely by checking the supply range
against the design rather than the shortlist.

---

## Rejecting a part on package alone

Some rejections need no further analysis. Get the user's package rule explicitly (see
`01-workflow.md` Phase 0) and then apply it mechanically.

The reference project's rule, after two rounds of clarification:

> **No QFN / DFN / VQFN / bottom-terminated / exposed-pad-only ICs.** Any package with leads on the
> outside is acceptable at any pitch ≥ 0.5 mm, TSSOP 0.65 included.

Note what the *clarification* removed. An early draft of the rule also preferred coarse pitch
(SOIC 1.27 > SOT-23 0.95 > TSSOP 0.65) and banned 0402 passives. Both were withdrawn: the user solders
fine-pitch leaded parts without trouble, and two-terminal passives may be any size. **A rule that is
stricter than the user's actual constraint costs money and board area for nothing** — the withdrawn
0805-only rule would have re-priced the entire passive BOM and grown the board.

What the rule bought, applied consistently:

| role | rejected | chosen | why |
|---|---|---|---|
| Li-ion charger | ESOP-8 with exposed pad | SOT-23-5, ¥0.12 | leaded, and 9× cheaper |
| I²S DAC | QFN-EP codecs at ¥3.37–6.73 | TSSOP-20, ¥8.56 | leaded; and at qty 1 the fee reverses the price order anyway |
| headphone amp | WQFN-16-EP, ¥8.22 | SOIC-8, ¥2.86 | leaded and cheaper |
| USB ESD array | — | SOT-23-6 | |

Result: **no exposed-pad part anywhere on the board**, in either the machine-placed or the
hand-soldered set, without paying a single avoidable fee.

Two package traps worth carrying:

- A "same function" substitute may not be a drop-in. Two backlight boost candidates in the reference
  project had completely different SOT-23-6 pinouts (`1 VIN, 2 CTRL, 3 SW, 4 GND, 5 COMP, 6 FB`
  versus `1 SW, 2 GND, 3 FB, 4 CTRL, 5 OV, 6 VIN`), so the choice had to precede the layout, not
  follow it.
- A **pin-compatible, land-compatible** substitute is the cheapest fix in existence. When an audio
  mux turned out to be unspecified at 3.3 V, the fix was a different part number with an identical
  SOIC-16 pinout and land pattern: ¥0, no schematic change, no PCB change, one BOM line edited.

---

## Stock: two pools, and they disagree

Machine-assembly stock and retail stock are **different inventories**. In the reference project one
basic 1 µF 0603 showed **9.15 million pieces of assembly stock and zero retail stock** — perfectly
placeable by machine, unbuyable as a hand-solder spare. A previous iteration had hit the same wall on
a different resistor.

So:

- Check the pool you will actually buy from.
- If a part is hand-soldered, it must be in **retail** stock now, not on backorder. The reference
  project's gate was `全部 28 / 现货 28` — every line in stock, none on order.
- Watch thin lines. Two of 28 lines had four-digit stock; everything else was six or seven digits.
  Four digits is fine for a one-off and would not be for a batch.

Also: **prices differ between the two systems** — the assembly service explicitly runs its own price
book (`嘉立创将完全弃用立创商城的价格体系，采用自用的价格体系`). Price a machine-assembly BOM from the
assembly match screen; price a hand-solder BOM from the retail cart.

**Currency, if you convert:** calibrate the rate against parts whose price you know in both
currencies rather than using a headline FX rate, and record the calibration. The reference project
used CNY = USD × 6.10, calibrated over 12–13 ladder readings with a 0.25 % spread and re-confirmed on
three parts to four decimals.

---

## Labelling prices: VERIFIED / ESTIMATE / NOT ESTABLISHED

**A price nobody has read off a live page is an ESTIMATE and must be labelled as one.** The
reference project's budget went through three states:

```
ESTIMATE   ≈ ¥257   (arithmetic on published rates, before any live read)
ESTIMATE   ≈ ¥195   (after the assembly decision changed)
VERIFIED     ¥260.19 (LCSC cart ¥103.53 + marketplace cart ¥156.66 + PCB ¥0, all read back)
```

Nobody was misled at any point, because each number carried its status.

Two related disciplines:

- **When documents disagree, name the authority.** The ledger summed the retail lines to ¥103.58
  while the BOM and the live cart read ¥102.45–103.53. The spread is ≈ 1 % and moves with the
  vendor's own promotional pricing. Ruling: **the cart page at order time is authoritative; do not
  chase the difference in the documents.**
- **Shipping is often NOT ESTABLISHED until checkout**, and checkout is exactly what you must not
  open. The reference project could not establish the free-shipping threshold (the help page says
  only that freight is weight-based and computed at settlement), but found prior art on the same
  account showing `订单金额：￥279.63（含运费￥0）` — so free shipping exists at ¥279, and whether
  ¥107.86 clears it is unknown. **Give the grand total both ways** rather than picking one.

---

## Staging carts without ever checking out

The goal is to leave the user two minutes of work: open the cart, tick, pay.

**Hard rules:**

- **Never tick a checkbox, never open the settlement page, never enter an address or a credential,
  never claim a coupon that changes account state without explicit permission.** The reference
  project's read-back recorded `0 of 54 checkboxes ticked; settlement total ¥0` as evidence.
- **Read the cart back line by line after staging**, and take quantities from the DOM inputs, not
  from what you believe you added. The arithmetic must close: in the reference project the sum of
  28 line totals equalled the cart's own displayed payable amount, exactly.
- **Record the cart header count before you start** (`购物车 (0)` → `(27)` → `(28)`), so you can
  prove nothing pre-existing was disturbed.
- **Do not touch unrelated items.** That cart also held ~31 unrelated lines; the report says so.

**Three cart-UI traps, all measured, all costly:**

1. **The cart page serves stale data immediately after an add.** Opening the cart right after adding
   an item showed the *pre-add* list — old line count, new item absent. Read as "the add failed",
   clicked again, **ended up with quantity 2**. **Judge an add by the success toast on the item
   page, never by the cart page or the header badge**, then verify on a later reload.
2. **A delete confirmation can close without deleting.** The confirm dialog opened reliably and the
   button was clicked at DOM-verified coordinates, but the click usually just dismissed the dialog
   with the item still present — 6+ attempts across coordinate clicks, element-reference clicks and
   synthesised pointer sequences before one committed. The one that worked announced itself by
   wedging the page for ~15 s. **Always reload and re-count after a delete; a closed dialog is
   evidence of nothing.**
3. **A site can go dark for reasons that are not anti-bot.** Every browser call against one domain
   returned "permission denied" while a different domain worked in the same browser, same tab group,
   same moment — and screenshots taken minutes earlier showed the account logged in with no CAPTCHA
   and no challenge. That is a tooling permission, not a session problem. **Diagnose it as one, stop
   touching the site, and hand it back** rather than working around it.

---

## The ledger

One file, one row per purchasable line, written to disk. Columns that earned their place:

```
designators | part | package | qty_needed | qty_from_leftovers | qty_to_buy |
MOQ | pack_step | unit_price | line_total | source | vendor_part_number |
confidence (VERIFIED/ESTIMATE) | note
```

The `note` column is where the upper-bound warnings, the insurance-line reasons, the substitutions
and the "measure on arrival" flags live. The reference project's ledger carried 56 rows including
the PCB itself and four lines that are not in the BOM at all — a spare module, an antenna, and two
insurance lines — because those are things that must be bought and would otherwise be invisible.

**Deliberately-unused manifest entries are worth recording too**, with the reason: a part dropped by
a later decision, a part whose retail stock was zero, a part whose datasheet turned out not to
publish a pinout. Otherwise the next reader re-derives the rejection.
