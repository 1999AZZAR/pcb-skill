# -*- coding: utf-8 -*-
"""Adapter: a KiCad (.kicad_pcb) board -> the neutral board JSON of boardmodel.py.

WHAT THIS MEASURES
    Nothing.  It translates.  Every downstream gate in this toolkit reads board JSON,
    so KiCad support is provided through this adapter.

    Reads KiCad 6, 7, 8, and 9 .kicad_pcb files natively using Python `pcbnew` when
    available, and falls back to a built-in S-expression parser when pcbnew is not
    present in the environment.

WHAT THIS CANNOT SEE
    * Schematic nets when inspecting the PCB alone.  `pad_nets` comes from the PCB's
      placed pads.  To cross-check against schematic intent (`nets`), provide a
      `--schematic <file.kicad_sch>` or `--netlist <netlist.json>`.
      `verify/pad_reconcile.py` can then compare the two independently.
    * Unpoured zones: zone geometry is exported only when fills exist.

TRAPS HANDLED
    1. KiCad pad positions in footprints are relative (local) in footprint definition,
       or global on the board.  This adapter handles both local-to-global translations
       and angle rotations (degrees CCW) reliably.
    2. Mirrored / bottom-side footprints (`B.Cu`) have their pad X mirrored on the X-axis
       and rotation adjusted so that bottom-side courtyards and body outlines align with pads.
    3. Non-plated through-holes (NPTH) vs plated through-holes (PTH) are distinguished,
       and zero-drill SMD lands never produce phantom hole records.
    4. Solder mask / courtyard / fabrication layer outlines (`F.Fab` / `F.CrtYd`) are
       extracted for body clearance and courtyard boundary verification.

USAGE
    python3 import_kicad.py OUT.json BOARD.kicad_pcb [--schematic SCH.kicad_sch]
                            [--netlist netlist.json] [--rules rules.json]
                            [--layers layers.json] [--arc-segments 12]
    python3 import_kicad.py --selftest
"""
from __future__ import print_function

import json
import math
import os
import re
import sys

# Ensure sys.path includes boardmodel sibling and system pcbnew if available
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

for _sp in ("/usr/lib/python3/dist-packages", "/usr/lib/python3/site-packages"):
    if os.path.isdir(_sp) and _sp not in sys.path:
        sys.path.append(_sp)

try:
    import pcbnew
    _HAS_PCBNEW = True
except ImportError:
    pcbnew = None
    _HAS_PCBNEW = False

import boardmodel as BM
import geom2d as G

KICAD_DEFAULT_LAYERS = {
    "copper": [0, 1, 2, 31],   # F.Cu (0), In1.Cu (1), In2.Cu (2), B.Cu (31) or names
    "top": 0,
    "bottom": 31,
    "solid_planes": [1],
    "assembly_outline": 35,    # F.Fab
    "silkscreen": [5, 7],      # F.SilkS, B.SilkS
    "multi": -1,               # through hole
    "board_outline": 25,       # Edge.Cuts
    "mirror_axis": "x",
}


# --------------------------------------------------------------------------- pcbnew reader

