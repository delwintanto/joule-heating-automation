# Joule Heating Automation

A Python-based experimental control system for automating Joule heating experiments and material sintering on Windows systems. The system automates temperature regulation, data logging, and provides real-time visualization during experiments.

## Overview

This project provides two main experiment modes:

1. **Constant Current Mode** (`joule_heating_constant_current.py`) - Apply fixed current levels for fixed durations
2. **PID Temperature Control Mode** (`joule_heating_pid.py`) - Maintain target temperatures using closed-loop PID control with automatic gain tuning

Both modes feature:
- Dual infrared temperature sensors (YCR for high temps, Optris for low temps)
- Real-time data visualization and live plotting
- Automatic data logging to CSV
- Safety temperature limits and monitoring
- Windows system sleep prevention during long experiments

## Project Structure

```
joule-heating-automation/
├── scripts/
│   ├── joule_heating_constant_current.py    # Main: Constant current experiment driver
│   ├── joule_heating_pid.py                 # Main: PID temperature control driver
│   ├── gui.py                               # Tkinter GUI for experiment parameters
│   │
│   ├── power_supply_etm.py                  # eTM-5050PC PSU Modbus RTU interface
│   ├── temp_sensor_ycr.py                   # YCR-D30180AR IR sensor (Modbus RTU)
│   ├── temp_sensor_optris.py                # Optris CT/CTlaser IR sensor (binary protocol)
│   ├── port_detect.py                       # Serial port discovery by hardware ID
│   │
│   ├── plot.py                              # Real-time matplotlib visualization
│   ├── save_data.py                         # CSV streaming with Windows file locking
│   ├── file_name.py                         # Experiment filename generation
│   │
│   ├── gradient_analysis.py                 # Peak/valley detection and analysis
│   ├── colour_map.py                        # ANSI temperature color codes
│   ├── print_summary.py                     # Experiment summary output
│   │
│   ├── system_sleep.py                      # Cross-platform system sleep prevention
│
└── .github/
    └── copilot-instructions.md              # AI coding agent guidelines
```

---

## Core Modules

### Hardware Control

#### `power_supply_etm.py`
- **Device**: eTM-5050PC Power Supply (Modbus RTU)
- **Features**:
  - Turn output ON/OFF
  - Set/read voltage (0-50V) and current (0-infinite A)
  - Automatic serial port discovery via hardware ID
  - Exception handling with `PSUError`

#### `temp_sensor_ycr.py`
- **Device**: YCR-D30180AR IR Thermometer (Modbus RTU, 9600 baud)
- **Features**:
  - Read temperature (°C)
  - Toggle laser pointer ON/OFF
  - Operating range: 300-2000°C (accurate above 300°C)
  - Custom 32-bit float packing for Modbus communication
  - Exception handling with `YCRIRError`

#### `temp_sensor_optris.py`
- **Device**: Optris CT/CTlaser/CTvideo (Binary protocol, 115200 baud)
- **Features**:
  - Read actual/process/head/box temperatures
  - Set emissivity and transmission
  - Toggle laser pointer and "Smart Averaging"
  - Operating range: 50-400°C (better for low temperatures)
  - Exception handling with `OptrisIRError`

#### `port_detect.py`
- **Purpose**: Automatic serial port discovery by hardware ID substring matching
- **Function**: `find_port_by_hwid(hwid_substr)` - returns COM port without manual specification

---

### Experiment Control

#### `joule_heating_constant_current.py`
Main script for constant-current experiments.

**Features:**
- Sequential current steps with configurable durations
- Dual-sensor temperature reading with automatic switching:
  - YCR for temps ≥ 300°C (high accuracy)
  - Optris fallback for temps < 300°C
- Real-time live plotting (temperature, current, resistance)
- Automatic cooldown phase after heating
- Safety limits: MAX_TEMP = 1200°C, MIN_TEMP = 50°C

**Key Functions:**
- `_read_temperature(ycr_sensor, optris_sensor)` - Selects appropriate sensor
- `joule_heating_run()` - Main experiment loop (heating phase)
- `cooldown()` - Records temperature during cooldown

**Execution:**
```bash
python joule_heating_constant_current.py
```

#### `joule_heating_pid.py`
Main script for PID-controlled temperature experiments.

**Features:**
- Auto-tuning via Ziegler-Nichols relay feedback method
- Manual PID gain entry option
- Dual-sensor temperature reading (same strategy as constant current)
- Temperature setpoint control with configurable ramp/hold phases
- Real-time PID output visualization
- Gradient analysis for peak detection during tuning

**Key Functions:**
- `_read_temperature(ycr_sensor, optris_sensor)` - Sensor selection logic
- `auto_tune_pid()` - Automatic PID parameter tuning
- `run_experiment()` - Main PID control loop

**Execution:**
```bash
python joule_heating_pid.py
```

---

### User Interface

#### `gui.py`
Tkinter-based GUI with two experiment modes.

