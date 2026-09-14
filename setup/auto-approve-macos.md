# Setup — the approval watcher (macOS)

Optional. You need this only if your desktop raises a permission card for **every** browser action,
so that a run which touches two hundred pages costs two hundred interruptions and stalls whenever
you step away.

**Read this section before anything else.**

---

## The health criterion, first

> **The only proof this tool works is a recent, real approval line in its log.**

A live process, a `loaded` launchd agent, and a trust flag reading `true` do **not** together prove
it still recognises the card. This class of tool fails silently by construction: it matches a window
that somebody else ships and can rename without telling you.

It has happened. On the Windows build of this same tool, a browser update renamed the permission
window; the watcher stayed alive, its health flag stayed `true`, and it approved **nothing** for a
day. The only symptom anywhere was the total absence of decision lines in the log.

So the health check is:

```bash
./ccaa status
```

and what you are reading is, in order of what actually matters:

| line | means |
|---|---|
| `last decision: CARD … / APPROVE …` **with a recent timestamp** | **this is the health signal.** Everything else is context |
| `ax (as launched): true` | the Accessibility grant is real *in the context launchd runs it in* — see the TCC trap below |
| `agent loaded : yes` + a pid | necessary, nowhere near sufficient |

**Zero decisions while cards are visibly firing is itself the alarm.** When that happens, start by
probing the card's real window title and size. Do not start by reading the approval code — the
approval code is almost never what broke.

A healthy pair of lines looks like this:

```
CARD    win=6055 pid=43322 owner=[Microsoft Edge] title=[] rect=592x592 userVisible=true front=[Claude]
APPROVE win=6055 kind=once method=return axErr=0 gone=true dismissMs=755
        intent='Claude wants to navigate to:' host='s.taobao.com'
        timing ready=617ms axWindow=39 tree=55 tries=12 nodes=45
```

`gone=true` means the card actually left the screen. `gone=false` must print a warning that says
explicitly that any later dismissal was a human, not the tool — that wording exists because an early
version of this tool claimed the owner's own clicks as its successes for a while (see Trap 2).

---

## What it is for, and what it deliberately does not do

The watcher answers **navigation and read** permission cards during research and sourcing. That is
the whole point: a long run should not need a human in the chair.

**Carts and payment are excluded on purpose.**

- The tool's `denyPhrases` refuses any card whose request mentions money moving — purchase, payment,
  checkout, place order, pay now, buy now, 付款, 支付, 下单, 结算, 立即购买, 确认订单.
- The browser extension separately refuses purchases, account creation and CAPTCHA solving without
  human input. This tool does not and cannot change that, and does not try to.
- The skill's own rule stands above both: the agent drives to the pre-payment page and stops.

The watcher removes an interruption. It does not remove a decision.

---

## The reference implementation

This machine's build lives at `~/codex/tool/claude-chrome-auto-approve/` and is registered in
`~/codex/doc/service-registry.md` as `claude-chrome-auto-approve-macos`. Its own `README.md` carries
the full measurement record.

**Do not copy the signing key or the certificate from any existing installation.** You will generate
your own identity in five minutes — that is Step 3 — and a shared code-signing key would be both a
security problem and useless, because the Accessibility grant is pinned to *your* signature on *your*
machine. Copy the Swift source and the config; generate the identity yourself.

Everything below is written so you can build your own from scratch.

---

## The architecture, and the one fact that forces it

```
launchd  <label>.card-stage        → a headless virtual display, 1920×1080
launchd  <label>.auto-approve      → the watcher: parks the browser on that display,
                                     detects cards, reads them, presses Allow
```

The virtual display is not a nicety. It follows from one measurement:

> **Chromium does not render a window whose Space is not on screen, and an unrendered window has an
> EMPTY accessibility tree.** Measured: 432 polls over 8 s against a card sitting on a background
> Space — no buttons ever appeared.

That kills the two obvious designs:

