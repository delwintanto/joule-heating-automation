# Joule Heating Automation

A comprehensive Python-based system for controlling joule-heating experiments with live plotting, real-time data logging, PID temperature control, and reliable hardware management.

## Overview

This repository provides an automated framework for running joule-heating experiments on resistive samples. The system supports two primary heating modes:

1. **Constant Current Mode** — Direct constant-current heating with live monitoring.
2. **PID-Controlled Mode** — Closed-loop temperature control using PID feedback.

Both modes feature live matplotlib plotting, streaming CSV data logging, and graceful hardware shutdown with Ctrl+C support.

**⚠️ Safety Warning:** These scripts command real hardware (power supplies, temperature sensors, lasers). Only run with proper safety interlocks, current-limiting protection, and after thorough offline testing.

## Table of Contents

- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Core Modules](#core-modules)
- [Experiment Scripts](#experiment-scripts)
- [Device Drivers](#device-drivers)
- [Utility Modules](#utility-modules)
- [Recent Refactors](#recent-refactors)
- [Architecture & Patterns](#architecture--patterns)
- [Pending Work](#pending-work)
- [FAQ & Troubleshooting](#faq--troubleshooting)

## Requirements

### Python Version
- Python 3.8+ (tested on 3.10+)

### Core Dependencies
Install via pip:

```bash
pip install matplotlib pandas simple-pid minimalmodbus pyserial
```

### Optional
- Custom device drivers (if using alternate temperature sensors or power supplies)
- Jupyter or IPython for interactive data analysis

## Quick Start

### Running an Experiment

From the `scripts` directory in PowerShell:

```powershell
# Constant-current heating run
python .\djs_cc.py

# PID-controlled heating run
python .\djs_pid.py
```

Both scripts will:
1. Initialize hardware (power supply, temperature sensors, optional lasers).
2. Launch a live matplotlib window showing temperature, voltage, and current in real time.
3. Stream measurements to a CSV file.
4. Gracefully shut down on Ctrl+C.

### Expected Output

- **Console:** Progress messages, phase transitions, data summaries, and any warnings.
- **Plot Window:** Three subplots (temperature vs. time, voltage vs. time, current vs. time) updated live.
- **CSV File:** Columns for elapsed time, voltage, current, and resistance, written per measurement.

## Project Structure

```
joule-heating-automation/
├── scripts/                          # Main experiment and helper modules
│   ├── README.md                     # This file
│   ├── djs_cc.py
│   ├── djs_pid.py
│   ├── device_utils.py               # Device initialization & shutdown helpers
│   ├── experiment_utils.py           # Shared measurement & data-append helpers
│   ├── signal_utils.py               # Centralized SIGINT/stop-event handling
│   ├── plot.py                       # Live plotting helpers
│   ├── save_data.py                  # Streaming CSV writer
│   ├── port_detect.py                # Serial port detection
│   ├── temp_sensor_ycr.py            # YCR temperature sensor driver
│   ├── temp_sensor_optris.py         # Optris temperature sensor driver
│   ├── temp_sensor_utils.py          # Temperature sensor utilities
│   ├── power_supply_etm.py           # ETM power supply driver
│   ├── colour_map.py                 # Plotting color/style utilities
│   ├── gradient_analysis.py          # Post-processing analysis tools
│   ├── print_summary.py              # Experiment summary printer
│   ├── system_sleep.py               # System sleep/wake utilities
│   ├── file_name.py                  # Experiment file naming helpers
│   ├── gui.py                        # GUI utilities (if present)
│   └── __pycache__/                  # Python bytecode cache
```

## Core Modules

### Experiment Scripts

#### `djs_cc.py`
**Purpose:** Run a constant-current heating experiment.

**Workflow:**
1. Initialize devices (power supply, YCR/Optris sensors, optional lasers).
2. Run heating phase (user-specified duration, constant current).
3. Cool-down phase (passively or actively, depending on configuration).
4. Collect t/v/i/r measurements and log to CSV.
5. Update live plot every cycle.

**Key Functions:**
- `main()` — experiment orchestration
- `run_experiment()` — heating loop with measurement & logging

**Usage:**
```python
python .\djs_cc.py
# Follow console prompts to set current, duration, and file name.
```

#### `djs_pid.py`
**Purpose:** Run a PID-controlled heating experiment.

**Workflow:**
1. Initialize devices (power supply, sensors, optional lasers).
2. Optional auto-tuning phase (PID parameter calibration).
3. Heating phase (closed-loop control to target temperature).
4. Cool-down phase (passive or active).
5. Collect t/v/i/r measurements and log to CSV.
6. Update live plot every cycle.

**Key Functions:**
- `main()` — experiment orchestration
- `auto_tune_pid()` — PID parameter auto-tuning
- `run_experiment()` — closed-loop heating loop with PID control

**Usage:**
```python
python .\djs_pid.py
# Follow prompts to set target temperature, PID parameters, and file name.
```

### Helper Modules

#### `device_utils.py`
**Purpose:** Centralize hardware initialization, laser control, and shutdown.

**Key Functions:**
- `init_devices()` — Opens power supply, YCR sensor, Optris sensor; returns a tuple `(psu, ycr_sensor, optris_sensor)`. Raises `SystemExit` on failure.
- `enable_lasers(ycr_sensor, optris_sensor, on=True, *, log=True)` — Toggles laser enable/disable on both sensors.
- `shutdown_devices(psu, ycr_sensor, optris_sensor, *, log=True)` — Closes all device connections safely.
- `close_all(...)` — Alias for `shutdown_devices()`.

**Why Centralize?** Reduces duplication across experiment scripts and ensures consistent error handling.

#### `experiment_utils.py`
**Purpose:** Provide shared measurement and data-append helpers.

**Key Functions:**
- `read_data(power_supply, ycr_sensor, optris_sensor, cool=False)` — Reads voltage (V), current (I), and resistance (R) from devices; returns `(t, v, i, r)` tuple where `t` is elapsed seconds and `r` is computed from V/I. If `cool=True`, assumes no active heating and may skip current measurement.
- `append_data(data, time_start, time_now, t, v, i, r)` — Appends a measurement row to the in-memory `data` dictionary (lists for each field).

**Why Centralize?** Ensures consistent measurement semantics and reduces code duplication in heating loops.

#### `plot.py`
**Purpose:** Provide live-plotting helpers.

**Key Functions:**
- `live_plot_init(fig_width=14, fig_height=5)` — Initializes matplotlib figure with three subplots (temperature, voltage, current).
- `live_plot_updt(fig, axes, lines, data=None, x=None, y1=None, y2=None, y3=None)` — Updates plot lines (legacy signature).
- `update_live_plot(fig, axes, lines, data=None, x=None, y1=None, y2=None, y3=None)` — Wrapper for consistent live-plot updates; accepts either `data` dictionary or explicit lists.

**Usage Example:**
```python
from plot import live_plot_init, update_live_plot

fig, axes, lines = live_plot_init()
data = {"elapsed_times": [], "temperatures": [], "voltages": [], "currents": []}

# In measurement loop:
update_live_plot(fig, axes, lines, data=data)
```

#### `save_data.py`
**Purpose:** Stream experiment data to CSV with atomic writes and partial-file safety.

**Key Functions:**
- `save_start(file_path, headers)` — Opens a CSV writer; returns the file handle and writer object.
- `save_row(writer, time_elapsed, voltage, current, resistance)` — Writes a single data row; flushes immediately for reliability.
- `save_finalise(file_path)` — Renames `.partial` file to final `.csv` (atomic rename on success).

**Design:** Uses a hidden `.partial` file during writing; on completion, renames to final name. If interrupted, the partial file remains (manual cleanup may be needed).

#### `signal_utils.py`
**Purpose:** Centralize SIGINT (Ctrl+C) handling and provide a module-level stop event.

**Key Objects:**
- `stop_event` — A module-level `threading.Event` that is set when Ctrl+C is detected.
- Context manager for registering/restoring SIGINT handlers.

**Why Centralize?** Ensures deterministic Ctrl+C behavior across all experiment scripts and allows graceful shutdown of measurement loops.

**Usage Example:**
```python
from signal_utils import stop_event

while not stop_event.is_set():
    # measurement loop
    read_data(...)
    # Ctrl+C will set stop_event and exit loop gracefully
```

### Device Drivers

#### `temp_sensor_ycr.py`
**Purpose:** Driver for YCR temperature sensor (contact-based measurement).

**Key Functions:**
- `TempSensorYCR` class or factory function to open/close and read temperature.

#### `temp_sensor_optris.py`
**Purpose:** Driver for Optris temperature sensor (infrared measurement).

**Key Functions:**
- `TempSensorOptris` class or factory function to open/close and read temperature.

#### `temp_sensor_utils.py`
**Purpose:** Shared temperature sensor utilities and helpers.

#### `power_supply_etm.py`
**Purpose:** Driver for ETM power supply.

**Key Functions:**
- Open, set current/voltage, read voltage/current, close.

#### `port_detect.py`
**Purpose:** Auto-detect serial port(s) for hardware devices.

### Utility Modules

#### `colour_map.py`
Plotting color/style definitions and utilities.

#### `file_name.py`
Helper functions for generating experiment file names and paths.

#### `print_summary.py`
Functions to print experiment summary statistics to console.

#### `gradient_analysis.py`
Post-processing analysis tools (e.g., thermal gradient computation, resistance vs. temperature plots).

#### `system_sleep.py`
Utilities for system sleep/wake control (may be used to prevent system sleep during long experiments).

#### `gui.py`
GUI utilities (if present; may be optional).

## Recent Refactors

### 1. Centralized Device Initialization & Shutdown
- **What:** `device_utils.init_devices()` and `enable_lasers()` replace duplicated hardware-open code in both experiment scripts.
- **Benefit:** Single source of truth for device initialization; easier to update drivers or add new sensors.

### 2. Centralized Signal Handling
- **What:** `signal_utils.stop_event` and SIGINT handler replace inline signal management.
- **Benefit:** Deterministic Ctrl+C behavior; graceful shutdown across all scripts.

### 3. Measurement & Data-Append Extraction
- **What:** `experiment_utils.read_data()` and `append_data()` centralize sensor reads and in-memory data storage.
- **Benefit:** Consistent measurement semantics; reduced duplication in heating loops.

### 4. Live-Plot Wrapper
- **What:** `plot.update_live_plot()` provides a consistent API over `live_plot_updt`.
- **Benefit:** Cleaner call sites; easier to update plotting logic.

## Architecture & Patterns

### Measurement & Control Flow
```
Experiment Loop:
  ├─ Read hardware (t, v, i, r) [experiment_utils.read_data()]
  ├─ Append to in-memory data [experiment_utils.append_data()]
  ├─ Write to CSV [save_data.save_row()]
  ├─ Update live plot [plot.update_live_plot()]
  └─ Check for Ctrl+C [signal_utils.stop_event.is_set()]
```

### Error Handling
- **Device Initialization:** Raises `SystemExit` on critical failure.
- **File I/O:** Catches narrow exceptions (`IOError`, `OSError`) to avoid losing in-memory data.
- **Signal Handling:** Restores original handler on context exit.

### Threading & Events
- `signal_utils.stop_event` is a thread-safe `threading.Event`.
- Useful for multi-threaded setups (e.g., hardware monitor thread + measurement thread).

## Pending Work

### `record_measurement()` Wrapper (Planned)
**What:** A single-call helper in `experiment_utils.py` that:
1. Calls `read_data()`
2. Calls `append_data()`
3. Optionally updates live-plot buffers
4. Calls `save_row()` inside try/except

**Why:** Eliminates repetitive read/append/save call sites; ensures CSV and in-memory data stay in sync; simplifies loop logic.

**Status:** Design approved; implementation pending user approval.

### Optional Enhancements
- **Simulated-device mode:** Mock power supply and sensors for offline testing.
- **Configuration file:** YAML/JSON for experiment parameters (current, duration, PID gains, etc.).
- **Data analysis postprocessor:** Automated resistance-temperature curve fitting, thermal-gradient analysis.
- **Unit tests:** Pytest suite for helper functions and device driver mocks.

## FAQ & Troubleshooting

### Q: My serial port is not detected. What should I do?

**A:** Check hardware connections and try:
```powershell
# List available serial ports in PowerShell
Get-WmiObject Win32_SerialPort | Select-Object Name, DeviceID

# Or use Python:
python -m serial.tools.list_ports
```

Then update the port in the experiment script or `port_detect.py`.

### Q: The plot window won't update. How do I fix it?

**A:** Ensure matplotlib is using a non-blocking backend:
```python
import matplotlib
matplotlib.use('TkAgg')  # or 'Qt5Agg'
```

This is usually set in `plot.py` by default.

### Q: Can I run multiple experiments in parallel?

**A:** Not recommended without significant refactoring, since both scripts access shared hardware resources. Design one experiment at a time.

### Q: How do I recover data if the script crashes?

**A:** Check the `.partial` CSV files in the output directory. Rename the most recent `.partial` file to `.csv` to recover partial data.

### Q: My resistance calculation is wrong. How do I debug?

**A:** Add debug prints in `experiment_utils.read_data()` to inspect raw V and I values:
```python
print(f"DEBUG: V={v}, I={i}, R={v/i if i > 0 else 0}")
```

### Q: Can I change the PID gains mid-experiment?

**A:** Not easily with the current design. You would need to pause, edit the script, and restart. Future work could add a runtime configuration file or GUI.

## Development & Contributing

### Adding a New Temperature Sensor

1. Create `temp_sensor_new.py` with an open/close/read interface.
2. Update `device_utils.init_devices()` to instantiate the new sensor.
3. Update experiment scripts if the sensor has a different API.

### Adding a New Power Supply

1. Create `power_supply_new.py` with methods to set/read voltage/current and close.
2. Update `experiment_utils.read_data()` if the API differs.
3. Update `device_utils.init_devices()`.

### Running Tests (Future)

```powershell
pytest tests/  # When test suite is implemented
```

## Safety Reminders

- **Always use a current-limiting power supply** in case of a short circuit.
- **Test with the power supply off** before running with real samples.
- **Have a thermal shutdown plan** (e.g., a relay to cut power if temperature exceeds a limit).
- **Monitor the sample** visually during early runs to detect arcing or melting.
- **Never leave an experiment unattended** for the first few runs.

## Support & Questions

For issues, feature requests, or questions:
1. Check the [FAQ & Troubleshooting](#faq--troubleshooting) section above.
2. Review the docstrings in individual modules (Google-style format).
3. Check serial port connections and hardware power.
4. If stuck, include:
   - Full error traceback
   - Hardware configuration (sensor types, power supply model)
   - Last few lines of console output
   - The generated CSV file (if any)

---

**Last Updated:** November 2025
**Repository:** joule-heating-automation
**Author(s):** Delwin Tanto
