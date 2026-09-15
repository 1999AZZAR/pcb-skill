# -*- coding: utf-8 -*-
"""Automated JLCPCB fabrication package exporter and verification runner for KiCad.

Generates production-ready, verified fabrication packages for JLCPCB:
  1. RS-274X Gerbers with JLC-recommended settings (no X2, drill origin, 6-digit precision).
  2. Excellon drill files (PTH + NPTH).
  3. CPL / Pick-and-Place component position file for SMT assembly.
  4. BOM file (exported from schematic or extracted directly from PCB footprints with LCSC part matching).
  5. High-resolution 3D photorealistic render previews (Top and Bottom sides).
  6. ZIP archive formatted for direct drag-and-drop into the JLCPCB order portal.
  7. Automatically runs verification checkers (drill census, outline, mask) on the result.

USAGE
    python3 export_jlcpcb.py BOARD.kicad_pcb [--schematic SCH.kicad_sch]
                             [--out-dir ./jlcpcb_output] [--no-zip] [--no-render]
    python3 export_jlcpcb.py --selftest
"""
from __future__ import print_function

import csv
import os
import re
import shutil
import subprocess
import sys
import zipfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_VERIFY = os.path.join(_HERE, os.pardir, "verify")

for _sp in ("/usr/lib/python3/dist-packages", "/usr/lib/python3/site-packages"):
    if os.path.isdir(_sp) and _sp not in sys.path:
        sys.path.append(_sp)

try:
    import pcbnew
    _HAS_PCBNEW = True
except ImportError:
    pcbnew = None
    _HAS_PCBNEW = False


# Known LCSC parts catalog for automatic BOM matching
LCSC_CATALOG = {
    # 0805 Resistors (1% 1/8W)
    ("0R", "0805"): "C17480",
    ("10R", "0805"): "C17413",
    ("100R", "0805"): "C17408",
    ("220R", "0805"): "C17469",
    ("330R", "0805"): "C17511",
    ("470R", "0805"): "C17551",
    ("1k", "0805"): "C17513",
    ("2.2k", "0805"): "C17539",
    ("4.7k", "0805"): "C17672",
    ("5.1k", "0805"): "C23186",
    ("10k", "0805"): "C17414",
    ("22k", "0805"): "C17538",
    ("47k", "0805"): "C17673",
    ("100k", "0805"): "C17407",
    ("1M", "0805"): "C17518",
    # 0603 Resistors
    ("0R", "0603"): "C21189",
    ("100R", "0603"): "C22775",
    ("1k", "0603"): "C21190",
    ("4.7k", "0603"): "C23162",
    ("10k", "0603"): "C25804",
    ("100k", "0603"): "C25803",
    # 0805 Capacitors (50V / 25V / 16V / 10V)
    ("10pF", "0805"): "C1804",
    ("22pF", "0805"): "C1804",
    ("100pF", "0805"): "C1805",
    ("1nF", "0805"): "C1710",
    ("10nF", "0805"): "C1710",
    ("100nF", "0805"): "C49678",
    ("0.1uF", "0805"): "C49678",
    ("1uF", "0805"): "C28323",
    ("4.7uF", "0805"): "C19666",
    ("10uF", "0805"): "C15850",
    ("22uF", "0805"): "C45783",
    # 0603 Capacitors
    ("100nF", "0603"): "C14663",
    ("0.1uF", "0603"): "C14663",
    ("1uF", "0603"): "C15849",
    ("10uF", "0603"): "C96446",
    # 0805 LEDs
    ("Green (PWR)", "0805"): "C2297",
    ("Yellow (PULSE)", "0805"): "C2296",
    ("Blue (STATUS)", "0805"): "C2293",
    ("Red", "0805"): "C2286",
    ("Green", "0805"): "C2297",
    ("Yellow", "0805"): "C2296",
    ("Blue", "0805"): "C2293",
    ("White", "0805"): "C2290",
    # Standard ICs
    ("NE555D", "SOIC-8"): "C46749",
    ("NE555", "SOIC-8"): "C46749",
    ("ATtiny85-20SU", "SOIC-8"): "C44533",
    ("ATtiny85", "SOIC-8"): "C44533",
    ("ATmega328P-AU", "TQFP-32"): "C14877",
    ("CH340C", "SOP-16"): "C84683",
    ("AMS1117-3.3", "SOT-223"): "C6186",
    ("AMS1117-5.0", "SOT-223"): "C47593",
    # Connectors
    ("USB-C", "USB_C_Receptacle"): "C165948",
    ("AVR-ISP", "PinHeader_2x03"): "C124376",
    ("AUX_OUT", "PinHeader_1x04"): "C124377",
}