| approach | focus | approval |
|---|---|---|
| hide the browser in another Space | fine | **breaks** — the approver goes blind and every card auto-declines |
| leave the browser in your Space | broken — a full-screen app is yanked to the browser's Space for ~6 s per card | works |
| park the browser on a **headless display** | fine | works |

A *display* behaves differently from a *Space*: every attached display has its own current Space and
they are all composited at once. A browser parked on a headless virtual display keeps rendering,
keeps a populated accessibility tree, and never touches what you are looking at. Measured with the
card firing:

```
front=[Claude]  claudeSpaceVisible=true  card=false
front=[Claude]  claudeSpaceVisible=true  card=true (588x588)   ← card up, on the stage
front=[Claude]  claudeSpaceVisible=true  card=false            ← approved, ~1.4 s
```

Frontmost app never changed, the Space never changed, and the card's own coordinates were off every
real screen.

No third-party software is needed: the private `CGVirtualDisplay*` classes in CoreGraphics create the
display (the same ones BetterDisplay and DeskPad use), and all four are present on macOS 26.

> **Name your stage process something nobody else uses.** This machine already runs a separate
> virtual-display helper for the owner's own remote desktop. `pkill -x` on a shared name matches
> both and blanks his session — it happened once during the port. If you have any other
> virtual-display tool, pick a distinct binary name and grep for collisions before you write a kill
> command.

---

## Step 1 — write the watcher

One Swift file is enough. The loop is: enumerate windows → recognise a card → walk its accessibility
tree → find the buttons → press Allow → confirm it left the screen → log the decision.

Four traps are wired into the working version and none of them should be "simplified" away.

### Trap 1 — the card is born blank and untitled

At `t+0` the window exists at full size with an **empty title** and a completely white body; it
renames itself to the settled title and paints its buttons some hundreds of milliseconds later.

Two consequences:

1. **Do not require the title to call a window a candidate.** Matching the settled title at birth
   matches nothing — and birth is exactly the moment you most want to have noticed the window.
   Match on the extension id plus a *configurable list* of settled titles, and once a window is
   yours, keep treating it as yours after it renames.
2. **A blank card proves nothing.** Keep re-walking the tree for a paint grace period (8 s works) and
   act only once the header text **and** an allow button **and** a decline button are all present. A
   card that never gets there is logged `TIMEOUT` and never approved on a guess.

### Trap 2 — `AXPress` returns success and does nothing

`AXUIElementPerformAction(kAXPressAction)` returns `.success` on this card and does **not** dismiss
it. Every time, ~350 ms, no effect.

Worse, that was briefly reported as *working*. The log said `axErr=0 gone=true` and the cards did
disappear — because the owner was pressing every one of them by hand while the tool did nothing. It
was caught by a timing argument, not by a code review: dismissal times of 419 / 485 / 1444 / 3488 ms
are a human reaction-time distribution, not a program pressing a button.

**Log `dismissMs` and look at its distribution.** If your tool's dismissals are lognormal around
half a second with a long tail, your tool is not the one pressing the button.

What works is **Return**, which the card binds to its allow button (it prints the return glyph on it),
delivered with `CGEvent.postToPid` — no activation, no pointer movement, no frontmost change.

### Trap 3 — the event source must be `.privateState`

`CGEventSource(stateID: .hidSystemState)` merges the synthetic key into the **real keyboard's**
state, so the Return becomes visible to the whole input stack. If you compose text through an IME, a
stray Return commits or destroys the in-progress composition. This was felt as *"it interrupted my
typing"* while a focus probe showed, across three clean runs at 10 ms resolution, that focus and
Space measurably never moved. `.privateState` keeps the event in its own state vector so only the
target process sees it.

### Trap 4 — `.optionAll` breaks the "did it go away" check

Enumerate with `.optionAll`, not `.optionOnScreenOnly` — the latter is scoped to the Space you are
looking at and misses every card on the stage. But a dismissed card's window **object lingers** in
the all-windows list after it leaves the screen, so "still exists" stops meaning "still up". The
watcher reported `gone=false` for a card that had already vanished, ran a pointless fallback, and
logged a warning accusing its own successful press of failing.

