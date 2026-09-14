# 02 — Adversarial review

A design agent cannot review its own work, because the same assumption that produced the fault
produces the check that misses it. Every phase therefore ends with a **fresh reviewer** whose only
job is to try to break the result.

This file is the protocol, then the meta-lessons — each with the specific failure that taught it.

---

## The protocol

### 1. Write the termination criterion *before* the review starts

A skilled adversarial reviewer, told to "find problems", finds problems forever. On another project
a review of this kind produced **22 candidate findings and zero delivered fixes**, because the exit
condition was self-referential — the blocker list could not empty while the reviewer was still
allowed to add to it.

So the brief says, in advance, what "done" looks like. For the reference project's route review:

> **One pass. Read-only. Produce a ranked finding list and a verdict of the form
> "FIX FIRST: <ids>". Do not iterate; do not re-review your own findings.**

And the reviewer opened its report with exactly that:

> Read-only, ONE pass, 2026-09-07. Nothing was modified: no document, library, footprint, rule set
> or file outside my own working directory.

### 2. Read-only means read-only

The reviewer exports its own copy and works on that. If it edits the live document, its findings and
the state they describe diverge, and nobody can tell which board was reviewed.

One consequence worth planning for: a read-only reviewer sometimes *cannot* settle a question.
The route reviewer found a copper pour with no fill and had to write:

> Whether the empty `AGND_ISLAND` pour is a stored-state artefact or a genuine fill failure. I
> measured only that no `POURED` record exists in either export. Rebuilding the pours would settle
> it and is a write, which this review is not allowed to make.

That is the correct output. It goes to the fix pass as an instruction, not as a verdict.

### 3. Build your own model from your own export

The reviewer must not read the builder's intermediate files. It exports the live document itself —
both forms, if the tool offers two — and rebuilds pads, nets, tracks, vias, holes and pours from
scratch. The reference project's route reviewer wrote 15 small tools to do this, and the finding
that mattered most (a differential pair referenced to a signal layer rather than the plane) was only
visible because it had built its own layer-stack model.

### 4. Self-check the model against the tool before trusting it

Before reporting a single number, reproduce numbers the builder already published, on your own code
path. The route reviewer's self-check:

> My engine reproduces the builder's own clearance sweep to four decimals on an independent code
> path: track-track **0.1064**, track-pad **0.1020**, track-via **0.1030**, via-via **0.1193**.
> Also reproduced exactly: 149 components, 516 pads, 1 882 tracks, 406 vias, 5 344.1 mm of copper,
> the width census, 429 drill hits, and the outline.

If your model cannot reproduce the agreed numbers, your model is wrong, and every novel number it
produces is worthless. Report the discrepancy as a finding about the *model*, not about the board.

### 5. Rank every finding, and give each one four things

| field | rule |
|---|---|
| **severity** | FATAL / SERIOUS / MINOR, defined below |
| **measurement** | the numbers, with coordinates, and where they came from |
| **failure scenario** | what a user experiences, physically, if this ships |
| **cheapest fix** | the smallest change that closes it, costed in parts / mm / area |

Severity definitions that held up in practice:

- **FATAL** — the board cannot be assembled or cannot work, or assembling it destroys something.
  *"A capacitor lies wholly inside the module body: the module cannot be fitted."*
  *"The connector's mouth faces the wrong way: the panel cannot be connected at all."*
- **SERIOUS** — it works, but a real failure mode is live, or a specification is violated.
  *"25 mm of buried 0.30 mm 0.5 oz copper carries the whole system current 0.25 mm under a lithium
  pouch; IPC-2221 wants 0.60 mm."*
- **MINOR** — record it, cost it, and let the orchestrator decide. Do not inflate it.

The "cheapest fix" column is what makes a review actionable rather than demoralising. Compare:

> Move **9 parts** — R408, R409, R410, R411, R413, R414, R415, C412, C413 — into the audio block
> beside U402/U403 and re-route the ~8 nets they own. No floorplan change; the audio zone has room.

versus "the analogue layout is bad".

### 6. Quarantine unmeasured hunches in a separate list

Every review ends with a section headed something like **"Suspicions, unverified — do not act on
these without a measurement."** Real examples:

