# Code Formatting Guide

This project uses automated code formatting tools to ensure consistency across all Python files.

## Setup

Install the development dependencies:

```bash
pip install -e ".[dev]"
```

This installs:
- **Black**: The opinionated code formatter
- **isort**: Import statement organizer
- **Ruff**: Fast Python linter

## Usage

### Format all code automatically

```bash
# Format with Black (applies changes)
black src/ experiments/

# Sort imports with isort (applies changes)
isort src/ experiments/

# Or use Ruff to format (faster, does both!)
ruff format src/ experiments/
```

### Check without modifying

```bash
# Check formatting without applying changes
black --check src/ experiments/

# Check import sorting
isort --check-only src/ experiments/

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
- **Target Python**: 3.8+
- **String quotes**: Double quotes (`"`)
- **Import ordering**: stdlib → third-party → first-party → local

## Editor Integration

### VS Code

Add to `.vscode/settings.json`:

```json
{
  "python.formatting.provider": "black",
  "[python]": {
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.organizeImports": true
    }
  },
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true
}
```

### Pre-commit Hook (Optional)

Create `.git/hooks/pre-commit`:

```bash
#!/bin/sh
black --check src/ experiments/ || exit 1
isort --check-only src/ experiments/ || exit 1
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
black src/ experiments/ && isort src/ experiments/ && ruff check --fix src/ experiments/

# Check everything before commit
black --check src/ experiments/ && isort --check-only src/ experiments/ && ruff check src/ experiments/
```
