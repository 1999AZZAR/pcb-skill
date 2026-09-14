# Setup — KiCad Development Environment

This skill drives **KiCad** (v7, v8, v9) directly through its command-line interface (`kicad-cli`),
Python geometry API (`pcbnew`), and open S-expression file manipulation.

---

## 1. Prerequisites

| Tool | Purpose | Check Command |
|---|---|---|
| **KiCad 9** (v9.0.x recommended, v7/v8 supported) | EDA suite + headless tools | `kicad-cli --version` |
| **Python 3.8+** | Running scripts, checkers, adapters | `python3 --version` |
| **pcbnew** Python bindings | Native board geometry & DSN/SES API | `python3 -c "import sys; sys.path.append('/usr/lib/python3/dist-packages'); import pcbnew; print(pcbnew.GetBuildVersion())"` |
| **Java 17+** (optional) | Running FreeRouting autorouter | `java -version` |

### Installing KiCad on Linux (Debian / Ubuntu / Pop!_OS)
```bash
sudo add-apt-repository --yes ppa:kicad/kicad-9.0-releases
sudo apt update
sudo apt install -y kicad python3-kicad
```

### Installing KiCad on macOS
```bash
brew install --cask kicad
```

---

## 2. Testing the Environment

Run the self-tests for all KiCad adapters and checkers:

```bash
cd scripts

# 1. KiCad board converter
python3 placement/import_kicad.py --selftest

# 2. Specctra SES router importer
python3 routing/ses_import.py --selftest

# 3. KiCad DRC runner
python3 kicad/drc_check.py --selftest

# 4. JLCPCB exporter & packager
python3 kicad/export_jlcpcb.py --selftest

# 5. Gerber & Drill verification
python3 verify/gerber.py --selftest
```

If all report `PASS`, the KiCad environment is ready for autonomous board design.
