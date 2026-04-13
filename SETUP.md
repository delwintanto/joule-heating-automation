# Setup Guide

## Installation

This project uses modern Python packaging with `pyproject.toml`. Follow these steps to set it up:

### 1. Clone or Download the Repository

```bash
cd "C:\Users\delwintanto\Documents\Python Scripts\joule-heating-automation"
```

### 2. Create a Virtual Environment (Recommended)

```bash
python -m venv .venv
```

### 3. Activate the Virtual Environment

**Windows PowerShell:**
```powershell
.\.venv\Scripts\Activate.ps1
```

**Windows Command Prompt:**
```cmd
.venv\Scripts\activate.bat
```

### 4. Install the Package in Editable Mode

```bash
pip install -e .
```

This will:
- Install all dependencies listed in `pyproject.toml`
- Set up the `joule_heating` package so it can be imported from anywhere
- Allow you to edit the source code without reinstalling

### 5. Verify Installation

```bash
python -c "import joule_heating; print(joule_heating.__version__)"
```

You should see the version number, e.g. `1.0.0`

## Running Experiments

Once installed, you can run the packaged console scripts directly:

### Constant Current Experiment
```bash
joule-cc
```

### PID-Controlled Experiment
```bash
joule-pid
```

You can also invoke the modules explicitly:

```bash
python -m joule_heating.experiments.cc
python -m joule_heating.experiments.pid
```

## Project Structure

```
joule-heating-automation/
├── src/
│   └── joule_heating/       # Main package
│       ├── analysis/        # Data analysis modules
│       ├── data/            # Data saving and file management
│       ├── devices/         # Hardware interfaces (PSU, sensors)
│       ├── experiments/     # Package entry points
│       ├── gui/             # Tkinter GUI components
│       ├── plotting/        # Matplotlib plotting
│       └── utils/           # Utility functions
├── pyproject.toml           # Package configuration & dependencies
├── requirements.txt         # Legacy - see pyproject.toml
└── README.md
```

## Development

### Installing Development Dependencies

```bash
pip install -e ".[dev]"
```

This includes additional tools like `pytest` and `ruff`.

### Code Style

- Follow PEP 8 conventions
- Use type hints where appropriate
- Document functions with docstrings

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError: No module named 'joule_heating'`:

1. Make sure you activated the virtual environment
2. Ensure you ran `pip install -e .`
3. Check that you're using the correct Python interpreter

### PowerShell Execution Policy

If you see "running scripts is disabled" when activating:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Or run scripts directly without activation:
```powershell
& ".venv\Scripts\python.exe" -m joule_heating.experiments.cc
```

### Cross-Platform Notes

- The package installs on Windows, macOS, and Linux.
- Some desktop integrations are Windows-specific and become no-ops on other platforms.
- The hardware workflow remains Windows-first unless you verify your serial drivers and device stack on another OS.

### Pylance/VS Code Issues

If VS Code shows import errors but the code runs:

1. Select the correct Python interpreter: `Ctrl+Shift+P` → "Python: Select Interpreter"
2. Choose the interpreter from `.venv/Scripts/python.exe`
3. Restart VS Code if needed

## Files to Ignore

- `.venv/` - Virtual environment (don't commit to Git)
- `*.egg-info/` - Package metadata (auto-generated)
- `__pycache__/` - Python bytecode (auto-generated)
- `requirements.txt` - Deprecated; `pyproject.toml` is the source of truth
