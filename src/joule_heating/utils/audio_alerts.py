"""Audio alert module for experiment notifications.

This module provides audio alert functions for notifying the user about
experiment milestones. On Windows it uses ``winsound.Beep``; on other
platforms it falls back to the terminal bell when available.

Functions:
    - alert_step_start: Beep to signal the start of a heating step
    - alert_cooldown_end: Beep to signal the end of cooldown phase

Author       : Delwin Tanto
Last updated : 21 Jan 2026
"""

import sys

try:
    import winsound
except ImportError:  # pragma: no cover - non-Windows fallback
    winsound = None

# Alert sound parameters
STEP_START_FREQUENCY = 1000  # Hz
STEP_START_DURATION = 500  # ms

COOLDOWN_END_FREQUENCY = 1200  # Hz
COOLDOWN_END_DURATION = 1000  # ms (longer beep for completion)


def alert_step_start() -> None:
    """Play alert sound for the start of a heating step."""
    try:
        if winsound is not None:
            winsound.Beep(STEP_START_FREQUENCY, STEP_START_DURATION)
        else:
            sys.stdout.write("\a")
            sys.stdout.flush()
    except RuntimeError as e:
        print(f"Warning: Could not play step start alert: {e}")


def alert_cooldown_end() -> None:
    """Play alert sound for the end of the cooldown phase."""
    try:
        if winsound is not None:
            winsound.Beep(COOLDOWN_END_FREQUENCY, COOLDOWN_END_DURATION)
        else:
            sys.stdout.write("\a")
            sys.stdout.flush()
    except RuntimeError as e:
        print(f"Warning: Could not play cooldown end alert: {e}")
