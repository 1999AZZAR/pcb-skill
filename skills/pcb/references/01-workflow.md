# 01 — The workflow

Four phases. Each produces artefacts, each closes with a gate, and a gate is a
**measurement someone else could reproduce** — not an opinion that the phase looks finished.

The reference project ran this loop once and needed 22 numbered work packages to do it. Most of
them were not new design; they were the consequence of a gate that had been declared closed on
evidence that turned out to be an assumption.

---

## Phase 0 — Align before starting

You are about to spend the user's money on a physical object that cannot be edited after it ships.
The cost of one wrong question at the start is a re-spin; the cost of asking it is 30 seconds.

### The question test

> **Ask a question only when its two answers give you a different board.**

Everything else is either research you should do yourself, or noise.

Worked examples from the reference project, all of which changed the board:

| question | answer A | answer B | what changed |
|---|---|---|---|
| Bluetooth: transmit, receive, or both? | receive only | **both** | a transmitter module, a source mux, an analogue switch, 3 nets, ~¥12 |
| "≥ 3 h playback" — screen on or screen off? | screen on | **screen off** | 1250 mAh vs 750 mAh → a 5.0 mm cell vs a 4.0 mm cell → 1 mm of device thickness |
| What packages will you hand-solder? | anything | **no QFN/DFN/exposed-pad** | codec, charger and amplifier all changed part; the whole BOM re-priced |
| One unit or several? | several | **one** | at qty 1 a ¥20 per-part machine-placement fee dwarfs every part price, so hand-assembly wins on cost, which then inverts the entire part-selection rule |
| Is there a hard budget? | "cheap" | **¥350, hard** | became a red line every task checked against, and killed one ordering route outright |

Counter-examples — things that were **asked and should not have been**, or that would have been:

- *"Which library class is this part in?"* — measurable. The whole basic library of the vendor was
  enumerated (351 parts), so "no basic connector exists" became a measurement rather than a belief.
- *"How much does this cost?"* — measurable, on a live page, in the user's own logged-in session.
- *"Should the decoupling cap be close to the pin?"* — this is your job.
- *"Do you want the free coupon?"* — of course they do. Find out what it costs the design instead.
- *"Should I ask the panel seller whether 2-lane operation works?"* — the user's ruling was **do not
  ask the seller**; the answer would be unverifiable marketing. Design a hedge instead (see 07).

### What Phase 0 produces

One document — call it `MISSION.md` — with:

- **Hard constraints, numbered `H1…Hn`.** Things that are never traded away. In the reference
  project: the board must be free; the feature list; the specific core module; the required extras;
  and *never place an order, pay, enter credentials or accept terms*.
- **Soft constraints, ranked, with the tie-break written down.** The reference project used
  `S1 price > S2 hand-solder count > S3 speed`, and that single ordering resolved perhaps thirty
  later decisions without another round-trip to the user.
- **Scope boundary.** What is *not* in scope (firmware, enclosure) and what "done" means for each
  deliverable.

**Gate 0:** every question whose two answers give a different board has an answer on record.

---

## The standing-authority pattern

At some point a user who is enjoying the work will say a version of *"stop asking me"*. In the
reference project, verbatim:

> 后面请不要让我决策，你有一定的选择，我希望你到最后可以直接推到底
>
> *("From here on, don't make me decide. You have some latitude — I want you to be able to push it
> all the way to the end.")*

This is a real transfer of authority and it should be accepted, because round-tripping every
decision is what makes hardware work take weeks. But it has to be operated, not just enjoyed.

**How to operate it:**

1. **Decide by the ranking already on record.** The authority is to *apply* `H1…Hn` and `S1 > S2 >
   S3`, not to invent new goals. If a decision cannot be resolved by the recorded priorities, that
   is exactly the case that still goes back to the user.
2. **When two options are genuinely close, pick the one that is cheaper to reverse — and say so.**
3. **Record every call with the measurement behind it**, in one append-only decision log, so the
   user can overrule *after the fact* instead of *before it*. That is the whole deal: they trade
   prior approval for a legible audit trail.
4. **Name what stays reserved.** Standing authority never extends to anything the agent may not do
   at all. In the reference project that was: anything needing a credential or a login, and pressing
   pay. Those did not relax and were restated in the mission file so no later worker could read the
   authority as broader than it was.
5. **Escalate a constraint change, not a decision.** "I decided X" needs no approval. "X means we
   can no longer meet H4" does.

**What the log must look like.** Append-only, with amendments that *supersede* rather than edit:

```
- D-4 Audio. DEFAULT = leaded chain … Switch to ES8388 only if the loading fee ≤ ¥8 [R2]
## Amendments after R2
- D-4 FINAL = leaded chain. The extended loading fee is ¥20/type, above the ¥8 break-even.
## Amendments after the user's SMT decision
- D-15 FINAL (supersedes). JLC supplies the bare PCB only …
```

The reference project's log has eleven amendment blocks and three of them overturn a decision from
the day before. Rewriting the earlier entry in place would have destroyed the reason each later
worker knew *why* a thing had been reconsidered — and twice, a worker caught a contradiction
precisely because the superseded text was still visible.

---

## Phase 1 — Concept

**Produces:** what the thing does, for whom, the architecture, the power budget, and the hard-vs-soft
constraint split.

**Do:**

- Build a **power budget table before choosing any part**, with a typical column and a worst-case
  column, and say which is which. The reference project's table (245 mA typical / 805 mA worst on
  the 3V3 rail) is what selected the converter, sized the cell, and later let a reviewer compute a
  trace's temperature rise from first principles.