> * **IPC-2221 vs IPC-2152.** Every temperature figure above is IPC-2221, which models an isolated
>   trace in still air. These traces are 0.21 mm from large planes on both sides. The real rise is
>   lower. **I did not compute an IPC-2152 number and will not present one.**
> * Whether the feedback resistors being 64 mm away *destabilises* the amplifier as opposed to
>   merely injecting noise. My expectation is noise — but I did not simulate it, and the finding
>   stands on the measured geometry, not on this.

This is not hedging. It is the difference between a finding and a guess, and mixing the two is how a
fix pass wastes a day chasing something nobody measured.

### 7. Record what you checked and found *correct*

> Stated explicitly because an adversarial review that only lists faults hides what was verified.

The route review's "found correct" section is as long as its findings section, and it is what let
the next three work packages skip re-auditing the netlist, the ground islands, the plane continuity
and the hand-assembly access. A later electrical audit opened with *"Checked and found CORRECT — do
not re-audit these"* and listed eleven items with their evidence.

### 8. Deliver a verdict, not a mood

> **Verdict: FIX FIRST — F1, F2, F3, F4, F5, F6, F7.**
> Everything in F8–F16 is recorded and can ship as it stands.

Then say what order to fix in and why: *"F1 is the cheapest and the most expensive to get wrong.
F4 changes what the Gerber contains, so it has to be settled before the package is generated."*

---

## Meta-lesson 1 — a green board is not a correct board

The reference project's first schematic terminated every net with a *net port*. Result:

- schematic DRC: **0 errors**
- visual inspection: every wire lands where it should, every net name correct
- the EDA's own netlist export: **five nets silently mis-resolved** — the backlight switching node
  merged into the TF card power rail, the I²S data line merged into ground, the UART TX merged into
  ground, and one SD data line merged into an unrelated control net.

A backlight switch node shorted to a card rail, and I²S data shorted to ground. Either would have
been found only after the board was fabricated and populated.

**What saved it:** 203 must-connect, 37 must-not-connect and 18 must-be-open assertions run against
the netlist export. Nothing else in the toolchain reported anything.

**The rule:** every green result names an instrument, and you must be able to say what that
instrument *cannot* see. DRC cannot see a net that resolves consistently to the wrong thing.

---

## Meta-lesson 2 — verify the tool before you trust the result

Several checkers on the reference project silently measured the wrong object. In every case the
*reading* was correct; the thing being read was not what the reader believed. That is the whole
class: **read-the-wrong-thing faults never look like errors.**

### 2a. The cached / stale model

A mechanical review exported the EDA's own 3D solid and measured heights off it. The tallest object
in the whole model, standing 8.477 mm above the board with pins protruding 1.40 mm out of the *back*
face into the battery area, **did not exist**. The part had been converted from a through-hole header
to three bare SMD pads, and the copper was correct — 3 pads, 0 drills, confirmed against the shipped
drill files — but the footprint document's title still read `HDR-TH_3P-P2.54-V-M-1`, and the EDA
resolves the 3D model from that title. Anyone who looked at the 3D, including the user, saw a part
that was not on the board.

**Guard:** cross-check every 3D-derived claim against the fabrication data. A hole exists if it is in
the drill file. A pad exists if it is in the copper Gerber.

### 2b. The bounding box that was reported as a pad

Two documents described a module's underside as *"two centre thermal lands, 4.0 × 3.0 mm and
7.0 × 7.0 mm"*. Segmenting the vendor's own rear-view photograph at the module's 25.00 mm scale gives
**20 discrete bare gold squares** — a 2×2 array of 0.73 × 0.70 mm and a 4×4 array of 1.13 × 1.10 mm,
**21.93 mm² of gold in total, not 61.0 mm²**. The two big rectangles were the third-party footprint
author's *bounding boxes*. (The derived centres agreed with the footprint records to 0.06 mm, which
is the cross-check that the photo scale was right.)

The same error class, one layer down: a Gerber clearance checker with no branch for the obround
aperture fell through to the rectangle case, modelled every SOIC/TSSOP pad as a full rectangle, and
reported **eleven clearance violations including a 0.0004 mm gap that would have been a short**. All
eleven were the tool. The real gap at that site was 0.1091 mm.

**Guard:** a pad is not its bounding rectangle. Carry the true outline — core box plus corner radius,
stadium, ellipse, polygon — and test the checker against a part whose real shape differs most from
its box.

### 2c. The copper labelled by the wrong owner

