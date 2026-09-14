# PCB Agent Skill

Autonomous, end-to-end PCB design, schematic capture, layout, routing, verification, and manufacturing exporter for AI coding agents (**Antigravity**, **Claude Code**, **Codex**).

Drives **KiCad 9** natively via headless command-line interfaces (`kicad-cli`), Python bindings (`pcbnew`), and direct S-expression manipulation.

---

## 1. Core Principles

1. **性价比 (Cost-Effectiveness)**: Every component is matched against real-world LCSC/JLCPCB catalog availability and pricing, netted against inventory on hand.
2. **好装配 (Hand & SMT Assemblable)**: Geometrically verified pad reachability, component orientation validation, and collision-free clearance zones.
3. **零缺陷 (Zero-Error Manufacturing Yield)**: Strict gates requiring **0 DRC errors, 0 warnings, and 0 unconnected nets** before exporting fabrication-ready packages.

---

## 2. Key Features & Architecture

* **Unified KiCad Automation Controller ([`kicad_ctl.py`](scripts/kicad/kicad_ctl.py))**:
  * 233 programmatic automation commands spanning schematics, footprints, routing, placement, netlists, and DRC checks.
  * Headless execution without requiring GUI interaction or display servers.

* **Connector Edge Orientation Engine ([`connector_rules.py`](scripts/kicad/core/connector_rules.py))**:
  * Eliminates backwards / reversed connector placement bugs.
  * Resolves KiCad library coordinate disparities where default 0° mating faces vary (USB Type-C points South $+Y$, 3.5mm Audio Jacks point West $-X$).
  * Enforces exact outward edge rotation angles across any board edge ($W=270^\circ$, $E=90^\circ$ for USB-C; $E=180^\circ$, $W=0^\circ$ for Audio Jacks).

* **Pre-Flight Placement & Clearance Validator ([`placement_validator.py`](scripts/kicad/core/placement_validator.py))**:
  * Replaces slow, iterative DRC trial-and-error with $<100\,\text{ms}$ mathematical pre-flight validation.
  * Audits true IPC courtyard polygon collisions (`F.CrtYd` / `B.CrtYd`), connector edge alignments, and $\ge 0.5\,\text{mm}$ board-edge clearances.
  * Seamlessly integrated into `scripts/kicad/drc_check.py` and `kicad_ctl.py audit-placement`.

* **Deterministic 2-Layer Router ([`autoroute_2layer.py`](scripts/kicad/autoroute_2layer.py))**:
  * Programmatic 2-layer layout builder enforcing the **5 Golden Rules**:
    1. Solid unbroken bottom ground plane (`B.Cu`).
    2. Dedicated local SMD GND via stubs straight to ground plane.
    3. Decoupled orthogonal routing (Top horizontal, Bottom short vertical jumpers).
    4. Outer margin power distribution trunks.
    5. Pin header column segregation (no diagonal crossing).
  * Built-in keepout rule area generator with explicit KiCad 9 permission flag handling.
  * Pad-level thermal relief spoke control (`ZONE_CONNECTION_FULL`) to prevent `starved_thermal` violations.

* **Hardened KiCad 9 Headless Engine**:
  * **Rule Area Permission Safety**: Prevents default blocking of tracks/vias when adding copper-pour keepouts.
  * **SWIG Iterator Guarding**: Protects against C++ pointer invalidation crashes during track deletion.
  * **Zone Island Topology Diagnostics**: Programmatic contour scanning via `zone.GetFilledPolysList()` to locate and bridge isolated ground flood islands.
  * **Rotated Pad Geometry Clearances**: Anisotropic clearance evaluations accounting for $90^\circ / 270^\circ$ orientation swaps.

* **1-Command JLCPCB Fabrication Exporter ([`export_jlcpcb.py`](scripts/kicad/export_jlcpcb.py))**:
  * RS-274X Gerbers (no X2, subtract soldermask, drill origin, 6-decimal precision).
  * Excellon drill files (separate PTH/NPTH, metric decimal).
  * JLCPCB-formatted CPL / Pick-and-Place centroid file.
  * LCSC catalog-matched Bill of Materials (BOM).
  * Photorealistic top and bottom 3D raytraced preview renders.
  * Production ZIP archive ready for 1-click ordering.
  * Independent drill census and board outline verification checkers.

---

## 3. Four-Phase Workflow Pipeline

| Phase | Output Deliverables | Gate Requirement |
| :--- | :--- | :--- |
| **1. Concept** | Functional specifications, pinout table, mechanical constraints | User confirms all physical and electrical trade-offs |
| **2. Schematic & Sourcing** | Validated `.kicad_sch`, embedded library symbols, priced BOM | `kicad-cli sch erc` passes clean; all nets asserted |
| **3. Layout & Routing** | Placed, routed, and poured `.kicad_pcb` | `kicad-cli pcb drc` **0 errors / 0 unconnected items** |
| **4. Fabrication** | Gerber archive, CPL, BOM, 3D renders in `jlcpcb_production/` | Independent verification scripts pass; package census clean |

---

## 4. Repository Structure

```
pcb-skill/
├── scripts/
│   ├── kicad/               # KiCad controller, 2-layer router, cleanup engine, JLCPCB exporter
│   ├── placement/           # Footprint courtyards, keepout checkers, clearance analysis
│   ├── routing/             # DSN/SES router runners, watchdog monitors
│   ├── verify/              # Netlist assertions, Gerber parser, drill census
│   └── run_all_tests.py     # 20-check automated regression test suite
├── skills/
│   └── pcb/
│       ├── SKILL.md         # Agent skill manifest & instruction prompt
│       └── references/      # Workflow rules, review protocols, JLC limits, bringup guides
├── docs/                    # Architecture documentation & case studies
├── setup/                   # Setup guides for KiCad, headless CLI, and browser integration
└── README.md
```

---

## 5. Automated Verification

Run the full headless test suite:

```bash
python3 scripts/run_all_tests.py
```

Validates toolchain availability, command dispatchers, board cleanup, router SES integration, DRC parsing, schematic symbol embedding, and live THT / SMT project rule checks.

---

## 6. Acknowledgments & Lineage

This skill builds upon, extends, and synthesizes concepts from two foundational open-source projects:

1. **[`daishuge/pcb-skill`](https://github.com/daishuge/pcb-skill)**:
   * Originator of the agentic hardware design workflow, real-world gating protocols, adversarial review methodology, and sourcing automation principles.
2. **[`mixelpixx/KiCAD-MCP-Server`](https://github.com/mixelpixx/KiCAD-MCP-Server)**:
   * Pioneer in programmatic KiCad automation, headless command dispatch architecture, and Model Context Protocol (MCP) tooling for computer-aided PCB design.

---

## 7. License

MIT License. See [LICENSE](LICENSE) for details.
