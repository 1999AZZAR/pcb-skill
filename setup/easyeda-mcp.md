# Setup — EasyEDA Pro over MCP

The skill drives the EDA directly: it reads the schematic and PCB as data, writes primitives,
runs DRC, and exports Gerbers without a human touching the canvas. That needs a bridge between
your MCP client and EasyEDA Pro.

**Use the bug-fix fork:** <https://github.com/sheares/easyeda-mcp-fix>

It is a fork of `javawizard/easyeda-agent-mcp-server` (itself a fork of
`QuincySx/easyeda-agent-mcp-server`) and it exists because the upstream bridge has failure modes
that destroy data quietly — a single component modify wiping every BOM field, API-drawn copper that
is electrically dead to its own SMD pads while DRC reads zero, netlist reads that hang five minutes
and return nothing. Seventeen such faults are fixed and documented in its README with the root cause
for each. Read that table before you decide you have found a new bug; you have probably found an
old one.

Everything below assumes that fork. Paths in `<angle brackets>` are yours to fill in.

---

## What you are installing

Two programs and one socket between them:

```
MCP client (Claude Code / Codex)
   │  stdio
   ▼
easyeda-agent-mcp-server ──spawns──▶ bridge daemon  (127.0.0.1:16168)
                                          ▲
                                          │ WebSocket
                                 .eext extension inside EasyEDA Pro
```

- The **MCP server** is a Node process your client spawns. It exposes ~98 tools.
- The **bridge daemon** starts itself on the first tool call.
- The **`.eext` extension** runs inside EasyEDA Pro and dispatches into its internal `eda.*` API.
  It is a separate artefact with its own version, installed through the EDA's own GUI.

Both halves have to be present and matched. Neither half tells you the other is stale unless you
ask, which is trap 1 below.

---

## Prerequisites

| | |
|---|---|
| **EasyEDA Pro** (嘉立创EDA专业版) desktop client | The web app can connect, but the desktop client is what the rest of this skill assumes |
| **Node ≥ 20.5** | `engines` floor in the fork's `package.json` |
| **git** | to clone |

Verified on EasyEDA Pro 3.2.166 / 3.2.184 / 3.2.186 on Windows and macOS. Nothing here is
version-locked, but the EDA's internal API does move — if a tool starts failing after an EDA
update, suspect the EDA before the bridge.

---

## Step 1 — build the bridge

```bash
git clone https://github.com/sheares/easyeda-mcp-fix.git
cd easyeda-mcp-fix
npm install
npm test              # 140 tests; two POSIX-only tests skip on Windows
npm run build         # produces build/dist/easyeda-agent-mcp-server_vN.N.N.eext
```

`npm run build` does two things at once: it compiles the MCP server into `dist/mcp-server/` and it
packages the extension into `build/dist/*.eext`. You need both outputs.

**A successful build is not an installation.** Say that out loud now, because trap 1 is exactly
someone forgetting it.

---

## Step 2 — install the extension into EasyEDA Pro

This is a GUI action. There is no API for it, and on a locked-down desktop it may need the machine
owner's hands.

1. Open EasyEDA Pro.
2. **高级 → 扩展 → 扩展管理器 → 导入扩展** (English builds: **Advanced → Extensions → Extension
   Manager → Import**). Pick the `.eext` from `build/dist/`.
3. Open the extension's **配置 / Settings** and set:
   - **允许与外部交互 / Allow interactive with external** — ON.
     Optional under the default Origin-trust mode; **mandatory** if you run the daemon with
     `EDA_WS_AUTH=require`. Turn it on anyway; it costs nothing and removes a whole class of
     "why is it not connecting".
   - **显示在顶部菜单 / Show in top menu** — ON. Not required for auto-connect on LCEDA 3.x, but it
     gives you a visible place to confirm the extension is loaded at all.
   - **自动更新 / Auto-update** — **OFF**. You are running a fork; letting the EDA replace it with
     the upstream build is a silent downgrade back into the bugs.
4. Restart EasyEDA Pro. The extension auto-connects on startup.

### Trap 1 — same-version reinstalls are a no-op

The installed `.eext` lives in EasyEDA's own IndexedDB, entirely separate from your `dist/`. Two
consequences, both of which have cost real hours:

- **Importing a build whose version matches the installed one does nothing at all** and reports no
  error. Bump `version` in `extension.json` before every rebuild you intend to install.
- **`bridge_restart` reloads only the daemon.** It cannot and does not reload the `.eext`. Restarting
  the bridge after an extension change gives you the old extension with a fresh daemon, which looks
  like your fix did not work.