A Gerber checker attributed poured copper to a net by asking which pour *boundary* contained the
point. Inside a higher-priority island's rectangle that is ambiguous: a lower-priority pour
legitimately fills the gaps the higher-priority one leaves, so ground fill was labelled as the
analogue island and same-net copper abutting itself looked like a violation.

**Guard:** match the Gerber's pour strokes and fill regions to the document's own poured polygons by
vertex coincidence. Exact, not heuristic.

### 2d. The mirror axis validated on a symmetric object

A connectivity tool mirrored bottom-layer components with `x = -x` where the correct transform is
`y = -y`. It was caught only because one four-pad part on that layer was asymmetric; **the other 148
pads were symmetric two-terminal chips that look identical either way**. Two independent reviewers
then confirmed it by different methods — one by net-attributed comparison (negating y gave 141/0 and
249/0 agreement; negating x gave 59 and 94 mismatches), one by Gerber connected components
(negating x produced 38 breaks and 37 shorts; negating y was self-consistent).

Impact was zero, because every part on the affected chain happened to be on the top layer. That is
luck, not design.

**Guard, and it generalises past PCB work:** **calibrate every geometric transform against a known
asymmetric object before using it to decide anything.** Validating a mirror on a symmetric sample is
not validation.

### 2e. The instrument that answers about the previous document

The schematic DRC call returns whatever the DRC panel currently holds — which, on the first call
after a change, is the *previous* document's result. The same 149-part page returned "3 warnings"
twice and "1 error + 21 warnings" twelve times in one session; an empty page returned "passed / 0",
then "20 warnings", then "4".

**Guard:** re-run until the same result repeats N times in a row. Reading an asynchronous instrument
once is how a schematic gets declared clean when it is not.

---

## Meta-lesson 3 — a wait condition must fire on a crash

An autorouter threw a `StackOverflowError` at 00:34. Its worker thread died; the JVM sat at 0 % CPU
without exiting and without writing output. The supervising loop's condition was *"output file
appears **or** process disappears"*. Neither ever became true. **It spun for 10 hours 53 minutes**
and the completion notification never came. The user had to ask why it had been stuck all day.

The exception was written in plain text in the log the whole time. Nobody was listening for it.

**The rule, and it is general:**

> Any condition that waits on a background job must be able to answer: **"if this crashed right now,
> would my filter emit a line?"** If not, the condition is wrong. Silence is not success.

Cover four terminal states, plus a rate floor:

| state | signal |
|---|---|
| **output present** | the expected artefact exists *and* is non-empty *and* the log says the session completed |
| **crash signature** | `OutOfMemoryError`, `StackOverflowError`, `FATAL`, `Killed`, headless/display exceptions — terminal on sight |
| **process gone** | pid no longer exists |
| **wall-clock timeout** | an absolute cap |
| **rate floor** | progress-per-minute against the run's own median; kill if the trailing window sits below ~10 % of it |

Two refinements paid for on the same tool:

- **Not every logged exception is terminal.** The router's optimiser threads throw a
  `NullPointerException` near the end of a session and the session *carries on and still writes its
  best result*. A too-eager crash rule journalled two good runs as crashes and killed a
  demonstration run at 1.1 minutes. So: named fatal errors are terminal immediately; an ordinary
  logged exception is terminal only once the log has also stopped growing **and** the progress
  counter has stopped moving.
- **Do not claim a rule works if it never fired.** The rate rule was never exercised, because none
  of these runs stalled. Rather than assert it, the same rule was replayed offline against the
  finished logs and the verdicts recorded. *"Run 2's supervisor was stopped a few seconds before its
  first poll while I moved on — that is a gap in the record and it is not going to be dressed up."*

**And measure the input before feeding an external tool.** The crash came from handing the router
3 326 pre-routed protected traces; its combining routine recurses per connected segment. Raising the
stack size only moved the crash from 3 seconds to 11 minutes. The actual fix was to protect **51**
traces instead of 3 326. Adding resources cannot fix a wrong input scale.

---

## Meta-lesson 4 — judge connectivity by islands merged, not by edges drawn

Two ways to ask "is this net connected", and only one of them is true.

**Wrong:** count that every pin has a track leaving it, or compare routed length against a minimum
spanning tree. A walker that merges any two nodes sharing a position counts a track ending on an
inner layer and another starting on the top layer at the same point as connected — **with no via
there**. It reported a board fully routed; the EDA's DRC then found four broken nets.

