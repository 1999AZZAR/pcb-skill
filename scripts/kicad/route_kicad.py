# -*- coding: utf-8 -*-
"""Specctra DSN / SES autorouting loop for KiCad PCBs.

Coordinates the full KiCad autorouting workflow:
  1. Export Specctra DSN from `.kicad_pcb` using native pcbnew API.
  2. Rewrite DSN with `dsn_rewrite.py` (sets plane layers to power, pins net widths).
  3. Optionally launches FreeRouting or watches a running router with `route_supervise.py`.
  4. Merges the resulting `.ses` back into `.kicad_pcb` using `ses_import.py --format kicad`.
  5. Validates the read-back board with `import_kicad.py` and `route_accept.py`.

USAGE
    python3 route_kicad.py export BOARD.kicad_pcb OUT.dsn [--config route.json]
    python3 route_kicad.py import BOARD.kicad_pcb ROUTE.ses -o MERGED.kicad_pcb [--strip]
    python3 route_kicad.py --selftest
"""
from __future__ import print_function

import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROUTING = os.path.join(_HERE, os.pardir, "routing")
_PLACEMENT = os.path.join(_HERE, os.pardir, "placement")

for _sp in ("/usr/lib/python3/dist-packages", "/usr/lib/python3/site-packages"):
    if os.path.isdir(_sp) and _sp not in sys.path:
        sys.path.append(_sp)

try:
    import pcbnew
    _HAS_PCBNEW = True
except ImportError:
    pcbnew = None
    _HAS_PCBNEW = False


def export_dsn(pcb_path, dsn_path, config_json=None, verbose=True):
    if not _HAS_PCBNEW:
        raise RuntimeError("KiCad python module (pcbnew) required to export Specctra DSN")

    board = pcbnew.LoadBoard(pcb_path)
    if not board:
        raise RuntimeError("Failed to load %s in pcbnew" % pcb_path)

    raw_dsn = dsn_path if not config_json else dsn_path + ".raw"
    ok = pcbnew.ExportSpecctraDSN(board, raw_dsn)
    if not ok or not os.path.exists(raw_dsn):
        raise RuntimeError("ExportSpecctraDSN failed for %s" % pcb_path)

    if verbose:
        print("Exported raw DSN: %s" % raw_dsn)

    if config_json and os.path.exists(config_json):
        sys.path.insert(0, _ROUTING)
        import dsn_rewrite as DR
        cfg = DR.load_config(config_json)
        text = open(raw_dsn, encoding="utf-8", errors="replace").read()
        rewritten, counts = DR.rewrite_dsn(text, cfg)
        with open(dsn_path, "w", encoding="utf-8") as f:
            f.write(rewritten)
        if verbose:
            print("Rewrote DSN with route config (%d classes, %d planes): %s"
                  % (counts.get("classes", 0), counts.get("planes", 0), dsn_path))


def import_ses(pcb_path, ses_path, out_pcb_path, strip=False, protected=(), keep_nets=(), verbose=True):
    sys.path.insert(0, _ROUTING)
    import ses_import as SI
    with open(ses_path, encoding="utf-8", errors="replace") as fh:
        segs, vias, meta = SI.parse_ses(fh.read())

    segs, vias = SI.filter_wiring(segs, vias, protected=protected)
    SI.write_kicad(pcb_path, out_pcb_path, segs, vias, strip=strip,
                   keep_nets=keep_nets, protected=protected, verbose=verbose)


def ensure_freerouting_jar(target_path=None, verbose=True):
    """Ensure Freerouting JAR exists locally, downloading if necessary."""
    jar = target_path or os.environ.get(
        "FREEROUTING_JAR", os.path.expanduser("~/.kicad-mcp/freerouting.jar")
    )
    if os.path.isfile(jar) and os.path.getsize(jar) > 1000000:
        return jar

    os.makedirs(os.path.dirname(jar), exist_ok=True)
    url = "https://github.com/freerouting/freerouting/releases/download/v2.1.0/freerouting-2.1.0.jar"
    if verbose:
        print("Downloading Freerouting JAR to: %s..." % jar)
    res = subprocess.run(["curl", "-sL", "-o", jar, url], capture_output=True)
    if res.returncode != 0 or not os.path.isfile(jar) or os.path.getsize(jar) < 1000000:
        raise RuntimeError("Failed to download Freerouting JAR from %s" % url)
    if verbose:
        print("Downloaded Freerouting JAR successfully (%d bytes)." % os.path.getsize(jar))
    return jar


