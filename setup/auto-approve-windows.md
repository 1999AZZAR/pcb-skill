# Setup — the approval watcher (Windows)

Optional, and the same problem as the macOS guide: if your desktop raises a permission card for
**every** browser action, a run that touches two hundred pages costs two hundred interruptions, and
on Windows the card also **takes the foreground and auto-declines after about 30 seconds**, so a run
left unattended does not merely stall — it fails.

> **Provenance.** This guide is written from the service-registry entry `claude-chrome-auto-approve`
> and the tool's own README, both of which record the measurements verbatim. The implementation
> itself lives on a laptop that was not reachable while this was written, so **the source was not
> re-read**. Treat the mechanisms below as accurate-as-recorded and the exact file layout as
> illustrative. Where a number is quoted, it was measured on that machine on the date noted.

---

## The health criterion, first

> **The only proof this tool works is a recent, real approval line in its log.**

This is not a stylistic preference. On 2026-09-04 this exact tool went blind for a day: the watcher
process was alive, the log said `hookAlive=True`, the scheduled task reported `Ready`, and permission
cards were being left on screen until they auto-declined. Nothing errored. **The only symptom
anywhere was the total absence of hook lines in the log.**

The cause was a browser update renaming a window — see "How it went blind" below.

So the health check is:

```powershell
control.ps1 -Action Status
```

and what you read, in order of what actually matters:

| line | means |
|---|---|
| a recent `HOOK …` followed by `APPROVE kind=once ok=True intent=…` | **this is the health signal** |
| `hookAlive=True` | the hook was *installed*. It says nothing about whether it still matches the popup |
| `running  pid=<n>  task=Ready` | necessary, nowhere near sufficient |

A healthy pair:

```
HOOK    ev=0x8002 hwnd=0x1C05DE first=True stoleForeground=False fgBefore=0x1060A[Claude] …
APPROVE kind=once ok=True intent='Claude wants to read page content on: <host>'
```

`ok=True` means the card was gone when re-checked. `ok=False` means the invoke returned but the card
survived — investigate it, do not let it pass.

**Zero decisions while cards are visibly firing is itself the alarm.** Start by probing the popup's
real title, not by reading the approval code.

Independent check, if you do not trust the status script:

```powershell
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
  Where-Object { $_.CommandLine -like '*auto-approve*' } | Select-Object ProcessId
Get-Content <tool dir>\auto-approve.log -Tail 5
```

---

## What it is for, and what it deliberately does not do

It answers **navigation and read** permission cards during research and sourcing.

**Carts and payment are excluded on purpose.**

- `denyPhrases` refuses any card whose request mentions money moving.
- The browser extension separately refuses purchases, account creation and CAPTCHA solving without
  human input. This tool does not and cannot change that.
- The skill's own rule stands above both: the agent drives to the pre-payment page and stops.

---

## What the card looks like

```
New permissions required
Claude wants to click on:
<host>
        [ Allow this action                ⏎ ]
        [ Decline                        ESC ]
        [ Always allow actions on this site  ]   ← often withheld
```

Measured properties:

| property | value |
|---|---|
| window class | `Chrome_WidgetWin_1`, owned by the browser process |
| window title | the extension id — **but see the rename trap** |
| takes foreground on appear | **yes** |
| auto-declines after | **~30 s** |
| geometry | **not stable** — observed at both `601×600` and `901×900` |

Two of those (the unstable geometry and the auto-decline) mean anything pixel-based or leisurely is
already wrong.

---

## Architecture

```
hook.cs      A WinEvent hook on its own thread with its own message loop.
             Fires on the popup's own SHOW / NAMECHANGE event, stamps
             WS_EX_NOACTIVATE + WS_EX_LAYERED(alpha 0) + WS_EX_TRANSPARENT,
             pins it TOPMOST, hands the foreground back if the popup took it,
             and queues the hwnd. Does no slow work — a slow WinEvent callback
             stalls event delivery for the entire desktop.

watcher.ps1  Drains that queue and approves through UI Automation.
```

Splitting them is not an aesthetic choice. The hook callback runs on the desktop's event path; doing
UI Automation work inside it degrades every application on the machine.

**Windows PowerShell 5.1 (`powershell.exe`) is required — not `pwsh`.** The `UIAutomationClient` /
`UIAutomationTypes` assemblies ship with the desktop framework and are not present in PowerShell 7.
A build that runs fine when you test it in `pwsh` and dies under the scheduled task is usually this.

---

## The approval path — three failures and one that works

All four were measured on the real card:

| approach | result |
|---|---|
| `PrintWindow(PW_RENDERFULLCONTENT)` then match the button by pixels | **Fails.** Captures the frame and the infobar; the extension page area is blank because it is GPU-composited |
| `PostMessage` `WM_KEYDOWN`/`WM_KEYUP` `VK_RETURN` to the top-level window, to `Chrome_RenderWidgetHostHWND`, and to `Intermediate D3D Window` | **Fails.** All three ignored; the card stays up until it times out |
| UI Automation `TreeWalker` on its own | **Fails.** Returns the window frame, title-bar buttons and infobar — nothing from the extension page |
| **`WM_GETOBJECT` / `OBJID_CLIENT` to the render-widget children FIRST, then `FindAll(Descendants)`, then `InvokePattern.Invoke()`** | **Works** |