**Right:** a **layer-aware** connected-components pass. Two nodes may merge only if their layer sets
intersect, and only a via or a through-hole pad spans every layer. Better still, do it on copper
geometry: rasterise each layer at 10–20 µm, label connected components with run-length union-find,
and treat each via or plated hole as a hyper-edge joining the (layer, component) nodes it lands on.

That same instrument answers a different question exactly: **which vias are redundant?** A via is
redundant only if deleting its hyper-edge leaves the whole net in one piece. On the reference
project's ground net that gave 122 redundant against 38 load-bearing — and the drill count came down
from 616 to 584 by deleting 32 of them, under a series of explicit keep rules (load-bearing;
within 2.00 mm of another net's via, because that is *that* layer change's return path; RF stitching;
and so on). Deleting "redundant" vias without those rules would have removed return paths that no
connectivity test can see.

**Also apply this to pours.** A pour that is declared is not a pour that exists. The reference
project shipped a review finding that read, in full: *"The analogue island has no copper — the pour
is declared but there is **no filled record for it at all**, 0 polygons, 0 mm², in both exports taken
minutes apart."* Judge a pour by its filled record, never by the rebuild call's return value: one
rebuild reported `rebuiltCount: 5, emptyCount: 0` while 24 ground pads were unconnected, and an
earlier iteration recorded the same lie with 120 of 143 pads open.

---

## Meta-lesson 5 — "no legal site" is not an answer while neighbours can move

A fix pass reported that two bias resistors had **no legal site within 6 mm** of the pins they had to
sit near, and left them undone. The ruling that came back:

> **"No legal site within 6 mm" is not an answer while other parts can move.** These are bias and
> coupling networks that must sit near their pins; if the neighbourhood is full, **move the
> neighbours** — the placer, the router and the module-body gate all still exist. Only after a real
> attempt with that degree of freedom may something be declared impossible, and then it comes with
> the measurement that proves it.

The next pass placed all four, plus 24 other new parts, moved 5 and re-footed 2, and declared **zero**
items impossible.

The general form: **an automated search failing is a fact about the search, not about the board.**
Before writing "impossible", say which degrees of freedom you held fixed and why. The honest version
of the same claim looks like the fader analysis, which rejected five placements by arithmetic
(*"needs 62.0 mm of wall; the longest clear left-wall run is 55.08 mm"*, *"body 6.5 mm > gap 4.741 mm,
and the longest clear 9.5 mm-wide lane anywhere on the top face is 10.80 mm, swept at 0.1 mm"*) and
then found the one that worked.

---

## Meta-lesson 6 — reviews disagree, and the disagreement is data

Two reviewers of the same board cited different rows of the same standard for the same clearance.
The later one showed the earlier had used the 31–50 V row for a 26.4 V net — conservative, so no harm,
but the finding's severity was wrong. Another pair disagreed about a differential pair's spacing
because one had read the top-layer legs and the other the inner-layer legs.

When a later measurement contradicts an earlier report, **say so explicitly and name both numbers**:

> The routing report's own pair table is wrong here: it lists D1 "at 0.50 pitch on Inner2 (0.310
> gap)". Measured, D1's Inner2 legs sit 0.860–2.375 mm centre-to-centre and have zero coupled length
> on either layer; 0.310 mm is the top-layer leg's gap.

Two reports that quietly disagree will be reconciled by whoever reads them next, badly.

---

## Meta-lesson 7 — review the reviewer's tooling too

The Gerber verification pass reported eleven violations on its first run and every one was its own
bug (§2b, §2c). It kept both wrong versions of the script on disk **deliberately, so the mistakes
stay visible**, and wrote the two root causes into its report as toolchain facts.

Do the same. A verification tool that has never been wrong has never been tested.

---

## Checklist for a review brief

```
[ ] scope: exactly what to review, and what to read only far enough not to duplicate
[ ] termination criterion, written before the review starts
[ ] read-only; work only inside <dir>; export your own copy
[ ] self-check: reproduce these known numbers on your own code path first
[ ] output: ranked findings (id / severity / measurement / failure scenario / cheapest fix)
[ ] output: a separate list of what you checked and found correct
[ ] output: a separate list of unverified suspicions, explicitly not findings
[ ] output: a verdict line "FIX FIRST: <ids>" and a fix order with reasons
[ ] one pass — do not iterate on your own findings
```
