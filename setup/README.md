# Setup

Four things, in this order. The skill checks all of them before it starts design work, and it will
stop rather than begin on an environment it cannot verify — because every hour spent designing
against a stale bridge or an expired session is an hour spent on the wrong board.

Each step below has a **proof**. Run it. "It looked fine" is not one of them.

---

## 1. KiCad Environment → [`kicad-setup.md`](kicad-setup.md)

Install KiCad (v9 native, v7/v8 supported) with `kicad-cli` and `pcbnew` Python bindings,
and verify the headless checker tools and scripts.

**How you know it worked:** `kicad-cli --version` outputs the installed version (e.g. `9.0.x`),
`python3 -c "import pcbnew"` imports cleanly without error, and running
`python3 scripts/run_all_tests.py` reports `ALL TESTS PASSED ✔️`.

---

## 2. Browser logins → [`browser-logins.md`](browser-logins.md)

Log in to your PCB house, your parts distributor and every marketplace the project will use, in the
browser profile the agent will drive. Grant those domains to the agent's browser extension —
including split hosts like `detail.` and `s.`. Not the login host.

**How you know it worked:** the agent can open your **cart page** on each site and read its contents
back, with no redirect to a login page and no permission error. That one check covers the session,
the domain grant and the browser profile at once. Do not judge by an avatar or a cart badge — an
expired session keeps both.

---

## 3. An approval watcher, if your desktop needs one → [`auto-approve-macos.md`](auto-approve-macos.md) · [`auto-approve-windows.md`](auto-approve-windows.md)

Only needed if every browser action raises a permission card the agent cannot press itself. On
Windows the card also auto-declines after about 30 seconds, so an unattended run does not stall — it
fails.

**Carts and payment are excluded on purpose.** The watcher refuses any card whose request mentions
money moving, the browser extension separately refuses purchases and account creation, and the skill
drives to the pre-payment page and stops. Three independent limits, and none of them is removed here.

**How you know it worked:** a **recent, real approval line in the watcher's log**. Nothing else
counts. A live process, a `Ready` scheduled task or a `loaded` launchd agent, and a trust flag
reading `true` are all compatible with a watcher that has silently stopped recognising the card —
this has happened, for a day, after a browser update renamed the window. Zero decisions while cards
are firing is the alarm, not the absence of one.

---

## 4. A notification channel

Long runs go quiet for hours at a time. Wire up whatever relay you already use — `scripts/notify/`
holds the reference one — so that silence is never ambiguous.

**How you know it worked:** send one test message and see it arrive on the device you will actually
be looking at. Then make the run's watchdog answer this question before you trust it: *if the job
crashed right now, would my filter emit a line?* If the answer is no, you do not have a
notification channel — you have a hope.

---

## The short version

| # | do | proof |
|---|---|---|
| 1 | install KiCad 9 and pcbnew, test headless toolchain | `kicad-cli --version` output; `python3 scripts/run_all_tests.py` reports all passed |
| 2 | log in everywhere; grant the domains to the extension | the agent reads your cart back, no redirect, no permission error |
| 3 | install the approval watcher, if you need one | a recent `APPROVE` line in its log |
| 4 | wire up notifications | a test message arrives, and the watchdog would emit a line on a crash |

Then read the skill itself — `../SKILL.md` once installed,
[`skills/pcb/SKILL.md`](../skills/pcb/SKILL.md) in this repo — and start at Phase 0.
