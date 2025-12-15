"""GUI package for Joule heating experiment interfaces.

This package provides GUI interfaces for both constant-current (CC) and
PID-controlled Joule heating experiments, along with shared utilities.

Modules:
    common: Shared widgets and utility functions
    gui_cc: Constant-current experiment GUI and callbacks
    gui_pid: PID-controlled experiment GUI and callbacks

Author       : Delwin Tanto
Last updated : 10 Dec 2025
"""

# Import main GUI functions for backward compatibility
from .gui_cc import (
    create_experiment_complete_callback_cc,
    create_gui_callbacks_cc,
    create_plot_callbacks_cc,
    gui_cc,
)
from .gui_pid import (
    create_experiment_complete_callback_pid,
    create_gui_callbacks_pid,
    create_plot_callbacks_pid,
    gui_pid,
)

# Re-export all public functions
__all__ = [
    "gui_cc",
    "gui_pid",
    "create_gui_callbacks_cc",
    "create_experiment_complete_callback_cc",
    "create_plot_callbacks_cc",
    "create_gui_callbacks_pid",
    "create_experiment_complete_callback_pid",
    "create_plot_callbacks_pid",
]
