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

from joule_heating.plotting import close_plot

from .exceptions import PSUError, TemperatureSensorError
from .power_supply_etm import etm_open, etm_set_onoff
from .temp_sensor_optris import optris_open, optris_set_laser
from .temp_sensor_ycr import ycr_open, ycr_set_laser


def init_devices():
    """Initialize PSU and at least one IR temperature sensor.

    Opens connections to the eTM-5050PC power supply (required) and attempts
    to connect both YCR and Optris temperature sensors. The PSU must connect
    successfully, but at least ONE temperature sensor must be available.
    Uses automatic serial port discovery by hardware ID.

    Returns:
        tuple: ``(psu, ycr_sensor, optris_sensor)`` where:
            - ``psu`` is always non-None (required)
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
        error_msg = "Both temperature sensors failed to connect:\n" + \
            "\n".join(errors)
        raise TemperatureSensorError(error_msg)

    # Report which sensors connected successfully
    if ycr_sensor is not None and optris_sensor is not None:
        print("All devices connected successfully.")
    elif ycr_sensor is not None:
        print("PSU and YCR sensor connected. Optris sensor unavailable.")
    else:
        print("PSU and Optris sensor connected. YCR sensor unavailable.")

    return psu, ycr_sensor, optris_sensor


def shutdown_devices(psu=None, ycr_sensor=None, optris_sensor=None, *, log=True):
    """Safely shutdown PSU and turn off IR sensor lasers.

    This function attempts to power off the PSU and disable lasers on both
    YCR and Optris sensors. Exceptions during shutdown are caught and
    optionally logged, ensuring one device failure doesn't prevent cleanup
    of others. This is particularly important during program termination
    when resources must be released gracefully.

    Args:
        psu: PSU device instance (minimalmodbus.Instrument or None).
            If ``None``, PSU shutdown is skipped.
        ycr_sensor: YCR IR temperature sensor instance (minimalmodbus.Instrument
            or None). If ``None``, YCR laser shutdown is skipped.
        optris_sensor: Optris IR sensor instance (serial.Serial or None).
            If ``None``, Optris laser shutdown is skipped.
        log (bool): If ``True``, print error messages when device shutdown fails.
            Default is ``True``. Set to ``False`` to suppress output.

    Returns:
        None

    Note:
        This function is non-fatal by design. Even if one device fails to
        shutdown, the function will attempt to shutdown remaining devices.
        Check log output (if enabled) to diagnose any shutdown issues.

    Example:
        ```python
        try:
            run_experiment()
        finally:
            shutdown_devices(psu, ycr_sensor, optris_sensor, log=True)
        ```
    """
    # Attempt PSU shutdown
    if psu is not None:
        try:
            etm_set_onoff(psu, on=False)
        except PSUError as e:
            if log:
                print(f"[Warning] Error switching off PSU: {e}")

    # Attempt YCR laser shutdown
    if ycr_sensor is not None:
        try:
            ycr_set_laser(ycr_sensor, on=False)
        except TemperatureSensorError as e:
            if log:
                print(f"[Warning] Error turning off YCR laser: {e}")

    # Attempt Optris laser shutdown
    if optris_sensor is not None:
        try:
            optris_set_laser(optris_sensor, on=False)
        except TemperatureSensorError as e:
            if log:
                print(f"[Warning] Error turning off Optris laser: {e}")


def close_all(psu=None, ycr_sensor=None, optris_sensor=None, *, log=True, skip_plot=False):
    """Convenience wrapper: shutdown devices and close plot.

    Combines :func:`shutdown_devices` and plot closing into a single call.
    Useful for cleanup code where you want to ensure both hardware and
    graphics resources are released.

    Args:
        psu: PSU device instance or ``None``.
        ycr_sensor: YCR IR sensor instance or ``None``.
        optris_sensor: Optris IR sensor instance or ``None``.
        log (bool): If ``True``, print error messages. Default is ``True``.
        skip_plot (bool): If ``True``, skip closing plot. Use when plot is already
            closed or when calling from background thread. Default is ``False``.

    Returns:
        None

    Example:
        ```python
        try:
            run_experiment()
        finally:
            close_all(psu, ycr_sensor, optris_sensor, figure, log=True)
        ```
    """
    # Shutdown hardware
    shutdown_devices(psu, ycr_sensor, optris_sensor, log=log)

    # Close plot (skip if already closed or called from background thread)
    if not skip_plot:
        try:
            close_plot()
        except OSError as e:
            if log:
                print(f"[Warning] Error closing plot: {e}")


def enable_lasers(ycr_sensor=None, optris_sensor=None, on=True, *, log=True):
    """Enable or disable IR sensor laser pointers.

    Turns the laser pointers ON or OFF on both YCR and Optris sensors.
    This is typically called at the start of an experiment to enable targeting,
    and at shutdown to disable them for safety.

    Args:
        ycr_sensor: YCR IR temperature sensor instance (minimalmodbus.Instrument
            or None). If ``None``, YCR laser control is skipped.
        optris_sensor: Optris IR sensor instance (serial.Serial or None).
            If ``None``, Optris laser control is skipped.
        on (bool): If ``True``, turn lasers ON. If ``False``, turn them OFF.
            Default is ``True``.
        log (bool): If ``True``, print error messages when laser control fails.
            Default is ``True``.

    Returns:
        None

    Example:
        ```python
        # Turn on lasers at experiment start
        enable_lasers(ycr_sensor, optris_sensor, on=True)

        # Turn off lasers at experiment end
        enable_lasers(ycr_sensor, optris_sensor, on=False)
        ```
    """
    # Attempt YCR laser control
    if ycr_sensor is not None:
        try:
            ycr_set_laser(ycr_sensor, on=on)
        except TemperatureSensorError as e:
            if log:
                status = "ON" if on else "OFF"
                print(f"[Warning] Error turning {status} YCR laser: {e}")

    # Attempt Optris laser control
    if optris_sensor is not None:
        try:
            optris_set_laser(optris_sensor, on=on)
        except TemperatureSensorError as e:
            if log:
                status = "ON" if on else "OFF"
                print(f"[Warning] Error turning {status} Optris laser: {e}")
