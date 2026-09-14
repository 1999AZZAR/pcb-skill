# Setup

Four things, in this order. The skill checks all of them before it starts design work, and it will
stop rather than begin on an environment it cannot verify — because every hour spent designing
against a stale bridge or an expired session is an hour spent on the wrong board.

Each step below has a **proof**. Run it. "It looked fine" is not one of them.

---

## 1. EasyEDA Pro over MCP → [`easyeda-mcp.md`](easyeda-mcp.md)

Build the bridge fork, install its extension inside EasyEDA Pro through the GUI, register the MCP
server with Claude Code or Codex, and — if the EDA is running half-offline — create the project by
hand once, because the API cannot.

**How you know it worked:** `server_info` returns `extensionConnected: true` **and** an
`extensionVersion` equal to the build you just installed, and `editor_get_open_tabs` lists the
documents you expect. A successful `npm run build` proves nothing: same-version extension imports are
a silent no-op.

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
| 1 | build the bridge, install the `.eext`, register the MCP server, create the project by hand if half-offline | `server_info` → `extensionConnected: true` + the version you built; `editor_get_open_tabs` lists your documents |
| 2 | log in everywhere; grant the domains to the extension | the agent reads your cart back, no redirect, no permission error |
| 3 | install the approval watcher, if you need one | a recent `APPROVE` line in its log |
| 4 | wire up notifications | a test message arrives, and the watchdog would emit a line on a crash |

Then read the skill itself — `../SKILL.md` once installed,
[`skills/pcb/SKILL.md`](../skills/pcb/SKILL.md) in this repo — and start at Phase 0.
