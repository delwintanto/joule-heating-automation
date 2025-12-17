"""Device control modules for Joule heating automation.

This package contains modules for controlling the power supply unit (PSU)
and IR temperature sensors used in Joule heating experiments.

Modules:
    - device_utils: Device initialization and shutdown utilities
    - exceptions: Custom exception definitions for device errors
    - power_supply_etm: Power supply unit control functions
    - temp_sensor_utils: Temperature sensor reading utilities
    - temp_sensor_ycr: YCR IR sensor specific functions
    - temp_sensor_optris: Optris IR sensor specific functions
    - port_detect: Serial port detection utilities

Author       : Delwin Tanto
Last updated : 17 Dec 2025
"""

from .device_utils import close_all, enable_lasers, init_devices, shutdown_devices
from .exceptions import DeviceError, PSUError, TemperatureSensorError
from .power_supply_etm import (
    etm_read_current,
    etm_read_voltage,
    etm_set_current,
    etm_set_onoff,
    etm_set_voltage,
)
from .temp_sensor_utils import read_temperature

__all__ = [
    "init_devices",
    "close_all",
    "shutdown_devices",
    "enable_lasers",
    "etm_set_onoff",
    "etm_set_current",
    "etm_set_voltage",
    "etm_read_current",
    "etm_read_voltage",
    "DeviceError",
    "PSUError",
    "TemperatureSensorError",
    "read_temperature",
]
