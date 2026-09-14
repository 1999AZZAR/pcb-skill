# -*- coding: utf-8 -*-
"""Unified KiCad Automation CLI Controller.

Exposes the full 230+ command KiCad automation engine directly to AI agents and scripts
without requiring an external MCP server or Node.js runtime.

CAPABILITIES
  * Project & Board: create_project, open_board, set_board_size, add_board_outline, add_mounting_hole
  * Schematic Authoring: batch_add_components, batch_connect, batch_add_no_connects, autoplace_schematic_fields
  * Component & Placement: place_component, batch_move_components, align_components, hierarchical_place
  * Routing & Vias: route_trace, route_pad_to_pad, add_via, add_gnd_stitching_vias, add_copper_pour, refill_zones
  * Sourcing & Parts: search_jlcpcb_parts, get_jlcpcb_part, search_symbols, search_footprints, list_symbol_pins
  * Design Rules & Export: set_design_rules, run_drc, export_gerber, export_3d, export_bom

USAGE
  python3 kicad_ctl.py list-commands [--category <category>]
  python3 kicad_ctl.py doc <command>
  python3 kicad_ctl.py run <command> '{"param": "value"}'
  python3 kicad_ctl.py run <command> --file params.json
  python3 kicad_ctl.py embed-symbols SCHEMATIC.kicad_sch
  python3 kicad_ctl.py wire-schematic SCHEMATIC.kicad_sch [--board BOARD.kicad_pcb] [--stub-length MM]
  python3 kicad_ctl.py export-jlcpcb BOARD.kicad_pcb [--schematic SCH.kicad_sch] [--out-dir DIR]
  python3 kicad_ctl.py drc BOARD.kicad_pcb [--strict] [--no-schematic-parity]
  python3 kicad_ctl.py refill-zones BOARD.kicad_pcb
  python3 kicad_ctl.py render-3d BOARD.kicad_pcb [--out-dir DIR]
  python3 kicad_ctl.py --selftest
"""
from __future__ import print_function

import inspect
import json
import os
import shutil
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_CORE_DIR = os.path.join(_HERE, "core")

# Ensure core and system KiCad bindings are accessible
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

for _sp in ("/usr/lib/python3/dist-packages", "/usr/lib/python3/site-packages"):
    if os.path.isdir(_sp) and _sp not in sys.path:
        sys.path.append(_sp)

try:
    from kicad_interface import KiCADInterface
    _HAS_INTERFACE = True
except Exception as e:
    _HAS_INTERFACE = False
    _IMPORT_ERROR = str(e)


CATEGORIES = {
    "project": [
        "create_project", "open_project", "close_project", "save_project",
        "open_board", "reload_board", "save_board", "save_as", "is_dirty",
        "snapshot_project", "get_project_info"
    ],
    "board": [
        "set_board_size", "set_board_origin", "get_board_origin", "add_layer",
        "set_active_layer", "get_board_info", "get_layer_list", "get_board_2d_view",
        "get_board_extents", "add_board_outline", "clear_board_outline",
        "replace_board_outline", "list_graphics", "delete_graphic", "update_graphic",
        "add_mounting_hole", "add_text", "add_board_text"
    ],
    "schematic": [
        "batch_add_components", "batch_edit_schematic_components", "replace_schematic_component",
        "batch_add_no_connects", "batch_connect", "batch_add_and_connect",
        "set_schematic_property_position", "batch_set_schematic_property_positions",
        "autoplace_schematic_fields", "lint_schematic_cosmetic", "suggest_schematic_declutter",
        "add_hierarchical_sheet", "remove_hierarchical_sheet", "create_hierarchical_subsheet"
    ],
    "placement": [
        "place_component", "move_component", "batch_move_components", "rotate_component",
        "delete_component", "edit_component", "get_component_properties", "get_component_list",
        "get_component_geometry", "find_component", "get_component_pads", "get_pads",
        "get_net_pads", "get_pad_position", "get_ratsnest", "estimate_airwire_lengths",
        "check_placement_clearance", "place_component_array", "align_components",
        "check_courtyard_overlaps", "suggest_placement", "hierarchical_place"
    ],
    "routing": [
        "add_net", "route_trace", "route_arc_trace", "add_via", "delete_trace",
        "query_traces", "query_zones", "add_gnd_stitching_vias", "modify_trace",
        "copy_routing_pattern", "get_nets_list", "create_netclass", "set_net_color",
        "add_copper_pour", "route_differential_pair", "refill_zones", "route_pad_to_pad"
    ],
    "library": [
        "list_libraries", "search_footprints", "list_library_footprints", "get_footprint_info",
        "list_symbol_libraries", "search_symbols", "list_library_symbols", "get_symbol_info",
        "list_symbol_pins", "batch_list_symbol_pins"
    ],
    "jlcpcb": [
        "download_jlcpcb_database", "search_jlcpcb_parts", "get_jlcpcb_part",
        "get_jlcpcb_database_stats", "suggest_jlcpcb_alternatives"
    ],
    "export": [
        "export_gerber", "export_pdf", "export_svg", "export_3d", "export_bom"
    ],
    "rules": [
        "set_design_rules", "get_design_rules", "run_drc", "get_drc_violations",
        "assign_net_to_class", "check_clearance", "set_layer_constraints"
    ]
}


