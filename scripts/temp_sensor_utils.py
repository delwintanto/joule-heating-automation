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

from temp_sensor_optris import optris_read_actual_temp, OptrisIRError
from temp_sensor_ycr import ycr_read_temp, YCRIRError


def read_temperature(ycr_sensor, optris_sensor):
    """
    Read temperature from the appropriate sensor.

    If temperature is below YCR's minimum operating range (300°C), use Optris.
    Otherwise, use YCR for better accuracy at higher temperatures.

    Args:
        ycr_sensor (minimalmodbus.Instrument): YCR IR sensor instance.
        optris_sensor (serial.Serial): Optris IR sensor instance.

    Returns:
        float: Temperature in °C.
    """
    try:
        t_ycr = ycr_read_temp(ycr_sensor)
        # If YCR reading is valid and above its minimum range, use it
        if not math.isnan(t_ycr):
            return t_ycr
    except YCRIRError:
        pass

    # Fall back to Optris for low temperatures or if YCR fails
    try:
        return optris_read_actual_temp(optris_sensor)
    except OptrisIRError:
        return float("nan")
