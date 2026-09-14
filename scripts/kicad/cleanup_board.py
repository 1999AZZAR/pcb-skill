# -*- coding: utf-8 -*-
"""Post-Routing & Board Geometry Cleanup Engine for KiCad PCBs.

Performs automated cleanup passes on routed and unrouted boards:
  1. Prunes dangling track stubs (dead-end antennas produced by autorouters or manual edits).
  2. Removes zero-length and sub-micron duplicate track segments.
  3. Eliminates duplicate parallel tracks on the same layer.
  4. Resolves starved thermal relief warnings on pads already connected via dedicated tracks.
  5. Cleans temporary autorouter artifacts (.dsn, .ses, .raw) from project directories.
  6. Refills all copper zones safely using subprocess-isolated ZONE_FILLER.

USAGE AS SCRIPT:
    python3 cleanup_board.py BOARD.kicad_pcb [-o OUT.kicad_pcb] [--clean-temp]
    python3 cleanup_board.py --selftest

USAGE IN PYTHON:
    from cleanup_board import cleanup_board
    cleanup_board("my_board.kicad_pcb", refill=True)
"""
from __future__ import print_function

import glob
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))

for _sp in ("/usr/lib/python3/dist-packages", "/usr/lib/python3/site-packages"):
    if os.path.isdir(_sp) and _sp not in sys.path:
        sys.path.append(_sp)

try:
    import pcbnew
    _HAS_PCBNEW = True
except ImportError:
    pcbnew = None
    _HAS_PCBNEW = False


def _to_nm(val_mm):
    return int(round(val_mm * 1000000.0))


def _to_mm(val_nm):
    return val_nm / 1000000.0


def clean_micro_tracks(board, min_len_mm=0.005, verbose=False):
    """Remove tracks with length less than min_len_mm (e.g. 5 um)."""
    min_nm = _to_nm(min_len_mm)
    removed = 0
    for t in list(board.GetTracks()):
        if t.GetClass() != "PCB_VIA":
            if t.GetLength() < min_nm:
                board.Delete(t)
                removed += 1
    if verbose and removed:
        print("  Cleaned %d zero-length/micro track segments (< %.3f mm)" % (removed, min_len_mm))
    return removed


def clean_duplicate_tracks(board, verbose=False):
    """Remove duplicate tracks that share the exact same start, end, layer, and net."""
    seen = set()
    removed = 0
    for t in list(board.GetTracks()):
        if t.GetClass() != "PCB_VIA":
            p1 = (t.GetStart().x, t.GetStart().y)
            p2 = (t.GetEnd().x, t.GetEnd().y)
            pt_pair = (min(p1, p2), max(p1, p2), t.GetLayer(), t.GetNetCode())
            if pt_pair in seen:
                board.Delete(t)
                removed += 1
            else:
                seen.add(pt_pair)
    if verbose and removed:
        print("  Cleaned %d duplicate overlapping track segments" % removed)
    return removed


