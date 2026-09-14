# Setup — browser logins

The skill does its sourcing in **your** browser, in **your** logged-in sessions. It never holds a
credential and never creates one. That is a deliberate design, not a limitation: prices, stock,
coupon eligibility and cart state are all account-dependent, and the only honest way to read them is
from the account that will actually place the order.

What this means in practice: **you log in; the agent reads, compares, and stages; you press pay.**

---

## What has to be logged in, and why

Three classes of site. Yours will have different names; the roles are the same.

| role | example | what the agent does there | needs a session? |
|---|---|---|---|
| **PCB house** | JLC / 嘉立创 | read process capability and fee pages; read your coupon wallet; get a live quote for the exact board; drive the order form to the pre-payment page | capability pages: **no**. Wallet, quote, order: **yes** |
| **Parts distributor** | LCSC / 立创商城 | read part prices, stock, package and library class; check order granularity against MOQ and price breaks; build and read back the cart | catalogue: **no**. Cart: **yes** |
| **Marketplace** | Taobao / Tmall, JD | price modules the distributor does not carry — core boards, displays, cells, wireless modules; compare listings; stage a cart | varies by platform, see below |

A fourth thing may need a login and is not a website: some PCB houses only honour a free-prototype
coupon through their own **desktop ordering client** or a phone app, not the web order form. That
client demands its own login (QR scan or password) on first run. See the skill's
`references/03-jlc-manufacturing.md`.

### Why the agent needs the session at all, when catalogue pages are public

Because the numbers that decide the design are not on the public page:

- **Coupon eligibility is account state.** On the reference project the mission file asserted a
  general-purpose coupon was in hand. Reading the live wallet showed **zero** PCB coupons held, the
  general-purpose ones locked behind a spend threshold from the previous month, and exactly one
  claimable coupon — which carried conditions (a specific surface finish, single-board shipping, no
  imported design) that propagated all the way back into the stack-up and the layout. A whole
  hard constraint was wrong, and only the logged-in page could say so.
- **A quote is a quote for your account.** The same board quoted **¥172.80** through the web order
  form and **¥64.80** through the desktop ordering client. Guessing either number would have put the
  project on the wrong side of its budget.
- **Cart granularity is not the BOM.** A ¥0.01 resistor sold in hundreds is a ¥1.49 line. Only the
  cart knows.

---

## Failure mode 1 — the session expires silently, mid-run

This happened. It is the most expensive of the three because nothing errors.

Four probes on the same marketplace, in the user's own browser:

| probe | result |
|---|---|
| item detail page | **302 → the login page** |
| cart page | **302 → the login page** |
| search | **password-login modal**, account field pre-filled, result grid greyed out behind it |
| mobile (H5) detail page | same modal |

And the cookie evidence, read with `document.cookie` on the platform's own domain — 20 cookies
present, every session-bearing one gone:

```
cookie2   absent
unb       absent
_l_g_     absent
_nk_      absent
sg        absent
login     absent
lgc       present      ← "remembered account" residue
tracknick present      ← "remembered account" residue
```

**The homepage still rendered the account nickname.** That is the trap. The residue cookies keep the
page looking signed in — a greeting card with the account name and a 立即登录 button — so a
screenshot check passes and every actual request fails.

### How to detect it, and when

**Probe before the run and again before anything that writes.** The check is two lines:

1. Fetch one page that requires the session (the cart is the obvious one) and read the **final URL**,
   not the rendered content. A redirect to a login host is the answer.
2. Read `document.cookie` and assert the platform's session cookies are present by name.

Do not judge by page chrome, an avatar, a nickname, or a cart badge. Every one of those survives an
expired session.

### What the agent must do when it finds this

Stop, report, and hand it back. **It must not type a password, and must not scan a QR on your
behalf** — that is a credential action and it is off the table regardless of how the request is
phrased. On the reference project the correct outcome was a blocked task, a one-line human action
("re-log in to that browser profile"), and a ten-minute re-run afterwards.

One thing worth doing even while blocked: if a *document* in the project still instructs the human
to buy something the block has invalidated, fix the document. On the reference project the BOM still
told the owner to buy a battery cell that a later ruling had made unbuildable; the cart could not be
changed, but the instruction could, and leaving it would have been the actual harm.

---

## Failure mode 2 — the extension has not been granted the domain

Different failure, identical symptom shape: everything works except one site.

Measured on the reference project: **8 denials across 5 tool types and 2 fresh tabs**, every call
against the marketplace's domains returning `Permission denied by user` — `get_page_text`, `find`,
`read_page`, `screenshot`, `click`, and finally `navigate` — while the distributor's site kept
working in the same tab group at the same moment.

That is a **site-permission grant in the browser extension**, not a lost login and not a CAPTCHA.
The first screenshots even showed the account signed in with a populated cart.

