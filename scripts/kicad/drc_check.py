# -*- coding: utf-8 -*-
"""Headless DRC check and report parser for KiCad PCBs.

Runs `kicad-cli pcb drc --format json` and formats the results into actionable
findings, grouped by severity and violation type.

USAGE
    python3 drc_check.py BOARD.kicad_pcb [--output drc_report.json] [--strict]
    python3 drc_check.py --selftest
"""
from __future__ import print_function

import json
import os
import subprocess
import sys
import tempfile


def run_drc(pcb_path, output_json=None, schematic_parity=True):
    if not os.path.exists(pcb_path):
        raise FileNotFoundError("PCB file not found: %s" % pcb_path)

    temp_out = output_json or tempfile.mktemp(suffix=".json", prefix="kicad_drc_")
    cmd = [
        "kicad-cli", "pcb", "drc",
        "--format", "json",
        "--units", "mm",
        "--severity-all",
        "-o", temp_out,
    ]
    if schematic_parity:
        cmd.append("--schematic-parity")
    cmd.append(pcb_path)

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if not os.path.exists(temp_out):
        raise RuntimeError("kicad-cli pcb drc failed: %s\n%s" % (res.stdout, res.stderr))

    with open(temp_out, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not output_json and os.path.exists(temp_out):
        try:
            os.remove(temp_out)
        except Exception:
            pass

    return parse_report(data)


def parse_report(data):
    violations = data.get("violations", [])
    unconnected = data.get("unconnected_items", [])
    parity = data.get("schematic_parity", [])

    errors = [v for v in violations if v.get("severity") == "error"]
    warnings = [v for v in violations if v.get("severity") == "warning"]

    categories = {}
    for v in violations:
        t = v.get("type", "unknown")
        categories[t] = categories.get(t, 0) + 1

    summary = {
        "errors_count": len(errors),
        "warnings_count": len(warnings),
        "unconnected_count": len(unconnected),
        "parity_issues_count": len(parity),
        "categories": categories,
        "errors": errors,
        "warnings": warnings,
        "unconnected": unconnected,
        "parity": parity,
        "clean": (len(errors) == 0 and len(unconnected) == 0 and len(parity) == 0),
    }
    return summary


def format_summary(res):
    lines = []
    lines.append("=" * 70)
    lines.append("KICAD DRC REPORT: %s" % ("CLEAN (PASS)" if res["clean"] else "VIOLATIONS DETECTED (FAIL)"))
    lines.append("=" * 70)
    lines.append("  Errors           : %d" % res["errors_count"])
    lines.append("  Warnings         : %d" % res["warnings_count"])
    lines.append("  Unconnected Nets : %d" % res["unconnected_count"])
    lines.append("  Schematic Parity : %d" % res["parity_issues_count"])
    if res["categories"]:
        lines.append("  Categories       :")
        for cat, cnt in sorted(res["categories"].items()):
            lines.append("    - %-24s: %d" % (cat, cnt))

    if res["errors"]:
        lines.append("\nERRORS (must fix):")
        for idx, e in enumerate(res["errors"][:15], 1):
            desc = e.get("description", "")
            items = ", ".join(it.get("description", "") for it in e.get("items", []))
            lines.append("  %d. [%s] %s (%s)" % (idx, e.get("type"), desc, items))

    if res["unconnected"]:
        lines.append("\nUNCONNECTED ITEMS:")
        for idx, u in enumerate(res["unconnected"][:10], 1):
            lines.append("  %d. %s" % (idx, u.get("description", "")))

    if res["parity"]:
        lines.append("\nSCHEMATIC PARITY DIFFERENCES:")
        for idx, p in enumerate(res["parity"][:10], 1):
            lines.append("  %d. %s" % (idx, p.get("description", "")))

    return "\n".join(lines)


def _selftest():
    sample = {
        "kicad_version": "9.0.2",
        "violations": [
            {"severity": "error", "type": "clearance", "description": "Track clearance"},
            {"severity": "warning", "type": "silk_over_copper", "description": "Silkscreen overlap"},
        ],
        "unconnected_items": [],
        "schematic_parity": [],
    }
    parsed = parse_report(sample)
    ok = (parsed["errors_count"] == 1 and parsed["warnings_count"] == 1 and not parsed["clean"])
    print("drc_check selftest: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return _selftest()
    if len(argv) < 2:
        print(__doc__)
        return 2

    pcb_path = argv[1]
    out_json = None
    if "-o" in argv:
        out_json = argv[argv.index("-o") + 1]
    elif "--output" in argv:
        out_json = argv[argv.index("--output") + 1]

    strict = "--strict" in argv
    check_parity = "--no-schematic-parity" not in argv
    res = run_drc(pcb_path, output_json=out_json, schematic_parity=check_parity)
    print(format_summary(res))

    if strict and (res["errors_count"] > 0 or res["unconnected_count"] > 0):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