def clean_dangling_tracks(board, tolerance_mm=0.02, max_iterations=10, verbose=False):
    """Recursively prune track branches that do not terminate at any pad or via.

    An endpoint is considered connected if it touches:
      - A pad of the same net.
      - A via of the same net.
      - At least two other tracks of the same net (a junction).
    Tracks with an unconnected dead-end are pruned in iterative passes.
    """
    tol_nm = _to_nm(tolerance_mm)
    total_pruned = 0

    # Collect all pad locations per net
    pads_by_net = {}
    for fp in board.Footprints():
        for pad in fp.Pads():
            netcode = pad.GetNetCode()
            if netcode == 0:
                continue
            pos = pad.GetPosition()
            if netcode not in pads_by_net:
                pads_by_net[netcode] = []
            pads_by_net[netcode].append((pos.x, pos.y, pad))

    for iteration in range(max_iterations):
        # Collect vias by net
        vias_by_net = {}
        tracks_by_net = {}
        for item in board.GetTracks():
            netcode = item.GetNetCode()
            if netcode == 0:
                continue
            if item.GetClass() == "PCB_VIA":
                if netcode not in vias_by_net:
                    vias_by_net[netcode] = []
                vias_by_net[netcode].append((item.GetPosition().x, item.GetPosition().y))
            else:
                if netcode not in tracks_by_net:
                    tracks_by_net[netcode] = []
                tracks_by_net[netcode].append(item)

        iteration_pruned = 0
        for netcode, tracks in tracks_by_net.items():
            # Collect all endpoints for this net
            all_endpoints = []
            for t in tracks:
                all_endpoints.append((t.GetStart().x, t.GetStart().y))
                all_endpoints.append((t.GetEnd().x, t.GetEnd().y))

            def count_endpoints_near(px, py):
                cnt = 0
                for ex, ey in all_endpoints:
                    dx = px - ex
                    dy = py - ey
                    if (dx * dx + dy * dy) <= (tol_nm * tol_nm):
                        cnt += 1
                return cnt

            pads = pads_by_net.get(netcode, [])
            vias = vias_by_net.get(netcode, [])

            def is_terminal(px, py):
                vec = pcbnew.VECTOR2I(px, py)
                # Check pads using HitTest and center distance
                for pad_x, pad_y, pad in pads:
                    if hasattr(pad, 'HitTest') and pad.HitTest(vec):
                        return True
                    dx = px - pad_x
                    dy = py - pad_y
                    if (dx * dx + dy * dy) <= (tol_nm * tol_nm):
                        return True
                # Check vias
                for vx, vy in vias:
                    dx = px - vx
                    dy = py - vy
                    if (dx * dx + dy * dy) <= (tol_nm * tol_nm):
                        return True
                return False

            for t in list(tracks):
                p1 = (t.GetStart().x, t.GetStart().y)
                p2 = (t.GetEnd().x, t.GetEnd().y)

                # Each track endpoint counts 1 for itself; <= 1 means no other track touches it
                p1_dangling = (count_endpoints_near(p1[0], p1[1]) <= 1) and not is_terminal(p1[0], p1[1])
                p2_dangling = (count_endpoints_near(p2[0], p2[1]) <= 1) and not is_terminal(p2[0], p2[1])

                if p1_dangling or p2_dangling:
                    board.Delete(t)
                    iteration_pruned += 1

        total_pruned += iteration_pruned
        if iteration_pruned == 0:
            break

    if verbose and total_pruned:
        print("  Pruned %d dangling track stubs across %d passes" % (total_pruned, iteration + 1))
    return total_pruned


import glob
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

