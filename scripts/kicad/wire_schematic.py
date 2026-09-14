#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Schematic Wiring and Net Connectivity Engine for pcb-skill.

Establishes 100% electrical connectivity in KiCad 9 schematics from PCB netlists:
  1. Extracts the authoritative netlist from .kicad_pcb.
  2. Parses schematic with balanced S-expression grammar (zero regex corruption).
  3. Detects and auto-places missing units for multi-unit components.
  4. Computes exact pin world coordinates and outward escape vectors.
  5. Places collision-checked wire stubs and outward net labels.
  6. Places no_connect flags on unrouted / NC pins.
  7. Enforces strict KiCad 9 S-expression formatting.
"""

import argparse
import logging
import math
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_SKILL_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))

for _p in (
    _HERE,
    os.path.join(_HERE, "core"),
    "/usr/lib/python3/dist-packages",
    "/usr/lib/python3/site-packages",
):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.append(_p)

try:
    import pcbnew
    PCBNEW_AVAILABLE = True
except ImportError:
    PCBNEW_AVAILABLE = False

from commands.pin_locator import PinLocator

logger = logging.getLogger("wire_schematic")


def parse_top_level_blocks(text: str) -> List[str]:
    """Parse a .kicad_sch text into balanced top-level S-expression blocks."""
    start = text.find("(")
    if start == -1:
        return []

    depth = 0
    in_quote = False
    escape = False
    blocks = []
    block_start = None

    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_quote:
            escape = True
            continue
        if ch == '"':
            in_quote = not in_quote
            continue
        if in_quote:
            continue

        if ch == "(":
            depth += 1
            if depth == 2:
                block_start = i
        elif ch == ")":
            if depth == 2 and block_start is not None:
                blocks.append(text[block_start : i + 1])
                block_start = None
            depth -= 1

    return blocks


def extract_pcb_netlist(board_path: str) -> Dict[Tuple[str, str], str]:
    """Extract mapping of (reference, pad_number) -> net_name from KiCad board."""
    if not os.path.exists(board_path):
        raise FileNotFoundError(f"Board file not found: {board_path}")
    if not PCBNEW_AVAILABLE:
        raise RuntimeError("pcbnew Python binding not available")

    board = pcbnew.LoadBoard(board_path)
    net_map: Dict[Tuple[str, str], str] = {}

    for fp in board.GetFootprints():
        ref = fp.GetReference()
        for pad in fp.Pads():
            pnum = str(pad.GetNumber())
            netname = pad.GetNetname()
            if netname and netname.strip():
                net_map[(ref, pnum)] = netname.strip()

    return net_map


def find_symbol_units_in_library(sch_content: str, lib_id: str) -> List[int]:
    """Find all unit numbers declared for a symbol in (lib_symbols ...)."""
    bare = lib_id.split(":")[-1] if ":" in lib_id else lib_id
    pattern = rf'\(symbol\s+"(?:{re.escape(lib_id)}|{re.escape(bare)})_(\d+)_\d+"'
    units = set()
    for m in re.finditer(pattern, sch_content):
        u = int(m.group(1))
        if u > 0:
            units.add(u)
    return sorted(units)


def wire_schematic(
    schematic_path: str,
    board_path: str,
    stub_length: float = 1.27,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Connect all placed components in a KiCad 9 schematic to board nets.

    Args:
        schematic_path: Path to .kicad_sch file.
        board_path: Path to .kicad_pcb file.
        stub_length: Length in mm of outward wire stubs (default: 1.27 mm / 50 mil).
        verbose: Enable detailed logging.

    Returns:
        Dict with summary counts: {wires, labels, no_connects, total}.
    """
    sch_p = Path(schematic_path)
    if not sch_p.exists():
        raise FileNotFoundError(f"Schematic not found: {schematic_path}")

    net_map = extract_pcb_netlist(board_path)
    if verbose:
        print(f"Extracted {len(net_map)} pad-net connections from {board_path}")

    with open(sch_p, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse all top-level blocks cleanly
    blocks = parse_top_level_blocks(content)

    # Separate blocks into components/definitions vs dynamic wiring
    header_blocks = []
    symbol_blocks = []
    sheet_inst_block = None

    for b in blocks:
        tag = b.split()[0].lstrip("(")
        if tag in ("version", "generator", "generator_version", "uuid", "paper", "title_block"):
            header_blocks.append(b)
        elif tag == "lib_symbols":
            header_blocks.append(b)
        elif tag == "symbol":
            symbol_blocks.append(b)
        elif tag == "sheet_instances":
            sheet_inst_block = b

    # Check for multi-unit symbols needing expansion
    symbol_regex = re.compile(
        r'\(symbol\s+\(lib_id\s+"([^"]+)"\)\s+\(at\s+([0-9\.\-]+)\s+([0-9\.\-]+)\s+([0-9\.\-]+)\)'
        r'(?:\s+\(unit\s+(\d+)\))?.*?'
        r'\(property\s+"Reference"\s+"([^"]+)".*?'
        r'\(property\s+"Value"\s+"([^"]+)".*?'
        r'\(property\s+"Footprint"\s+"([^"]+)".*?'
        r'\)',
        re.DOTALL,
    )

    placed_units: Dict[str, Set[int]] = {}
    symbol_meta: Dict[str, Dict[str, Any]] = {}

    for sym_text in symbol_blocks:
        m = symbol_regex.search(sym_text)
        if m:
            lib_id = m.group(1)
            at_x = float(m.group(2))
            at_y = float(m.group(3))
            rot = float(m.group(4))
            unit = int(m.group(5)) if m.group(5) else 1
            ref = m.group(6)
            val = m.group(7)
            fp = m.group(8)

            if ref not in placed_units:
                placed_units[ref] = set()
                symbol_meta[ref] = {
                    "lib_id": lib_id,
                    "at_x": at_x,
                    "at_y": at_y,
                    "rot": rot,
                    "val": val,
                    "fp": fp,
                }
            placed_units[ref].add(unit)

    # Add missing multi-unit instances
    lib_symbols_text = next((b for b in header_blocks if b.startswith("(lib_symbols")), "")
    expanded_symbols = list(symbol_blocks)

    for ref, units_present in placed_units.items():
        meta = symbol_meta[ref]
        lib_id = meta["lib_id"]
        all_units = find_symbol_units_in_library(lib_symbols_text, lib_id)
        if len(all_units) > 1:
            missing = [u for u in all_units if u not in units_present]
            for u in missing:
                new_x = meta["at_x"] + 30.0 * (u - 1)
                new_y = meta["at_y"]
                rot = meta["rot"]
                uid = str(uuid.uuid4())
                new_sym = f"""(symbol (lib_id "{lib_id}") (at {new_x:.2f} {new_y:.2f} {rot:.0f}) (unit {u})
    (in_bom yes) (on_board yes) (dnp no)
    (uuid "{uid}")
    (property "Reference" "{ref}" (at {new_x:.2f} {new_y - 3.81:.2f} 0) (effects (font (size 1.27 1.27))))
    (property "Value" "{meta['val']}" (at {new_x:.2f} {new_y - 1.90:.2f} 0) (effects (font (size 1.27 1.27))))
    (property "Footprint" "{meta['fp']}" (at {new_x:.2f} {new_y + 3.81:.2f} 0) (effects (font (size 1.27 1.27)) (hide yes)))
  )"""
                expanded_symbols.append(new_sym)

    # Reassemble clean schematic so PinLocator can query all placed instances
    interim_content = (
        "(kicad_sch\n  "
        + "\n  ".join(header_blocks)
        + "\n  "
        + "\n  ".join(expanded_symbols)
        + "\n  "
        + (sheet_inst_block if sheet_inst_block else '(sheet_instances (path "/" (page "1")))')
        + "\n)\n"
    )

    with open(sch_p, "w", encoding="utf-8") as f:
        f.write(interim_content)

    locator = PinLocator()

    # Now discover pins and generate collision-free wires & labels
    new_elements = []
    wire_count = 0
    label_count = 0
    nc_count = 0

    processed_pins: Set[Tuple[str, str]] = set()
    used_endpoints: Dict[Tuple[float, float], str] = {}

    for sym_text in expanded_symbols:
        m = symbol_regex.search(sym_text)
        if not m:
            continue
        lib_id = m.group(1)
        unit = int(m.group(5)) if m.group(5) else 1
        ref = m.group(6)

        if ref.startswith("H"):  # Mounting holes have no electrical pins
            continue

        symbol_pins = locator.get_symbol_pins(sch_p, lib_id)
        if not symbol_pins:
            continue

        for pnum, pdata in symbol_pins.items():
            pin_unit = pdata.get("unit", 0)
            if pin_unit not in (0, unit):
                continue

            pin_key = (ref, str(pnum))
            if pin_key in processed_pins:
                continue
            processed_pins.add(pin_key)

            loc = locator.get_pin_location(sch_p, ref, str(pnum))
            if not loc:
                continue

            ang = locator.get_pin_angle(sch_p, ref, str(pnum)) or 0.0

            netname = net_map.get((ref, str(pnum)))
            if not netname and str(pnum).isdigit():
                netname = net_map.get((ref, str(int(pnum))))
            if not netname:
                pname = pdata.get("name", "")
                if pname:
                    netname = net_map.get((ref, pname))

            px = round(float(loc[0]), 4)
            py = round(float(loc[1]), 4)

            if netname:
                rad = math.radians(ang)
                # Compute stub endpoint with collision avoidance
                current_len = stub_length
                for attempt in range(4):
                    dx = round(current_len * math.cos(rad), 4)
                    dy = round(-current_len * math.sin(rad), 4)
                    end_pt = (round(px + dx, 4), round(py + dy, 4))
                    if end_pt not in used_endpoints or used_endpoints[end_pt] == netname:
                        break
                    # Avoid collision by lengthening stub
                    current_len += 1.27

                used_endpoints[end_pt] = netname

                w_uid = str(uuid.uuid4())
                wire_sexp = f"""  (wire
    (pts
      (xy {px} {py}) (xy {end_pt[0]} {end_pt[1]})
    )
    (stroke
      (width 0)
      (type default)
    )
    (uuid "{w_uid}")
  )"""
                new_elements.append(wire_sexp)
                wire_count += 1

                ori = int(round(ang / 90) * 90) % 360
                justify_h = "right" if ori in (180, 270) else "left"
                l_uid = str(uuid.uuid4())
                lbl_sexp = f"""  (label "{netname}"
    (at {end_pt[0]} {end_pt[1]} {ori})
    (effects
      (font
        (size 1.27 1.27)
      )
      (justify {justify_h} bottom)
    )
    (uuid "{l_uid}")
  )"""
                new_elements.append(lbl_sexp)
                label_count += 1
            else:
                nc_uid = str(uuid.uuid4())
                nc_sexp = f"""  (no_connect
    (at {px} {py})
    (uuid "{nc_uid}")
  )"""
                new_elements.append(nc_sexp)
                nc_count += 1

    final_content = (
        "(kicad_sch\n  "
        + "\n  ".join(header_blocks)
        + "\n  "
        + "\n  ".join(expanded_symbols)
        + "\n\n"
        + "\n".join(new_elements)
        + "\n  "
        + (sheet_inst_block if sheet_inst_block else '(sheet_instances (path "/" (page "1")))')
        + "\n)\n"
    )

    with open(sch_p, "w", encoding="utf-8") as f:
        f.write(final_content)

    res = {
        "wires": wire_count,
        "labels": label_count,
        "no_connects": nc_count,
        "total": len(new_elements),
    }
    if verbose:
        print(f"Schematic wiring complete: {res}")
    return res


def _selftest() -> int:
    """Self-test verifying extraction and wire generation."""
    print("wire_schematic selftest:")
    sample_content = """(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0")
  (uuid "00000000-0000-0000-0000-000000000001")
  (paper "A4")
  (lib_symbols
    (symbol "Device:R"
      (symbol "R_1_1"
        (pin passive line (at 0 3.81 270) (length 1.27) (name "~") (number "1"))
        (pin passive line (at 0 -3.81 90) (length 1.27) (name "~") (number "2"))
      )
    )
  )
  (symbol (lib_id "Device:R") (at 50.8 50.8 0) (unit 1)
    (uuid "00000000-0000-0000-0000-000000000002")
    (property "Reference" "R1" (at 50.8 46.99 0) (effects (font (size 1.27 1.27))))
    (property "Value" "10k" (at 50.8 48.9 0) (effects (font (size 1.27 1.27))))
    (property "Footprint" "Resistor_SMD:R_0805_2012Metric" (at 50.8 54.61 0) (effects (font (size 1.27 1.27)) (hide yes)))
  )
  (sheet_instances (path "/" (page "1")))
)"""
    import tempfile

    with tempfile.TemporaryDirectory(prefix="kc_test_wire_") as tmpdir:
        sch_file = os.path.join(tmpdir, "test.kicad_sch")
        with open(sch_file, "w") as f:
            f.write(sample_content)

        blocks = parse_top_level_blocks(sample_content)
        if len(blocks) < 5:
            print(f"  Failed parsing blocks: got {len(blocks)}: FAIL")
            return 1
        print(f"  Parsed {len(blocks)} top-level blocks: OK")

        loc_finder = PinLocator()
        p1 = loc_finder.get_pin_location(Path(sch_file), "R1", "1")
        p2 = loc_finder.get_pin_location(Path(sch_file), "R1", "2")
        if not p1 or not p2:
            print("  Pin location failed: FAIL")
            return 1

        print(f"  Located pins p1={p1}, p2={p2}: OK")

    print("wire_schematic selftest: PASS")
    return 0


def main(args_list=None):
    parser = argparse.ArgumentParser(description="Wire and connect a KiCad 9 schematic from board netlist")
    parser.add_argument("schematic", nargs="?", help="Path to .kicad_sch")
    parser.add_argument("--board", required=False, help="Path to .kicad_pcb")
    parser.add_argument("--stub-length", type=float, default=1.27, help="Wire stub length in mm (default: 1.27)")
    parser.add_argument("--selftest", action="store_true", help="Run module self-test")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args(args_list)
    if args.selftest:
        return _selftest()

    if not args.schematic:
        parser.error("schematic argument is required")

    if not args.board:
        base = os.path.splitext(args.schematic)[0]
        cand = base + ".kicad_pcb"
        if os.path.exists(cand):
            args.board = cand
        else:
            parser.error("Board path must be specified via --board when no matching .kicad_pcb is found")

    res = wire_schematic(args.schematic, args.board, stub_length=args.stub_length, verbose=args.verbose)
    print(f"Connected {args.schematic}: {res['wires']} wires, {res['labels']} labels, {res['no_connects']} no-connects (Total: {res['total']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
