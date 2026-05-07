"""Temperature sensor utility functions for joule heating experiments.

This module provides a unified interface for reading temperature data from multiple
IR sensor types (YCR and Optris). It implements sensor selection logic to choose the
most appropriate sensor based on temperature range and availability.

Key Features:
    - Automatic sensor selection based on temperature range
    - Graceful fallback handling between sensors
    - Returns NaN when all sensors fail (safe for data logging)

Sensor Characteristics:
    - YCR: For temperatures between 300 and 1800°C
    - Optris: For temperature between 50 and 400°C

Example:
    >>> from temp_sensor_ycr import ycr_open
    >>> from temp_sensor_optris import optris_open
    >>> from temp_sensor_utils import read_temperature
    >>>
    >>> ycr_sensor = ycr_open()
    >>> optris_sensor = optris_open()
    >>> temp = read_temperature(ycr_sensor, optris_sensor)
    >>> print(f"Current temperature: {temp}°C")

Dependencies:
    - temp_sensor_optris: Optris IR sensor interface
    - temp_sensor_ycr: YCR IR sensor interface
"""

import math
from typing import Any

from .exceptions import TemperatureSensorError
from .temp_sensor_optris import optris_read_actual_temp
from .temp_sensor_ycr import ycr_read_temp

# Hysteresis for sensor switching.
# Once YCR has been returning valid readings, hold the last valid YCR reading
# for up to this many consecutive NaN reads before falling back to Optris.
# This prevents a transient Modbus timeout (e.g., from EMI during heating)
# from causing a permanent switch to the Optris 400°C cap.
_YCR_HOLDOVER_COUNT = 2
# Mutable container so state can be mutated from nested functions without `global`
_ycr_state = {"nan_streak": 0, "last_temp": float("nan")}


def reset_temperature_reader() -> None:
    """Reset sensor-switching state between experiments.

    Clears the cached YCR reading and NaN streak counter so that stale
    state from a previous experiment does not affect the next one.
    Call this at the start of each new experiment run.
    """
    _ycr_state["nan_streak"] = 0
    _ycr_state["last_temp"] = float("nan")


def read_temperature(ycr_sensor: Any, optris_sensor: Any) -> float:
    """Read temperature from the appropriate sensor.

    Tries YCR first. If YCR returns a valid (non-NaN) reading, it is used
    and the NaN streak counter resets. If YCR returns NaN for up to
    ``_YCR_HOLDOVER_COUNT`` consecutive reads, the last valid YCR reading is
    held and returned instead of falling back to Optris — this prevents a
    brief Modbus timeout (e.g. from EMI during high-current heating) from
    causing the Optris 400°C saturation limit to reach the PID controller.
    After more than ``_YCR_HOLDOVER_COUNT`` consecutive NaN reads, or when no
    valid YCR reading has ever been seen, falls back to Optris.

    Args:
        ycr_sensor (minimalmodbus.Instrument or None): YCR IR sensor instance,
            or None if unavailable.
        optris_sensor (serial.Serial or None): Optris IR sensor instance,
            or None if unavailable.

    Returns:
        float: Temperature in °C. Returns NaN if all sensors are None or fail.
    """
    if ycr_sensor is not None:
        t_ycr = ycr_read_temp(ycr_sensor)
        if not math.isnan(t_ycr):
            _ycr_state["nan_streak"] = 0
            _ycr_state["last_temp"] = t_ycr
            return t_ycr
        # YCR returned NaN — transient failure or below its range
        _ycr_state["nan_streak"] += 1
        if _ycr_state["nan_streak"] <= _YCR_HOLDOVER_COUNT and not math.isnan(
            _ycr_state["last_temp"]
        ):
            return _ycr_state["last_temp"]  # Hold last valid YCR reading briefly

    # Fall back to Optris (YCR unavailable, persistent failure, or no holdover value)
    if optris_sensor is not None:
        try:
            return optris_read_actual_temp(optris_sensor)
        except TemperatureSensorError:
            pass

    return float("nan")
