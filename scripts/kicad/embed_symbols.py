#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Embeds full symbol definitions into KiCad 9 schematic lib_symbols section.

Prevents the "?? component" problem where symbols render as question marks in KiCad
because their graphic primitives and pin definitions are missing from (lib_symbols ...).
"""
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_CORE = os.path.join(_HERE, "core")

for _p in (_CORE, "/usr/lib/python3/dist-packages", "/usr/lib/python3/site-packages"):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.append(_p)

# Common non-standard or legacy symbol names mapped to official KiCad 9 symbols
CANONICAL_ALIASES = {
    "Amplifier_Operational:MCP6004-P": "Amplifier_Operational:MCP6004",
    "Amplifier_Operational:MCP6002-P": "Amplifier_Operational:MCP6002",
    "Device:Rotary_Encoder_Switch": "Device:R_Potentiometer_Dual",
    "Device:Potentiometer": "Device:R_Potentiometer",
    "Device:Potentiometer_Dual": "Device:R_Potentiometer_Dual",
    "Connector:Conn_02x03_Odd_Even": "Connector_Generic:Conn_02x03_Odd_Even",
    "Connector:Conn_01x02": "Connector_Generic:Conn_01x02",
    "Connector:Conn_01x04": "Connector_Generic:Conn_01x04_Pin",
    "Connector:USB_C_Receptacle_USB2.0": "Connector:USB_C_Receptacle_USB2.0_16P",
}


def embed_symbols(schematic_path, verbose=True):
    """Embed all placed symbol definitions into a schematic's lib_symbols table."""
    if not os.path.exists(schematic_path):
        raise FileNotFoundError("Schematic not found: %s" % schematic_path)

    with open(schematic_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Canonicalize legacy or non-standard symbol names
    for alias, canonical in CANONICAL_ALIASES.items():
        if f'"{alias}"' in content:
            content = content.replace(f'"{alias}"', f'"{canonical}"')
            if verbose:
                print(f"  Canonicalized symbol alias: {alias} -> {canonical}")

    # 2. Extract unique lib_ids used in schematic
    placed_lib_ids = sorted(set(re.findall(r'\(lib_id\s+"([^"]+)"\)', content)))
    if not placed_lib_ids:
        if verbose:
            print("  No symbol instances found in schematic.")
        return {"success": True, "embedded_count": 0}

    # 3. Find existing symbols inside lib_symbols
    existing_lib_symbols = set()
    lib_sym_match = re.search(r'\(lib_symbols\s*(.*?)\n  \)', content, re.DOTALL)
    if lib_sym_match:
        existing_lib_symbols = set(re.findall(r'\(symbol\s+"([^"]+)"', lib_sym_match.group(1)))

    missing_symbols = [lid for lid in placed_lib_ids if lid not in existing_lib_symbols]

    from commands.dynamic_symbol_loader import DynamicSymbolLoader
    loader = DynamicSymbolLoader()

    newly_embedded = 0
    extracted_blocks = []

    for lib_id in missing_symbols:
        if ":" not in lib_id:
            continue
        lib, sym = lib_id.split(":", 1)
        block = loader.extract_symbol_from_library(lib, sym)
        if block:
            indented = "\n".join("    " + line if line.strip() else line for line in block.strip().split("\n"))
            extracted_blocks.append(indented)
            newly_embedded += 1
            if verbose:
                print(f"  Extracted & embedded: {lib_id} ({len(block)} chars)")
        else:
            if verbose:
                print(f"  Warning: symbol '{lib_id}' not found in system libraries")

    if not extracted_blocks and "(lib_symbols" in content:
        if verbose:
            print("  All symbols already present in lib_symbols.")
        return {"success": True, "embedded_count": 0}

    # 4. Inject or update (lib_symbols ...)
    if "(lib_symbols" in content:
        lib_sym_start = content.find("(lib_symbols")
        depth = 0
        lib_sym_end = lib_sym_start
        for i in range(lib_sym_start, len(content)):
            if content[i] == "(":
                depth += 1
            elif content[i] == ")":
                depth -= 1
                if depth == 0:
                    lib_sym_end = i
                    break
        content = content[:lib_sym_end] + "\n" + "\n".join(extracted_blocks) + "\n  " + content[lib_sym_end:]
    else:
        lib_section = "  (lib_symbols\n" + "\n".join(extracted_blocks) + "\n  )\n"
        first_sym = content.find("  (symbol (lib_id")
        if first_sym != -1:
            content = content[:first_sym] + lib_section + content[first_sym:]
        else:
            last_paren = content.rfind(")")
            content = content[:last_paren] + lib_section + content[last_paren:]

    # 5. Standardize on KiCad 9 schema version header
    content = re.sub(r'\(version \d+\)', '(version 20250114)', content)
    content = re.sub(r'\(generator "[^"]+"\)', '(generator "eeschema")', content)
    if 'generator_version' not in content:
        content = content.replace('(generator "eeschema")', '(generator "eeschema")\n  (generator_version "9.0")')

    with open(schematic_path, "w", encoding="utf-8") as f:
        f.write(content)

    if verbose:
        print(f"Successfully updated schematic with {newly_embedded} embedded symbol(s): {schematic_path}")

    return {"success": True, "embedded_count": newly_embedded, "total_symbols": len(placed_lib_ids)}


def _selftest():
    import tempfile
    tmp = tempfile.mktemp(suffix=".kicad_sch", prefix="kc_sym_test_")
    stub = (
        '(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0")\n'
        '  (uuid 00000000-0000-0000-0000-000000000000)\n'
        '  (paper "A4")\n'
        '  (symbol (lib_id "Device:R") (at 50 50 0) (unit 1)\n'
        '    (uuid 11111111-0000-0000-0000-000000000001)\n'
        '    (property "Reference" "R1" (at 50 44 0))\n'
        '    (property "Value" "10k" (at 50 46 0))\n'
        '  )\n'
        ')\n'
    )
    open(tmp, "w", encoding="utf-8").write(stub)
    try:
        res = embed_symbols(tmp, verbose=False)
        content = open(tmp, "r", encoding="utf-8").read()
        ok = (res.get("success") and "(lib_symbols" in content and '(symbol "Device:R"' in content)
        print("embed_symbols selftest: %s" % ("PASS" if ok else "FAIL"))
        return 0 if ok else 1
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def main(argv):
    if "--selftest" in argv:
        return _selftest()
    if len(argv) < 2:
        print("Usage: python3 embed_symbols.py SCHEMATIC.kicad_sch")
        return 2
    res = embed_symbols(argv[1], verbose=True)
    return 0 if res.get("success") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