The only honest confirmation is a live version readback — Step 4.

---

## Step 3 — register the MCP server

The server is a plain stdio process: `node <repo>/dist/mcp-server/index.js`.

### Claude Code

```bash
claude mcp add easyeda-agent -- node /abs/path/to/easyeda-mcp-fix/dist/mcp-server/index.js
```

or, equivalently, in your Claude Code config's `mcpServers` block:

```json
{
  "easyeda-agent": {
    "type": "stdio",
    "command": "node",
    "args": ["/abs/path/to/easyeda-mcp-fix/dist/mcp-server/index.js"]
  }
}
```

If your `node` is not on the PATH a GUI-launched client inherits — common on macOS with a Homebrew
or version-manager install — add an explicit `env.PATH` to the entry rather than editing your shell
profile:

```json
"env": { "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin" }
```

### Codex

`~/.codex/config.toml`:

```toml
[mcp_servers.easyeda-agent]
command = "node"
args = ["/abs/path/to/easyeda-mcp-fix/dist/mcp-server/index.js"]
```

(`codex mcp add` writes the same table if you prefer the CLI. Check `codex mcp --help` on your
version if the key names differ.)

**Restart the client after adding the server.** Tool lists are read once at startup; a client that
was already running will not see the new tools, and — worse — a client holding a *cached older* tool
list will call tools with parameters the current server no longer takes.

---

## Step 4 — verify it is live

Two calls. Do both, every session, before any design work.

### `server_info`

```
server_info()
```

What you are reading:

| field | what it must say | why |
|---|---|---|
| `extensionConnected` | `true` | `false` means the EDA half is not talking. It usually reconnects on its own — wait, do not `bridge_restart` |
| `extensionVersion` | the version you just built | this is the readback that defeats trap 1. If it shows the old number, your import silently did nothing |
| `extensionUuid` | stable across restarts | a changed uuid means a different extension is installed than you think |

### `editor_get_open_tabs`

```
editor_get_open_tabs()
```

Returns the documents the editor actually has open, with their uuids. This is your proof that the
bridge is not merely connected but addressing the right EDA instance — the daemon can serve several
EasyEDA instances at once, and every tool takes an optional `instance_id` and `document` for
cross-tab routing. If you have two instances open and do not pin one, you will eventually write to
the wrong board.

Also useful once you have a project: `project_get_structure` for the board/schematic/PCB tree.

### What does **not** prove it is live

- A successful `npm run build`.
- The extension appearing in the EDA's extension list.
- A tool call returning `success: true`. Several tools on this API return success on writes that did
  not land — that is the entire subject of the skill's `references/05-easyeda-mcp.md`, and it is not
  optional reading before your first write.

### A 45-second timeout usually is not a hang

If a tool times out at ~45 s, the extension has most likely dropped its WebSocket rather than the
editor hanging. Check `server_info` for `extensionConnected: false` and wait; it reconnects on its
own. Restarting the bridge at this point just adds a variable.

---

## HALF_OFFLINE vs online, and what it costs you

EasyEDA Pro can run in a **half-offline** mode (`半离线` / `HALF_OFFLINE`) where projects live
locally and no account sync is involved. It is convenient — no login, no cloud round-trip, and the
project cannot be quietly changed under you — but it removes one capability the API otherwise has.

**Project creation through the API does not work in this mode.** Measured, not inferred:

- `project_create` fails with the local-server error `1111116 请求参数path错误`. The underlying
  create-project endpoint wants a filesystem `path` the extension API has no way to pass.
- `project_import_file` into a *new* project fails too — including on the runtime's own unmodified
  export. So it is the mode, not your archive.

### The consequence, and the workaround

**The human must create the project once, in the GUI:** 文件 → 新建 → 工程 (**File → New →
Project**), name it, done. That is the only manual step; everything after it is API-driven.

Then load your staged content with `project_import_file` targeting that project's uuid
(`existingProjectUuid`). Three things to know before you do:

1. **Importing into a non-empty project GRAFTS rather than replaces.** You get a second board and
   duplicated panel documents. Clean up with `project_delete_board` and
   `project_delete_detached_pcb` — but the empty schematic shell and the stray `Panel1_*` documents
   **cannot be deleted through the API** and need a right-click in the GUI. Import into an empty
   project.
2. **Some standalone runtimes reject legacy `.epro` and want `.epro2`.** The fork keeps trying
   `.epro` for forward compatibility and, when that exact call fails, appends the `.epro2` recovery
   path to the error instead of leaving you with a generic import failure.
