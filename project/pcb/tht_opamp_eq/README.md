# THT 3.3V Stereo 3-Band Equalizer & Preamp

An ultra-compact, high-fidelity, 100% Through-Hole (THT) stereo audio equalizer and headphone/line preamplifier designed for 3.3V battery or single-supply operation.

Zero surface-mount components. Optimized for hand soldering, DIY audio gear, portable headphone setups, and custom instrument tone shaping.

---

## Highlights & Specifications

| Parameter | Specification | Details |
|---|---|---|
| **Form Factor** | 88.0 mm × 61.0 mm | Ultra-compact 2-layer PCB |
| **Component Technology** | 100% Through-Hole (THT) | Easy hand assembly with basic iron |
| **Supply Voltage** | 3.3V DC (1.8V to 5.5V tolerated) | Single-cell LiFePO4, 3.7V Li-Ion (via LDO), or 2x/3x AA |
| **Active Core** | Microchip MCP6004 (DIP-14) | Quad Rail-to-Rail I/O CMOS Op-Amp |
| **Quiescent Current** | ~3.0 mA total (including LED) | Extremely power-efficient for battery use |
| **Input / Output** | Dual 3.5 mm TRS Stereo Jacks | AC-coupled audio line & headphone drive |
| **Tone Controls** | Bass, Mid, Treble (±10 to 12 dB) | Active feedback Baxandall topology |
| **Volume & Balance** | Log Volume + Linear Balance | Independent stereo level and stereo imaging |
| **Grounding** | Solid `B.Cu` Ground Plane | Full ground pour for minimum hum and noise |
| **Mounting** | 4× M3 Mounting Holes | 4.0 mm inset from board corners |
| **DRC Compliance** | **0 Errors, 0 Warnings, 0 Unconnected Nets** | 100% clean KiCad strict DRC pass |

---

## Circuit Architecture

```text
[3.5mm Stereo IN] 
       │
       ▼ (1 µF AC Coupling)
[VOL Potentiometer (50k Log)] 
       │
       ▼
[Active 3-Band Baxandall Filter] ── MCP6004 (U1A / U1D)
  ├── BASS  (100k Linear) ~100 Hz shelf (±12 dB)
  ├── MID   (100k Linear) ~1.0 kHz band (±10 dB)
  └── TREB  (100k Linear) ~10 kHz shelf (±12 dB)
       │
       ▼
[BAL Potentiometer (100k Linear)] (Stereo cross-attenuation)
       │
       ▼
[Output Driver & Buffer Stage]   ── MCP6004 (U1B / U1C)
       │
       ▼ (100 µF AC Coupling + 47Ω isolation)
[3.5mm Stereo OUT]
```

### 1. Dual Rail-to-Rail Op-Amp (MCP6004 DIP-14)
- **Sections A & D**: Left and Right inverting active tone stages. Placing the tone network in the negative feedback loop ensures low distortion and predictable boost/cut curves.
- **Sections B & C**: Left and Right output driver stages configured for clean buffering with 47Ω series output resistors (`R_STAB_L`, `R_STAB_R`) to prevent oscillation when driving capacitive cables or low-impedance headphones.

### 2. Virtual Ground Bias (VBIAS)
- Single-supply audio requires referencing AC signals to mid-rail ($V_{CC} / 2 = 1.65\text{ V}$).
- Created by a low-noise resistive divider (`R_BIAS1`, `R_BIAS2` = 100 kΩ) heavily decoupled by `C_BIAS1` (47 µF electrolytic) and `C_BIAS2` (100 nF ceramic).
- Virtual ground connects to the non-inverting pins (Pins 3 and 12 of U1) with dedicated traces and zero ground loops.

### 3. Five Control Knobs (14.0 mm Pitch)
Five dual-gang Alpha RD902F vertical potentiometers line the top edge for convenient front-panel integration:
1. **VOL** (`RV1`): 50 kΩ Dual Audio (Logarithmic) — Input gain and volume attenuation.
2. **BASS** (`RV2`): 100 kΩ Dual Linear — Low-frequency shelf response.
3. **MID** (`RV3`): 100 kΩ Dual Linear — Mid-frequency vocal and instrument presence.
4. **TREB** (`RV4`): 100 kΩ Dual Linear — High-frequency air and sparkle.
5. **BAL** (`RV5`): 100 kΩ Dual Linear — Left-to-Right stereo pan balance.

