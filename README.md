# joule-heating-automation

Python tools for **constant-current** and **PID-controlled** Sirect Joule Synthesis (DJS) with live plotting, safe device control, and CSV logging.  
Primary targets: **Windows 10/11**, **eTM-5050PC PSU** (Modbus RTU), **YCR-D30180AR IR thermometer** (Modbus RTU).

---

## Features

- **Two run modes**
  - Constant-current experiments via `joule_heating_constant_current.py`, including cooldown logic, CSV lifecycle, and live plotting.
  - PID-controlled experiments via `joule_heating_pid.py` with auto-tuning (relay test), cooldown logging, and summary/plot outputs.
- **GUI front-end** for parameter entry, saving/loading parameter sets, and starting runs.
- **Device drivers**
  - PSU: eTM-5050PC (Modbus RTU)
  - IR thermometer: YCR-D30180AR (Modbus RTU)
- **Live plotting** of temperature/current/resistance during run.
- **Auto-save CSV** lifecycle with start, append, and finalize.
- **Console summary + step log** after each run.

---

## Repository Structure

.
├─ joule_heating_constant_current.py
├─ joule_heating_pid.py
├─ gui.py
├─ power_supply_etm.py
├─ temp_sensor_ycr.py
├─ plot.py
├─ gradient_analysis.py
└─ (missing modules listed below)

---

## Hardware & OS

- **OS**: Windows 10/11  
- **PSU**: eTM-5050PC (Modbus RTU, USB/serial)  
- **IR thermometer**: YCR-D30180AR (Modbus RTU)

> **Note**: Both drivers expect a helper `port_detect.find_port_by_hwid(...)` to map HWIDs to COM ports.

---

## Python Environment

**Recommended Python:** 3.10–3.12 (64-bit)

**Install dependencies**
```bash
pip install minimalmodbus pyserial pandas matplotlib simple-pid

---

## Quick Start

### **1. Constant-Current Mode**

python joule_heating_constant_current.py

Configure:
- Sample ID
- Current steps + durations
- Max voltage
- Cooldown thresholds

Program opens IR sensor & PSU, starts live plot, saves CSV, then cooldown until T < MIN_TEMP for COOLDOWN_BUFFER seconds before finalizing CSV and closing plots

---

### **2. PID-Controlled Mode**

python joule_heating_pid.py

Configure:
- Sample ID
- Temperature setpoints + durations
- Current and voltage limits
- Cooldown thresholds
- Tuning choice (Manual/Auto)

Auto-tuning: relay test finds oscillation period/amplitude, computes ZN gains, then runs your profile; gains default if oscillations not detected

---

## Outputs

- **CSV file** (time, T, V, I, R)
- **Summary** (min/max temps, durations, profile results)
- **Step log**
- **Plots** for temp/current/resistance

---

## Safety & Limits

- **Temperature limits** (`MAX_TEMP`, `MIN_TEMP`)  
- **Voltage and current limits** enforced by PSU driver  
- **NaN-protected logic** to avoid runaway behavior  
- **System sleep prevention** (requires `system_sleep.py`)

---

## Configuration Notes

- HWID matching: Update the HWID_SUBSTR constants in `power_supply_etm.py` and `temp_sensor_ycr.py` to match your system’s COM port HWIDs for reliable auto-detection.
- IR temperature calibration: The temperature read applies a ×1.205 scaling; adjust if you re-calibrate your sensor.
- Serial settings: Defaults are set in code (9600 baud, PSU: 8N1; IR: 8E1) — change only if your hardware differs.

---

## Development & Testing Tips

- Run GUI for interactive use:

  python gui.py

- Run device drivers directly to test connectivity.
- All plots close automatically; you can override via custom `close_plot()`.

---

## License

TBD

---