- Enumerate architectures and price them *including their fees*, not just their part cost. A ¥3.37
  codec that costs a ¥20 machine-placement fee loses to an ¥8.56 one that costs nothing.
- Tag every figure **VERIFIED (source + date)** / **COMPUTED** / **ESTIMATE** / **NOT ESTABLISHED**.
  This tagging survives into every later document and is the single cheapest discipline in the whole
  workflow.

**Gate 1:** the architecture's cost, current, and physical envelope are each traceable to a
measurement or an explicitly labelled estimate.

---

## Phase 2 — Schematic and sourcing

**Produces:** a complete schematic, a priced BOM netted against stock the user already owns, and
staged carts.

**Decomposition that worked:** one worker builds the schematic *as data* (a Python description of
every component, pin and net) and generates the EDA document from it. Then the schematic is
regenerable, diffable, and — crucially — a second program can assert against the same data.

**Gate 2 is not DRC.** DRC passed with zero errors on a schematic where the backlight switching node
was shorted to the TF card rail and the I²S data line was shorted to ground (see `05-easyeda-mcp.md`).
The gate is **assertions against the EDA's own exported netlist**:

| assertion class | count in the reference project |
|---|---|
| must-connect (pin → net) | 203 |
| must-not-connect (net ≠ net) | 37 |
| must-be-open (pin has no net) | 18 |
| per-net pin-count equals the generator's intent | every net |

That last row is what catches a *silent merge*: a merged net has more pins than intended and a split
net has fewer, and neither shows up as a missing connection.

Also in Gate 2:

- **Every footprint resolves.** 29 distinct footprints, 0 missing, checked by uuid against the
  library — not by looking at the canvas.
- **BOM reconciles against the parts manifest**, with every deliberate substitution written down and
  justified. The reference project had 13 substitutions and every one had a one-line reason.
- **Save, quit the EDA completely, reopen, and re-measure.** Same-process results are not evidence
  about the saved document.

**Sourcing gate:** every price is VERIFIED against a live page or labelled ESTIMATE. See `04-sourcing.md`.

---

## Phase 3 — Layout and routing

**Produces:** a placed, routed, poured board.

**Split placement and routing into separate work packages with an adversarial review between them.**
The reference project's placement review returned 2 FATAL, 10 SERIOUS and 3 MINOR findings, and both
FATALs were floorplan-level — they had to be found *before* 5 344 mm of copper existed.

**The placement gate is routability, not legality.** A placement with zero courtyard overlaps can
still be unroutable. Derive it:

- Sweep the free spans between parts and ask how many are ≥ **(via pad + 2 × clearance)** wide, not
  how many are ≥ (track + clearance). In the reference project the shelf pitch was designed at
  0.76 mm against a 0.704 mm via lane — and then the board's *actual* live rule set turned out to be
  a 2-layer profile with 0.152 mm clearance, which makes the lane 0.804 mm and drops the
  via-capable fraction from 87 % to 56 %. **Check which rule set is actually loaded.**
- For every fine-pitch part, compute the escape explicitly. An 88-pad module on 1.0 mm pitch with
  0.7 mm-wide pads leaves 0.300 mm between pads — a 0.50 mm via does not fit, so every escape must
  clear a pad *end*, and after one via per pad the ring is full.
- List parts with **no** side offering a via lane. Twelve, in the reference project, six of them in
  the audio cluster.

**Before routing, read the layer status directly.** A four-layer board can sit in a state where the
design rules say four layers, the physical stack-up record says four layers, and the inner layers'
`layerStatus` is `0` — copper cannot be placed on them. Hours of autorouting on a board that is
electrically two layers is the failure this prevents.

**Gate 3:**

- 0 unrouted connections; every net's copper is **one island**, checked layer-aware (two segments
  ending at the same XY on different layers are *not* connected without a via).
- DRC 0 errors, and every warning attributed by ablation rather than waved away.
- An independent clearance sweep that reproduces the EDA's own numbers on a different code path.
- Pad-by-pad reconciliation of PCB nets against schematic nets: symmetric difference empty.
- Cold restart, re-measure, fingerprint unchanged.
- Adversarial review clear (see `02-review.md`).

---

## Phase 4 — Fabrication and purchase

**Produces:** a verified fabrication package and an order driven to the pre-payment page.