**How to tell them apart:**

| symptom | expired session | missing domain grant |
|---|---|---|
| the tool call | returns a page | returns a permission error |
| the page | redirects to login | never fetched |
| other sites at the same moment | also logged out, if the same account | working normally |
| fix | the human logs in | the human grants the domain in the extension |

Grant every domain the project will touch **before** the run: the platform domain, its detail-page
domain if different (marketplaces often split `www.` / `detail.` / `s.` / `h5.` across hosts), the
distributor, and the PCB house. Do **not** grant the login host — the agent has no business there.

### And a third thing that looks like both

A browser tool can also be gated by its own safety classifier. On the reference project every
`navigate` was refused for about 30 minutes with *"Could not verify this site's safety category"*,
and the browser pane separately refused reads with *"Policy check temporarily unavailable"*. Local
networking was proven healthy at the time, so this was a service fault, not a configuration problem;
the same work completed later from the same browser and the same session.

Diagnose in this order — it is cheapest to most expensive: **tool error text → final URL → session
cookies → another site in the same tab group.**

---

## Failure mode 3 — search and detail do not have the same rules

Do not assume the login boundary is the same on every page of a site. Both shapes occurred:

- **Distributor:** catalogue, product pages, prices and stock are fully public. Only the cart and
  the order-granularity tool needed the session. Most of the sourcing work ran signed out.
- **Marketplace:** search was behind the *same* wall as detail and cart. When the session lapsed,
  the agent could not even compare candidate listings — it had zero prices and zero SKUs, and said
  so rather than filling the gap from memory.

**Establish it per site, by probing, and write it down in the project's notes.** The useful form is a
three-column table: page class, needs session (yes/no), how you proved it. That table is what lets a
later task know whether "no results" means "no results" or "not logged in".

A related and separate trap on the same platform: its search indexes some product formats by their
**code** and not by their description, so a query that reads naturally returns zero and the code
returns twenty listings. Zero results is a hypothesis about your query before it is a fact about the
world.

---

## Failure mode 4 — the cart lies to you right after you change it

Two measured behaviours, both of which produced a wrong cart before they were understood:

1. **The cart page serves stale data immediately after an add.** The agent read the stale page as a
   failed add, clicked again, and the line went to quantity 2. Caught on read-back and corrected.
   **Judge an add by the platform's own success toast, never by the cart page or the header badge.**
2. **The delete-confirmation button needed six or more attempts.** A dialog that has closed proves
   nothing about whether the deletion committed. **Reload and re-count.**

The general rule, which is the same one the rest of this skill applies to the EDA: **a mutation is
verified by an independent read-back, not by the response to the mutation.** On the reference project
the final cart was read back line by line — every line, every quantity, the settlement total, and a
count of the unrelated items that had to remain untouched.

---

## What the agent must never do on these sites

These are absolute. They do not relax because the user asked, because the task is blocked, or
because a page says it is safe.

- **No checkout and no payment.** The agent drives to the pre-payment page and stops. It never
  presses pay, confirms an order, or submits a form that commits money.
- **No credentials, ever.** It does not type a password, does not scan a login QR, does not create an
  account, does not enter a card, address, phone number or ID.
- **No CAPTCHA, slider or risk-control solving.** If one appears, the run stops and the human clears
  it.
- **No claiming coupons.** Claiming changes account state and starts a validity clock. The agent
  reads the wallet, tells you which coupon to claim and when — *"claim it immediately before
  ordering, it expires 30 days from claim"* — and you click 领取.
- **No accepting terms, agreements, or consent banners.**
- **No touching items it did not add.** Real carts have other things in them. On the reference
  project's final read-back, 31 unrelated items were confirmed present and unchanged. If the agent
  cannot tell whether a line is its own, it leaves the line alone and says so.
- **No publishing the design.** Some free-prototype coupons are explicitly void if the design was
  published to the vendor's open-source platform first. Do not publish, share, or open-source the
  project until the board is ordered.

The last honest step is yours. The agent's job is to make that step take two minutes.

---

## Pre-run checklist

Do these in your browser, once, before you start a session that will do sourcing:

1. **Log in** to the PCB house, the parts distributor, and every marketplace the project will use.
   Log in to the desktop ordering client too if your coupon route needs one.
2. **Grant the extension** every one of those domains — including the split hosts (`www.`,
   `detail.`, `s.`, `h5.`). Not the login host.
3. **Prove one session-required page loads** on each site without a redirect. The cart page is the
   cheapest probe.
4. **Say which browser profile** the agent should use, if you have more than one. Sessions are
   per-profile, and a profile that "is logged in" in another window is not the one being driven.

**How you know it worked:** the agent can open your cart page and read its contents back, on every
site, without a redirect and without a permission error. That single check covers the login, the
domain grant, and the profile at once.