---

## Bill of Materials (BOM)

All 51 components are through-hole parts readily sourced from LCSC, Mouser, Digikey, or local electronics suppliers:

| Designator | Value | Footprint / Package | Description | Qty |
|---|---|---|---|---|
| **U1** | MCP6004-E/P | `DIP-14_W7.62mm` | Quad Rail-to-Rail I/O Op-Amp | 1 |
| **RV1** | 50k Dual Log (A50K) | `Potentiometer_Alpha_RD902F-40-00D_Dual_Vertical` | Master Stereo Volume Control | 1 |
| **RV2** | 100k Dual Lin (B100K) | `Potentiometer_Alpha_RD902F-40-00D_Dual_Vertical` | Bass Control (±12 dB @ 100 Hz) | 1 |
| **RV3** | 100k Dual Lin (B100K) | `Potentiometer_Alpha_RD902F-40-00D_Dual_Vertical` | Midrange Control (±10 dB @ 1 kHz) | 1 |
| **RV4** | 100k Dual Lin (B100K) | `Potentiometer_Alpha_RD902F-40-00D_Dual_Vertical` | Treble Control (±12 dB @ 10 kHz) | 1 |
| **RV5** | 100k Dual Lin (B100K) | `Potentiometer_Alpha_RD902F-40-00D_Dual_Vertical` | Stereo Balance Control | 1 |
| **J1** | 3.5mm Stereo | `Jack_3.5mm_Ledino_KB3SPRS_Horizontal` | Audio Input TRS Jack | 1 |
| **J2** | 3.5mm Stereo | `Jack_3.5mm_Ledino_KB3SPRS_Horizontal` | Audio Output TRS Jack | 1 |
| **J3** | 2-pin 2.54mm | `PinHeader_1x02_P2.54mm_Vertical` | DC Power Input (Pin 1: +3.3V, Pin 2: GND) | 1 |
| **D1** | 3mm Green/Red | `LED_D3.0mm` | Power Indicator LED | 1 |
| **C_PWR1** | 100 µF 16V | `CP_Radial_D5.0mm_P2.00mm` | Main Power Bulk Filter Capacitor | 1 |
| **C_PWR2** | 100 nF 50V | `C_Disc_D3.8mm_W2.6mm_P2.50mm` | High-Frequency Power Decoupling | 1 |
| **C_BIAS1** | 47 µF 16V | `CP_Radial_D5.0mm_P2.00mm` | Virtual Ground (VBIAS) Bulk Filter | 1 |
| **C_BIAS2** | 100 nF 50V | `C_Disc_D3.8mm_W2.6mm_P2.50mm` | VBIAS High-Frequency Bypass | 1 |
| **C_IN_L, C_IN_R** | 1.0 µF 50V | `C_Disc_D3.8mm_W2.6mm_P2.50mm` | Audio Input DC-Blocking Capacitors | 2 |
| **C_OUT_L, C_OUT_R** | 100 µF 16V | `CP_Radial_D5.0mm_P2.00mm` | Audio Output DC-Blocking Capacitors | 2 |
| **C_BASS_L1, C_BASS_R1** | 47 nF | `C_Disc_D3.8mm_W2.6mm_P2.50mm` | Bass Filter Frequency Setting | 2 |
| **C_MID_L1, C_MID_R1** | 22 nF | `C_Disc_D3.8mm_W2.6mm_P2.50mm` | Midrange Filter Frequency Setting | 2 |
| **C_TREB_L1, C_TREB_L2, C_TREB_R1, C_TREB_R2** | 2.2 nF | `C_Disc_D3.8mm_W2.6mm_P2.50mm` | Treble Filter Frequency Setting | 4 |
| **R_BIAS1, R_BIAS2** | 100 kΩ 1/4W | `R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal` | VBIAS Voltage Divider (1% Tol) | 2 |
| **R_PWR** | 1.0 kΩ 1/4W | `R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal` | LED Current Limiter | 1 |
| **R_IN_L, R_IN_R** | 100 kΩ 1/4W | `R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal` | Input AC Coupling Bias Reference | 2 |
| **R_IN_EQ_L, R_IN_EQ_R** | 10 kΩ 1/4W | `R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal` | Tone Stage Input Isolation | 2 |
| **R_FB_EQ_L, R_FB_EQ_R** | 10 kΩ 1/4W | `R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal` | Tone Stage Feedback Loop Resistors | 2 |
| **R_BASS_L, R_BASS_R** | 10 kΩ 1/4W | `R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal` | Bass Stage Shaping | 2 |
| **R_TREB_L, R_TREB_R** | 4.7 kΩ 1/4W | `R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal` | Treble Stage Shaping | 2 |
| **R_FB_L, R_FB_R** | 22 kΩ 1/4W | `R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal` | Driver Stage Feedback (+6 dB Gain) | 2 |
| **R_GND_L, R_GND_R** | 22 kΩ 1/4W | `R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal` | Driver Stage Ground Divider | 2 |
| **R_STAB_L, R_STAB_R** | 47 Ω 1/4W | `R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal` | Output Cable/Capacitive Isolation | 2 |
| **R_PULL_L, R_PULL_R** | 100 kΩ 1/4W | `R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal` | Anti-Pop Jack Ground Bleeder | 2 |
| **H1, H2, H3, H4** | M3 | `MountingHole_3.2mm_M3_Pad` | 3.2 mm Plated Mounting Holes | 4 |