That last row is the whole trick: Chromium builds its web-content accessibility tree **lazily**, and
only once a client asks for it that specific way. Poke first, and the buttons appear:

```
Button 'Allow this action'  rect=1462,468 539x55  pat=Invoke
Button 'Decline'            rect=1462,530 539x55  pat=Invoke
Text   'Claude wants to click on:'
Text   '<host>'
```

`Invoke` needs no focus, no mouse and no pixel coordinates, so it is immune to the popup being
resized or moved. Measured detect-to-approved: **~1.2–2.4 s**, against a ~30 s deadline.

---

## Window placement — the two obvious answers are both wrong

The card takes the foreground, so it must be neutralised. Three placements were tried and the first
two look obviously correct:

| placement | focus | approval |
|---|---|---|
| move off-screen to `-32000,-32000` | fine | **breaks** — Chromium stops rendering an off-screen window, and an unrendered window has an **empty accessibility tree**, so the approver reports "no allow button found" on a perfectly good card |
| `HWND_BOTTOM`, on screen but under everything | fine | **breaks the same way** — fully covered counts as occluded |
| **stay in place, `TOPMOST`, alpha 0, click-through** | fine | **works** |

So the window is left exactly where the browser put it, on top so nothing can occlude it, but fully
transparent and click-through. Chromium still considers it visible and keeps rendering; you can
neither see it nor hit it.

This is the same underlying fact the macOS build runs into and solves differently (a headless
virtual display). **Hiding the card and reading the card are in direct conflict on both platforms.**

### The bug worth remembering: the tool was the thief

An early version called `SetForegroundWindow(previousWindow)` unconditionally on the show event. But
the popup does not necessarily own the foreground at that moment, and the remembered "previous"
window can be stale — so **the restore itself yanked the user out of whatever they were in**, and the
popup got the blame.

The restore is now conditional on `GetForegroundWindow() == popup`, and **every decision logs
`fgBefore` / `restoreTo` / `fgAfter` with window titles** so this is never guesswork again.

---

