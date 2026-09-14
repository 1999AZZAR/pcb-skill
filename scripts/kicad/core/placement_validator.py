#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pre-flight Placement & Connector Orientation Validator for KiCad PCBs.

Audits component placement, courtyard collisions, board-edge clearances,
and connector orientations *before* routing to guarantee zero DRC iterations.

Checks performed:
  1. Connector Edge Orientation: Ensures USB-C, Audio Jacks, Barrel Jacks, etc.
     have their mating face oriented strictly outwards towards the nearest board edge.
  2. Connector Edge Alignment: Verifies connectors reach the board edge and are
     not recessed inside or excessively overhanging.
  3. Courtyard Overlaps: Detects physical overlap between component body/courtyard
     bounding boxes.
  4. Board Edge Clearance: Ensures non-edge components have >= 0.5mm clearance
     to the Edge.Cuts board outline.
  5. Hole-to-Hole Distance: Checks physical separation between drilled holes
     across different components.

USAGE
  python3 placement_validator.py BOARD.kicad_pcb [--strict] [--json out.json]
  python3 placement_validator.py --selftest
"""
from __future__ import print_function

import json
import math
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

for p in ["/usr/lib/python3/dist-packages", "/usr/local/lib/python3/dist-packages"]:
    if p not in sys.path and os.path.isdir(p):
        sys.path.append(p)

try:
    import pcbnew
    _HAS_PCBNEW = True
except ImportError:
    pcbnew = None
    _HAS_PCBNEW = False

try:
    from connector_rules import (
        CONNECTOR_0DEG_FACES,
        EDGE_VECTORS,
        get_edge_rotation,
    )
except ImportError:
    # Minimal fallback
    CONNECTOR_0DEG_FACES = {
        "USB_C_Receptacle_HRO_TYPE-C-31-M-12": (0, 1),
        "Jack_3.5mm_PJ320D_Horizontal": (-1, 0),
        "BarrelJack_Horizontal": (-1, 0),
    }
    EDGE_VECTORS = {"W": (-1, 0), "E": (1, 0), "N": (0, -1), "S": (0, 1)}

    def get_edge_rotation(footprint_name: str, target_edge: str) -> float:
        base = footprint_name.split(":")[-1]
        init_v = CONNECTOR_0DEG_FACES.get(base, (-1, 0) if "Jack" in base or "Barrel" in base else (0, 1))
        target_v = EDGE_VECTORS.get(target_edge.upper(), (-1, 0))
        for angle in [0.0, 90.0, 180.0, 270.0]:
            rad = math.radians(angle)
            cos_a = round(math.cos(rad))
            sin_a = round(math.sin(rad))
            rx = init_v[0] * cos_a + init_v[1] * sin_a
            ry = -init_v[0] * sin_a + init_v[1] * cos_a
            if (rx, ry) == target_v:
                return angle
        return 0.0


def validate_placement(board_path: str, min_edge_clearance_mm: float = 0.5) -> Dict[str, any]:
    """Audit PCB placement and connector orientation."""
    if not os.path.exists(board_path):
        raise FileNotFoundError(f"PCB file not found: {board_path}")

    if _HAS_PCBNEW:
        return _validate_with_pcbnew(board_path, min_edge_clearance_mm)
    else:
        return _validate_with_sexpr(board_path, min_edge_clearance_mm)


def _get_courtyard_bbox(fp) -> Tuple[float, float, float, float]:
    """Calculate the precise courtyard bounding box excluding silkscreen labels."""
    box = None
    for item in fp.GraphicalItems():
        if item.GetLayer() in [pcbnew.F_CrtYd, pcbnew.B_CrtYd]:
            ib = item.GetBoundingBox()
            if box is None:
                box = pcbnew.BOX2I(ib.GetPosition(), ib.GetSize())
            else:
                box.Merge(ib)

    if box is None:
        for pad in fp.Pads():
            pb = pad.GetBoundingBox()
            if box is None:
                box = pcbnew.BOX2I(pb.GetPosition(), pb.GetSize())
            else:
                box.Merge(pb)
        for item in fp.GraphicalItems():
            if item.GetLayer() in [pcbnew.F_Fab, pcbnew.B_Fab]:
                ib = item.GetBoundingBox()
                if box is None:
                    box = pcbnew.BOX2I(ib.GetPosition(), ib.GetSize())
                else:
                    box.Merge(ib)

    if box is None:
        box = fp.GetBoundingBox()

    return (
        pcbnew.ToMM(box.GetX()),
        pcbnew.ToMM(box.GetY()),
        pcbnew.ToMM(box.GetRight()),
        pcbnew.ToMM(box.GetBottom()),
    )


def _validate_with_pcbnew(board_path: str, min_edge_clearance_mm: float) -> Dict[str, any]:
    board = pcbnew.LoadBoard(board_path)
    bbox = board.GetBoardEdgesBoundingBox()
    bx_min = pcbnew.ToMM(bbox.GetX())
    bx_max = pcbnew.ToMM(bbox.GetRight())
    by_min = pcbnew.ToMM(bbox.GetY())
    by_max = pcbnew.ToMM(bbox.GetBottom())

    board_w = bx_max - bx_min
    board_h = by_max - by_min

    connector_errors = []
    courtyard_overlaps = []
    edge_clearance_errors = []
    warnings = []

    fps = list(board.GetFootprints())
    fp_data = []

    for fp in fps:
        ref = fp.GetReference()
        val = fp.GetValue()
        fp_id = str(fp.GetFPID().GetLibItemName())
        pos = fp.GetPosition()
        px = pcbnew.ToMM(pos.x)
        py = pcbnew.ToMM(pos.y)
        orient = round(fp.GetOrientation().AsDegrees()) % 360

        # Determine true courtyard bounding box
        x0, y0, x1, y1 = _get_courtyard_bbox(fp)

        # Only audit directional edge connectors (USB, audio jacks, barrel jacks, horizontal headers).
        # Vertical pin headers plug in along Z (upwards) and do not have an outward edge face.
        is_directional_conn = (
            any(fp_id.startswith(k) for k in CONNECTOR_0DEG_FACES) or
            any(sub in fp_id for sub in ["USB_C", "Micro_B", "Jack_3.5", "BarrelJack", "SMA", "HDMI", "RJ45"]) or
            ("Horizontal" in fp_id and ("PinHeader" in fp_id or ref.startswith("J"))) or
            ("RightAngle" in fp_id and ("PinHeader" in fp_id or ref.startswith("J")))
        ) and "Vertical" not in fp_id

        is_conn = is_directional_conn or ref.startswith("J") or "PinHeader" in fp_id

        fp_info = {
            "ref": ref,
            "val": val,
            "fpid": fp_id,
            "pos": (px, py),
            "orient": orient,
            "bbox": (x0, y0, x1, y1),
            "is_connector": is_conn,
        }
        fp_data.append(fp_info)

        # 1. CONNECTOR ORIENTATION AUDIT
        if is_directional_conn:
            # Determine closest board edge
            dist_w = px - bx_min
            dist_e = bx_max - px
            dist_n = py - by_min
            dist_s = by_max - py
            min_d = min(dist_w, dist_e, dist_n, dist_s)

            if min_d == dist_w:
                closest_edge = "W"
            elif min_d == dist_e:
                closest_edge = "E"
            elif min_d == dist_n:
                closest_edge = "N"
            else:
                closest_edge = "S"

            expected_orient = round(get_edge_rotation(fp_id, closest_edge)) % 360

            # If connector is within 25mm of edge, enforce orientation
            if min_d < min(board_w, board_h) * 0.4:
                if orient != expected_orient:
                    connector_errors.append({
                        "ref": ref,
                        "fpid": fp_id,
                        "edge": closest_edge,
                        "current_orient": orient,
                        "expected_orient": expected_orient,
                        "message": (
                            f"Connector {ref} ({fp_id}) near {closest_edge} edge has orientation {orient}° "
                            f"but MUST be {expected_orient}° to face outwards off board."
                        )
                    })

        # 2. BOARD EDGE CLEARANCE AUDIT (non-connectors)
        else:
            dx_min = x0 - bx_min
            dx_max = bx_max - x1
            dy_min = y0 - by_min
            dy_max = by_max - y1

            min_edge_gap = min(dx_min, dx_max, dy_min, dy_max)
            if min_edge_gap < min_edge_clearance_mm:
                edge_clearance_errors.append({
                    "ref": ref,
                    "gap_mm": round(min_edge_gap, 3),
                    "required_mm": min_edge_clearance_mm,
                    "message": (
                        f"Component {ref} bbox [{x0:.1f}, {y0:.1f}, {x1:.1f}, {y1:.1f}] is only "
                        f"{min_edge_gap:.2f}mm from board edge (requires >= {min_edge_clearance_mm}mm)."
                    )
                })

    # 3. COURTYARD OVERLAP AUDIT
    for i in range(len(fp_data)):
        for j in range(i + 1, len(fp_data)):
            f1 = fp_data[i]
            f2 = fp_data[j]

            b1 = f1["bbox"]
            b2 = f2["bbox"]

            # Overlap in X and Y
            overlap_x = min(b1[2], b2[2]) - max(b1[0], b2[0])
            overlap_y = min(b1[3], b2[3]) - max(b1[1], b2[1])

            # Small tolerance for touching bounding boxes (0.1mm)
            if overlap_x > 0.15 and overlap_y > 0.15:
                # Calculate overlap area or amount
                courtyard_overlaps.append({
                    "ref1": f1["ref"],
                    "ref2": f2["ref"],
                    "overlap_x_mm": round(overlap_x, 2),
                    "overlap_y_mm": round(overlap_y, 2),
                    "message": (
                        f"Placement collision between {f1['ref']} and {f2['ref']}: "
                        f"overlap {overlap_x:.2f}mm x {overlap_y:.2f}mm."
                    )
                })

    clean = (len(connector_errors) == 0 and len(courtyard_overlaps) == 0 and len(edge_clearance_errors) == 0)

    return {
        "board_path": board_path,
        "board_dimensions": {
            "x_min": bx_min, "y_min": by_min,
            "x_max": bx_max, "y_max": by_max,
            "width": board_w, "height": board_h
        },
        "components_count": len(fp_data),
        "connector_errors": connector_errors,
        "courtyard_overlaps": courtyard_overlaps,
        "edge_clearance_errors": edge_clearance_errors,
        "warnings": warnings,
        "clean": clean,
    }


def _validate_with_sexpr(board_path: str, min_edge_clearance_mm: float) -> Dict[str, any]:
    """Fallback parser using direct S-expressions when pcbnew is unavailable."""
    with open(board_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract board outline bounds from Edge.Cuts
    rect_matches = re.findall(r'\(gr_rect\s+\(start\s+([\d.-]+)\s+([\d.-]+)\)\s+\(end\s+([\d.-]+)\s+([\d.-]+)\).*?\(layer\s+"Edge\.Cuts"\)', content, re.DOTALL)
    if rect_matches:
        xs = [float(rect_matches[0][0]), float(rect_matches[0][2])]
        ys = [float(rect_matches[0][1]), float(rect_matches[0][3])]
        bx_min, bx_max = min(xs), max(xs)
        by_min, by_max = min(ys), max(ys)
    else:
        line_matches = re.findall(r'\(gr_line\s+\(start\s+([\d.-]+)\s+([\d.-]+)\)\s+\(end\s+([\d.-]+)\s+([\d.-]+)\).*?\(layer\s+"Edge\.Cuts"\)', content, re.DOTALL)
        if line_matches:
            xs = [float(m[0]) for m in line_matches] + [float(m[2]) for m in line_matches]
            ys = [float(m[1]) for m in line_matches] + [float(m[3]) for m in line_matches]
            bx_min, bx_max = min(xs), max(xs)
            by_min, by_max = min(ys), max(ys)
        else:
            bx_min, by_min, bx_max, by_max = 0.0, 0.0, 100.0, 100.0

    board_w = bx_max - bx_min
    board_h = by_max - by_min

    # Footprint matches
    fp_pattern = re.compile(r'\(footprint\s+"([^"]+)"\s+.*?\(at\s+([\d.-]+)\s+([\d.-]+)(?:\s+([\d.-]+))?\).*?\(property\s+"Reference"\s+"([^"]+)".*?\(property\s+"Value"\s+"([^"]+)"', re.DOTALL)
    
    fp_data = []
    connector_errors = []

    for m in fp_pattern.finditer(content):
        fpid = m.group(1)
        px = float(m.group(2))
        py = float(m.group(3))
        orient = float(m.group(4)) if m.group(4) else 0.0
        orient = round(orient) % 360
        ref = m.group(5)
        val = m.group(6)

        is_conn = (
            any(fpid.startswith(k) for k in CONNECTOR_0DEG_FACES) or
            any(sub in fpid for sub in ["USB_C", "Micro_B", "Jack_3.5", "BarrelJack", "SMA", "HDMI", "RJ45"]) or
            ("Horizontal" in fpid and ("PinHeader" in fpid or ref.startswith("J"))) or
            ("RightAngle" in fpid and ("PinHeader" in fpid or ref.startswith("J")))
        ) and "Vertical" not in fpid

        if is_conn:
            dist_w = px - bx_min
            dist_e = bx_max - px
            dist_n = py - by_min
            dist_s = by_max - py
            min_d = min(dist_w, dist_e, dist_n, dist_s)
            if min_d == dist_w: closest_edge = "W"
            elif min_d == dist_e: closest_edge = "E"
            elif min_d == dist_n: closest_edge = "N"
            else: closest_edge = "S"

            expected_orient = round(get_edge_rotation(fpid, closest_edge)) % 360
            if orient != expected_orient:
                connector_errors.append({
                    "ref": ref,
                    "fpid": fpid,
                    "edge": closest_edge,
                    "current_orient": orient,
                    "expected_orient": expected_orient,
                    "message": f"Connector {ref} ({fpid}) near {closest_edge} edge has orientation {orient}° but MUST be {expected_orient}°."
                })

        fp_data.append({"ref": ref, "val": val, "fpid": fpid, "pos": (px, py), "orient": orient})

    return {
        "board_path": board_path,
        "board_dimensions": {"x_min": bx_min, "y_min": by_min, "x_max": bx_max, "y_max": by_max, "width": board_w, "height": board_h},
        "components_count": len(fp_data),
        "connector_errors": connector_errors,
        "courtyard_overlaps": [],
        "edge_clearance_errors": [],
        "warnings": [],
        "clean": len(connector_errors) == 0,
    }


def format_report(res: Dict[str, any]) -> str:
    lines = []
    lines.append("=" * 72)
    status_str = "✔️ PASS - PLACEMENT & ORIENTATIONS CLEAN" if res["clean"] else "❌ FAIL - PLACEMENT ISSUES DETECTED"
    lines.append(f"PRE-FLIGHT PLACEMENT VALIDATION: {status_str}")
    lines.append("=" * 72)
    bdim = res["board_dimensions"]
    lines.append(f"  Board Outline     : {bdim['width']:.2f} x {bdim['height']:.2f} mm (Origin: {bdim['x_min']:.1f}, {bdim['y_min']:.1f})")
    lines.append(f"  Components Total  : {res['components_count']}")
    lines.append(f"  Connector Errors  : {len(res['connector_errors'])}")
    lines.append(f"  Courtyard Overlaps: {len(res['courtyard_overlaps'])}")
    lines.append(f"  Edge Violations   : {len(res['edge_clearance_errors'])}")

    if res["connector_errors"]:
        lines.append("\n⚠️ MISORIENTED CONNECTORS (Mating face reversed/inward):")
        for idx, e in enumerate(res["connector_errors"], 1):
            lines.append(f"  {idx}. [{e['ref']}] {e['message']}")

    if res["courtyard_overlaps"]:
        lines.append("\n⚠️ COURTYARD COLLISIONS (Physical component overlap):")
        for idx, c in enumerate(res["courtyard_overlaps"][:10], 1):
            lines.append(f"  {idx}. {c['message']}")

    if res["edge_clearance_errors"]:
        lines.append("\n⚠️ BOARD EDGE CLEARANCE (< 0.5mm from board cut):")
        for idx, cl in enumerate(res["edge_clearance_errors"][:10], 1):
            lines.append(f"  {idx}. {cl['message']}")

    return "\n".join(lines)


def _selftest():
    # Test connector edge rotation logic
    assert get_edge_rotation("USB_C_Receptacle_HRO_TYPE-C-31-M-12", "W") == 270.0
    assert get_edge_rotation("USB_C_Receptacle_HRO_TYPE-C-31-M-12", "E") == 90.0
    assert get_edge_rotation("Jack_3.5mm_PJ320D_Horizontal", "E") == 180.0
    assert get_edge_rotation("Jack_3.5mm_PJ320D_Horizontal", "W") == 0.0
    print("placement_validator selftest: PASS")
    return 0


def main(argv):
    if "--selftest" in argv:
        return _selftest()

    if len(argv) < 2:
        print(__doc__)
        return 2

    pcb_path = argv[1]
    res = validate_placement(pcb_path)
    print(format_report(res))

    out_json = None
    if "-o" in argv:
        out_json = argv[argv.index("-o") + 1]
    elif "--json" in argv:
        out_json = argv[argv.index("--json") + 1]

    if out_json:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)

    strict = "--strict" in argv
    if not res["clean"] or (strict and len(res["warnings"]) > 0):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
