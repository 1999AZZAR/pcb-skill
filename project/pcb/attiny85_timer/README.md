# ATtiny85 & NE555 Timer Experimental Development Board

An autonomous hybrid timing & processing module combining an **Atmel ATtiny85-20SU** microcontroller with a hardware **TI NE555D** precision timer. Designed and validated using **KiCad 9** with production-ready JLCPCB fabrication deliverables.

---

## 📌 Architecture Overview

- **Microcontroller**: ATtiny85-20SU (8-pin SOIC, 8 MHz internal oscillator or external clocking).
- **Hardware Timer**: NE555D (8-pin SOIC configured in astable multivibrator mode).
- **Power Delivery**: 5V via standard USB-C receptacle (`TYPE-C-31-M-12`) with dual 5.1k CC pull-down resistors for USB-PD source compliance.
- **In-System Programming**: Standard 2x3 2.54mm AVR-ISP programming header for flashing firmware with USBasp / ArduinoISP.
- **Auxiliary Output**: 1x4 2.54mm pin header exposing power, timer pulse output, and microcontroller PWM/GPIO.
- **Visual Telemetry**:
  - `D1` (Green): 5V Main Power Rail
  - `D2` (Yellow): NE555 Hardware Pulse Output Indicator
  - `D3` (Blue): ATtiny85 GPIO Status LED

---

## 🗂️ Project File Structure

```text
pcb_trial/
├── README.md                      # Complete project documentation & hardware spec
├── attiny85_timer.kicad_pro       # KiCad 9 Project metadata
├── attiny85_timer.kicad_sch       # KiCad 9 Schematic with fully embedded lib_symbols
├── attiny85_timer.kicad_pcb       # KiCad 9 2-Layer Board Layout & Ground Planes
└── jlcpcb_production/             # One-click manufacturing package
    ├── attiny85_timer_gerber_jlcpcb.zip  # Gerber (RS-274X) + Excellon drill package
    ├── attiny85_timer_bom_jlcpcb.csv     # Bill of Materials formatted for JLCPCB SMT
    ├── attiny85_timer_cpl_jlcpcb.csv     # Component Placement List (Centroid / Pick-and-Place)
    ├── attiny85_timer_render_top.png     # Photorealistic 3D top render
    └── attiny85_timer_render_bottom.png  # Photorealistic 3D bottom render
```

---

## ⚡ Bill of Materials (BOM)

| Designator | Description | Footprint | LCSC Part # |
| :--- | :--- | :--- | :--- |
| **U1** | NE555D Precision Timer | SOIC-8_3.9x4.9mm_P1.27mm | C46749 |
| **U2** | ATtiny85-20SU AVR MCU | SOIC-8_3.9x4.9mm_P1.27mm | C44533 |
| **J1** | USB-C 16-Pin Receptacle | HRO TYPE-C-31-M-12 | C165948 |
| **J2** | AVR-ISP 2x3 Pin Header | PinHeader_2x03_P2.54mm_Vertical | C225434 |
| **J3** | AUX 1x4 Pin Header | PinHeader_1x04_P2.54mm_Vertical | C2243 |
| **C1** | 10µF 16V Ceramic Cap | C_0805_2012Metric | C15850 |
| **C2** | 1µF 16V Ceramic Cap | C_0805_2012Metric | C28323 |
| **C3** | 10nF 50V Ceramic Cap | C_0805_2012Metric | C1710 |
| **C4, C5** | 100nF 50V Decoupling Caps | C_0805_2012Metric | C49678 |
| **D1** | Green LED (Power) | LED_0805_2012Metric | C2297 |
| **D2** | Yellow LED (Timer Pulse) | LED_0805_2012Metric | C2296 |
| **D3** | Blue LED (MCU Status) | LED_0805_2012Metric | C2293 |
| **R1, R2** | 5.1kΩ 1% (USB-C CC) | R_0805_2012Metric | C17637 |
| **R3, R4, R8**| 1kΩ 1% (LED Ballast) | R_0805_2012Metric | C17513 |
| **R5, R7** | 10kΩ 1% Pull-up | R_0805_2012Metric | C17414 |
| **R6** | 47kΩ 1% Timing Resistor | R_0805_2012Metric | C17713 |

---

## 🛠️ Verification & DRC Status

- **Design Rule Checks (DRC)**:
  - Errors: `0`
  - Warnings: `0`
  - Unconnected Nets: `0`
- **KiCad Compatibility**: Built and natively formatted for **KiCad v9.0+** (`(version 20250114)` schematic, `(version 20241229)` PCB) with 100% self-contained graphics.
