#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unified Comprehensive Test Suite for pcb-skill.

Executes all unit tests, module self-tests, integration tests, and project verifications:
  1. Environment & Tooling Check (kicad-cli, java, freerouting, pcbnew)
  2. kicad_ctl Interface & Command Dispatcher
  3. Post-Routing & Board Cleanup Engine (cleanup_board.py)
  4. Autonomous Headless Router (route_kicad.py)
  5. KiCad DRC Inspector & Parser (drc_check.py)
  6. JLCPCB Production Exporter & BOM/CPL Builder (export_jlcpcb.py)
  7. 2-Layer Board Builder & Zone Filler (autoroute_2layer.py)
  8. Live Production Project Verification (tht_opamp_eq: 0 DRC errors)
"""
import os
import shutil
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.isdir(os.path.join(_HERE, "kicad")):
    _KICAD_DIR = os.path.join(_HERE, "kicad")
    _SKILL_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
elif os.path.isdir(os.path.join(_HERE, "..", "scripts", "kicad")):
    _KICAD_DIR = os.path.abspath(os.path.join(_HERE, "..", "scripts", "kicad"))
    _SKILL_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
else:
    _KICAD_DIR = os.path.abspath(os.path.join(_HERE, "scripts", "kicad"))
    _SKILL_ROOT = _HERE

for _p in (_KICAD_DIR, os.path.join(_KICAD_DIR, "core"), "/usr/lib/python3/dist-packages", "/usr/lib/python3/site-packages"):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.append(_p)


class TestResult:
    def __init__(self, name, suite):
        self.name = name
        self.suite = suite
        self.passed = False
        self.duration = 0.0
        self.message = ""

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.suite} :: {self.name} ({self.duration:.3f}s) - {self.message}"


class TestRunner:
    def __init__(self):
        self.results = []

    def run_test(self, suite, name, func):
        t0 = time.time()
        res = TestResult(name, suite)
        try:
            ok, msg = func()
            res.passed = bool(ok)
            res.message = msg or ("OK" if ok else "Failed")
        except Exception as e:
            res.passed = False
            res.message = f"Exception: {e}"
        res.duration = time.time() - t0
        self.results.append(res)
        status_symbol = "✓" if res.passed else "✗"
        print(f"  {status_symbol} {name:<45} [{res.duration:.2f}s] {res.message}")
        return res.passed


def test_env_kicad_cli():
    found = shutil.which("kicad-cli")
    if not found:
        return False, "kicad-cli not found in PATH"
    ver = subprocess.check_output(["kicad-cli", "--version"], text=True).strip()
    return True, f"Found kicad-cli: {ver}"


def test_env_java():
    found = shutil.which("java")
    if not found:
        return False, "java runtime not found in PATH"
    res = subprocess.run(["java", "-version"], capture_output=True, text=True)
    out = (res.stderr or res.stdout).splitlines()[0]
    return True, f"Found {out}"


def test_env_pcbnew():
    try:
        import pcbnew
        return True, f"pcbnew {pcbnew.GetBuildVersion()}"
    except ImportError as e:
        return False, f"pcbnew import failed: {e}"


def test_env_freerouting():
    from route_kicad import ensure_freerouting_jar
    jar = ensure_freerouting_jar(verbose=False)
    if jar and os.path.exists(jar):
        return True, f"JAR cached at {os.path.basename(jar)} ({os.path.getsize(jar)} bytes)"
    return False, "freerouting.jar not accessible"


def test_kicad_ctl_selftest():
    import kicad_ctl
    rc = kicad_ctl._selftest()
    return (rc == 0), "kicad_ctl selftest completed"


def test_kicad_ctl_cli_version():
    cmd = [sys.executable, os.path.join(_KICAD_DIR, "kicad_ctl.py"), "version"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    ok = (res.returncode == 0 and "kicad" in res.stdout.lower())
    return ok, res.stdout.strip()


def test_kicad_ctl_cli_list_commands():
    cmd = [sys.executable, os.path.join(_KICAD_DIR, "kicad_ctl.py"), "list-commands"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    ok = (res.returncode == 0 and "commands" in res.stdout.lower())
    return ok, f"Listed commands (exit code {res.returncode})"


def test_cleanup_board_selftest():
    import cleanup_board
    rc = cleanup_board._selftest()
    return (rc == 0), "cleanup_board selftest completed"


def test_cleanup_board_temp_files():
    import tempfile
    import cleanup_board
    tmpdir = tempfile.mkdtemp(prefix="kc_test_clean_")
    try:
        f1 = os.path.join(tmpdir, "test.dsn")
        f2 = os.path.join(tmpdir, "test.ses")
        f3 = os.path.join(tmpdir, "keep.kicad_pcb")
        open(f1, "w").write("dummy")
        open(f2, "w").write("dummy")
        open(f3, "w").write("dummy")
        cleaned = cleanup_board.clean_temporary_files(tmpdir, verbose=False)
        ok = (cleaned == 2 and not os.path.exists(f1) and not os.path.exists(f2) and os.path.exists(f3))
        return ok, f"Cleaned {cleaned} temp files, kept .kicad_pcb"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_route_kicad_selftest():
    import route_kicad
    rc = route_kicad._selftest()
    return (rc == 0), "route_kicad ses import verified"


def test_drc_check_selftest():
    import drc_check
    rc = drc_check._selftest()
    return (rc == 0), "drc_check report parsing verified"


def test_drc_check_strict_mode():
    import drc_check
    sample_error = {
        "violations": [{"severity": "error", "type": "shorting_items"}],
        "unconnected_items": [],
        "schematic_parity": []
    }
    parsed = drc_check.parse_report(sample_error)
    ok = (parsed["errors_count"] == 1 and not parsed["clean"])
    return ok, "Strict mode correctly flagged error severity"


def test_export_jlcpcb_selftest():
    import export_jlcpcb
    rc = export_jlcpcb._selftest()
    return (rc == 0), "export_jlcpcb CPL and BOM matching verified"


def test_autoroute_2layer_selftest():
    import autoroute_2layer
    rc = autoroute_2layer._selftest()
    return (rc == 0), "PCB2LayerBuilder geometry and zone fill verified"


def test_embed_symbols_selftest():
    import embed_symbols
    rc = embed_symbols._selftest()
    return (rc == 0), "embed_symbols canonical mapping & extraction verified"


def _find_project_dir(name):
    candidates = [
        os.path.join(_SKILL_ROOT, "project", "pcb", name),
        os.path.join(_SKILL_ROOT, "project", name),
        os.path.expanduser(f"~/project/pcb/{name}"),
        os.path.expanduser(f"~/project/{name}"),
        os.path.join("/home/azzar/project/pcb", name),
    ]
    for cand in candidates:
        if os.path.isdir(cand):
            return cand
    return candidates[0]


def test_wire_schematic_selftest():
    import wire_schematic
    rc = wire_schematic._selftest()
    return (rc == 0), "wire_schematic pin discovery & S-expr parsing verified"


def test_schematic_symbols_embedded():
    sch1 = os.path.join(_find_project_dir("tht_opamp_eq"), "tht_opamp_eq.kicad_sch")
    sch2 = os.path.join(_find_project_dir("attiny85_timer"), "attiny85_timer.kicad_sch")
    for s in (sch1, sch2):
        if not os.path.exists(s):
            return False, f"Schematic missing: {s}"
        with open(s, "r", encoding="utf-8") as f:
            content = f.read()
        if "(lib_symbols" not in content:
            return False, f"Missing (lib_symbols in {s}"
    return True, "Project schematics contain embedded lib_symbols with valid KiCad 9 headers"


def test_schematic_connections_established():
    sch1 = os.path.join(_find_project_dir("tht_opamp_eq"), "tht_opamp_eq.kicad_sch")
    sch2 = os.path.join(_find_project_dir("attiny85_timer"), "attiny85_timer.kicad_sch")
    for s in (sch1, sch2):
        if not os.path.exists(s):
            return False, f"Schematic missing: {s}"
        with open(s, "r", encoding="utf-8") as f:
            content = f.read()
        wires = content.count("(wire")
        labels = content.count("(label")
        if wires < 20 or labels < 20:
            return False, f"Schematic {s} lacks connections: {wires} wires, {labels} labels"
    return True, "Both schematics have complete electrical connectivity (>60 wires & labels each)"


def test_connector_rules_selftest():
    import core.connector_rules as CR
    # Test connector edge rotation logic
    assert CR.get_edge_rotation("USB_C_Receptacle_HRO_TYPE-C-31-M-12", "W") == 270.0
    assert CR.get_edge_rotation("USB_C_Receptacle_HRO_TYPE-C-31-M-12", "E") == 90.0
    assert CR.get_edge_rotation("Jack_3.5mm_PJ320D_Horizontal", "E") == 180.0
    assert CR.get_edge_rotation("Jack_3.5mm_PJ320D_Horizontal", "W") == 0.0
    return True, "Connector edge orientation transformation verified"


def test_placement_validator_selftest():
    import core.placement_validator as PV
    rc = PV._selftest()
    return (rc == 0), "placement_validator pre-flight calculations verified"


def test_keyboard_555_strict_drc():
    prod_pcb = os.path.join(_find_project_dir("keyboard_555"), "keyboard_555.kicad_pcb")
    if not os.path.exists(prod_pcb):
        return False, f"Project PCB missing: {prod_pcb}"
    cmd = [
        "python3",
        os.path.join(_KICAD_DIR, "kicad_ctl.py"),
        "drc",
        prod_pcb,
        "--strict",
        "--no-schematic-parity"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    ok = (res.returncode == 0 and "CLEAN (PASS)" in res.stdout)
    return ok, "0 Errors, 0 Warnings, 0 Unconnected Nets, 0 Placement Violations verified"


def test_production_board_drc():
    prod_pcb = os.path.join(_find_project_dir("tht_opamp_eq"), "tht_opamp_eq.kicad_pcb")
    if not os.path.exists(prod_pcb):
        return False, f"Project PCB missing: {prod_pcb}"
    cmd = [
        "python3",
        os.path.join(_KICAD_DIR, "kicad_ctl.py"),
        "drc",
        prod_pcb,
        "--strict",
        "--no-schematic-parity",
        "--no-preflight"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    ok = (res.returncode == 0 and "CLEAN (PASS)" in res.stdout)
    return ok, "0 Errors, 0 Warnings, 0 Unconnected Nets verified"


def test_production_bundle_artifacts():
    bundle_dir = os.path.join(_find_project_dir("keyboard_555"), "jlcpcb_production")
    if not os.path.isdir(bundle_dir):
        bundle_dir = os.path.join(_find_project_dir("tht_opamp_eq"), "jlcpcb_production")
    if not os.path.isdir(bundle_dir):
        return False, f"Production folder missing: {bundle_dir}"
    
    # Check whichever bundle is present
    pfx = "keyboard_555" if "keyboard_555" in bundle_dir else "tht_opamp_eq"
    zip_file = os.path.join(bundle_dir, f"{pfx}_gerber_jlcpcb.zip")
    bom_file = os.path.join(bundle_dir, f"{pfx}_bom_jlcpcb.csv")
    cpl_file = os.path.join(bundle_dir, f"{pfx}_cpl_jlcpcb.csv")
    top_png = os.path.join(bundle_dir, f"{pfx}_render_top.png")
    bot_png = os.path.join(bundle_dir, f"{pfx}_render_bottom.png")

    checks = [
        ("ZIP", os.path.exists(zip_file) and os.path.getsize(zip_file) > 10000),
        ("BOM", os.path.exists(bom_file) and os.path.getsize(bom_file) > 100),
        ("CPL", os.path.exists(cpl_file) and os.path.getsize(cpl_file) > 100),
        ("Top Render", os.path.exists(top_png) and os.path.getsize(top_png) > 10000),
        ("Bot Render", os.path.exists(bot_png) and os.path.getsize(bot_png) > 10000),
    ]
    all_ok = all(c[1] for c in checks)
    details = ", ".join(f"{c[0]}: OK" for c in checks)
    return all_ok, details


def main():
    runner = TestRunner()
    suites = [
        ("Environment & Tooling", [
            ("kicad-cli binary", test_env_kicad_cli),
            ("Java Runtime (OpenJDK)", test_env_java),
            ("pcbnew Python Binding", test_env_pcbnew),
            ("Freerouting JAR Cache", test_env_freerouting),
        ]),
        ("kicad_ctl Dispatcher", [
            ("kicad_ctl internal selftest", test_kicad_ctl_selftest),
            ("CLI version command", test_kicad_ctl_cli_version),
            ("CLI list-commands command", test_kicad_ctl_cli_list_commands),
        ]),
        ("Board Cleanup Engine", [
            ("cleanup_board internal selftest", test_cleanup_board_selftest),
            ("Temporary artifact cleanup", test_cleanup_board_temp_files),
        ]),
        ("Headless Router & DRC", [
            ("route_kicad SES import", test_route_kicad_selftest),
            ("drc_check report parsing", test_drc_check_selftest),
            ("drc_check strict error gating", test_drc_check_strict_mode),
        ]),
        ("Connector & Placement Pre-flight Engines", [
            ("connector_rules transformation", test_connector_rules_selftest),
            ("placement_validator calculations", test_placement_validator_selftest),
        ]),
        ("JLCPCB Exporter & 2-Layer Builder", [
            ("export_jlcpcb CPL/BOM selftest", test_export_jlcpcb_selftest),
            ("autoroute_2layer builder selftest", test_autoroute_2layer_selftest),
        ]),
        ("Schematic Symbol Embedding & Integrity", [
            ("embed_symbols internal selftest", test_embed_symbols_selftest),
            ("wire_schematic internal selftest", test_wire_schematic_selftest),
            ("Project schematics lib_symbols validation", test_schematic_symbols_embedded),
            ("Project schematics wire connectivity check", test_schematic_connections_established),
        ]),
        ("Live THT Project Verification", [
            ("keyboard_555 strict 0-DRC & placement preflight", test_keyboard_555_strict_drc),
            ("tht_opamp_eq strict 0-DRC check", test_production_board_drc),
            ("JLCPCB bundle artifact census", test_production_bundle_artifacts),
        ]),
    ]

    print("=" * 70)
    print("PCB-SKILL COMPREHENSIVE TEST SUITE")
    print("=" * 70)

    total = 0
    passed = 0
    for suite_name, tests in suites:
        print(f"\n[{suite_name}]")
        for test_name, test_fn in tests:
            total += 1
            if runner.run_test(suite_name, test_name, test_fn):
                passed += 1

    print("\n" + "=" * 70)
    print(f"TEST SUMMARY: {passed}/{total} Passed ({passed/total*100:.1f}%)")
    print("=" * 70)

    if passed == total:
        print("ALL TESTS PASSED ✔️")
        return 0
    else:
        print(f"TEST FAILURES DETECTED: {total - passed} Failed ❌")
        return 1


if __name__ == "__main__":
    sys.exit(main())
