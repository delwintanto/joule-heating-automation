# Joule Heating Automation

**A Python-based experimental control system for sintering materials through resistive (Joule) heating.**

Automate constant-current and PID-controlled temperature Joule heating experiments with real-time data acquisition, live plotting, and hardware management for materials science research on Windows operating system.

---

## Overview

This system provides automated control and data acquisition for Joule heating experiments, supporting two primary operation modes:

1. **Constant Current Mode** — Fixed current for specified durations with temperature monitoring
2. **PID Temperature Control Mode** — Closed-loop feedback control to maintain target temperatures

### Key Features

- ✅ **Real-time monitoring** — Live matplotlib plots (Temperature, Voltage, Current, Resistance)
- ✅ **Automated data logging** — CSV export with atomic writes and partial-file recovery
- ✅ **Modbus hardware control** — eTM-5050PC power supply + YCR/Optris IR temperature sensors
- ✅ **PID auto-tuning** — Ziegler-Nichols relay feedback for parameter optimization
- ✅ **GUI interface** — Tkinter-based parameter entry with tooltips and validation
- ✅ **Safety features** — Emergency shutdown, max temperature limits, graceful Ctrl+C handling
- ✅ **Skip functionality** — Skip individual heating steps during experiments
- ✅ **Windows integration** — Sleep prevention during experiments, console window positioning

### Safety Warning

These scripts control real hardware (power supplies, temperature sensors, lasers). **Only use with:**
- Proper safety interlocks and current-limiting protection
- Thermal cutoff relays for emergency shutdown
- Visual monitoring during initial runs
- Thorough offline testing

**Never leave experiments unattended during initial testing.**

---

## Table of Contents

- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Hardware Requirements](#-hardware-requirements)
- [Project Structure](#-project-structure)
- [Usage Guide](#-usage-guide)
- [Configuration](#-configuration)
- [Development](#-development)
- [Troubleshooting](#-troubleshooting)
- [Architecture](#-architecture)

---

## Installation

### Prerequisites

- **Python 3.8+** (tested on 3.10+)
- **Windows OS** (required for pywin32 features)
- **Git** (optional, for cloning)

### Step 1: Clone the Repository

```powershell
git clone https://github.com/delwintanto/joule-heating-automation.git
cd joule-heating-automation
```

### Step 2: Create Virtual Environment

```powershell
python -m venv .venv
```

### Step 3: Activate Virtual Environment

**PowerShell:**
```powershell
.\.venv\Scripts\Activate.ps1
```

If you get an execution policy error, use:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Command Prompt:**
```cmd
.venv\Scripts\activate.bat
```

### Step 4: Install Package

```powershell
pip install -e .
```

This installs the `joule_heating` package and all dependencies listed in `pyproject.toml`.

### Step 5: Verify Installation

```powershell
python -c "import joule_heating; print(joule_heating.__version__)"
```

Should output: `1.0.0`

---

## Quick Start

### Running Experiments

**Constant Current Experiment:**
```powershell
python experiments\run_cc_experiment.py
```

**PID Temperature Control Experiment:**
```powershell
python experiments\run_pid_experiment.py
```

Or use the VS Code debugger (F5) with the configured Python interpreter.

### What Happens During an Experiment

1. **Hardware initialization** — Detects and opens PSU and temperature sensors
2. **Parameter entry** — GUI prompts for currents, durations, temperatures, etc.
3. **Live plotting** — Matplotlib window opens with real-time data visualization
4. **Data logging** — CSV file created with timestamped measurements
5. **Experiment execution** — Heating phases run with safety monitoring
6. **Cooldown phase** — Passive cooling until minimum temperature reached
7. **Shutdown** — Hardware closed gracefully, final plot saved

### Expected Outputs

- **Console:** Progress messages, phase transitions, measurement summaries
- **CSV File:** `<timestamp>_<sample_name>.csv` with columns: Time (s), Temperature (°C), Current (A), Voltage (V), Resistance (Ω)

---

## Hardware Requirements

### Supported Equipment

| Device Type | Model | Connection | HWID |
|------------|-------|------------|------|
| **Power Supply** | eTM-5050PC | Modbus RTU (RS-485) | `AB0P06NMA` |
| **IR Sensor 1** | YCR-D30180AR | Modbus RTU (RS-485) | `AQ03H99EA` |
| **IR Sensor 2** | Optris OPTCTL3MLCF4 | Serial (proprietary protocol) | `10C4:834B` |

### Hardware Configuration

- **Modbus Settings:** 9600 baud, 8 data bits, 1 stop bit, even/no parity
- **Auto-detection:** Devices detected via hardware ID substring matching
- **Multiple sensors:** System supports simultaneous YCR and Optris sensors (reads from both, uses first valid)

---

## Project Structure

```
joule-heating-automation/
├── experiments/                   # Main experiment entry points
│   ├── run_cc_experiment.py       # Constant-current experiment
│   └── run_pid_experiment.py      # PID temperature experiment
│
├── src/joule_heating/             # Main package
│   ├── analysis/                  # Data analysis modules
│   │   └── gradient_analysis.py
│   ├── data/                      # Data handling
│   │   ├── file_name.py           # Filename generation
│   │   ├── print_summary.py       # Summary printing
│   │   └── save_data.py           # CSV streaming writer
│   ├── devices/                   # Hardware interfaces
│   │   ├── device_registry.py     # Central device configuration
│   │   ├── device_utils.py        # Initialization/shutdown
│   │   ├── port_detect.py         # Serial port detection
│   │   ├── power_supply_etm.py    # PSU driver
│   │   ├── temp_sensor_optris.py  # Optris temperature sensor driver
│   │   ├── temp_sensor_utils.py   # Temperature sensor selection logic
│   │   └── temp_sensor_ycr.py     # YCR temperature sensor driver
│   ├── gui/                       # Tkinter GUI components
│   │   ├── common.py              # Shared widgets
│   │   ├── gui_cc.py              # Constant-current GUI
│   │   └── gui_pid.py             # PID GUI
│   ├── plotting/                  # Visualization
│   │   └── plot.py                # Live matplotlib plotting
│   └── utils/                     # Utilities
│       ├── console_utils.py       # Console positioning (Windows)
│       ├── skip_step.py           # Skip functionality
│       └── system_sleep.py        # Sleep prevention (Windows)
│
├── pyproject.toml                 # Package configuration & dependencies
├── requirements.txt               # Legacy dependency list (deprecated)
├── README.md                      # This file
├── SETUP.md                       # Detailed setup guide
├── MIGRATION_SUMMARY.md           # Migration notes
└── .gitignore                     # Git ignore rules
```

---

## Usage Guide

### Constant Current Mode

**Use case:** Simple fixed-current heating for materials characterization

**Workflow:**
1. Run `python experiments\run_cc_experiment.py`
2. GUI opens — enter parameters:
   - Sample name
   - Current values (A) for each step
   - Duration (s) for each step
   - Max voltage limit (V)
3. Click "Start Experiment"
4. Monitor live plot and console
5. Press Ctrl+C or wait for completion

**Parameters:**
- **Currents:** Comma-separated list (e.g., `5, 10, 15`)
- **Durations:** Comma-separated list matching currents (e.g., `60, 120, 180`)
- **Max Voltage:** Safety limit (experiment aborts if exceeded)

### PID Temperature Control Mode

**Use case:** Precision temperature control for sintering experiments

**Workflow:**
1. Run `python experiments\run_pid_experiment.py`
2. GUI opens — enter parameters:
   - Sample name
   - Target temperatures (°C) for each step
   - Duration (s) for each step
   - PID gains (Kp, Ki, Kd) or enable auto-tuning
   - Max current limit (A)
3. If auto-tuning enabled, system performs relay feedback test first
4. Click "Start Experiment"
5. System maintains target temperatures via PID feedback

**Auto-tuning:**
- Uses Ziegler-Nichols relay feedback method
- Automatically calculates optimal PID gains
- Saves tuning data to separate CSV file

---

## Configuration

### Device Configuration

Edit `src/joule_heating/devices/device_registry.py`:

```python
DEVICE_HWIDS = {
    "PSU": "AB0P06NMA",            # Your PSU hardware ID
    "YCR_SENSOR": "AQ03H99EA",     # Your YCR sensor ID
    "OPTRIS_SENSOR": "10C4:834B",  # Your Optris sensor ID
}
```

### Safety Limits

Edit experiment files or GUI defaults:

```python
MAX_TEMP = 1200  # °C - Emergency shutdown temperature
MIN_TEMP = 50    # °C - Cooldown stop temperature
```

### Data Storage

Default output directory is set in GUI files:
```python
DEFAULTDIR = r"C:\Users\<username>\Documents\Joule_Heating_Data"
```

---

## Development

### Adding New Devices

1. **Create driver module** in `src/joule_heating/devices/`:
   ```python
   # new_sensor.py
   def new_sensor_open(port=None):
       # Implementation
       pass
   ```

2. **Register in device_registry.py**:
   ```python
   DEVICE_HWIDS = {
       "NEW_SENSOR": "HARDWARE_ID_STRING",
   }
   ```

3. **Update device_utils.py** to initialize new device

### Code Style

- Follow PEP 8 conventions
- Use type hints where appropriate
- Document functions with Google-style docstrings
- Keep modules focused and single-purpose

### Running Tests

```powershell
# Not yet implemented - future work
pytest tests/
```

### Development Dependencies

```powershell
pip install -e ".[dev]"  # Installs black, flake8, pytest
```

---

## Troubleshooting

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'joule_heating'`

**Solution:**
1. Ensure virtual environment is activated
2. Run `pip install -e .` from project root
3. In VS Code: Select correct interpreter (Ctrl+Shift+P → "Python: Select Interpreter")

### Serial Port Detection Fails

**Problem:** `RuntimeError: No PSU detected`

**Solution:**
1. Check USB connections
2. Verify device is powered on
3. List ports: `python -m serial.tools.list_ports`
4. Update HWID in `device_registry.py` if needed

### Matplotlib Plot Not Updating

**Problem:** Plot window freezes or doesn't refresh

**Solution:**
1. Ensure matplotlib backend is set: `matplotlib.use('TkAgg')`
2. Check that `plt.pause()` is being called
3. Try different backend: `matplotlib.use('Qt5Agg')`

### CSV File Corrupted

**Problem:** `.partial` file exists but no `.csv`

**Solution:**
- Rename `.partial` file to `.csv` manually
- Data is valid, just wasn't finalized due to early exit

### PowerShell Execution Policy Error

**Problem:** Cannot run activation script

**Solution:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Or use direct Python path:
```powershell
& ".venv\Scripts\python.exe" experiments\run_cc_experiment.py
```

---

## Architecture

### Three-Layer Design

```
┌─────────────────────────────────┐
│   Experiment Scripts            │  ← User entry points
│   (run_cc_experiment.py, etc)   │
└─────────────────────────────────┘
            ↓
┌─────────────────────────────────┐
│   Experiment Logic Layer        │  ← Control loops, PID
│   (GUI, data collection)        │
└─────────────────────────────────┘
            ↓
┌─────────────────────────────────┐
│   Hardware Abstraction Layer    │  ← Device drivers
│   (Modbus interfaces)           │
└─────────────────────────────────┘
```

### Key Patterns

**Modbus Device Interface:**
```python
device = device_open()          # Auto-detect port
device_set_parameter(device, value=X)
data = device_read_parameter(device)
device.serial.close()
```

**Data Flow:**
```python
Measurement Loop:
  → read_temperature(sensors)
  → read_voltage/current(psu)
  → calculate resistance
  → save_row(csv_writer)
  → update_live_plot(figure)
  → check stop conditions
```

**Error Strategy:**
- Device errors → Raise custom exceptions (PSUError, YCRIRError)
- File I/O errors → Catch and retry
- Safety violations → Emergency shutdown
- User interrupts → Graceful cleanup

---

## Data Output Format

### CSV Structure

```csv
Time (s),Temperature (°C),Current (A),Voltage (V),Resistance (Ω)
0.0,25.4,0.0,0.0,inf
1.0,26.1,5.0,2.3,0.46
2.0,28.5,5.0,2.4,0.48
...
```

### Plot Output

Three-panel figure:
- **Top:** Temperature vs Time
- **Middle:** Current vs Time  
- **Bottom:** Resistance vs Time (or Voltage vs Time)

Dual y-axes for overlaying multiple parameters.

---

## License

This project is provided as-is for research purposes. See individual files for author information.

**Author:** Delwin Tanto  
**Last Updated:** 15 Dec 2025

---

## Support

For questions or issues:
1. Check [Troubleshooting](#-troubleshooting) section
2. Review module docstrings (Google-style format)
3. Check serial connections and hardware power
4. Create an issue with:
   - Full error traceback
   - Hardware configuration
   - Console output
   - Generated CSV file (if any)

---

**Happy Experimenting!**
**Author(s):** Delwin Tanto