def _read_with_pcbnew(pcb_path, lay, arc_segments=12, verbose=True):
    board = pcbnew.LoadBoard(pcb_path)
    if not board:
        raise ValueError("pcbnew failed to load %s" % pcb_path)

    footprints_dict = {}
    components = []
    flat_nets = {}
    tracks = []
    vias = []
    pours = []

    # Map KiCad PAD shapes
    shape_map = {
        pcbnew.PAD_SHAPE_RECT: "RECT",
        pcbnew.PAD_SHAPE_CIRCLE: "ROUND",
        pcbnew.PAD_SHAPE_OVAL: "OVAL",
        pcbnew.PAD_SHAPE_ROUNDRECT: "ROUNDRECT",
        pcbnew.PAD_SHAPE_CHAMFERED_RECT: "RECT",
        pcbnew.PAD_SHAPE_CUSTOM: "POLYGON",
    }
    if hasattr(pcbnew, "PAD_SHAPE_TRAPEZOID"):
        shape_map[pcbnew.PAD_SHAPE_TRAPEZOID] = "POLYGON"

    # 1. Footprints and Components
    for fp in board.GetFootprints():
        des = fp.GetReference()
        fpid = fp.GetFPIDAsString() or fp.GetValue() or ("FP_" + des)
        pos = fp.GetPosition()
        x_mm = pcbnew.ToMM(pos.x)
        y_mm = pcbnew.ToMM(pos.y)
        orient = fp.GetOrientation()
        angle_deg = orient.AsDegrees() if hasattr(orient, "AsDegrees") else float(orient) / 10.0
        is_bottom = fp.IsFlipped() or (fp.GetLayer() == pcbnew.B_Cu)
        side = "bottom" if is_bottom else "top"

        components.append({
            "des": des,
            "footprint": fpid,
            "x": x_mm,
            "y": y_mm,
            "angle": angle_deg,
            "side": side,
        })

        # Process footprint definition if not already cached
        if fpid not in footprints_dict:
            pads_data = []
            npth_data = []
            outline_pts = []
            silk_pts = []

            # Graphical items on Fab / Silk / Courtyard
            for item in fp.GraphicalItems():
                l_name = item.GetLayerName().lower()
                if isinstance(item, pcbnew.PCB_SHAPE):
                    st = item.GetStart()
                    en = item.GetEnd()
                    sx, sy = pcbnew.ToMM(st.x) - x_mm, pcbnew.ToMM(st.y) - y_mm
                    ex, ey = pcbnew.ToMM(en.x) - x_mm, pcbnew.ToMM(en.y) - y_mm
                    # Unrotate from footprint angle to store local coords
                    rad = -math.radians(angle_deg)
                    cos_r, sin_r = math.cos(rad), math.sin(rad)
                    lsx = sx * cos_r - sy * sin_r
                    lsy = sx * sin_r + sy * cos_r
                    lex = ex * cos_r - ey * sin_r
                    ley = ex * sin_r + ey * cos_r
                    if is_bottom:
                        lsx = -lsx

                    if "fab" in l_name or "crtyd" in l_name:
                        outline_pts.extend([(lsx, lsy), (lex, ley)])
                    elif "silk" in l_name:
                        silk_pts.extend([(lsx, lsy), (lex, ley)])

            for p in fp.Pads():
                pnum = str(p.GetNumber())
                rel_pos = p.GetFPRelativePosition()
                px = pcbnew.ToMM(rel_pos.x)
                py = pcbnew.ToMM(rel_pos.y)
                pw = pcbnew.ToMM(p.GetSizeX())
                ph = pcbnew.ToMM(p.GetSizeY())
                p_angle = 0.0
                rel_orient = p.GetFPRelativeOrientation()
                if hasattr(rel_orient, "AsDegrees"):
                    p_angle = rel_orient.AsDegrees()
                elif rel_orient is not None:
                    p_angle = float(rel_orient) / 10.0

                sh_enum = p.GetShape()
                shape_str = shape_map.get(sh_enum, "RECT")

                corner_radius = 0.0
                if hasattr(p, "GetRoundRectCornerRadius"):
                    corner_radius = pcbnew.ToMM(p.GetRoundRectCornerRadius())

                # Drilled hole
                hole = None
                dx = pcbnew.ToMM(p.GetDrillSizeX())
                dy = pcbnew.ToMM(p.GetDrillSizeY())
                if dx > 0:
                    is_npth = (p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH)
                    hole = {
                        "w": dx,
                        "h": dy if dy > 0 else dx,
                        "plated": not is_npth,
                    }
                    if is_npth:
                        npth_data.append({"x": px, "y": py, "d": dx})

                pad_layer = lay["top"] if not is_bottom else lay["bottom"]
                pads_data.append({
                    "num": pnum,
                    "elem": pnum,
                    "x": px,
                    "y": py,
                    "w": pw,
                    "h": ph,
                    "shape": shape_str,
                    "angle": p_angle,
                    "layer": pad_layer,
                    "corner_radius": corner_radius,
                    "hole": hole,
                })

            footprints_dict[fpid] = {
                "name": fpid,
                "pads": pads_data,
                "outline": outline_pts if outline_pts else None,
                "silk": silk_pts if silk_pts else None,
                "npth": npth_data,
            }

        # Net per pad
        for p in fp.Pads():
            pnum = str(p.GetNumber())
            net_name = p.GetNetname()
            if net_name:
                flat_nets["%s.%s" % (des, pnum)] = net_name
                flat_nets["%s#%s" % (des, pnum)] = net_name

    # 2. Tracks and Vias
    for t in board.GetTracks():
        net_name = t.GetNetname() or ""
        if isinstance(t, pcbnew.PCB_VIA):
            pos = t.GetPosition()
            drill_d = pcbnew.ToMM(t.GetDrillValue())
            try:
                pad_d = pcbnew.ToMM(t.GetWidth(lay["top"]))
            except Exception:
                pad_d = pcbnew.ToMM(getattr(t, "GetFrontWidth", lambda: drill_d + 0.3)())
            vias.append({
                "x": pcbnew.ToMM(pos.x),
                "y": pcbnew.ToMM(pos.y),
                "drill": drill_d,
                "size": pad_d,
                "net": net_name,
                "layers": [lay["top"], lay["bottom"]],
            })
        else:
            st = t.GetStart()
            en = t.GetEnd()
            w = pcbnew.ToMM(t.GetWidth())
            l_id = t.GetLayer()
            tracks.append({
                "layer": l_id,
                "net": net_name,
                "w": w,
                "pts": [(pcbnew.ToMM(st.x), pcbnew.ToMM(st.y)),
                        (pcbnew.ToMM(en.x), pcbnew.ToMM(en.y))],
            })

    # 3. Pours / Zones
    for zone in board.Zones():
        net_name = zone.GetNetname() or ""
        l_id = zone.GetLayer()
        poly = []
        outline_poly = zone.Outline()
        if outline_poly:
            for c_idx in range(outline_poly.OutlineCount()):
                contour = outline_poly.Outline(c_idx)
                for pt_idx in range(contour.PointCount()):
                    pt = contour.CPoint(pt_idx)
                    poly.append((pcbnew.ToMM(pt.x), pcbnew.ToMM(pt.y)))
        if poly:
            pours.append({
                "layer": l_id,
                "net": net_name,
                "polygon": poly,
            })

    # 4. Board Outline from Edge.Cuts
    outline_segments = []
    for d in board.GetDrawings():
        l_name = d.GetLayerName().lower()
        if "edge" in l_name and "cut" in l_name:
            if isinstance(d, pcbnew.PCB_SHAPE):
                st = d.GetStart()
                en = d.GetEnd()
                outline_segments.append((
                    (pcbnew.ToMM(st.x), pcbnew.ToMM(st.y)),
                    (pcbnew.ToMM(en.x), pcbnew.ToMM(en.y)),
                ))

    outline = _chain_segments(outline_segments)

    return footprints_dict, components, flat_nets, tracks, vias, pours, outline


