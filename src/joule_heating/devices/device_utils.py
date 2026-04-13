"""Centralized hardware device management utilities.

This module provides helper functions to safely initialize, control, and
shutdown hardware devices (PSU, temperature sensors) used in Joule Heating
experiments. By consolidating device management, we ensure consistent
error handling and simplify cleanup across multiple scripts.

Key functions:
- :func:`shutdown_devices`: Safely shutdown PSU and turn off IR sensor lasers.
- :func:`close_all`: Convenience wrapper for shutdown_devices + plot closing.

Usage:
=====
```python
from joule_heating.devices import init_devices, shutdown_devices, close_all, PSUError

try:
    psu, ycr_sensor, optris_sensor = init_devices()
    # Run experiment...
finally:
    # Option 1: shutdown devices with error handling built-in
    shutdown_devices(psu, ycr_sensor, optris_sensor)

    # Option 2: shutdown + close plot in one call
    close_all(psu, ycr_sensor, optris_sensor)
```

Author       : Delwin Tanto
Last updated : 16 Dec 2025
"""

from typing import NamedTuple

from joule_heating.plotting import close_plot

from .exceptions import PSUError, TemperatureSensorError
from .power_supply_etm import etm_open, etm_set_onoff
from .temp_sensor_optris import optris_open, optris_set_laser
from .temp_sensor_ycr import ycr_open, ycr_set_laser


class Devices(NamedTuple):
    """Container for hardware device handles.

    Attributes:
        power_supply: eTM-5050PC PSU (minimalmodbus.Instrument).
        ycr_sensor: YCR IR sensor (minimalmodbus.Instrument or None).
        optris_sensor: Optris IR sensor (serial.Serial or None).
    """

    power_supply: object
    ycr_sensor: object
    optris_sensor: object


class Measurement(NamedTuple):
    """Single measurement reading from hardware.

    Attributes:
        temperature: Temperature in °C.
        voltage: Voltage in V.
        current: Current in A.
        resistance: Resistance in Ω (computed as V/I, or inf when I=0).
    """

    temperature: float
    voltage: float
    current: float
    resistance: float


def init_devices() -> "Devices":
    """Initialize PSU and at least one IR temperature sensor.

    Opens connections to the eTM-5050PC power supply (required) and attempts
    to connect both YCR and Optris temperature sensors. The PSU must connect
    successfully, but at least ONE temperature sensor must be available.
    Uses automatic serial port discovery by hardware ID.

    Returns:
        Devices: Named tuple ``(power_supply, ycr_sensor, optris_sensor)`` where:
            - ``power_supply`` is always non-None (required)
            - ``ycr_sensor`` is the YCR sensor instance or None if unavailable
            - ``optris_sensor`` is the Optris sensor instance or None if unavailable
            - At least one of the two sensors will be non-None

    Raises:
        PSUError: If PSU fails to initialize.
        TemperatureSensorError: If BOTH temperature sensors fail to connect.
            Error message includes details from both sensor failures.

    Example:
        ```python
        try:
            psu, ycr_sensor, optris_sensor = init_devices()
            # At least one sensor is guaranteed to be available
        except (PSUError, TemperatureSensorError) as e:
            # Handle device connection failure
            print(f"Device error: {e}")
        ```
    """
    # Initialize PSU (required)
    psu = etm_open()

    # Try to connect both temperature sensors
    ycr_sensor = None
    optris_sensor = None
    errors = []

    try:
        ycr_sensor = ycr_open()
    except TemperatureSensorError as e:
        errors.append(f"YCR sensor: {e}")

    try:
        optris_sensor = optris_open()
    except TemperatureSensorError as e:
        errors.append(f"Optris sensor: {e}")

    # Require at least one sensor to be connected
    if ycr_sensor is None and optris_sensor is None:
        error_msg = "Both temperature sensors failed to connect:\n" + "\n".join(errors)
        raise TemperatureSensorError(error_msg)

    # Report which sensors connected successfully
    if ycr_sensor is not None and optris_sensor is not None:
        print("All devices connected successfully.")
    elif ycr_sensor is not None:
        print("PSU and YCR sensor connected. Optris sensor unavailable.")
    else:
        print("PSU and Optris sensor connected. YCR sensor unavailable.")

    return Devices(psu, ycr_sensor, optris_sensor)


def shutdown_devices(devices: "Devices | None" = None, *, log: bool = True) -> None:
    """Safely shutdown PSU and turn off IR sensor lasers.

    This function attempts to power off the PSU and disable lasers on both
    YCR and Optris sensors. Exceptions during shutdown are caught and
    optionally logged, ensuring one device failure doesn't prevent cleanup
    of others. This is particularly important during program termination
    when resources must be released gracefully.

    Args:
        devices (Devices or None): Device handles to shut down.
        log (bool): If ``True``, print error messages when device shutdown fails.
            Default is ``True``. Set to ``False`` to suppress output.

    Returns:
        None
    """
    if devices is None:
        return

    # Attempt PSU shutdown
    if devices.power_supply is not None:
        try:
            etm_set_onoff(devices.power_supply, on=False)
        except PSUError as e:
            if log:
                print(f"[Warning] Error switching off PSU: {e}")

    # Attempt YCR laser shutdown
    if devices.ycr_sensor is not None:
        try:
            ycr_set_laser(devices.ycr_sensor, on=False)
        except TemperatureSensorError as e:
            if log:
                print(f"[Warning] Error turning off YCR laser: {e}")

    # Attempt Optris laser shutdown
    if devices.optris_sensor is not None:
        try:
            optris_set_laser(devices.optris_sensor, on=False)
        except TemperatureSensorError as e:
            if log:
                print(f"[Warning] Error turning off Optris laser: {e}")


def close_all(
    devices: "Devices | None" = None, *, log: bool = True, skip_plot: bool = False
) -> None:
    """Convenience wrapper: shutdown devices and close plot.

    Combines :func:`shutdown_devices` and plot closing into a single call.
    Useful for cleanup code where you want to ensure both hardware and
    graphics resources are released.

    Args:
        devices (Devices or None): Device handles to shut down.
        log (bool): If ``True``, print error messages. Default is ``True``.
        skip_plot (bool): If ``True``, skip closing plot. Default is ``False``.

    Returns:
        None
    """
    # Shutdown hardware
    shutdown_devices(devices, log=log)

    # Close plot (skip if already closed or called from background thread)
    if not skip_plot:
        try:
            close_plot()
        except OSError as e:
            if log:
                print(f"[Warning] Error closing plot: {e}")


def enable_lasers(devices: "Devices | None" = None, on: bool = True, *, log: bool = True) -> None:
    """Enable or disable IR sensor laser pointers.

    Args:
        devices (Devices or None): Device handles. If ``None``, nothing happens.
        on (bool): If ``True``, turn lasers ON. If ``False``, turn them OFF.
        log (bool): If ``True``, print error messages when laser control fails.

    Returns:
        None
    """
    if devices is None:
        return

    # Attempt YCR laser control
    if devices.ycr_sensor is not None:
        try:
            ycr_set_laser(devices.ycr_sensor, on=on)
        except TemperatureSensorError as e:
            if log:
                status = "ON" if on else "OFF"
                print(f"[Warning] Error turning {status} YCR laser: {e}")

    # Attempt Optris laser control
    if devices.optris_sensor is not None:
        try:
            optris_set_laser(devices.optris_sensor, on=on)
        except TemperatureSensorError as e:
            if log:
                status = "ON" if on else "OFF"
                print(f"[Warning] Error turning {status} Optris laser: {e}")
