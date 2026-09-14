# `scripts/kicad/` — Headless KiCad Automation, DRC, and JLCPCB Export

Tools for driving KiCad without user interface interaction.

---

## The scripts

| script | what it does | dependencies |
|---|---|---|
| `kicad_ctl.py` | unified CLI automation controller exposing 233 KiCad commands & batch recipes | `kicad-skip`, `sexpdata`, `pcbnew` / stdlib |
| `drc_check.py` | runs `kicad-cli pcb drc --format json`, aggregates errors, unrouted items, and schematic parity | `kicad-cli` |
| `export_jlcpcb.py` | 1-command JLCPCB fabrication packager (Gerbers, Drill, CPL, BOM, ZIP) + verification | `kicad-cli` |
| `route_kicad.py` | Specctra DSN export, FreeRouting supervisor, and SES merger into `.kicad_pcb` | `pcbnew` / stdlib |

---

## Quick start

### 1. Unified KiCad Control Automation
```bash
# List available commands
python3 kicad_ctl.py list-commands --category schematic
python3 kicad_ctl.py list-commands --category placement

# Execute a command
python3 kicad_ctl.py run search_symbols '{"query": "ESP32"}'

# Execute a multi-step batch recipe
python3 kicad_ctl.py batch recipe.json
```

### 2. Headless DRC
```bash
python3 drc_check.py board.kicad_pcb --strict
```
Returns exit code 0 if 100% clean, or outputs categorized violations with reference designators and locations.

### 2. Export JLCPCB Fabrication ZIP
```bash
python3 export_jlcpcb.py board.kicad_pcb [--schematic board.kicad_sch]
```
Produces:
- `jlcpcb_production/gerber/` containing RS-274X Gerbers and Excellon drill files
- `jlcpcb_production/board_cpl_jlcpcb.csv` (JLCPCB-formatted Pick and Place)
- `jlcpcb_production/board_bom_jlcpcb.csv` (JLCPCB-formatted BOM)
- `jlcpcb_production/board_gerber_jlcpcb.zip` (Ready to upload to JLCPCB)
- Runs automated drill census and outline checks.

### 3. Autorouting Loop
```bash
# Export Specctra DSN
python3 route_kicad.py export board.kicad_pcb board.dsn --config route.json

# (Run your router, e.g. FreeRouting, producing board.ses)

# Import SES back into KiCad PCB
python3 route_kicad.py import board.kicad_pcb board.ses -o routed.kicad_pcb --strip
```

All scripts self-test:
```bash
for f in *.py; do python3 "$f" --selftest; done
```