---

## Assembly & Soldering Sequence

To ensure easy physical access for your soldering iron tip, solder components in ascending order of height:

1. **DIP Socket (Optional)**: If using a 14-pin DIP socket for U1, solder it first.
2. **Resistors**: 1/4W axial metal-film resistors (flat against PCB).
3. **Ceramic & Film Capacitors**: 2.2 nF, 22 nF, 47 nF, 100 nF, 1 µF disc/box capacitors.
4. **Power Header & LED**: 2-pin power header `J3` and 3 mm indicator LED `D1` (note cathode flat side).
5. **Electrolytic Capacitors**: 47 µF (`C_BIAS1`), 100 µF (`C_PWR1`, `C_OUT_L`, `C_OUT_R`) — observe polarity (`+` marked on silkscreen).
6. **Audio Jacks**: 3.5 mm TRS connectors `J1` and `J2`.
7. **Potentiometers**: 5x Alpha dual-gang pots `RV1`–`RV5` (snap bracket lugs into mounting holes and solder).
8. **IC Insertion**: Insert `MCP6004` into socket or PCB (Pin 1 oriented toward notch).

---

## PCB Fabrication & Ordering Guide

The design is 100% compliant with standard prototype manufacturing specs (JLCPCB, PCBWay, OSH Park):

- **Production Package**: Upload [`jlcpcb_production/tht_opamp_eq_gerber_jlcpcb.zip`](file:///home/azzar/project/tht_opamp_eq/jlcpcb_production/tht_opamp_eq_gerber_jlcpcb.zip) directly to the manufacturer's order page.
- **Recommended Options**:
  - **Dimensions**: 88.0 mm × 61.0 mm (detected automatically from zip)
  - **Layers**: 2 Layers
  - **PCB Thickness**: 1.6 mm
  - **Copper Weight**: 1 oz (35 µm)
  - **Surface Finish**: HASL Lead-Free (RoHS) or Regular HASL
  - **Solder Mask**: Green, Matte Black, Blue, or Red
  - **Silkscreen**: White
  - **Drill Minimum**: 0.3 mm / 0.8 mm via

---

## Project Structure

```text
/home/azzar/project/tht_opamp_eq/
├── README.md                      # Complete documentation & specifications
├── tht_opamp_eq.kicad_pcb         # Master production PCB file (KiCad 9)
├── tht_opamp_eq.kicad_sch         # Schematic source file (KiCad 9)
├── tht_opamp_eq.kicad_pro         # KiCad project file
└── jlcpcb_production/             # Final manufacturing release bundle
    ├── tht_opamp_eq_gerber_jlcpcb.zip   # Gerber & Excellon drill archive
    ├── tht_opamp_eq_bom_jlcpcb.csv      # Formatted BOM for JLCPCB / sourcing
    ├── tht_opamp_eq_cpl_jlcpcb.csv      # Component placement list (XY coordinates)
    ├── tht_opamp_eq_render_top.png      # High-res photorealistic 3D top render
    └── tht_opamp_eq_render_bottom.png   # High-res photorealistic 3D bottom render
```