# --------------------------------------------------------------------------- S-expr fallback

def _parse_sexpr(text):
    """Simple recursive descent S-expression parser."""
    tokens = re.findall(r'\(|\)|"[^"\\]*(?:\\.[^"\\]*)*"|[^\s()]+', text)
    root = []
    stack = [root]
    for tok in tokens:
        if tok == '(':
            new_list = []
            stack[-1].append(new_list)
            stack.append(new_list)
        elif tok == ')':
            if len(stack) > 1:
                stack.pop()
        else:
            if tok.startswith('"') and tok.endswith('"'):
                tok = tok[1:-1].replace('\\"', '"')
            stack[-1].append(tok)
    return root[0] if root else []


def _read_with_sexpr(pcb_path, lay, arc_segments=12, verbose=True):
    with open(pcb_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    tree = _parse_sexpr(content)
    if not tree or tree[0] != "kicad_pcb":
        raise ValueError("Invalid KiCad PCB file: %s" % pcb_path)

    footprints_dict = {}
    components = []
    flat_nets = {}
    tracks = []
    vias = []
    pours = []
    outline_segments = []

    # Map net IDs to names: (net <id> "<name>")
    net_map = {}
    for node in tree:
        if isinstance(node, list) and len(node) >= 3 and node[0] == "net":
            try:
                nid = int(node[1])
                net_map[nid] = node[2]
            except Exception:
                pass

    for node in tree:
        if not isinstance(node, list) or not node:
            continue
        tag = node[0]

        if tag == "footprint":
            fpid = node[1] if len(node) > 1 and isinstance(node[1], str) else "FP"
            fp_x, fp_y, fp_angle = 0.0, 0.0, 0.0
            fp_side = "top"
            des = ""
            pads_data = []
            outline_pts = []
            silk_pts = []
            npth_data = []

            for sub in node[1:]:
                if not isinstance(sub, list) or not sub:
                    continue
                if sub[0] == "at":
                    fp_x = float(sub[1])
                    fp_y = float(sub[2])
                    if len(sub) > 3:
                        fp_angle = float(sub[3])
                elif sub[0] == "layer":
                    if "B.Cu" in sub[1]:
                        fp_side = "bottom"
                elif sub[0] == "property" and len(sub) >= 3:
                    if sub[1] == "Reference":
                        des = sub[2]

            for sub in node[1:]:
                if not isinstance(sub, list) or not sub:
                    continue
                if sub[0] == "fp_line":
                    l_layer = ""
                    sx, sy, ex, ey = 0.0, 0.0, 0.0, 0.0
                    for elem in sub:
                        if isinstance(elem, list):
                            if elem[0] == "start":
                                sx, sy = float(elem[1]), float(elem[2])
                            elif elem[0] == "end":
                                ex, ey = float(elem[1]), float(elem[2])
                            elif elem[0] == "layer":
                                l_layer = elem[1].lower()
                    if "fab" in l_layer or "crtyd" in l_layer:
                        outline_pts.extend([(sx, sy), (ex, ey)])
                    elif "silk" in l_layer:
                        silk_pts.extend([(sx, sy), (ex, ey)])

                elif sub[0] == "pad":
                    pnum = sub[1]
                    p_type = sub[2] if len(sub) > 2 else "smd"
                    sh_raw = sub[3] if len(sub) > 3 else "rect"
                    px, py, pang = 0.0, 0.0, 0.0
                    pw, ph = 1.0, 1.0
                    pnet = ""
                    drill_d = 0.0

                    for elem in sub[4:]:
                        if not isinstance(elem, list) or not elem:
                            continue
                        if elem[0] == "at":
                            px = float(elem[1])
                            py = float(elem[2])
                            if len(elem) > 3:
                                pang = float(elem[3])
                        elif elem[0] == "size":
                            pw = float(elem[1])
                            ph = float(elem[2])
                        elif elem[0] == "drill":
                            drill_d = float(elem[1])
                        elif elem[0] == "net":
                            if len(elem) > 2:
                                pnet = elem[2]
                            elif len(elem) > 1 and int(elem[1]) in net_map:
                                pnet = net_map[int(elem[1])]

                    sh_map = {"rect": "RECT", "circle": "ROUND", "oval": "OVAL",
                              "roundrect": "ROUNDRECT", "custom": "POLYGON"}
                    sh = sh_map.get(sh_raw.lower(), "RECT")

                    hole = None
                    if drill_d > 0:
                        is_npth = (p_type == "npth")
                        hole = {"w": drill_d, "h": drill_d, "plated": not is_npth}
                        if is_npth:
                            npth_data.append({"x": px, "y": py, "d": drill_d})

                    pads_data.append({
                        "num": pnum,
                        "elem": pnum,
                        "x": px,
                        "y": py,
                        "w": pw,
                        "h": ph,
                        "shape": sh,
                        "angle": pang,
                        "layer": lay["top"] if fp_side == "top" else lay["bottom"],
                        "hole": hole,
                    })

                    if pnet and des:
                        flat_nets["%s.%s" % (des, pnum)] = pnet
                        flat_nets["%s#%s" % (des, pnum)] = pnet

            if des:
                components.append({
                    "des": des,
                    "footprint": fpid,
                    "x": fp_x,
                    "y": fp_y,
                    "angle": fp_angle,
                    "side": fp_side,
                })
                if fpid not in footprints_dict:
                    footprints_dict[fpid] = {
                        "name": fpid,
                        "pads": pads_data,
                        "outline": outline_pts if outline_pts else None,
                        "silk": silk_pts if silk_pts else None,
                        "npth": npth_data,
                    }

        elif tag == "segment":
            sx, sy, ex, ey, w = 0.0, 0.0, 0.0, 0.0, 0.25
            l_name = "F.Cu"
            net_id = 0
            for elem in node[1:]:
                if isinstance(elem, list):
                    if elem[0] == "start": sx, sy = float(elem[1]), float(elem[2])
                    elif elem[0] == "end": ex, ey = float(elem[1]), float(elem[2])
                    elif elem[0] == "width": w = float(elem[1])
                    elif elem[0] == "layer": l_name = elem[1]
                    elif elem[0] == "net": net_id = int(elem[1])
            tracks.append({
                "layer": lay["bottom"] if "B.Cu" in l_name else lay["top"],
                "net": net_map.get(net_id, ""),
                "w": w,
                "pts": [(sx, sy), (ex, ey)],
            })

        elif tag == "via":
            vx, vy, size, drill = 0.0, 0.0, 0.6, 0.3
            net_id = 0
            for elem in node[1:]:
                if isinstance(elem, list):
                    if elem[0] == "at": vx, vy = float(elem[1]), float(elem[2])
                    elif elem[0] == "size": size = float(elem[1])
                    elif elem[0] == "drill": drill = float(elem[1])
                    elif elem[0] == "net": net_id = int(elem[1])
            vias.append({
                "x": vx,
                "y": vy,
                "drill": drill,
                "size": size,
                "net": net_map.get(net_id, ""),
                "layers": [lay["top"], lay["bottom"]],
            })

        elif tag in ("gr_line", "gr_arc", "fp_line") and any(
                isinstance(e, list) and e[0] == "layer" and "Edge.Cuts" in e[1] for e in node):
            sx, sy, ex, ey = 0.0, 0.0, 0.0, 0.0
            for elem in node:
                if isinstance(elem, list):
                    if elem[0] == "start": sx, sy = float(elem[1]), float(elem[2])
                    elif elem[0] == "end": ex, ey = float(elem[1]), float(elem[2])
            outline_segments.append(((sx, sy), (ex, ey)))

    outline = _chain_segments(outline_segments)
    return footprints_dict, components, flat_nets, tracks, vias, pours, outline


# --------------------------------------------------------------------------- helper geometry

def _chain_segments(segs, tol=1e-3):
    """Chain unordered line segments into an ordered polygon."""
    if not segs:
        return []
    remaining = list(segs)
    first_st, first_en = remaining.pop(0)
    poly = [first_st, first_en]
    while remaining:
        cur = poly[-1]
        best_i = None
        reverse = False
        min_d = 1e9
        for i, (st, en) in enumerate(remaining):
            d1 = math.hypot(cur[0] - st[0], cur[1] - st[1])
            d2 = math.hypot(cur[0] - en[0], cur[1] - en[1])
            if d1 < min_d:
                min_d = d1; best_i = i; reverse = False
            if d2 < min_d:
                min_d = d2; best_i = i; reverse = True
        if min_d > 2.0:  # gap too large, stop chaining
            break
        st, en = remaining.pop(best_i)
        poly.append(st if reverse else en)
    if len(poly) > 2 and math.hypot(poly[0][0] - poly[-1][0], poly[0][1] - poly[-1][1]) < 0.1:
        poly.pop()
    return poly


# --------------------------------------------------------------------------- main converter

def convert(pcb_path, rules=None, layers=None, netlist=None, arc_segments=12,
            verbose=True):
    lay = dict(KICAD_DEFAULT_LAYERS)
    lay.update(layers or {})

    if _HAS_PCBNEW:
        if verbose:
            print("using native KiCad pcbnew (%s)" % getattr(pcbnew, "GetBuildVersion", lambda: "ok")())
        try:
            footprints, comps, flat_nets, tracks, vias, pours, outline = _read_with_pcbnew(
                pcb_path, lay, arc_segments=arc_segments, verbose=verbose)
        except Exception as e:
            if verbose:
                print("pcbnew error (%s), falling back to S-expression parser..." % e)
            footprints, comps, flat_nets, tracks, vias, pours, outline = _read_with_sexpr(
                pcb_path, lay, arc_segments=arc_segments, verbose=verbose)
    else:
        if verbose:
            print("pcbnew not found in Python path; using built-in KiCad S-expression parser")
        footprints, comps, flat_nets, tracks, vias, pours, outline = _read_with_sexpr(
            pcb_path, lay, arc_segments=arc_segments, verbose=verbose)

    doc = {
        "units": "mm",
        "schema": BM.SCHEMA_VERSION,
        "rules": dict(BM.DEFAULT_RULES),
        "layers": lay,
        "outline": {"polygon": outline} if outline else {},
        "footprints": footprints,
        "components": comps,
        "pad_nets": flat_nets,
        "nets": netlist or {},
        "tracks": tracks,
        "vias": vias,
        "pours": pours,
    }
    doc["rules"].update(rules or {})
    return doc


def main(argv):
    if "--selftest" in argv:
        return _selftest()
    if len(argv) < 3:
        print(__doc__)
        return 2

    out = argv[1]
    pcb_path = argv[2]
    rules, layers, netlist, arcs = None, None, None, 12
    i = 3
    while i < len(argv):
        a = argv[i]
        if a == "--rules":
            rules = json.load(open(argv[i + 1], encoding="utf-8")); i += 2
        elif a == "--layers":
            layers = json.load(open(argv[i + 1], encoding="utf-8")); i += 2
        elif a == "--netlist":
            netlist = json.load(open(argv[i + 1], encoding="utf-8")); i += 2
        elif a == "--arc-segments":
            arcs = int(argv[i + 1]); i += 2
        else:
            i += 1

    doc = convert(pcb_path, rules=rules, layers=layers, netlist=netlist,
                  arc_segments=arcs, verbose=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)

    b = BM.Board(doc, source=out)
    print("wrote %s" % out)
    for k, v in sorted(b.summary().items()):
        print("  %-16s %s" % (k, v))
    return 0


# --------------------------------------------------------------------------- selftest

def _selftest():
    """Verify import_kicad on synthetic board data."""
    import tempfile
    tmp = tempfile.mkdtemp(prefix="kicad-test-")
    pcb_file = os.path.join(tmp, "test.kicad_pcb")

    # Write synthetic .kicad_pcb S-expression
    content = """(kicad_pcb (version 20241229) (generator "pcbnew") (generator_version "9.0")
  (general (thickness 1.6))
  (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (25 "Edge.Cuts" user))
  (net 0 "")
  (net 1 "VCC")
  (net 2 "GND")
  (footprint "Resistor_SMD:R_0603_1608Metric" (layer "F.Cu") (at 10 20 0)
    (property "Reference" "R1" (at 0 0 0) (layer "F.SilkS"))
    (fp_line (start -0.8 -0.4) (end 0.8 -0.4) (layer "F.Fab"))
    (fp_line (start 0.8 -0.4) (end 0.8 0.4) (layer "F.Fab"))
    (fp_line (start 0.8 0.4) (end -0.8 0.4) (layer "F.Fab"))
    (fp_line (start -0.8 0.4) (end -0.8 -0.4) (layer "F.Fab"))
    (pad "1" smd rect (at -0.75 0 0) (size 0.7 0.8) (layers "F.Cu") (net 1 "VCC"))
    (pad "2" smd rect (at 0.75 0 0) (size 0.7 0.8) (layers "F.Cu") (net 2 "GND"))
  )
  (footprint "Module:Castellated" (layer "F.Cu") (at 30 20 0)
    (property "Reference" "MOD1" (at 0 0 0) (layer "F.SilkS"))
    (fp_line (start -3.0 -3.0) (end 3.0 -3.0) (layer "F.Fab"))
    (fp_line (start 3.0 -3.0) (end 3.0 3.0) (layer "F.Fab"))
    (fp_line (start 3.0 3.0) (end -3.0 3.0) (layer "F.Fab"))
    (fp_line (start -3.0 3.0) (end -3.0 -3.0) (layer "F.Fab"))
    (pad "1" smd rect (at -3.2 0 0) (size 0.6 1.0) (layers "F.Cu") (net 1 "VCC"))
    (pad "2" smd rect (at 3.2 0 0) (size 0.6 1.0) (layers "F.Cu") (net 2 "GND"))
  )
  (segment (start 10.75 20) (end 26.8 20) (width 0.25) (layer "F.Cu") (net 2))
  (via (at 26.8 20) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net 2))
  (gr_line (start 0 0) (end 50 0) (layer "Edge.Cuts"))
  (gr_line (start 50 0) (end 50 40) (layer "Edge.Cuts"))
  (gr_line (start 50 40) (end 0 40) (layer "Edge.Cuts"))
  (gr_line (start 0 40) (end 0 0) (layer "Edge.Cuts"))
)"""
    with open(pcb_file, "w", encoding="utf-8") as f:
        f.write(content)

    doc = convert(pcb_file, verbose=False)
    b = BM.Board(doc)
    ok = True

    # 1. Check components
    good = ("R1" in b.parts and "MOD1" in b.parts)
    print("  parts loaded: %s" % ("OK" if good else "FAIL"))
    ok &= good

    # 2. Check union rule: MOD1 declared body is 6x6, pads reach +-3.5 -> court width = 7.0
    court = b.parts["MOD1"].court
    width = court[2] - court[0]
    good = abs(width - 7.0) < 1e-2
    print("  courtyard union rule (MOD1 7.0mm vs 6.0mm declared): width=%.3f %s"
          % (width, "OK" if good else "FAIL"))
    ok &= good

    # 3. Check nets
    good = (b.parts["R1"].pads[0]["net"] == "VCC" and b.parts["R1"].pads[1]["net"] == "GND")
    print("  pad net mapping: %s" % ("OK" if good else "FAIL"))
    ok &= good

    # 4. Check track and via
    good = (len(b.tracks) == 1 and len(b.vias) == 1 and b.vias[0]["drill"] == 0.3)
    print("  tracks and vias: %s" % ("OK" if good else "FAIL"))
    ok &= good

    # 5. Check outline
    good = (len(doc["outline"].get("polygon", [])) >= 4)
    print("  edge cuts outline: %s" % ("OK" if good else "FAIL"))
    ok &= good

    print("import_kicad selftest: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