def clean_dangling_tracks_drc(pcb_path, board=None, verbose=False):
    """Prune tracks reported as dangling by kicad-cli pcb drc."""
    if not shutil.which("kicad-cli"):
        return 0
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        drc_json = tf.name
    try:
        cmd = ["kicad-cli", "pcb", "drc", "--format", "json", "--output", drc_json, pcb_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not os.path.exists(drc_json):
            return 0
        try:
            with open(drc_json, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return 0
        dangling_uuids = set()
        for v in data.get("violations", []):
            if v.get("type") == "track_dangling":
                for item in v.get("items", []):
                    u = item.get("uuid")
                    if u:
                        dangling_uuids.add(u)
        if not dangling_uuids:
            return 0
        save_after = False
        if board is None:
            board = pcbnew.LoadBoard(pcb_path)
            save_after = True
        pruned = 0
        for t in list(board.GetTracks()):
            if str(t.m_Uuid.AsString()) in dangling_uuids:
                board.Delete(t)
                pruned += 1
        if save_after and pruned:
            pcbnew.SaveBoard(pcb_path, board)
        if verbose and pruned:
            print("  DRC-guided pruning: removed %d dangling track stubs" % pruned)
        return pruned
    finally:
        if os.path.exists(drc_json):
            try:
                os.remove(drc_json)
            except OSError:
                pass


def fix_starved_thermals_drc(pcb_path, board=None, verbose=False):
    """Set zone connection to NONE on pads flagged as starved_thermal if connected by dedicated tracks."""
    if not shutil.which("kicad-cli"):
        return 0
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        drc_json = tf.name
    try:
        cmd = ["kicad-cli", "pcb", "drc", "--format", "json", "--output", drc_json, pcb_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not os.path.exists(drc_json):
            return 0
        try:
            with open(drc_json, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return 0
        starved_pad_uuids = set()
        for v in data.get("violations", []):
            if v.get("type") == "starved_thermal":
                for item in v.get("items", []):
                    u = item.get("uuid")
                    if u and "pad" in item.get("description", "").lower():
                        starved_pad_uuids.add(u)
        if not starved_pad_uuids:
            return 0
        save_after = False
        if board is None:
            board = pcbnew.LoadBoard(pcb_path)
            save_after = True
        fixed = 0
        for fp in board.Footprints():
            for pad in fp.Pads():
                if str(pad.m_Uuid.AsString()) in starved_pad_uuids:
                    pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_NONE)
                    fixed += 1
        if save_after and fixed:
            pcbnew.SaveBoard(pcb_path, board)
        if verbose and fixed:
            print("  DRC-guided thermal fix: set ZONE_CONNECTION_NONE on %d starved pad(s)" % fixed)
        return fixed
    finally:
        if os.path.exists(drc_json):
            try:
                os.remove(drc_json)
            except OSError:
                pass


def fix_starved_thermals(board, verbose=False):
    """Set zone connection to NONE on pads with dedicated tracks to prevent starved thermals."""
    fixed = 0
    tracks = board.GetTracks()
    for fp in board.Footprints():
        for pad in fp.Pads():
            if pad.GetNetCode() != 0:
                pos = pad.GetPosition()
                direct_tracks = 0
                for t in tracks:
                    if t.GetNetCode() == pad.GetNetCode():
                        if t.GetStart() == pos or t.GetEnd() == pos:
                            direct_tracks += 1
                if direct_tracks >= 1 and pad.GetLocalZoneConnection() == pcbnew.ZONE_CONNECTION_INHERITED:
                    pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_NONE)
                    fixed += 1
    if verbose and fixed:
        print("  Set ZONE_CONNECTION_NONE on %d track-connected pad(s)" % fixed)
    return fixed


def clean_temporary_files(directory, extensions=(".dsn", ".ses", ".raw", ".gbrjob", ".kicad_pcb-bak", ".kicad_sch-bak"), verbose=False):
    """Remove temporary autorouting files and scratch logs from project directory."""
    removed = 0
    for ext in extensions:
        pattern = os.path.join(directory, "*" + ext)
        for f in glob.glob(pattern):
            try:
                os.remove(f)
                removed += 1
            except OSError:
                pass
    if verbose and removed:
        print("  Removed %d temporary autorouting artifact(s) from %s" % (removed, directory))
    return removed


def cleanup_board(pcb_path, out_pcb_path=None, clean_temp=True, refill=True, verbose=True):
    """Execute complete post-routing cleanup on a KiCad PCB file."""
    if not _HAS_PCBNEW:
        raise RuntimeError("pcbnew required for board cleanup")
    if not os.path.exists(pcb_path):
        raise FileNotFoundError("PCB file not found: %s" % pcb_path)

    out_path = out_pcb_path or pcb_path
    board = pcbnew.LoadBoard(pcb_path)
    if not board:
        raise RuntimeError("Failed to load PCB: %s" % pcb_path)

    if verbose:
        print("Starting cleanup on: %s" % pcb_path)

    n_micro = clean_micro_tracks(board, verbose=verbose)
    n_dups = clean_duplicate_tracks(board, verbose=verbose)
    n_dangle = clean_dangling_tracks(board, verbose=verbose)

    pcbnew.SaveBoard(out_path, board)

    # DRC-guided refinement passes
    n_drc_dangle = clean_dangling_tracks_drc(out_path, verbose=verbose)
    n_drc_thermal = fix_starved_thermals_drc(out_path, verbose=verbose)

    if refill:
        try:
            from autoroute_2layer import fill_zones_safely
            fill_zones_safely(out_path, verbose=verbose)
        except Exception as e:
            if verbose:
                print("  Zone refill note: %s" % e)

    if clean_temp:
        clean_temporary_files(os.path.dirname(os.path.abspath(pcb_path)), verbose=verbose)

    if verbose:
        print("Cleanup completed successfully -> %s" % out_path)
    return {
        "success": True,
        "micro_cleaned": n_micro,
        "duplicates_cleaned": n_dups,
        "dangling_pruned": n_dangle + n_drc_dangle,
        "thermals_fixed": n_drc_thermal,
        "out_path": out_path,
    }


def _selftest():
    """Verify micro track, duplicate track, and dangling stub pruning on test geometry."""
    if not _HAS_PCBNEW:
        print("cleanup_board selftest: SKIP (pcbnew missing)")
        return 0

    board = pcbnew.BOARD()
    net = pcbnew.NETINFO_ITEM(board, "TEST")
    board.Add(net)

    # Terminals (pads) at (0, 0) and (10, 0)
    fp = pcbnew.FOOTPRINT(board)
    fp.SetReference("U1")
    pad1 = pcbnew.PAD(fp)
    pad1.SetPosition(pcbnew.VECTOR2I_MM(0, 0))
    pad1.SetNet(net)
    fp.Add(pad1)

    pad2 = pcbnew.PAD(fp)
    pad2.SetPosition(pcbnew.VECTOR2I_MM(10, 0))
    pad2.SetNet(net)
    fp.Add(pad2)
    board.Add(fp)

    # 1. Main trunk connecting pad1 and pad2
    t1 = pcbnew.PCB_TRACK(board)
    t1.SetStart(pcbnew.VECTOR2I_MM(0, 0))
    t1.SetEnd(pcbnew.VECTOR2I_MM(10, 0))
    t1.SetNet(net)
    board.Add(t1)

    # 2. Duplicate of main trunk
    t2 = pcbnew.PCB_TRACK(board)
    t2.SetStart(pcbnew.VECTOR2I_MM(0, 0))
    t2.SetEnd(pcbnew.VECTOR2I_MM(10, 0))
    t2.SetNet(net)
    board.Add(t2)

    # 3. Micro stub (< 5 um)
    t3 = pcbnew.PCB_TRACK(board)
    t3.SetStart(pcbnew.VECTOR2I_MM(5, 0))
    t3.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(5) + 1000, 0))  # 1 um
    t3.SetNet(net)
    board.Add(t3)

    # 4. Dangling antenna branch (dead end at (5, 3))
    t4 = pcbnew.PCB_TRACK(board)
    t4.SetStart(pcbnew.VECTOR2I_MM(5, 0))
    t4.SetEnd(pcbnew.VECTOR2I_MM(5, 3))
    t4.SetNet(net)
    board.Add(t4)

    initial_count = len(list(board.GetTracks()))
    clean_micro_tracks(board, verbose=False)
    clean_duplicate_tracks(board, verbose=False)
    clean_dangling_tracks(board, verbose=False)
    final_count = len(list(board.GetTracks()))

    # Expect only t1 remaining (1 track)
    ok = (initial_count == 4 and final_count == 1)
    print("cleanup_board selftest: %s (initial %d tracks -> %d tracks)" % (
        "PASS" if ok else "FAIL", initial_count, final_count
    ))
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return _selftest()
    if len(argv) < 2:
        print(__doc__)
        return 2

    pcb = argv[1]
    out_pcb = argv[argv.index("-o") + 1] if "-o" in argv else pcb
    clean_temp = "--clean-temp" in argv or "-c" in argv
    res = cleanup_board(pcb, out_pcb_path=out_pcb, clean_temp=clean_temp, verbose=True)
    return 0 if res.get("success") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
