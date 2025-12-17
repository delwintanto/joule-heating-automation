"""Custom exceptions for hardware device errors.

This module defines exception types for hardware control errors in the
Joule heating automation system. All exceptions inherit from a common
base to allow unified error handling.

Exception Hierarchy:
    DeviceError (base)
    ├── PSUError (power supply errors)
    └── TemperatureSensorError (IR sensor errors)

Author       : Delwin Tanto
Last updated : 17 Dec 2025
"""


class DeviceError(Exception):
    """Base exception for all hardware device errors.
    
    This is the parent class for all device-specific exceptions,
    allowing code to catch all device errors with a single except clause.
    """


class PSUError(DeviceError):
    """Exception raised for power supply (PSU) related errors.
    
    Raised when communication with the eTM-5050PC power supply fails,
    or when PSU operations (set voltage, set current, turn on/off) fail.
    """


class TemperatureSensorError(DeviceError):
    """Exception raised for temperature sensor related errors.
    
    Raised when communication with IR temperature sensors (YCR or Optris)
    fails, or when sensor operations (read temperature, set emissivity,
    control laser) fail.
    """
