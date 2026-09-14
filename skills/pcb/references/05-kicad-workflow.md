# 05 — Driving KiCad: Automation, CLI, and Scripting Guide

How an AI agent drives **KiCad (v7, v8, v9)** reliably from the command line, Python,
and direct file generation — without flaky browser extensions or opaque electron IPC.

KiCad is open, transparent, and completely file-based:
- Schematics: `.kicad_sch` (human-readable S-expressions)
- PCB layout: `.kicad_pcb` (human-readable S-expressions)
- Project config: `.kicad_pro` (JSON)
- Headless CLI: `kicad-cli`
- Python API: `pcbnew`

---

## 1. The Headless Toolkit: `kicad-cli`

KiCad ships with a first-class CLI (`kicad-cli`). Never require a human to click GUI buttons
for checks, exports, or conversions that the CLI does in half a second.

### Electrical Rules Check (ERC)
```bash
kicad-cli sch erc --format json -o erc_report.json project.kicad_sch
```
Outputs machine-readable JSON containing pin-to-pin conflicts, unconnected pins, and missing power flags.

### Design Rules Check (DRC)
```bash
# Direct runner with parsed diagnostic output:
python3 scripts/kicad/drc_check.py project.kicad_pcb --strict

# Or via unified controller:
python3 scripts/kicad/kicad_ctl.py drc project.kicad_pcb --strict
```
Checks clearances, annular rings, track widths, dangling tracks, unrouted nets, and schematic parity.

### Fabrication Outputs (Gerber, Drill, CPL, BOM, 3D Renders)
Use the automated wrapper that handles JLCPCB production packaging:
```bash
python3 scripts/kicad/export_jlcpcb.py project.kicad_pcb [--schematic project.kicad_sch]
# Or:
python3 scripts/kicad/kicad_ctl.py export-jlcpcb project.kicad_pcb
```
This automatically produces:
1. RS-274X Gerbers (no X2, subtract soldermask, drill origin, 6 decimal precision).
2. Excellon drill files (separate PTH/NPTH, metric, decimal format).
3. SMT Pick & Place (CPL) with normalized JLCPCB column headers (`Designator,Val,Package,Mid X,Mid Y,Rotation,Layer`).
4. BOM with fuzzy LCSC part catalog matching (fallback to direct PCB footprint extraction if schematic is absent).
5. 3D photorealistic raytraced preview renders (`render_top.png` and `render_bottom.png`).
6. Verified ZIP archive ready for 1-click drag-and-drop into JLCPCB order portal.

---

## 2. Complete Automation Controller: `kicad_ctl.py`