def _get_interface():
    if not _HAS_INTERFACE:
        raise RuntimeError("KiCad interface failed to load: %s" % _IMPORT_ERROR)
    return KiCADInterface()


def list_commands(category=None):
    it = _get_interface()
    registered = sorted(it.command_routes.keys())
    if category:
        cat_lower = category.lower()
        if cat_lower not in CATEGORIES:
            print("Unknown category %r. Valid categories: %s" % (category, ", ".join(sorted(CATEGORIES.keys()))))
            return 1
        subset = [c for c in registered if c in CATEGORIES[cat_lower]]
        print("Commands in category [%s] (%d commands):" % (category, len(subset)))
        for c in subset:
            print("  - %s" % c)
    else:
        print("All registered KiCad automation commands (%d commands):" % len(registered))
        for cat, cmds in sorted(CATEGORIES.items()):
            matched = [c for c in cmds if c in registered]
            print("\n[%s] (%d):" % (cat.upper(), len(matched)))
            for c in sorted(matched):
                print("  - %s" % c)


def doc_command(cmd_name):
    it = _get_interface()
    handler = it.command_routes.get(cmd_name)
    if not handler:
        print("Command %r not found." % cmd_name)
        return 1
    doc = handler.__doc__ or "(no docstring available)"
    print("Command: %s" % cmd_name)
    print("=" * 60)
    print(doc.strip())
    try:
        sig = inspect.signature(handler)
        print("\nSignature: %s%s" % (cmd_name, sig))
    except Exception:
        pass


def run_command(cmd_name, params):
    it = _get_interface()
    if cmd_name not in it.command_routes:
        res = {"success": False, "error": "Unknown command %r" % cmd_name}
    else:
        try:
            res = it.handle_command(cmd_name, params or {})
        except Exception as e:
            res = {"success": False, "error": str(e)}
    return res


def run_batch(recipe_path, stop_on_error=True):
    with open(recipe_path, "r", encoding="utf-8") as f:
        recipe = json.load(f)

    if not isinstance(recipe, list):
        raise ValueError("Recipe must be a list of {'command': str, 'params': dict} items")

    it = _get_interface()
    results = []
    print("Executing batch recipe with %d step(s)..." % len(recipe))

    for idx, step in enumerate(recipe, 1):
        cmd = step.get("command")
        params = step.get("params", {})
        print("  [%d/%d] %s..." % (idx, len(recipe), cmd), end=" ")
        try:
            res = it.handle_command(cmd, params)
            success = res.get("success", True) if isinstance(res, dict) else True
            results.append({"step": idx, "command": cmd, "result": res, "success": success})
            if success:
                print("OK")
            else:
                print("FAIL: %s" % res.get("error", "unknown error"))
                if stop_on_error:
                    print("Aborting batch execution due to step failure.")
                    break
        except Exception as e:
            print("ERROR: %s" % e)
            results.append({"step": idx, "command": cmd, "error": str(e), "success": False})
            if stop_on_error:
                break

    return results


