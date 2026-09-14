#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Connector Edge Orientation and Alignment Engine for pcb-skill.

Resolves the fundamental KiCad connector orientation ambiguity:
Footprint libraries in KiCad do NOT share a uniform 0-degree mating direction.
Some face -X (West), some face +Y (South), some face -Y (North).

This module:
  1. Maintains an authoritative registry of common edge connectors and their 0-deg mating face vectors.
  2. Computes the exact KiCad orientation angle (0, 90, 180, 270) to face any board edge (West, East, North, South).
  3. Audits placed connectors on a board to detect 180-degree reversed connectors facing inward.
"""

import math
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

try:
    import pcbnew
except ImportError:
    for p in ["/usr/lib/python3/dist-packages", "/usr/local/lib/python3/dist-packages"]:
        if p not in sys.path and os.path.isdir(p):
            sys.path.append(p)
    try:
        import pcbnew
    except ImportError:
        pcbnew = None

# Registry of connector footprint basenames and their default mating face vector at angle = 0 deg
# Vectors: (dx, dy) where the mating plug enters from the outside towards the connector:
# "W" = (-1, 0) [faces West], "E" = (1, 0) [faces East]
# "N" = (0, -1) [faces North], "S" = (0, 1) [faces South]
CONNECTOR_0DEG_FACES = {
    # USB Type-C
    "USB_C_Receptacle_HRO_TYPE-C-31-M-12": (0, 1),      # 0 deg faces South (+Y)
    "USB_C_Receptacle_GCT_USB4085": (0, 1),              # 0 deg faces South (+Y)
    "USB_C_Receptacle_GCT_USB4105": (0, 1),              # 0 deg faces South (+Y)
    "USB_C_Receptacle_Amphenol_12401610E4#2A": (0, 1),   # 0 deg faces South (+Y)
    "USB_C_Receptacle_Palconn_UTC16-G": (0, 1),          # 0 deg faces South (+Y)

    # Micro USB
    "USB_Micro_B_Molex_47346-0001": (0, 1),              # 0 deg faces South (+Y)
    "USB_Micro_B_Amphenol_10103594-0001LF": (0, 1),      # 0 deg faces South (+Y)
    "USB_Mini_B_Lumberg_2486_01_Horizontal": (0, 1),     # 0 deg faces South (+Y)

    # Audio Jacks
    "Jack_3.5mm_PJ320D_Horizontal": (-1, 0),             # 0 deg faces West (-X)
    "Jack_3.5mm_PJ320A_Horizontal": (-1, 0),             # 0 deg faces West (-X)
    "Jack_3.5mm_Cui_SJ1-3533NG_Horizontal": (-1, 0),     # 0 deg faces West (-X)
    "Jack_3.5mm_Cui_SJ-3523-SMT_Horizontal": (-1, 0),    # 0 deg faces West (-X)
    "Jack_6.35mm_Neutrik_NMJ4HFD2_Horizontal": (-1, 0),  # 0 deg faces West (-X)

    # Barrel Jacks & Power
    "BarrelJack_Horizontal": (-1, 0),                    # 0 deg faces West (-X)
    "BarrelJack_CUI_PJ-002AH_Horizontal": (-1, 0),       # 0 deg faces West (-X)
    "BarrelJack_CUI_PJ-102AH_Horizontal": (-1, 0),       # 0 deg faces West (-X)

    # RF Connectors
    "SMA_Amphenol_901-144_Horizontal": (-1, 0),          # 0 deg faces West (-X)
    "SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount": (-1, 0),    # 0 deg faces West (-X)

    # SD Card Sockets
    "MicroSD_HC_Hirose_DM3D-SF": (0, 1),                 # 0 deg faces South (+Y)
}

# Target board edge to required outward vector
EDGE_VECTORS = {
    "W": (-1, 0),      # Left board edge (X = 0)
    "WEST": (-1, 0),
    "LEFT": (-1, 0),
    "E": (1, 0),       # Right board edge (X = W)
    "EAST": (1, 0),
    "RIGHT": (1, 0),
    "N": (0, -1),      # Top board edge (Y = 0)
    "NORTH": (0, -1),
    "TOP": (0, -1),
    "S": (0, 1),       # Bottom board edge (Y = H)
    "SOUTH": (0, 1),
    "BOTTOM": (0, 1),
}


def get_edge_rotation(footprint_name: str, target_edge: str) -> float:
    """Calculate the required KiCad orientation angle (0, 90, 180, 270 deg) for a connector.

    Args:
        footprint_name: KiCad footprint name (e.g. 'USB_C_Receptacle_HRO_TYPE-C-31-M-12' or 'Jack_3.5mm_PJ320D_Horizontal')
        target_edge: Target board edge ('W', 'E', 'N', 'S')

    Returns:
        float: Orientation angle in degrees (clockwise rotation in KiCad coordinates).
    """
    # Clean library prefix if present
    base_name = footprint_name.split(":")[-1] if ":" in footprint_name else footprint_name

    target_v = EDGE_VECTORS.get(target_edge.upper())
    if not target_v:
        raise ValueError(f"Unknown target edge: {target_edge}. Must be W, E, N, or S.")

    # Lookup 0 deg mating face vector
    init_v = CONNECTOR_0DEG_FACES.get(base_name)
    if not init_v:
        # Heuristic fallback: if 'Jack' or 'Barrel' in name -> default West (-1, 0); if 'USB' -> default South (0, 1)
        if any(k in base_name for k in ["Jack", "Barrel", "SMA"]):
            init_v = (-1, 0)
        else:
            init_v = (0, 1)

    # In KiCad screen coordinates (X right, Y down):
    # KiCad EDA_ANGLE rotation transforms a local footprint coordinate (vx, vy) by angle theta to:
    #   vx' = vx * cos(theta) + vy * sin(theta)
    #   vy' = -vx * sin(theta) + vy * cos(theta)
    # (Since +Y is down, positive angle rotates counter-clockwise in Cartesian polar terms,
    #  mapping (0, 1) [South] at 90 deg to (1, 0) [East], 180 deg to (0, -1) [North], 270 deg to (-1, 0) [West])
    for angle in [0.0, 90.0, 180.0, 270.0]:
        rad = math.radians(angle)
        cos_a = round(math.cos(rad))
        sin_a = round(math.sin(rad))

        rx = init_v[0] * cos_a + init_v[1] * sin_a
        ry = -init_v[0] * sin_a + init_v[1] * cos_a

        if (rx, ry) == target_v:
            return angle

    return 0.0


def audit_connector_orientations(board_path: str) -> List[Dict[str, any]]:
    """Audit all connectors on a KiCad PCB to detect reversed or misoriented connectors.

    Args:
        board_path: Path to .kicad_pcb

    Returns:
        List of violation dictionaries for any misaligned connector.
    """
    if pcbnew is None:
        return [{"error": "pcbnew python module not available"}]

    board = pcbnew.LoadBoard(board_path)
    bbox = board.GetBoardEdgesBoundingBox()
    bx_min = pcbnew.ToMM(bbox.GetX())
    bx_max = pcbnew.ToMM(bbox.GetRight())
    by_min = pcbnew.ToMM(bbox.GetY())
    by_max = pcbnew.ToMM(bbox.GetBottom())

    violations = []

    for fp in board.GetFootprints():
        ref = fp.GetReference()
        val = fp.GetValue()
        fp_id = fp.GetFPID().GetLibItemName()
        fp_name = str(fp_id)

        # Check if this footprint is a known connector
        is_conn = any(fp_name.startswith(k) for k in CONNECTOR_0DEG_FACES) or \
                  any(sub in fp_name for sub in ["USB_C", "Micro_B", "Jack_3.5", "BarrelJack"])

        if not is_conn:
            continue

        pos = fp.GetPosition()
        px = pcbnew.ToMM(pos.x)
        py = pcbnew.ToMM(pos.y)
        orient = round(fp.GetOrientation().AsDegrees()) % 360

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

        # Calculate expected orientation
        expected_orient = round(get_edge_rotation(fp_name, closest_edge)) % 360

        if orient != expected_orient:
            violations.append({
                "reference": ref,
                "value": val,
                "footprint": fp_name,
                "position": (px, py),
                "current_orientation": orient,
                "closest_edge": closest_edge,
                "expected_orientation": expected_orient,
                "description": (
                    f"Connector {ref} ({fp_name}) near {closest_edge} edge has orientation {orient}° "
                    f"but needs {expected_orient}° to face outward off the board."
                ),
            })

    return violations


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].endswith(".kicad_pcb"):
        res = audit_connector_orientations(sys.argv[1])
        if not res:
            print("✔️ All edge connectors correctly oriented!")
            sys.exit(0)
        else:
            print(f"⚠️ Found {len(res)} misoriented connector(s):")
            for v in res:
                print("  -", v["description"])
            sys.exit(1)
    else:
        # Run self-test
        print("Self-test: Connector edge orientation calculator")
        tests = [
            ("USB_C_Receptacle_HRO_TYPE-C-31-M-12", "W", 270.0),
            ("USB_C_Receptacle_HRO_TYPE-C-31-M-12", "E", 90.0),
            ("USB_C_Receptacle_HRO_TYPE-C-31-M-12", "S", 0.0),
            ("USB_C_Receptacle_HRO_TYPE-C-31-M-12", "N", 180.0),
            ("Jack_3.5mm_PJ320D_Horizontal", "E", 180.0),
            ("Jack_3.5mm_PJ320D_Horizontal", "W", 0.0),
            ("BarrelJack_Horizontal", "W", 0.0),
            ("BarrelJack_Horizontal", "E", 180.0),
        ]
        all_ok = True
        for fp, edge, expected in tests:
            rot = get_edge_rotation(fp, edge)
            ok = (rot == expected)
            if not ok: all_ok = False
            print(f"  {fp:35s} -> {edge}: got {rot}°, expected {expected}° [{ok}]")
        print("Self-test status:", "PASS" if all_ok else "FAIL")