For deep programmatic control over schematics, placement, routing, and libraries, the skill provides
[`scripts/kicad/kicad_ctl.py`](file:///home/azzar/.agents/skills/pcb/scripts/kicad/kicad_ctl.py), exposing **233 automation commands** directly:

### Command Categories
```bash
# List all 233 commands
python3 scripts/kicad/kicad_ctl.py list-commands

# List commands by category (project, board, schematic, placement, routing, library, jlcpcb, export, rules)
python3 scripts/kicad/kicad_ctl.py list-commands --category schematic
python3 scripts/kicad/kicad_ctl.py list-commands --category placement
python3 scripts/kicad/kicad_ctl.py list-commands --category routing

# Inspect command documentation and parameters
python3 scripts/kicad/kicad_ctl.py doc batch_add_components
python3 scripts/kicad/kicad_ctl.py doc hierarchical_place
```

### Direct Execution Examples
```bash
# Search symbols in local KiCad libraries:
python3 scripts/kicad/kicad_ctl.py run search_symbols '{"query": "ESP32"}'

# Search JLCPCB parts catalog:
python3 scripts/kicad/kicad_ctl.py run search_jlcpcb_parts '{"query": "CH340C", "basic_only": true}'

# Place components:
python3 scripts/kicad/kicad_ctl.py run place_component '{"reference": "R1", "x": 100, "y": 100, "layer": "F.Cu"}'

# Align components geometrically:
python3 scripts/kicad/kicad_ctl.py run align_components '{"references": ["C1", "C2", "C3"], "alignment": "horizontal", "spacing": 5.0}'

# Refill copper zones safely:
python3 scripts/kicad/kicad_ctl.py refill-zones project.kicad_pcb
```

---

## 3. The 5 Golden Rules of Zero-Error 2-Layer PCB Design

2-layer PCB designs fail when agents treat top and bottom copper as symmetric scratchpads.
To guarantee 100% DRC clean, high-signal-integrity, production-ready boards:

1. **Rule 1: Solid B.Cu Ground Plane**
   - Dedicate the entire bottom layer (`B.Cu`) to a continuous, unbroken copper ground plane.
   - Never run long horizontal signal traces across `B.Cu` that slice the ground plane in half.

2. **Rule 2: Dedicated SMD GND Via Stubs**
   - Every surface-mount GND pad MUST receive an immediate local via (offset ~1.5mm) dropping straight into the `B.Cu` ground plane.
   - Never daisy-chain GND tracks between SMD components on the top layer (`F.Cu`).

3. **Rule 3: Decoupled Orthogonal Routing**
   - Top layer (`F.Cu`): Horizontal and local point-to-point signal routing.
   - Bottom layer (`B.Cu`): Short vertical jumper segments only when two top-layer signals intersect.

4. **Rule 4: Outer Margin Power Distribution**
   - Primary power trunks (e.g. `+5V` or `+3V3`) run along the perimeter/margins of the board (width 0.35–0.50mm).
   - Use perpendicular drop-stubs to IC VCC pins and decoupling capacitors.

5. **Rule 5: 2xN Pin Header Column Segregation**
   - When routing to double-row pin headers (e.g. 2x3 AVR-ISP, 2x5 SWD):
     - Column 1 pins (pins 1, 3, 5...) must escape strictly towards the outer left margin.
     - Column 2 pins (pins 2, 4, 6...) must escape strictly towards the outer right margin.
     - Never cross a track from column 1 diagonally between pads of column 2.

---

## 4. Deterministic 2-Layer Layout Engine: `autoroute_2layer.py`

[`scripts/kicad/autoroute_2layer.py`](file:///home/azzar/.agents/skills/pcb/scripts/kicad/autoroute_2layer.py) provides a high-level, fluent Python builder implementing all 5 Golden Rules:

```python
from autoroute_2layer import PCB2LayerBuilder

# 1. Initialize 50x50mm board with chamfered corners and JLCPCB rules
builder = PCB2LayerBuilder(50.0, 50.0, chamfer_mm=2.0)
builder.setup_jlcpcb_rules(track_default=0.25)

# 2. Register nets
builder.add_nets(["GND", "+5V", "SIG_PULSE", "RESET"])

# 3. Add 4-corner mounting holes (M3)
builder.add_mounting_holes(margin=4.0)

# 4. Place footprints
u1 = builder.add_footprint("Package_SO.pretty", "SOIC-8_3.9x4.9mm_P1.27mm", "U1", "NE555D", 22.0, 20.0)
u2 = builder.add_footprint("Package_SO.pretty", "SOIC-8_3.9x4.9mm_P1.27mm", "U2", "ATtiny85", 37.0, 26.0)

# 5. Bind nets to pads
builder.bind_pad("U1", "1", "GND")
builder.bind_pad("U1", "8", "+5V")

# 6. Apply Golden Rule 2: Dedicated local GND via stub
builder.connect_smd_gnd_stub("U1", "1", offset_x=0.0, offset_y=-1.5)

# 7. Route orthogonal tracks
builder.add_polyline([(22.0, 25.0), (30.0, 25.0), (30.0, 30.0)], "SIG_PULSE", width_mm=0.25, layer="F.Cu")

# 8. Add solid B.Cu ground plane & safe refill
builder.add_ground_plane(layer="B.Cu", net="GND", margin_mm=1.0)
builder.save_and_fill("my_project.kicad_pcb")
```

---

## 5. Critical KiCad 9 SWIG API Nuances & Fixes

When scripting `pcbnew` in Python:

1. **Safe Zone Refill (`ZONE_FILLER`)**:
   `ZONE_FILLER.Fill()` in KiCad 9 requires a `pcbnew.ZONES()` vector proxy, NOT a Python tuple from `board.Zones()`.
   Furthermore, filling an uncommitted in-memory board can segfault. Always use the Save/Load subprocess pattern:
   ```python
   pcbnew.SaveBoard(path, board)
   board = pcbnew.LoadBoard(path)
   zones = pcbnew.ZONES()
   for z in board.Zones():
       zones.push_back(z)
   filler = pcbnew.ZONE_FILLER(board)
   filler.Fill(zones)
   pcbnew.SaveBoard(path, board)
   ```

2. **Via Width across Padstacks (`PCB_VIA`)**:
   KiCad 9 migrated vias to multi-layer padstacks. Calling `via.SetWidth(width)` without layer arguments emits an assertion warning.
   Use the layer-pair overload:
   ```python
   via.SetWidth(pcbnew.F_Cu, mm(0.6))
   via.SetWidth(pcbnew.B_Cu, mm(0.6))
   ```

3. **Plated Through-Hole (PTH) Pads Connect All Layers**:
   Never place a via on top of a PTH pin-header pad. PTH pads inherently connect `F.Cu` and `B.Cu` through their copper plating barrel.

4. **Rule Area / Keepout Default Flags Trap (`SetIsRuleArea`)**:
   In KiCad 9, calling `zone.SetIsRuleArea(True)` sets `SetDoNotAllowTracks(True)`, `SetDoNotAllowVias(True)`, and `SetDoNotAllowPads(True)` by default, while leaving `SetDoNotAllowCopperPour(False)`!
   If intending to block copper pour only (e.g. under an RF antenna, crystal, or USB-C connector), you MUST explicitly configure all four flags:
   ```python
   kz = pcbnew.ZONE(board)
   kz.SetLayer(pcbnew.F_Cu)
   kz.SetIsRuleArea(True)
   kz.SetDoNotAllowCopperPour(True)   # Must explicitly ENABLE
   kz.SetDoNotAllowTracks(False)       # Must explicitly DISABLE default block
   kz.SetDoNotAllowVias(False)         # Must explicitly DISABLE default block
   kz.SetDoNotAllowPads(False)         # Must explicitly DISABLE default block
   ```
   Failing to set these causes dozens of spurious `items_not_allowed` DRC violations.

5. **SWIG Iterator Invalidation on Track / Item Removal (`board.Remove`)**:
   Calling `board.Remove(item)` while iterating or immediately re-calling `board.GetTracks()` can corrupt the SWIG C++ iterator and crash with `TypeError: 'SwigPyObject' object is not iterable`.
   **Fix**: Always snapshot references into a Python `list()` before any removals:
   ```python
   all_tracks = list(board.GetTracks())
   for t in all_tracks:
       if should_remove(t):
           board.Remove(t)
   # Do not re-iterate board.GetTracks() in the same loop without a fresh snapshot
   ```

6. **Ground Plane Island Topology & "Zone [GND] Unconnected" DRC**:
   KiCad flags `Missing connection between items: Zone [GND] on F.Cu vs Zone [GND] on B.Cu` at `(1.0, 1.0)`.
   *Note: `(1.0, 1.0)` is NOT the fault location — it is simply the zone's polygon origin!*
   **Root Cause**: Dense signal tracks (e.g. parallel button buses or data lines) sever the copper flood into isolated sub-islands. If any sub-polygon on `F.Cu` or `B.Cu` has no via/PTH connecting it to the main connectivity tree, KiCad flags the whole zone object as unconnected.
   **Programmatic Diagnosis**:
   ```python
   ps = zone.GetFilledPolysList(zone.GetLayer())
   for i in range(ps.OutlineCount()):
       poly = pcbnew.SHAPE_POLY_SET()
       poly.AddOutline(ps.Outline(i))
       # Check if any through-hole via or PTH pad lies inside poly.Contains(pt)
   ```
   **Fix**: Place a stitching via at the geometric intersection where the isolated island overlaps the opposite-layer ground plane.

7. **Rotated SMD Pad Geometry in Clearance Calculations**:
   `pad.GetSize()` returns dimensions in footprint local space. If `pad.GetOrientation().AsDegrees() == 90` or `270`, the width and height swap in board global space!
   A pad of size `0.85 x 0.30 mm` at 90° extends `0.15 mm` in X and `0.425 mm` in Y.
   Clearance calculations must evaluate the rotated global bounding box plus solder mask expansion ($0.05\,\text{mm}$) to avoid `clearance` and `solder_mask_bridge` violations.

8. **Thermal Relief Spoke Starvation (`starved_thermal`)**:
   When KiCad project rules enforce `"starved_thermal": "error"` (requiring $\ge 2$ spokes), SMD passive GND pads placed near board edges or keepouts often get only 1 spoke.
   **Fix**: For SMD passives where hand soldering or standard reflow is used, configure solid zone connection on that specific pad:
   ```python
   pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
   ```
   Then trigger `ZONE_FILLER.Fill(zones)`.

9. **DRC Runner Rule Parity**:
   Running `kicad-cli pcb drc` on a standalone `.kicad_pcb` in `/tmp` uses KiCad default rules. Running it in the project directory with `.kicad_pro` present evaluates custom project rules (such as `starved_thermal` or netclass clearance overrides).
   Always run DRC in the project directory with the matching `.kicad_pro` present to catch project-level constraints early.

---

## 6. End-to-End Headless Verification Pipeline

Always verify the final design through the automated verification suite:

```bash
# 1. Run headless DRC (must be 0 errors, 0 unconnected items)
python3 scripts/kicad/drc_check.py project.kicad_pcb --strict

# 2. Export complete JLCPCB package (Gerbers, Drills, CPL, BOM, 3D Renders, ZIP)
python3 scripts/kicad/export_jlcpcb.py project.kicad_pcb

# 3. Check drill census and outline
python3 scripts/verify/drill_census.py project/jlcpcb_production/gerber/*.drl
python3 scripts/verify/outline_check.py project/jlcpcb_production/gerber/*Edge_Cuts*
```
All outputs are verified independently of the GUI before proceeding to fabrication.