## Install — and why there are two triggers

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File <tool dir>\install-startup.ps1
Start-ScheduledTask -TaskName claude-chrome-auto-approve
```

Remove with `-Remove`. To start by hand: `wscript.exe start-hidden.vbs` (a `WScript.Shell.Run(…, 0,
False)` launcher, so no console window is ever created, plus a duplicate-instance guard).

The task is **per-user and non-elevated**, with **two** triggers:

1. **At logon** — the normal start.
2. **Every 10 minutes** — the self-heal.

The second one exists because the launcher starts PowerShell and returns immediately, so the
scheduler sees the task succeed at once and its restart-on-failure settings would never fire. If the
watcher died it would stay dead until the next logon. The launcher exits early when a watcher is
already running, so the repeat is a no-op in the normal case.

**Verified:** kill the watcher, run the launcher twice, exactly one process remains.

> `-RepetitionDuration ([TimeSpan]::MaxValue)` is rejected by the Task Scheduler with `0x80041318`.
> An **empty** `Duration` set on the registered trigger is what means "forever".

The macOS port replaces both triggers with launchd `KeepAlive`, which restarts in seconds instead of
up to ten minutes. If you are building this fresh on Windows and have a supervisor available, prefer
it.

### Stopping must also disable the task

Killing the process alone is not a stop — the 10-minute self-heal quietly resurrects it and your stop
button looks broken. A stop kills the watcher **and** disables the scheduled task; a start re-enables
it.

---

## Encoding rules — three silent failures

All measured on 2026-09-04. Every one of them fails **silently**: no error message, just something
not working.

| file type | required encoding | symptom when wrong |
|---|---|---|
| `.ps1` containing non-ASCII | **UTF-8 with BOM** | Windows PowerShell 5.1 decodes a BOM-less file as ANSI; every non-ASCII string becomes mojibake and then a parse error |
| `.vbs` containing non-ASCII | **UTF-16 LE with BOM** | Windows Script Host rejects a UTF-8 BOM with `invalid character` at line 1, column 1; the shortcut simply does nothing |
| a temp file a `.vbs` reads with `OpenTextFile(…, TristateTrue)` | **UTF-16 LE** | writing it as UTF-8 does not fail — it renders every popup as mojibake, so the text looks wrong when the *decoding* is wrong |

The safe habit: **keep `watcher.ps1` pure ASCII** and put every localised string in `config.json`,
read explicitly as UTF-8. That sidesteps the first row entirely.

---

## How it went blind — the incident in full

Worth reading once, because it is the failure mode this whole page is organised around.

**Symptom:** watcher alive, `hookAlive=True`, cards left on screen until they auto-declined, nothing
errored. The log simply had no `HOOK` lines after a restart.

**Root cause, measured rather than reasoned about.** The window was matched by an *exact* string
compare against `_crx_<extension id>`. A probe that polled every top-level window every 80 ms while a
real card was triggered caught the popup twice:

```
18:49:27.484  hwnd=0xA044C class=Chrome_WidgetWin_1 title=[_crx__<id>]
18:49:27.673  hwnd=0xA044C class=Chrome_WidgetWin_1 title=[Claude for Chrome]
```

Two changes at once, either of which alone breaks an exact match:

1. The birth title gained a second underscore — `_crx__<id>`, not `_crx_<id>`.
2. About **190 ms** later the window renamed itself to the extension page's own title.

**Fix:** match on the extension id as a **substring** (a 32-character id cannot collide with anything
else on the desktop), plus a configurable list of settled titles in `config.json`, plus one more
thing that is easy to miss — **keep treating a window already recorded as ours as ours after it
renames**. Without that last part the rename drops the popup into the "remember the user's window"
branch, and the popup itself gets recorded as the window to restore focus to.

**The general lesson:** an exact title match is a silent single point of failure. The browser renames
these windows without notice and nothing errors when the match stops matching.

---

## Safety limits — build these in, not on

- **Act only on a card that has both an allow and a decline button.** The extension's first-run
  onboarding screen ("Claude can now control your browser") has neither and is left alone —
  confirmed in the log.
- **Prefer "Always allow actions on this site" when the extension offers it**, because that stops the
  prompts at the source rather than answering one every time.
- **Do not try to defeat the extension's own site classification.** Reading the bundle,
  `disableAlwaysAllow = !classification.isResolved || classification.category === "category3"`, and
  category 3/4 are the tier where the product deliberately withholds standing permission and demands
  per-action approval. Shopping sites land there. Patching that out is off the table.
- **Scope `denyPhrases` to the request line plus the host — not the whole card text.** Every card
  carries a standing disclaimer along the lines of "Claude will not purchase items, create accounts,
  or bypass captchas without input", so matching the whole card against the money words **blocked
  100 % of cards** the first time this guard ran.
- **`allowDomains` / `denyDomains`** narrow it further; default `*`.
- **Any card it refuses is restored to a normal, visible, clickable window for a human.**
- The browser itself still refuses purchases, account creation and CAPTCHA solving without human
  input. This tool does not and cannot change that.

---

## Known limitation, honestly stated

**A brief visual flash of the popup remains.** The hook fires on the window's own show/name-change
event, which is already a few frames after Windows has put it on screen, so it is visible for that
moment before being made transparent. And the log shows the foreground restore is sometimes simply
refused by the system:

```
HOOK ev=0x3 stoleForeground=True
  fgBefore=0x36047A[_crx_…]  restoreTo=0x1060A[Claude]  fgAfter=0x36047A[_crx_…]
```

`fgAfter` unchanged means `SetForegroundWindow` did not take. No keyboard input loss was observed,
and the owner accepted this state, but it is **not** solved.

Untried levers, recorded so nobody re-derives them:

- retry the foreground restore a few times over the following ~200 ms instead of once;
- intercept at `EVENT_OBJECT_CREATE` and pre-stamp the styles before the title is even set —
  accepting the risk of briefly touching unrelated new browser windows;
- run the browser on a separate Windows desktop, which makes focus theft impossible by construction
  but costs the ability to use that browser interactively. (This is the closest Windows analogue to
  what the macOS build does with a virtual display.)

**Windows has no per-application "may never take focus" setting.** The one global knob,
`SPI_SETFOREGROUNDLOCKTIMEOUT`, was already at its maximum (`2147483647` ms) on that machine and this
popup gets past it anyway. That was measured — do not go back and "fix" it there.

---

## Optional: a tray indicator

The reference build added one, as its **own** process and its own scheduled task (logon +
10-minute self-heal), deliberately separate from the watcher: the watcher runs a tight drain loop
with no message pump, and a tray hosted inside it would disappear exactly when the watcher restarts —
the moment you most want it on screen saying what happened. The tray never talks to the watcher
directly; it polls the same facts the status command reports, so there is one definition of "is it
working" rather than a second opinion.

Two Windows facts it cost time to learn:

- **Windows 11 files new tray icons into the overflow.** Drag it out once. The promotion flag lives
  at `HKCU\Control Panel\NotifyIconSettings\<hash>\IsPromoted`, keyed by executable path plus an icon
  id that is not stable for a WinForms `NotifyIcon` — so this stays a one-time manual drag rather
  than a registry write.
- **`NotifyIcon.Text` throws above 63 characters** rather than truncating, and took the tray down on
  its first timer tick. Assemble the tooltip by dropping lower-priority lines, not by cutting one in
  half.

Whatever you build, make it confirm itself. A silent button is worse than no button for a tool whose
whole job is to run where nobody is watching it.