**The package must be verified independently of the EDA that produced it.** Write a Gerber/Excellon
reader and re-derive everything: outline, copper layer count, drill census, mask opening per pad,
minimum track, minimum different-net clearance. The reference project's Gerber-side sweep confirmed
0.1020 mm minimum clearance against the design-side model's 0.1020 mm — two artefacts from
different code paths agreeing is what "verified" means here.

**Gate 4:**

| check | how |
|---|---|
| outline exactly as specified | parse the outline layer |
| N copper layers, each with copper | count the files *and* their content |
| drill count under the surcharge threshold | parse the Excellon, and beware double-counting (see 03) |
| every pad has a mask opening | match copper flashes to mask flashes **and** `G36` regions |
| min track / min clearance | exhaustive different-net sweep, exact geometry |
| nothing outside the outline | measure hole *edges*, not centres |

Then order — and see `03-jlc-manufacturing.md` for which route honours a coupon. **Drive to the
pre-payment page and stop.** Logins, CAPTCHAs and payment are the user's; prepare everything else so
their part takes two minutes.

### Uniform Project Deliverables & Final Cleanup (Mandatory)

To prevent bloat and maintain complete directory uniformity across all PCB projects (e.g. `keyboard_555`, `esp32c3_controller`, `stereo_mixer_4ch`), Phase 4 MUST conclude with a cleanup and consolidation pass before handing off to the user:

1. **Purge Intermediate Scaffolding**: Delete all generator/router scripts (`gen_*.py`, `assert_netlist.py`), trial routing boards (`test_*`), raw netlists (`*.net`), and debug dumps (`*.json`, `*.log`, `*missing3Dmodels.txt`).
2. **Consolidate Documentation into `README.md`**: Do NOT leave temporary `MISSION.md`, `DECISIONS.md`, or `PROGRESS.md` in the project root. Synthesize all architectural decisions, constraints, circuit formulas, BOM table, and verification metrics into a single master `README.md` embedding the 3D top/bottom preview renders.
3. **Generate Standard Reports**: Run `kicad-cli pcb drc --output <project>-drc.rpt <project>.kicad_pcb` and `kicad-cli sch erc -o <project>-erc.rpt <project>.kicad_sch`.
4. **Strict Final Directory Structure**:
   ```
   <project_name>/
   ├── jlcpcb_production/
   │   ├── gerber/
   │   ├── <project_name>_bom_jlcpcb.csv
   │   ├── <project_name>_cpl_jlcpcb.csv
   │   ├── <project_name>_gerber_jlcpcb.zip
   │   ├── <project_name>_render_bottom.png
   │   └── <project_name>_render_top.png
   ├── <project_name>-drc.rpt
   ├── <project_name>-erc.rpt
   ├── <project_name>.kicad_pcb
   ├── <project_name>.kicad_prl
   ├── <project_name>.kicad_pro
   ├── <project_name>.kicad_sch
   ├── README.md
   └── fp-info-cache
   ```

---

## How to decompose the work

**One worker, one deliverable, one report.** In the reference project each package wrote
`task-<n>-report.md` and appended one dated line to a shared progress log. The report is the
deliverable; the code is scaffolding.

**Three files carry the project across context boundaries:**

| file | what it holds | who writes it |
|---|---|---|
| `MISSION.md` | goal, hard constraints, ranked soft constraints, scope, standing authority | the orchestrator, once |
| `DECISIONS.md` | every ruling, with the measurement, append-only with amendments | the orchestrator |
| `PROGRESS.md` | one dated line per completed package | everyone |

Workers get **file paths, not pasted content**. A 42 KB decision log read by ten workers costs
nothing; the same content pasted into ten prompts costs ten times.

**Rules that stopped real collisions:**

- **A reviewer must be a different worker from the builder, and read-only.** Not a second pass by
  the same worker.
- **Parallel workers must not touch the same files.** Two workers with the same EDA document open
  is how an unsaved tab gets clobbered; the reference project had a worker deliberately not switch
  documents because another agent had an unsaved tab.
- **Copy measured numbers into a worker's brief from the original output, never from memory.** A
  brief in the reference project stated the wrong coordinate unit — a value the orchestrator had
  personally disproved ten minutes earlier and then re-typed from recollection. The worker caught it
  by triple-calibrating against known geometry. That was luck.
- **Reuse before rewriting.** Every rewrite re-pays every price the original already paid. The
  reference project's second iteration reused the first's autoroute chain, price-fetch scripts and
  trap list, and each of those saved a day.

---

## When a phase has to be re-opened

It will. The reference project withdrew a released fabrication package twice.

- **Withdraw the package explicitly.** Move it to `superseded/` with a note saying exactly why. A
  superseded package that is still sitting next to the current one will eventually get ordered.
- **Re-run the whole gate, not the delta.** After a fix pass that touched 28 parts, the acceptance
  gates were re-run from a fresh export with nothing cached.
- **Fix everything that is free while the board is open.** The re-open is the expensive part; the
  fixes are not. The reference project's final pass closed twelve findings in one commit because
  they all rode on one re-open — and every one of them would have been impossible after the coupon
  was spent.
