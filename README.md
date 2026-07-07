# Joule Heating Automation

Python software for running Joule-heating experiments with a lab-friendly GUI.

Main run modes:
- Constant current mode (`joule-cc`)
- PID temperature-control mode (`joule-pid`)

This guide is written for lab users with limited coding background.


## Table of contents

- [Lab quick start (Windows)](#lab-quick-start-windows)
- [Before you press start (safety checklist)](#before-you-press-start-safety-checklist)
- [First-time setup](#first-time-setup)
- [How to run an experiment](#how-to-run-an-experiment)
- [Parameter cheatsheet](#parameter-cheatsheet)
- [Where your data is saved](#where-your-data-is-saved)
- [Shutdown procedure](#shutdown-procedure)
- [Emergency shutdown procedure](#emergency-shutdown-procedure)
- [Troubleshooting (lab-focused)](#troubleshooting-lab-focused)
- [Supported hardware](#supported-hardware)
- [Advanced/developer notes](#advanced--developer-notes)
- [Security](#security)


## Lab quick start (Windows)

If software is already installed:

1. Connect and power on PSU + sensor(s)
2. Open VS Code, PowerShell or other IDE of your choice
3. Open the project folder:
   - For VS Code, click `File > Open Folder...`
   - For PowerShell, use the following command:

     ```powershell
     cd "Directory"
     ```

4. Activate the environment:
   - For VS Code, press `Ctrl+Shift+P`, type in `Python: Select Interpreter`, and select the recommended venv
   - For PowerShell, use the following command:

     ```powershell
     .\.venv\Scripts\Activate.ps1
     ```

5. Start the program by pressing the play button on VS Code or by entering one of the following:

   ```powershell
   joule-cc
   ```

   or

   ```powershell
   joule-pid
   ```

6. Fill GUI fields and click Start


## Before you press start (Safety Checklist)

- PSU output wiring checked
- Sensor(s) connected and reading sensible temperature
- Max voltage/current limits entered correctly
- Operator knows emergency stop procedure
- Initial/new recipe runs are supervised

**This software controls real hardware. Do not leave new runs unattended.**


## First-time setup

### Requirements

- Python 3.10+
- Windows recommended (full hardware workflow validated on Windows)

### Install

```powershell
git clone https://github.com/delwintanto/joule-heating-automation.git
cd joule-heating-automation
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

### Verify installation

```powershell
python -c "import joule_heating; print(joule_heating.__version__)"
```

If PowerShell blocks script activation:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```


## How to run an experiment

### Constant current mode (`joule-cc`)

Use when you want fixed current steps.

1. Run `joule-cc`
2. Enter:
   - Sample name
   - Current list (A), e.g. `5, 8, 10`
   - Duration list (s), e.g. `60, 90, 120`
   - Max voltage (V)
3. Click Start
4. Monitor live plot and status

### PID temperature mode (`joule-pid`)

Use when you want temperature setpoint control.

1. Run `joule-pid`
2. Enter:
   - Sample name
   - Temperature setpoints (°C), e.g. `400, 600, 800`
   - Durations (s), e.g. `60, 90, 120`
   - Max current (A)
   - Max voltage (V)
   - PID gains (if known) or Auto Tuning
3. Click Start

Notes:
- Auto tuning estimates PID gains before the main run
- Step skipping can be requested via GUI/stop-event behavior


## Parameter cheatsheet

- **Currents / Temperatures**: comma-separated values
- **Durations**: must match number of steps
- **Max Voltage / Max Current**: safety limits (not targets)
- **Sample Name**: used in output filename

Simple first-trial examples (adjust for your setup):
- CC: `current=20`, `duration=30`, `max voltage=30`
- PID: `setpoint=500`, `duration=120`, `max current=20`, `max voltage=30`


## Where your data is saved

CSV files are saved in:

`~/Documents/Joule_Heating_Data`

Typical CSV columns:
- Time (s)
- Temperature (°C)
- Current (A)
- Voltage (V)
- Resistance (Ω)

If a run is interrupted, you may see a `.partial` file. In many cases it can be renamed to `.csv` for recovery.


## Shutdown procedure

Use this for normal end-of-run shutdown.

1. Let the run finish or stop at a safe step boundary from the GUI
2. Confirm live current has dropped to `0 A` and heating has stopped
3. Wait for cooldown to complete (or to your lab’s safe temperature)
4. Close the program window
5. Turn PSU output OFF at the front panel
6. Save/log run notes (sample ID, limits, unusual behavior)

Notes:
- The software attempts to turn output off automatically, but always verify on the PSU
- If a `.partial` file remains, keep it and rename to `.csv` only after confirming file integrity


## Emergency shutdown procedure

Use this when temperature/current behavior is unsafe, unstable, or unexpected.

1. **Immediately remove heating power** using your lab emergency method:
   - Hit hardware E-stop (if available), or
   - Turn PSU output OFF immediately
2. Keep clear of hot hardware and allow passive cooling
3. Close the software after power is safely off
4. Notify supervisor or follow lab incident procedure
5. Preserve logs and data files for review (`.csv` / `.partial`)

Do not restart another run until root cause is identified (wiring, limits, sensor validity, or device fault).


## Troubleshooting (lab-focused)

### “No PSU detected” or sensor not found

1. Check USB/serial cables and power
2. Re-plug device
3. Run:

   ```powershell
   python -m serial.tools.list_ports
   ```

4. Confirm HWID values in `src/joule_heating/devices/device_registry.py`

### GUI starts but temperature is NaN or not changing

- Verify at least one IR sensor is connected and aimed correctly
- Check sensor power/wiring
- Restart app after reconnecting devices

### Plot does not update

- Keep GUI and plot windows open and unblocked
- Rerun from a fresh PowerShell session

### Import/module errors

Usually environment setup issue:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e .
```

### Activation script blocked

Run the following command and try again:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```


## Supported Hardware

| Device Type | Model | Connection | HWID |
|---|---|---|---|
| Power Supply | eTM-5050PC | Modbus RTU (RS-485) | `AB0P06NMA` |
| IR Sensor | YCR-D30180AR | Modbus RTU (RS-485) | `AQ03H99EA` |
| IR Sensor | Optris OPTCTL3MLCF4 | Serial | `10C4:834B` |


## Advanced / Developer Notes

For development/customization work:

- Entry points:
  - `joule-cc -> joule_heating.experiments.cc:main`
  - `joule-pid -> joule_heating.experiments.pid:main`
- Main folders:
  - `src/joule_heating/devices`: hardware drivers
  - `src/joule_heating/experiments`: control loops
  - `src/joule_heating/gui`: Tkinter UI
  - `src/joule_heating/data`: CSV + summaries
  - `src/joule_heating/plotting`: plots
- Dev setup:

  ```powershell
  pip install -e ".[dev]"
  pytest tests/
  ruff check .
  ruff format --check .
  ```


## Support

When reporting issues, include:
- Full traceback
- Hardware connected (model and count)
- Console output
- CSV or `.partial` file (if available)


## Security

This project is intended to be safe to host publicly, but keep these checks in place:

- Do not commit API keys, passwords, access tokens, or private keys
- Keep machine-specific paths and local usernames out of docs/examples where possible
- Keep experiment output data (`.csv`, images) out of git unless intentionally anonymized and shared
- Review PRs for accidental secrets before merge

### Vulnerability disclosure template

If you find a security issue, please report it privately first.

Suggested contact block (replace placeholders):

```text
Security Contact: [your-email@example.com]
PGP Key (optional): [link-or-fingerprint]
Preferred Language: English
Expected Acknowledgement Time: 72 hours
```

Suggested report format:

```text
Subject: [SECURITY] Short title

1) Affected component/file:
2) Impact:
3) Reproduction steps:
4) Proof of concept (if safe to share):
5) Suggested fix (optional):
```

Please avoid opening a public issue for unpatched vulnerabilities.

---

**Author:** Joule Heating Automation Contributors