3. **An import re-uuids hand-built footprints.** Any offline verifier you wrote against the previous
   export will then silently drop the renamed parts' pads and report a *better*-looking board. After
   any import, regenerate your analysis inputs from a fresh `project_export_file`, and if pads appear
   to have vanished, ask the EDA (`pcb_get_component_pins`) before believing the loss.

### Also worth knowing before you commit to a mode

Some PCB houses tie their free-prototype coupon to the design being **native to their EDA and not
imported**. If that applies to you, the safest shape is: the ordered document is a GUI-created native
document whose *content* was loaded through the extension API. Decide this before you build the
project, not at the order page. See the skill's `references/03-jlc-manufacturing.md`.

---

## The backup repo — where a bad write goes to be recovered

**Every destructive upload is auto-committed to a git repo before it lands.**

| | |
|---|---|
| default location | `~/.easyeda-mcp-backup` |
| override | `EDA_BACKUP_DIR` in the daemon's environment |
| what you get back | the tool response includes a **backup SHA** |

That SHA is the thing to keep. When an edit goes wrong — and on this API an edit going wrong is a
`success: true` with half your wires missing, not an exception — you `git show <sha>` in that repo,
pull the pre-write source back out, and push it again with `document_load_from_file`.

Uploads default to `validate='strict'`: the fork's Zod schema runs over the new source and **aborts
the upload** on any unknown or malformed line. Downloads validate in `warn` mode and attach a report.
`document_validate` runs the same check on demand. If a download surfaces `unknown-tag` samples, the
schema is missing coverage for a shape your EDA build actually emits — extend it rather than
disabling validation.

Two habits worth having from day one:

- Take a `project_export_file` snapshot of your own before any batch write, and name it with a
  timestamp. The backup repo protects the *document*; your snapshot protects the *project*.
- Compare exports **archive-to-archive**. Runtime-form and archive-form differ in bookkeeping counts
  (`PAD_NET`, `POURED`) without differing in connectivity, so a runtime-vs-archive diff invents
  changes that are not there.

---

## Bulk edits — do not do them one tool call at a time

Each per-primitive MCP call is a WebSocket round trip, ~100 ms. Hooking up one chip is hundreds of
them. The fork ships an in-tree TypeScript editing library (`src/lib/`, tour in
`src/lib/README.md`) for the pull-edit-push loop instead:

```
1. project_export_file            → .epro/.epro2 ZIP of NDJSON on disk
2. unzip it
3. a throwaway ts-node script: loadSchematic() + SchematicWriter
4. document_load_from_file        → push the result back in one call
```

`SchematicWriter` handles the bookkeeping that is easy to get silently wrong: sequential element
ids, unique ids, `maxId` in the header, junction wires at component-to-component connections, and
designator allocation. `examples/add-fpga-config-resistors.ts` is a working script to copy from.

The library's schemas are the same ones that validate your uploads, so a document the writer
produces is a document the bridge will accept.

---

## Security posture

The daemon binds `127.0.0.1:16168` only. Its WebSocket auth is a challenge-response: the daemon
writes a per-run random token (mode `0600`, inside a `0700` state directory) and challenges every
extension connection to read it back, which proves the peer runs as the same user. A wrong answer
always closes the socket.

By default, a connection that *cannot* read the token — the browser web app, or a desktop install
without the extension's external-interaction permission — is still accepted on Origin trust. Set
`EDA_WS_AUTH=require` in the daemon's environment to refuse unauthenticated connections outright.
That is desktop-client-only and requires the extension's external-interaction permission to be on.

The fork's `AUDIT.md` documents all three layers with severity ratings; seven criticals were
identified and all seven are resolved on that branch.

---

## Health criterion — what "ready" means

Before the skill starts design work, all four of these must be true, checked and not assumed:

1. `server_info` returns `extensionConnected: true`.
2. `extensionVersion` matches the build you installed.
3. `editor_get_open_tabs` returns the documents you expect, from the instance you intend to write to.
4. You know which mode the EDA is in (`HALF_OFFLINE` or online) and have created the project by hand
   if it is the former.

If any of them is uncertain, fix it now. Every hour spent on a design whose bridge is talking to a
stale extension is an hour spent on the wrong board.

---

## Next

The skill's `references/05-easyeda-mcp.md` is the trap list — the API calls that return `true` and do
nothing, the coordinate systems that disagree, the geometry that is not what it looks like. **Read it
before your first write**, not after your first surprise.