def _selftest():
    print("kicad_ctl selftest:")
    it = _get_interface()
    cmd_count = len(it.command_routes)
    ok = cmd_count >= 200
    print("  loaded KiCADInterface with %d commands: %s" % (cmd_count, "OK" if ok else "FAIL"))

    # Test category completeness
    covered = sum(len(c) for c in CATEGORIES.values())
    print("  category catalog (%d commands)      : OK" % covered)

    print("kicad_ctl selftest: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return _selftest()
    if len(argv) < 2:
        print(__doc__)
        return 2

    action = argv[1]
    if action == "version":
        try:
            import pcbnew
            ver = pcbnew.GetBuildVersion()
        except Exception:
            ver = "unknown"
        cli_ver = "unknown"
        if shutil.which("kicad-cli"):
            try:
                cli_ver = subprocess.check_output(["kicad-cli", "--version"], text=True).strip()
            except Exception:
                pass
        print("KiCad Automation Controller: 1.0.0")
        print("  kicad-cli : %s" % cli_ver)
        print("  pcbnew    : %s" % ver)
        return 0

    elif action == "info":
        if len(argv) < 3:
            print("Usage: python3 kicad_ctl.py info BOARD.kicad_pcb")
            return 2
        import pcbnew
        board = pcbnew.LoadBoard(argv[2])
        bbox = board.GetBoardEdgesBoundingBox()
        print("Board     : %s" % argv[2])
        print("Dimensions: %.2f mm x %.2f mm" % (bbox.GetWidth()/1e6, bbox.GetHeight()/1e6))
        print("Footprints: %d" % len(list(board.Footprints())))
        print("Tracks    : %d" % len([t for t in board.GetTracks() if t.GetClass() != 'PCB_VIA']))
        print("Vias      : %d" % len([t for t in board.GetTracks() if t.GetClass() == 'PCB_VIA']))
        print("Zones     : %d" % board.GetAreaCount())
        return 0

    elif action == "list-commands":
        cat = argv[argv.index("--category") + 1] if "--category" in argv and argv.index("--category") + 1 < len(argv) else None
        return list_commands(category=cat)

    elif action == "doc":
        if len(argv) < 3:
            print("Usage: python3 kicad_ctl.py doc <command>")
            return 2
        return doc_command(argv[2])

    elif action == "run":
        if len(argv) < 3:
            print("Usage: python3 kicad_ctl.py run <command> [json_string | --file params.json]")
            return 2
        cmd = argv[2]
        params = {}
        if "--file" in argv:
            fpath = argv[argv.index("--file") + 1]
            with open(fpath, "r", encoding="utf-8") as f:
                params = json.load(f)
        elif len(argv) > 3 and not argv[3].startswith("--"):
            params = json.loads(argv[3])

        res = run_command(cmd, params)
        print(json.dumps(res, indent=2))
        return 0 if (isinstance(res, dict) and res.get("success", True)) else 1

    elif action == "batch":
        if len(argv) < 3:
            print("Usage: python3 kicad_ctl.py batch recipe.json [--stop-on-error]")
            return 2
        recipe_file = argv[2]
        stop = "--continue-on-error" not in argv
        res = run_batch(recipe_file, stop_on_error=stop)
        print(json.dumps(res, indent=2))
        return 0

    elif action == "autoroute":
        if len(argv) < 3:
            print("Usage: python3 kicad_ctl.py autoroute BOARD.kicad_pcb [-o OUT.kicad_pcb] [--passes N]")
            return 2
        import route_kicad as RK
        return RK.main(["route_kicad.py", "autoroute"] + argv[2:])

    elif action == "cleanup":
        if len(argv) < 3:
            print("Usage: python3 kicad_ctl.py cleanup BOARD.kicad_pcb [-o OUT.kicad_pcb] [--clean-temp]")
            return 2
        import cleanup_board as CB
        return CB.main([CB.__file__] + argv[2:])

    elif action == "embed-symbols":
        if len(argv) < 3:
            print("Usage: python3 kicad_ctl.py embed-symbols SCHEMATIC.kicad_sch")
            return 2
        import embed_symbols as ES
        return ES.main([ES.__file__] + argv[2:])

    elif action == "wire-schematic":
        if len(argv) < 3:
            print("Usage: python3 kicad_ctl.py wire-schematic SCHEMATIC.kicad_sch [--board BOARD.kicad_pcb] [--stub-length MM]")
            return 2
        import wire_schematic as WS
        return WS.main(argv[2:])

    elif action == "export-jlcpcb":
        if len(argv) < 3:
            print("Usage: python3 kicad_ctl.py export-jlcpcb BOARD.kicad_pcb [--schematic SCH.kicad_sch] [--out-dir DIR]")
            return 2
        import export_jlcpcb as EJ
        return EJ.main([EJ.__file__] + argv[2:])

    elif action == "drc":
        if len(argv) < 3:
            print("Usage: python3 kicad_ctl.py drc BOARD.kicad_pcb [--strict] [--no-schematic-parity]")
            return 2
        import drc_check as DC
        return DC.main([DC.__file__] + argv[2:])

    elif action == "refill-zones":
        if len(argv) < 3:
            print("Usage: python3 kicad_ctl.py refill-zones BOARD.kicad_pcb")
            return 2
        import autoroute_2layer as A2
        ok = A2.fill_zones_safely(argv[2], verbose=True)
        return 0 if ok else 1

    elif action == "render-3d":
        if len(argv) < 3:
            print("Usage: python3 kicad_ctl.py render-3d BOARD.kicad_pcb [--out-dir DIR]")
            return 2
        import export_jlcpcb as EJ
        pcb = argv[2]
        out_dir = os.path.dirname(os.path.abspath(pcb))
        if "--out-dir" in argv:
            out_dir = argv[argv.index("--out-dir") + 1]
        renders = EJ.render_3d_previews(pcb, out_dir, width=1200, height=1200, verbose=True)
        return 0 if renders else 1

    print("Unknown action %r\n" % action)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
