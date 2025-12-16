"""eTM-5050PC power supply Modbus RTU interface.

Features:
- Turn output ON/OFF
- Set: output voltage (V), output current (A)
- Read: output voltage (V), output current (A)

Default settings (see device manual):
- Baud rate     : 9600
- Framing       : 8 data bits, no parity, 1 stop bit (8N1)
- Timeout       : 0.5 second

Usage:
    python power_supply_etm.py
or import the functions in your own code

Author       : Delwin Tanto
Last updated : 06 Nov 2025
"""

import minimalmodbus

from .device_registry import DEVICE_HWIDS
from .port_detect import find_port_by_hwid

# Constants
HWID_SUBSTR = DEVICE_HWIDS["PSU"]  # eTM-5050PC PSU hardware ID substring


# -------------------- Custom exception --------------------


class PSUError(Exception):
    """Base exception for power supply related errors.

    Args:
        message (str): Human readable error message.
    """

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


# -------------------- Initialisation --------------------


def etm_open(port=None, slave_address=1):
    """Open and initialise a serial connection to the eTM-5050PC PSU.

    Args:
        port (str, optional): Explicit port name (e.g. ``'COM10'``). If ``None``
            the function will attempt to discover the device by HWID using
            :func:`port_detect.find_port_by_hwid`.
        slave_address (int): Modbus slave address (default: 1).

    Returns:
        minimalmodbus.Instrument: Configured Modbus RTU instrument instance.

    Raises:
        PSUError: If the device cannot be initialised or opened.
    """
    if port is None:
        port = find_port_by_hwid(HWID_SUBSTR)

    try:
        device = minimalmodbus.Instrument(port, slave_address)
        device.serial.baudrate = 9600
        device.serial.bytesize = 8
        device.serial.stopbits = 1
        device.serial.timeout = 0.5
        device.serial.write_timeout = 0.5
        device.serial.parity = "N"
        device.mode = minimalmodbus.MODE_RTU
        print(f"Power supply initialised on {port}.")
        return device
    except (OSError, minimalmodbus.ModbusException) as e:
        raise PSUError(f"Failed to initialise eTM-5050PC: {e}") from e


# -------------------- Write commands --------------------


def etm_set_onoff(power_supply, *, on):
    """Turn the PSU output on or off.

    Args:
        power_supply (minimalmodbus.Instrument): The connected PSU.
        on (bool): ``True`` to turn on, ``False`` to turn off.

    Raises:
        PSUError: If the Modbus write fails.
    """
    try:
        power_supply.write_register(0x0001, 1 if on else 0)
    except (OSError, minimalmodbus.ModbusException) as e:
        raise PSUError(f"Failed to turn PSU {'ON' if on else 'OFF'}: {e}") from e


def etm_set_voltage(power_supply, *, voltage):
    """Set the PSU output voltage.

    Args:
        power_supply (minimalmodbus.Instrument): The connected PSU.
        voltage (float): Desired output voltage in volts (0.0 to 50.0 V).

    Raises:
        ValueError: If ``voltage`` is out of the allowed range.
        PSUError: If communication with the device fails.
    """
    if not 0.0 <= voltage <= 50.0:
        raise ValueError("Voltage must be between 0 and 50 V")
    try:
        power_supply.write_register(0x0030, voltage * 10.0, 1)
    except (ValueError, OSError, minimalmodbus.ModbusException) as e:
        raise PSUError(f"Failed to set PSU voltage to {voltage} V: {e}") from e


def etm_set_current(power_supply, *, current):
    """Set the PSU output current.

    Args:
        power_supply (minimalmodbus.Instrument): The connected PSU.
        current (float): Desired output current in amperes (0.0 to 50.0 A).

    Raises:
        ValueError: If ``current`` is out of the allowed range.
        PSUError: If communication with the device fails.
    """
    if not 0.0 <= current <= 50.0:
        raise ValueError("Current must be between 0 and 50 A")
    try:
        power_supply.write_register(0x0031, current * 10.0, 1)
    except (ValueError, OSError, minimalmodbus.ModbusException) as e:
        raise PSUError(f"Failed to set PSU current to {current} A: {e}") from e


# -------------------- Read commands --------------------


def etm_read_voltage(power_supply):
    """Read the PSU output voltage.

    Args:
        power_supply (minimalmodbus.Instrument): The connected PSU.

    Returns:
        float: Current output voltage in volts or ``math.nan`` if read failed.
    """
    try:
        return power_supply.read_register(0x0010, 2)
    except (OSError, minimalmodbus.ModbusException):
        return float("nan")


def etm_read_current(power_supply):
    """Read the PSU output current.

    Args:
        power_supply (minimalmodbus.Instrument): The connected PSU.

    Returns:
        float: Current output current in amperes or ``math.nan`` if read failed.
    """
    try:
        return power_supply.read_register(0x0011, 2)
    except (OSError, minimalmodbus.ModbusException):
        return float("nan")


if __name__ == "__main__":
    etm_psu = etm_open()

    try:
        # Optionally set parameters here:
        # etm_set_onoff(etm_psu, True)  # Turn output ON
        # etm_set_onoff(etm_psu, False)  # Turn output OFF
        # etm_set_voltage(etm_psu, 12.0)  # Set output voltage to 12.0 V
        # etm_set_current(etm_psu, 1.5)   # Set output current to 1.5 A

        print(f"Voltage: {etm_read_voltage(etm_psu):.1f} V")
        print(f"Current: {etm_read_current(etm_psu):.1f} A")
    finally:
        etm_psu.serial.close()