**Components:**
- `LabeledEntry` widget - Composite label + entry + tooltip
- `RowCounter` class - Tracks grid placement
- `gui_cc()` - Constant current mode GUI (currents, durations, max voltage)
- `gui_pid()` - PID mode GUI (setpoints, durations, PID gains, tuning method)

**Features:**
- Tooltips for parameter hints
- Default directory for saving experiments
- JSON or txt import/export of experiment parameters

---

### Data Management

#### `save_data.py`
Windows-focused CSV streaming with file locking.

**Features:**
- Streaming writes (flush every N rows)
- Hidden file attribute (`0x02`) on temporary `.partial` files
- Advisory file locking via `msvcrt.locking()` (Windows only)
- Atomic rename: `.partial` → final filename
- Column order: Time (s), Temperature (°C), Current (A), Voltage (V), Resistance (Ω)

**Key Functions:**
- `save_start(sample_name, tuning=False)` - Open file and write header
- `save_row(elapsed_s, t_meas, i_meas, v_meas, r_meas)` - Append row
- `save_finalise()` - Close file and rename to final location

#### `file_name.py`
Generates safe, unique experiment filenames.

**Features:**
- Creates `~/Documents/Joule_Heating_Data/` directory
- Sanitizes sample names (replaces illegal chars with `_`)
- Formats: `YYYYMMDD_<sample_name>[_tuning_data].csv`
- Auto-increments if file exists: `..._1.csv`, `..._2.csv`, etc.

---

### Visualization

#### `plot.py`
Real-time matplotlib visualization with dual y-axes.

**Features**:
- Live plot with 3 traces on shared timeline:
  - Temperature (°C) - red axis
  - Current (A) - blue axis
  - Resistance (Ω) - green axis
- Window positioning support
- Non-blocking display (block=False)
- Safe position setting (cross-platform)

**Key Functions:**
- `live_plot_init(sample_name, position)` - Initialize figure
- `live_plot_updt()` - Update plot with new data
- `close_plot()` - Clean up

#### `colour_map.py`
ANSI escape codes for terminal temperature visualization.

**Feature:**
- Maps temperature range to 6-color gradient (yellow → orange → red)
- Returns ANSI 256-color codes for console output
- Handles NaN (displays grey)

---

### Data Analysis

#### `gradient_analysis.py`
Peak/valley detection and thermal transition analysis.

**Features:**
- Savitzky-Golay smoothing for noise reduction
- Prominence-based extrema detection
- Gradient-based slope change analysis
- Period and amplitude calculation
- Automated plotting of results

**Use Cases:**
- Detect thermal transients (sharp temperature rises)
- Identify oscillation periods during PID tuning
- Analyze cooling curves

---

### Utilities

#### `print_summary.py`
Formats and displays experiment results.

**Functions:**
- `print_summary()` - Prints experiment metadata (sample, currents/temps, PID gains, max temperature)
- `print_steps()` - Tables showing heating phases for constant-current or PID modes

#### `system_sleep.py`
Cross-platform system sleep prevention.

**Features:**
- Windows: SetThreadExecutionState API
- macOS: caffeinate subprocess
- Linux: xset commands
- Context manager usage: `with prevent_sleep(): ...`

#### `xy_plotter.py` (Optional)
XRD data plotter for `.xy` files.

**Features:**
- Asymmetric least squares (ALS) baseline subtraction
- Trace normalization
- Vertically stacked subplots
- GUI file picker for batch processing

---

## Hardware Setup

### Serial Devices

Three devices communicate via serial ports (auto-detected by hardware ID):

| Device | Hardware ID Substring | Baud Rate | Protocol |
|--------|----------------------|-----------|----------|
| eTM-5050PC PSU | `AB0P06NMA` | 9600 | Modbus RTU (8N1) |
| YCR-D30180AR IR | `AQ03H99EA` | 9600 | Modbus RTU (8E1) |
| Optris IR | `10C4:834B` | 115200 | Binary protocol |

### Temperature Sensor Strategy

The system automatically selects the best sensor based on temperature range:

```
Temperature Range | Sensor | Reason
0-400°C          | Optris | YCR lower limit is 300°C
300-1800°C       | YCR    | Optris upper limit is 400°C
```

If one sensor fails, the other is used as fallback. If both fail, NaN is recorded.

---

## Dependencies

### Required Packages
```
pandas>=1.0.0           # Data manipulation
matplotlib>=3.0.0       # Plotting
numpy>=1.18.0           # Numerical computing
scipy>=1.5.0            # Signal processing (Savitzky-Golay, sparse operations)
scikit-learn>=0.24.0    # (Optional, may be unused)
minimalmodbus>=2.0.0    # Modbus RTU communication
pyserial>=3.5           # Serial port detection
simple-pid>=0.2.3       # PID controller
tkinter                 # (Built-in) GUI framework
```

### Installation
```bash
pip install -r requirements.txt
```

---

## Usage

### Constant Current Mode
```bash
python scripts/joule_heating_constant_current.py
```