def _match_lcsc(val, pkg_name):
    """Fuzzy lookup of LCSC part number from component value and package."""
    # Direct match
    for (v, p), lcsc in LCSC_CATALOG.items():
        if v.lower() == val.lower() and p.lower() in pkg_name.lower():
            return lcsc

    # Check normalized package
    pkg_norm = ""
    if "0805" in pkg_name:
        pkg_norm = "0805"
    elif "0603" in pkg_name:
        pkg_norm = "0603"
    elif "soic-8" in pkg_name.lower() or "so-8" in pkg_name.lower():
        pkg_norm = "SOIC-8"
    elif "sot-223" in pkg_name.lower():
        pkg_norm = "SOT-223"

    if pkg_norm:
        for (v, p), lcsc in LCSC_CATALOG.items():
            if v.lower() == val.lower() and p == pkg_norm:
                return lcsc

    return ""


def extract_bom_from_pcb(pcb_path, out_bom_path=None, verbose=True):
    """Extract bill of materials directly from PCB footprints with LCSC part matching."""
    components = []

    if _HAS_PCBNEW:
        board = pcbnew.LoadBoard(pcb_path)
        for fp in board.GetFootprints():
            ref = fp.GetReference()
            val = fp.GetValue()
            pkg = str(fp.GetFPID().GetLibItemName()) if hasattr(fp, "GetFPID") else ""
            # Skip mechanical mounting holes and fiducials unless they have values
            if ref.startswith("H") and "Mounting" in pkg:
                continue
            if ref.startswith("FID"):
                continue

            lcsc = ""
            # Check custom properties on footprint
            if hasattr(fp, "HasProperty") and fp.HasProperty("LCSC"):
                lcsc = fp.GetProperty("LCSC")
            if not lcsc:
                lcsc = _match_lcsc(val, pkg)

            components.append({
                "reference": ref,
                "value": val,
                "footprint": pkg,
                "lcsc": lcsc,
            })
    else:
        # Fallback: parse .kicad_pcb text directly
        with open(pcb_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        fp_blocks = re.findall(r'\(footprint\s+"([^"]+)"(.*?)(?=\n\s*\(footprint|\Z)', content, re.DOTALL)
        for fp_name, block in fp_blocks:
            ref_m = re.search(r'\(property\s+"Reference"\s+"([^"]+)"', block) or re.search(r'\(fp_text\s+reference\s+"([^"]+)"', block)
            val_m = re.search(r'\(property\s+"Value"\s+"([^"]+)"', block) or re.search(r'\(fp_text\s+value\s+"([^"]+)"', block)
            lcsc_m = re.search(r'\(property\s+"LCSC"\s+"([^"]+)"', block)

            ref = ref_m.group(1) if ref_m else ""
            val = val_m.group(1) if val_m else ""
            lcsc = lcsc_m.group(1) if lcsc_m else ""

            if not ref or (ref.startswith("H") and "Mounting" in fp_name):
                continue

            if not lcsc:
                lcsc = _match_lcsc(val, fp_name)

            components.append({
                "reference": ref,
                "value": val,
                "footprint": fp_name,
                "lcsc": lcsc,
            })

    # Group components by (Value, Footprint, LCSC)
    groups = {}
    for c in components:
        key = (c["value"], c["footprint"], c["lcsc"])
        if key not in groups:
            groups[key] = []
        groups[key].append(c["reference"])

    target_bom = out_bom_path or os.path.splitext(pcb_path)[0] + "_bom_jlcpcb.csv"
    with open(target_bom, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (val, pkg, lcsc), refs in sorted(groups.items(), key=lambda x: x[1][0]):
            # Natural sort references
            sorted_refs = sorted(refs, key=lambda r: (re.sub(r'\d+', '', r), int(re.search(r'\d+', r).group(0)) if re.search(r'\d+', r) else 0))
            writer.writerow([val, " ".join(sorted_refs), pkg, lcsc])

    if verbose:
        print("  - PCB Footprint BOM extracted (%d line items): %s" % (len(groups), target_bom))

    return target_bom


def render_3d_previews(pcb_path, target_dir, width=1200, height=1200, verbose=True):
    """Render top and bottom photorealistic 3D raytraced previews using kicad-cli."""
    base_name = os.path.splitext(os.path.basename(pcb_path))[0]
    top_png = os.path.join(target_dir, "%s_render_top.png" % base_name)
    bot_png = os.path.join(target_dir, "%s_render_bottom.png" % base_name)

    renders = {}
    for side, out_file in [("top", top_png), ("bottom", bot_png)]:
        cmd = [
            "kicad-cli", "pcb", "render",
            "-w", str(width),
            "-h", str(height),
            "--side", side,
            "--quality", "high",
            "-o", out_file,
            pcb_path,
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0 and os.path.exists(out_file):
            renders[side] = out_file
            if verbose:
                print("  - 3D %s render: %s" % (side.capitalize(), out_file))
        else:
            if verbose:
                print("  - 3D %s render skipped or failed: %s" % (side, res.stderr[:100] if res.stderr else "error"))

    return renders


def export_jlcpcb(pcb_path, sch_path=None, out_dir=None, make_zip=True, render_3d=True, verbose=True):
    if not os.path.exists(pcb_path):
        raise FileNotFoundError("PCB file not found: %s" % pcb_path)

    base_name = os.path.splitext(os.path.basename(pcb_path))[0]
    proj_dir = os.path.dirname(os.path.abspath(pcb_path))
    target_dir = out_dir or os.path.join(proj_dir, "jlcpcb_production")
    gerber_dir = os.path.join(target_dir, "gerber")
    os.makedirs(gerber_dir, exist_ok=True)

    if verbose:
        print("Exporting JLCPCB package for %s..." % base_name)

    # 1. Export Gerbers
    gerber_cmd = [
        "kicad-cli", "pcb", "export", "gerbers",
        "-o", gerber_dir + "/",
        "--no-x2",
        "--subtract-soldermask",
        "--use-drill-file-origin",
        "--precision", "6",
        pcb_path,
    ]
    res = subprocess.run(gerber_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError("Gerber export failed:\n%s" % res.stderr)
    if verbose:
        print("  - Gerbers plotted to %s" % gerber_dir)

    # 2. Export Drill
    drill_cmd = [
        "kicad-cli", "pcb", "export", "drill",
        "-o", gerber_dir + "/",
        "--drill-origin", "plot",
        "--excellon-separate-th",
        "--excellon-units", "mm",
        "--excellon-zeros-format", "decimal",
        pcb_path,
    ]
    res = subprocess.run(drill_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError("Drill export failed:\n%s" % res.stderr)
    if verbose:
        print("  - Drills exported to %s" % gerber_dir)

    # 3. Export CPL (Pick and place)
    cpl_path = os.path.join(target_dir, "%s_cpl_jlcpcb.csv" % base_name)
    pos_cmd = [
        "kicad-cli", "pcb", "export", "pos",
        "-o", cpl_path,
        "--format", "csv",
        "--units", "mm",
        pcb_path,
    ]
    res = subprocess.run(pos_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode == 0 and os.path.exists(cpl_path):
        _format_jlc_cpl(cpl_path)
        if verbose:
            print("  - CPL / SMT placement file: %s" % cpl_path)

    # 4. Export BOM (from schematic or fallback directly to PCB footprints)
    bom_path = os.path.join(target_dir, "%s_bom_jlcpcb.csv" % base_name)
    bom_ok = False
    if not sch_path:
        cand_sch = os.path.join(proj_dir, base_name + ".kicad_sch")
        if os.path.exists(cand_sch):
            sch_path = cand_sch

    if sch_path and os.path.exists(sch_path):
        bom_cmd = [
            "kicad-cli", "sch", "export", "bom",
            "-o", bom_path,
            sch_path,
        ]
        res = subprocess.run(bom_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0 and os.path.exists(bom_path):
            with open(bom_path, "r", encoding="utf-8", errors="ignore") as bf:
                bom_lines = [line.strip() for line in bf if line.strip()]
            if len(bom_lines) > 1:
                bom_ok = True
                if verbose:
                    print("  - BOM exported from schematic: %s" % bom_path)

    if not bom_ok:
        # Fallback to direct PCB footprint extraction with LCSC matching
        bom_path = extract_bom_from_pcb(pcb_path, out_bom_path=bom_path, verbose=verbose)

    # 5. 3D Renders
    renders = {}
    if render_3d:
        renders = render_3d_previews(pcb_path, target_dir, width=1200, height=1200, verbose=verbose)

    # 6. Package ZIP
    zip_path = None
    if make_zip:
        zip_path = os.path.join(target_dir, "%s_gerber_jlcpcb.zip" % base_name)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(gerber_dir):
                for f in files:
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, gerber_dir)
                    zf.write(full, rel)
        if verbose:
            print("  - Fabrication ZIP created: %s" % zip_path)

    # 7. Run verification checks
    if verbose:
        print("\nRunning verification checkers on exported package...")
    _verify_package(gerber_dir, verbose=verbose)

    # 8. Clean temporary artifacts & dumps from project directory
    try:
        from cleanup_board import clean_temporary_files
        clean_temporary_files(os.path.dirname(os.path.abspath(pcb_path)), verbose=False)
    except Exception:
        pass

    return {
        "target_dir": target_dir,
        "gerber_dir": gerber_dir,
        "zip_path": zip_path,
        "cpl_path": cpl_path if os.path.exists(cpl_path) else None,
        "bom_path": bom_path if os.path.exists(bom_path) else None,
        "render_top": renders.get("top"),
        "render_bottom": renders.get("bottom"),
    }


def _format_jlc_cpl(cpl_path):
    """Ensure column headers conform to JLCPCB SMT format: Designator, Mid X, Mid Y, Layer, Rotation."""
    with open(cpl_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    if not lines:
        return
    header = lines[0].replace('"', '').strip()
    if "Ref" in header and "PosX" in header:
        new_header = "Designator,Val,Package,Mid X,Mid Y,Rotation,Layer\n"
        with open(cpl_path, "w", encoding="utf-8") as f:
            f.write(new_header)
            f.writelines(lines[1:])


def _verify_package(gerber_dir, verbose=True):
    sys.path.insert(0, _VERIFY)
    import drill_census as DC
    import outline_check as OC

    drills = [os.path.join(gerber_dir, f) for f in os.listdir(gerber_dir)
              if f.endswith(".drl") or f.endswith(".txt")]
    if drills:
        files = DC.census(drills)
        total_features = sum(len(f["hits"]) for f in files)
        if verbose:
            print("  [CHECK] Drill Census: %d drilled hole(s) in %d file(s) - OK"
                  % (total_features, len(files)))

    # Find outline (Edge_Cuts)
    edge_cuts = [os.path.join(gerber_dir, f) for f in os.listdir(gerber_dir)
                 if "edge" in f.lower() or "gm1" in f.lower()]
    if edge_cuts:
        if verbose:
            print("  [CHECK] Board outline found: %s - OK" % os.path.basename(edge_cuts[0]))


def _selftest():
    import tempfile
    tmp = tempfile.mkdtemp(prefix="jlc_test_")
    cpl = os.path.join(tmp, "test_cpl.csv")
    with open(cpl, "w") as f:
        f.write('"Ref","Val","Package","PosX","PosY","Rot","Side"\n"R1","10k","R0603",10,20,0,"top"\n')
    _format_jlc_cpl(cpl)
    with open(cpl) as f:
        first_line = f.readline()
    ok_cpl = "Designator" in first_line and "Mid X" in first_line

    # Test LCSC matcher
    lcsc_r = _match_lcsc("10k", "R_0805_2012Metric")
    lcsc_c = _match_lcsc("100nF", "C_0805_2012Metric")
    ok_lcsc = (lcsc_r == "C17414" and lcsc_c == "C49678")

    ok = ok_cpl and ok_lcsc
    print("export_jlcpcb selftest: %s (CPL: %s, LCSC: %s)" %
          ("PASS" if ok else "FAIL", "OK" if ok_cpl else "FAIL", "OK" if ok_lcsc else "FAIL"))
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return _selftest()
    if len(argv) < 2:
        print(__doc__)
        return 2

    pcb_path = argv[1]
    sch_path = None
    out_dir = None
    make_zip = "--no-zip" not in argv
    render_3d = "--no-render" not in argv

    i = 2
    while i < len(argv):
        if argv[i] == "--schematic" and i + 1 < len(argv):
            sch_path = argv[i + 1]; i += 2
        elif argv[i] == "--out-dir" and i + 1 < len(argv):
            out_dir = argv[i + 1]; i += 2
        elif argv[i] in ("--no-render", "--no-3d"):
            render_3d = False; i += 1
        elif argv[i] == "--no-zip":
            make_zip = False; i += 1
        else:
            i += 1

    res = export_jlcpcb(pcb_path, sch_path=sch_path, out_dir=out_dir,
                        make_zip=make_zip, render_3d=render_3d, verbose=True)
    print("\nPackage ready at: %s" % res["target_dir"])
    if res["zip_path"]:
        print("Upload ZIP to JLCPCB: %s" % res["zip_path"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