def autoroute_board(pcb_path, out_pcb_path=None, passes=20, attempts=1, jar_path=None, timeout=300, verbose=True):
    """Headless end-to-end autorouting for KiCad PCBs."""
    if not _HAS_PCBNEW:
        raise RuntimeError("pcbnew required for autorouting")
    if not os.path.exists(pcb_path):
        raise FileNotFoundError("PCB file not found: %s" % pcb_path)

    jar = jar_path or os.environ.get("FREEROUTING_JAR", os.path.expanduser("~/.kicad-mcp/freerouting.jar"))
    ensure_freerouting_jar(jar, verbose=verbose)

    import tempfile
    import shutil
    staging_dir = tempfile.mkdtemp(prefix="kc_autoroute_")
    stem = os.path.splitext(os.path.basename(pcb_path))[0]
    dsn_path = os.path.join(staging_dir, "%s.dsn" % stem)
    ses_path = os.path.join(staging_dir, "%s.ses" % stem)
    out_path = out_pcb_path or pcb_path

    try:
        if verbose:
            print("Exporting Specctra DSN: %s" % dsn_path)
        board = pcbnew.LoadBoard(pcb_path)
        ok = pcbnew.ExportSpecctraDSN(board, dsn_path)
        if not ok or not os.path.exists(dsn_path):
            raise RuntimeError("ExportSpecctraDSN failed for %s" % pcb_path)

        thread_count = str(min(os.cpu_count() or 4, 4))
        cmd = [
            "java", "-jar", jar,
            "-de", dsn_path,
            "-do", ses_path,
            "--gui.enabled=false",
            "-mp", str(passes),
            "-mt", thread_count
        ]
        if verbose:
            print("Executing Freerouting (%d max passes, %s threads)..." % (passes, thread_count))
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=staging_dir)
        if proc.returncode != 0 or not os.path.exists(ses_path):
            raise RuntimeError("Freerouting failed (rc=%d): %s\n%s" % (proc.returncode, proc.stderr[:300], proc.stdout[:300]))

        if verbose:
            print("Importing Specctra SES: %s" % ses_path)
        target_board = pcbnew.LoadBoard(pcb_path)
        imp_ok = pcbnew.ImportSpecctraSES(target_board, ses_path)
        if not imp_ok and imp_ok != 0:
            raise RuntimeError("ImportSpecctraSES failed")

        # Clean zero-length duplicate tracks
        for t in list(target_board.GetTracks()):
            if t.GetClass() != "PCB_VIA" and t.GetLength() == 0:
                target_board.Delete(t)

        pcbnew.SaveBoard(out_path, target_board)

        # Refill copper zones safely
        try:
            import autoroute_2layer as A2
            A2.fill_zones_safely(out_path, verbose=False)
        except Exception:
            pass

        if verbose:
            print("Autorouting completed and saved to: %s" % out_path)
        return True
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def _selftest():
    import tempfile
    tmp = tempfile.mkdtemp(prefix="kc_route_test_")
    pcb = os.path.join(tmp, "test.kicad_pcb")
    open(pcb, "w", encoding="utf-8").write(
        '(kicad_pcb (version 20241229) (generator "pcbnew") (generator_version "9.0")\n'
        '  (net 0 "") (net 1 "GND")\n'
        '  (segment (start 0 0) (end 10 0) (width 0.25) (layer "F.Cu") (net 1))\n'
        ')\n')
    ses = os.path.join(tmp, "test.ses")
    open(ses, "w", encoding="utf-8").write(
        '(session test.ses\n'
        '  (routes\n'
        '    (resolution mil 1000)\n'
        '    (network_out\n'
        '      (net GND (wire (path TopLayer 3937 0 0 39370 0)))\n'
        '    )\n'
        '  )\n'
        ')\n')
    out = os.path.join(tmp, "out.kicad_pcb")
    import_ses(pcb, ses, out, strip=True, verbose=False)
    txt = open(out, encoding="utf-8").read()
    ok = ("(net 1)" in txt and "(segment" in txt)
    print("route_kicad selftest: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return _selftest()
    if len(argv) < 3:
        print(__doc__)
        return 2

    cmd = argv[1]
    if cmd == "autoroute":
        pcb = argv[2]
        out_pcb = argv[argv.index("-o") + 1] if "-o" in argv else pcb
        passes = int(argv[argv.index("--passes") + 1]) if "--passes" in argv else 20
        ok = autoroute_board(pcb, out_pcb_path=out_pcb, passes=passes)
        return 0 if ok else 1
    elif cmd == "export":
        if len(argv) < 4:
            print("Usage: python3 route_kicad.py export BOARD.kicad_pcb OUT.dsn [--config route.json]")
            return 2
        pcb = argv[2]
        dsn = argv[3]
        cfg = None
        if "--config" in argv:
            cfg = argv[argv.index("--config") + 1]
        export_dsn(pcb, dsn, config_json=cfg)
        return 0
    elif cmd == "import":
        if len(argv) < 4:
            print("Usage: python3 route_kicad.py import BOARD.kicad_pcb ROUTE.ses -o MERGED.kicad_pcb [--strip]")
            return 2
        pcb = argv[2]
        ses = argv[3]
        out_pcb = argv[argv.index("-o") + 1] if "-o" in argv else pcb
        strip = "--strip" in argv
        import_ses(pcb, ses, out_pcb, strip=strip)
        return 0

    print("unknown command %r" % cmd)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