1. Enter sample name, current levels, durations, and max voltage in GUI
2. System initializes both sensors and PSU
3. Applies sequential current steps
4. Records temperature, voltage, current, resistance to CSV
5. Automatic cooldown phase
6. Displays summary and plots results

### PID Temperature Control Mode
```bash
python scripts/joule_heating_pid.py
```

1. Enter sample name and experiment parameters in GUI
2. **Auto-tuning** (if selected):
   - Applies relay feedback (alternating high/low current)
   - Detects oscillations to calculate Kp, Ki, Kd
3. **Main experiment**:
   - Controls current to maintain temperature setpoints
   - Supports ramp and hold phases
4. **Cooldown phase**: Records temperature as sample cools
5. Summary and plots displayed

---

## Data Output

### CSV Format
```
Time (s), Temperature (°C), Current (A), Voltage (V), Resistance (Ω)
0.0,      25.3,            0.0,         0.0,         0.0
0.1,      26.1,            2.5,         10.2,        4.08
0.2,      27.8,            2.5,         10.3,        4.12
...
```

### File Location
```
~/Documents/Joule_Heating_Data/YYYYMMDD_<sample_name>.csv
```

### Tuning Data
```
~/Documents/Joule_Heating_Data/YYYYMMDD_<sample_name>_tuning_data.csv
```

---

## Safety Features

1. **Temperature Limits**:
   - MAX_TEMP = 1200°C: Emergency shutdown if exceeded
   - MIN_TEMP = 50°C: Cooldown detection threshold

2. **Sensor Redundancy**:
   - Dual IR sensors provide fallback if one fails
   - NaN readings recorded but don't crash system

3. **File Locking** (Windows):
   - Advisory locks prevent concurrent data writes
   - Hidden `.partial` files during writing

4. **System Sleep Prevention**:
   - Keeps system awake during long experiments
   - Cross-platform support

---

## Configuration

### Hardware IDs
If your device hardware IDs differ, update these constants:

```python
# power_supply_etm.py
HWID_SUBSTR = "AB0P06NMA"

# temp_sensor_ycr.py
HWID_SUBSTR = "AQ03H99EA"

# temp_sensor_optris.py
HWID_SUBSTR = "10C4:834B"
```

### Temperature Limits
```python
# joule_heating_constant_current.py / joule_heating_pid.py
MAX_TEMP = 1200  # Safety limit
MIN_TEMP = 50    # Cooldown threshold (constant-current) or color mapping min (PID)
```

### PID Tuning Parameters
```python
# joule_heating_pid.py, auto_tune_pid()
switch_interval = 5  # Seconds between current switching
tuning_durr = 120    # Total tuning duration (seconds)
```

---

## Troubleshooting

### "No serial port matched HWID"
- Verify devices are connected
- Check Device Manager for correct COM ports
- Update HWID_SUBSTR if device IDs differ

### Temperature readings stuck at 50°C
- Optris sensor has 50°C lower limit (clamping behavior)
- Below 50°C, reading may not reflect actual temperature
- Use Optris primarily for 50-300°C range

### PID auto-tuning fails (no oscillations detected)
- Sample may have high thermal mass (poor oscillation)
- Increase `tuning_durr` for longer observation
- Use manual PID gains as fallback

### CSV file locked (Windows)
- Ensure previous experiment finished (`save_finalise()` called)
- Check for stale `.partial` files in `~/Documents/Joule_Heating_Data/`
- Restart if file remains locked

---

## Development Notes

### Key Patterns

1. **Dual-Sensor Reading**:
   ```python
   def _read_temperature(ycr_sensor, optris_sensor):
       # Try YCR first (300°C+)
       # Fall back to Optris for low temps
       # Return NaN if both fail
   ```

2. **Error Handling**:
   - Hardware errors raise `PSUError`, `YCRIRError`, `OptrisIRError`
   - Caught in experiment loops; logged but don't crash
   - Finally blocks ensure cleanup

3. **Live Plotting**:
   - Non-blocking display: `plt.show(block=False)`
   - Updates per iteration: `live_plot_updt()`
   - Managed deques (maxlen=500) for memory efficiency

### Testing
- No formal test suite; experiments validate functionality
- Console output with ANSI colors shows real-time status
- CSV data used for post-experiment analysis

---

## Author & License

**Author**: Delwin Tanto  
**Last Updated**: November 2025

---

## References

- **Power Supply**: eTM-5050PC (Modbus RTU documentation)
- **YCR Sensor**: YCR-D30180AR (Modbus RTU interface, 9600 baud)
- **Optris Sensor**: CT/CTlaser series (Binary protocol, 115200 baud)
- **PID Tuning**: Ziegler-Nichols method via relay feedback
- **Signal Processing**: Savitzky-Golay filter (scipy.signal)

---

## Future Enhancements

- [ ] Logging to database instead of CSV
- [ ] Web-based remote monitoring dashboard
- [ ] Advanced PID algorithms (model predictive control)
- [ ] Multiprocess data acquisition
- [ ] Integration with lab management systems
- [ ] Predictive maintenance alerts