**Test `kCGWindowIsOnscreen`, not existence.**

### Build note

Compile **without `-O`**. It is a polling loop; optimisation buys nothing, and on this file `-O`
pinned three `swift-frontend` processes at 98 % CPU for minutes. Unoptimised it compiles in about
five seconds.

---

## Step 2 — the config file

Keep every string that can change out of the binary:

```json
{
  "extensionIds":   ["<the extension id>"],
  "windowTitles":   ["Claude for Chrome"],
  "browserOwners":  ["Microsoft Edge", "Google Chrome", "Chromium"],
  "allowButtons":   ["Allow this action", "Allow", "允许此操作", "允许"],
  "declineButtons": ["Decline", "拒绝"],
  "headerMarkers":  ["New permissions required", "需要新权限"],
  "allowDomains":   ["*"],
  "denyDomains":    [],
  "denyPhrases":    ["purchase", "payment", "checkout", "place order", "pay now",
                     "buy now", "付款", "支付", "下单", "结算", "立即购买", "确认订单"],
  "pollMs": 20,
  "cardMinWidth": 300,  "cardMaxWidth": 1000,
  "cardMinHeight": 250, "cardMaxHeight": 1100,
  "paintGraceMs": 8000,
  "restoreFocus": true
}
```

Localised button names belong here because the card follows the browser's UI language, and a build
that only knows English goes blind the day someone switches locale — the same silent-failure shape
as the renamed window.

---

## Step 3 — code-sign it, and understand why

Reading and pressing another process's UI needs the **Accessibility** TCC grant, which only a human
can give, in System Settings → Privacy & Security → Accessibility.

**The grant is pinned to the code signature, and this is where people lose an afternoon.**

With an **ad-hoc** signature the designated requirement is a `cdhash`. The hash changes on every
build, so **every rebuild silently revokes the grant** — observed live: rebuild, re-sign, next start
logs `axTrusted=false`, and nothing else says anything is wrong.

Sign with a **stable self-signed identity** instead:

1. Keychain Access → Certificate Assistant → **Create a Certificate…**
2. Name it something you will recognise; Identity Type **Self Signed Root**; Certificate Type
   **Code Signing**.
3. Keep the private key in your login keychain. Do not share it and do not commit it.

Then sign the bundle with that identity every time:

```bash
swiftc -o watcher Sources/main.swift          # note: no -O
cp watcher YourApp.app/Contents/MacOS/YourApp
codesign --force --sign "<Your Identity Name>" YourApp.app
codesign -d -r- YourApp.app                   # print the designated requirement
```

The requirement you want to see is bundle-id **plus certificate**, neither of which changes when the
code does:

```
identifier "<your.bundle.id>" and certificate root = H"<your cert hash>"
```

Have your build script *assert* on this. A one-line check that greps `codesign -dv` output for
`Signature=adhoc` and shouts if it finds it is the cheapest insurance in the whole setup.

Verify by doing it: rebuild, re-sign, restart under launchd, confirm the trust flag is still `true`.

> A **Developer ID** identity is not automatically better here. On this machine one was tried first
> and rejected: `codesign` cannot reach its private key non-interactively without the login keychain
> being unlocked, which a launchd-started build cannot rely on.

### The TCC trap that returns a false pass

> **Never test the Accessibility grant by running the binary from a shell.**

TCC attributes a tool spawned by your terminal or your agent to the **parent application** — which
has its own Accessibility grant — so the probe answers a confident, useless `axTrusted=true` while
the watcher, under launchd, has no grant at all.

Measured on this machine, and the reason the control script deliberately does not run a fresh probe.
The only context that counts is the one launchd runs it in, so:

**Have the watcher record its own trust state in its log at startup, and read the health check from
that line.** Not from a probe you just spawned.

