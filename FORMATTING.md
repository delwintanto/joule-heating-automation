# Code Formatting Guide

This project uses automated code formatting tools to ensure consistency across all Python files.

## Setup

Install the development dependencies:

```bash
pip install -e ".[dev]"
```

This installs:
- **Ruff**: Fast Python linter
- **pytest**: Test runner for local validation

## Usage

### Format all code automatically

```bash
# Format code
ruff format src/ experiments/

# Fix imports and other auto-fixable lint issues
ruff check --fix src/ experiments/
```

### Check without modifying

```bash
# Check formatting without applying changes
ruff format --check src/ experiments/

# Check for code issues
ruff check src/ experiments/
```

### Fix issues automatically

```bash
# Auto-fix issues found by Ruff
ruff check --fix src/ experiments/
```

## Configuration

All formatting rules are defined in `pyproject.toml`:

- **Line length**: 100 characters
- **Target Python**: 3.10+
- **String quotes**: Double quotes (`"`)
- **Import ordering**: stdlib → third-party → first-party → local

## Editor Integration

### VS Code

Add to `.vscode/settings.json`:

```json
{
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.fixAll": "explicit",
      "source.organizeImports": "explicit"
    }
  },
  "ruff.nativeServer": "on"
}
```

### Pre-commit Hook (Optional)

Create `.git/hooks/pre-commit`:

```bash
#!/bin/sh
ruff format --check src/ experiments/ || exit 1
ruff check src/ experiments/ || exit 1
```

Make it executable:
```bash
chmod +x .git/hooks/pre-commit  # Linux/Mac
```

## Style Decisions

### Docstrings
- Use triple double-quotes: `"""`
- First line on same line as opening quotes
- Google-style format for Args/Returns/Raises

### Imports
```python
# Standard library
import os
from datetime import datetime

# Third-party
import pandas as pd
from simple_pid import PID

# First-party (joule_heating package)
from joule_heating.devices import init_devices
```

### Quotes
- Double quotes for strings: `"hello"`
- Single quotes only for dict keys in rare cases
- f-strings for formatting: `f"Temperature: {temp:.1f}"`

## Common Commands

```bash
# Complete formatting pipeline
ruff format src/ experiments/ && ruff check --fix src/ experiments/

# Check everything before commit
ruff format --check src/ experiments/ && ruff check src/ experiments/
```
