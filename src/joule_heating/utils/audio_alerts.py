"""Audio alert module for experiment notifications.

This module provides audio alert functions using Windows beep for notifying
the user about experiment milestones (start of heating steps, start/end of cooldown).

Functions:
    - alert_step_start: Beep to signal the start of a heating step
    - alert_cooldown_start: Beep to signal the start of cooldown phase
    - alert_cooldown_end: Beep to signal the end of cooldown phase

Author       : Delwin Tanto
Last updated : 21 Jan 2026
"""

import winsound

# Alert sound parameters
STEP_START_FREQUENCY = 1000  # Hz
STEP_START_DURATION = 500    # ms

COOLDOWN_END_FREQUENCY = 1200  # Hz
COOLDOWN_END_DURATION = 1000   # ms (longer beep for completion)


def alert_step_start():
    """Play alert sound for the start of a heating or cooldownstep."""
    try:
        winsound.Beep(STEP_START_FREQUENCY, STEP_START_DURATION)
    except RuntimeError as e:
        print(f"Warning: Could not play step start alert: {e}")


def alert_cooldown_end():
    """Play alert sound for the end of the cooldown phase.    """
    try:
        winsound.Beep(COOLDOWN_END_FREQUENCY, COOLDOWN_END_DURATION)
    except RuntimeError as e:
        print(f"Warning: Could not play cooldown end alert: {e}")