Make the watcher **refuse to run without the grant** — exit non-zero, log `FATAL`, and raise the
system consent dialog — rather than starting up and approving nothing. A tool that fails loudly at
launch is worth far more than one that fails silently forever.

---

## Step 4 — install the two launchd agents

Both are **user** agents in `gui/<uid>`, both `RunAtLoad` and `KeepAlive`.

`~/Library/LaunchAgents/<label>.auto-approve.plist`:

```xml
<dict>
  <key>Label</key><string>&lt;label&gt;.auto-approve</string>
  <key>ProgramArguments</key>
  <array><string>/abs/path/YourApp.app/Contents/MacOS/YourApp</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>StandardOutPath</key><string>/abs/path/logs/launchd.out.log</string>
  <key>StandardErrorPath</key><string>/abs/path/logs/launchd.err.log</string>
  <key>ProcessType</key><string>Interactive</string>
</dict>
```

`KeepAlive` replaces the Windows build's logon task plus 10-minute self-heal: launchd restarts the
watcher the moment it dies, rather than up to ten minutes later. `ThrottleInterval` keeps a missing
Accessibility grant to one honest retry every 30 s instead of a crash loop — which matters precisely
*because* the watcher exits rather than pretending it can approve.

The stage agent is the same shape, pointing at your virtual-display binary, with a shorter throttle.
Give the stage process **no** permissions: parking lives in the watcher, which already holds the
Accessibility grant, so the whole setup needs exactly one TCC grant.

Load them:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/<label>.card-stage.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/<label>.auto-approve.plist
```

**A stop must unload the agent, not just kill the process.** With `KeepAlive` on, killing the
process alone brings it straight back and your stop button looks broken:

```bash
launchctl bootout gui/$(id -u)/<label>.auto-approve
pkill -f YourApp
```

Verified behaviour worth reproducing on your own build: kill the stage, the display is back within
6 s and the watcher re-parks the browser within 5 s.

---

## Safety limits — build these in, not on

Every one of these exists because something went wrong without it.

- **Act only on a card showing the header marker AND an allow button AND a decline button.** The
  extension's first-run onboarding screen has none of these and must be left alone.
- **Prefer a standing "always allow on this site" button when the card offers one** — it stops the
  prompts at the source. On the sites that matter for sourcing it is *not* offered: the product
  withholds standing permission for that tier on purpose, and patching that out is off the table.
- **Scope `denyPhrases` to the intent line plus the host — not the whole card text.** Every card
  carries a standing disclaimer along the lines of "Claude will not purchase items, create accounts,
  or bypass captchas without input". Matching the whole card against the money words therefore blocks
  **100 % of cards**. Learned on Windows; still true on macOS.
- **A card whose host cannot be read is SKIPPED, not approved.** The first host extractor on this
  build matched the literal `.` out of the footer sentence "Revoke site permissions in settings.",
  logging `host='.'` on every decision — so the allow/deny domain lists were gating on nothing at
  all. A safety gate that cannot see the host is not a safety gate.
- **Any card it refuses is left alone, visible and clickable, for a human.**

---

## Operating it

```bash
./ccaa start      # bootstrap the agent
./ccaa status     # the health check above
./ccaa log 40     # tail the decision log
./ccaa stop       # bootout AND kill
```

To use the browser by hand, drag its window back to the real display. Parking should be gentle by
design — move a window only if it is *not already* on the stage — so it will not fight you, though it
will re-park the next new window. Keep an environment variable that disables parking entirely for
when you want the browser in front of you.

---

## When it goes blind

The symptom is always the same: it runs, nothing errors, and no decisions appear.

1. Confirm cards are actually firing (trigger one deliberately).
2. **Probe the card's real window title, owner and size** while it is up — an 80 ms all-windows
   poll is enough. That is how the Windows build's rename was caught, and it is where every one of
   these investigations should start.
3. Compare what you measured against `windowTitles`, `extensionIds`, `browserOwners` and the card
   size bounds in your config. Most breakages are a config line, not a code change.
4. Only then read the approval path.
