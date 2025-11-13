"""
YCR-D30180AR IR thermometer interface using Modbus RTU protocol.

Features:
- Read temperature (°C)
- Turn laser pointer ON/OFF

Default settings (see device manual):
- Baud rate     : 9600
- Framing       : 8 data bits, even parity, 1 stop bit (8E1)
- Timeout       : 0.5 second

Usage:
    python temp_sensor_ycr.py
or import the functions in your own code

Author       : Delwin Tanto
Last updated : 06 Nov 2025
"""

import struct
import minimalmodbus
from port_detect import find_port_by_hwid


# Constants
HWID_SUBSTR = "AQ03H99EA"  # YCR-D30180AR hardware ID substring


# -------------------- Custom exception --------------------

class YCRIRError(Exception):
    """Base exception for IR sensor related errors."""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


# -------------------- Helper functions --------------------

def _regs_to_float_be_lowfirst(regs):
    """Convert two 16-bit Modbus registers to float32.

    Interprets two consecutive 16-bit register values as a single-precision
    floating-point number. Assumes big-endian byte order within each word and
    that the low-address word contains the least significant word (LSW) of
    the 32-bit value.

    Args:
        regs (list): Two 16-bit register values [low_addr_word, high_addr_word].

    Returns:
        float: Interpreted as 32-bit IEEE float.
    """
    raw = (regs[1] << 16) | regs[0]
    return struct.unpack('>f', struct.pack('>I', raw))[0]


def _float_to_regs_be_lowfirst(value):
    """Convert float32 to two 16-bit Modbus registers.

    Converts a single-precision floating-point number to two consecutive
    16-bit register values for Modbus transmission. Assumes big-endian byte
    order within each word and that the low-address word contains the least
    significant word (LSW).

    Args:
        value (float): The floating-point value to convert.

    Returns:
        list: Two 16-bit integers [low_addr_word, high_addr_word].
    """
    b = struct.pack('>f', float(value))  # 4 bytes, big-endian
    hi = (b[0] << 8) | b[1]              # high 16 bits
    lo = (b[2] << 8) | b[3]              # low 16 bits
    return [lo, hi]                      # [low_addr_word, high_addr_word]


# -------------------- Initialisation --------------------

def ycr_open(port=None, slave_address=1):
    """Open a Modbus RTU connection to the YCR-D30180AR IR thermometer.

    Establishes a serial connection configured for YCR Modbus communication
    (9600 baud, 8E1 framing). If no port is specified, performs automatic
    HWID-based port discovery.

    Args:
        port (str, optional): Explicit COM port identifier (e.g., 'COM10').
            If None, discovers port via HWID substring. Defaults to None.
        slave_address (int, optional): Modbus slave address. Defaults to 1.

    Returns:
        minimalmodbus.Instrument: Configured Modbus device instance.

    Raises:
        RuntimeError: If the port cannot be discovered by HWID.
        YCRIRError: If connection fails after all retry attempts.
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
        device.serial.parity = "E"
        device.mode = minimalmodbus.MODE_RTU
        print(f"\033[32mYCR-D30180AR initialised on {port}\033[0m")
        return device
    except (OSError, minimalmodbus.ModbusException) as e:
        raise YCRIRError(f"Failed to initialise YCR-D30180AR: {e}") from e


# -------------------- Temperature --------------------

def ycr_read_temp(temp_sensor):
    """Read the target temperature with factory calibration applied.

    Reads the temperature measurement from Modbus register 0x0400 (two-word
    float) and applies the factory calibration factor (×1.205). Returns NaN
    if communication fails.

    Args:
        temp_sensor (minimalmodbus.Instrument): The connected YCR sensor.

    Returns:
        float: Temperature in degrees Celsius. Returns math.nan on error.
    """
    try:
        regs = temp_sensor.read_registers(0x0400, 2)
        return _regs_to_float_be_lowfirst(regs) * 1.205
    except (
        TimeoutError,
        IOError,
        YCRIRError,
        struct.error,
        OSError,
        minimalmodbus.ModbusException,
    ):
        return float('nan')


# -------------------- Emissivity --------------------

def ycr_read_emissivity(temp_sensor):
    """Read the emissivity setting from the sensor.

    Retrieves the emissivity value from Modbus register 0x0402 (two-word
    float). Emissivity is a material property used to convert IR measurements
    to accurate temperature readings.

    Args:
        temp_sensor (minimalmodbus.Instrument): The connected YCR sensor.

    Returns:
        float: Emissivity in range [0.1, 1.0]. Returns math.nan on error.
    """
    try:
        regs = temp_sensor.read_registers(0x0402, 2)
        return _regs_to_float_be_lowfirst(regs)
    except (TimeoutError, OSError, minimalmodbus.ModbusException):
        return float('nan')


def ycr_set_emissivity(temp_sensor, *, emissivity):
    """Set the emissivity value in the sensor.

    Configures the emissivity (material's infrared emission property) used
    for temperature calculation. Value is written to Modbus register 0x0402.

    Args:
        temp_sensor (minimalmodbus.Instrument): The connected YCR sensor.
        emissivity (float): Desired emissivity in range [0.1, 1.0].

    Raises:
        YCRIRError: If emissivity is outside valid range [0.1, 1.0].
    """
    if not 0.1 <= emissivity <= 1.0:
        raise YCRIRError("Emissivity must be between 0.1 and 1.0")

    try:
        regs = _float_to_regs_be_lowfirst(emissivity)
        temp_sensor.write_registers(0x0402, regs)
    except (TimeoutError, OSError, minimalmodbus.ModbusException):
        pass


# -------------------- Laser pointer --------------------

def ycr_set_laser(temp_sensor, *, on):
    """Control the laser pointer ON/OFF.

    Sends a Modbus write command to control the built-in laser pointer used
    for targeting the measurement area on the sample surface.

    Args:
        temp_sensor (minimalmodbus.Instrument): The connected YCR sensor.
        on (bool): True to turn laser ON, False to turn laser OFF.
    """
    try:
        temp_sensor.write_register(0x0438, 1 if on else 0)
    except (TimeoutError, OSError, minimalmodbus.ModbusException):
        pass


# -------------------- Averaging --------------------

def ycr_read_avg_time(temp_sensor):
    """Read the averaging time window setting.

    Retrieves the temporal averaging window from Modbus register 0x0414
    (two-word float). The sensor internally averages temperature readings
    over this time window to reduce noise.

    Args:
        temp_sensor (minimalmodbus.Instrument): The connected YCR sensor.

    Returns:
        float: Averaging time in seconds, range [0, 999.9]. Returns math.nan on error.
    """
    try:
        regs = temp_sensor.read_registers(0x0414, 2)
        return _regs_to_float_be_lowfirst(regs)
    except (TimeoutError, OSError, minimalmodbus.ModbusException):
        return float('nan')


def ycr_set_avg_time(temp_sensor, *, avg_time):
    """Set the averaging time window for temperature readings.

    Configures the temporal averaging window (register 0x0414). Higher values
    provide more smoothing but slower response to temperature changes. Value
    of 0 enables real-time (no averaging).

    Args:
        temp_sensor (minimalmodbus.Instrument): The connected YCR sensor.
        avg_time (float): Averaging window in seconds. Must be 0 (real-time)
            or in range [0.1, 999.9].

    Raises:
        YCRIRError: If avg_time is outside valid range.
    """
    if not (avg_time == 0 or 0.1 <= avg_time <= 999.9):
        raise YCRIRError(
            "Averaging time must be 0 (real-time) or between 0.1 and 999.9 seconds")

    try:
        regs = _float_to_regs_be_lowfirst(avg_time)
        temp_sensor.write_registers(0x0414, regs)
    except (TimeoutError, OSError, minimalmodbus.ModbusException):
        pass


# -------------------- Sensor temperature --------------------

def ycr_read_body_temp(temp_sensor):
    """Read the sensor body (electronics) temperature.

    Retrieves the internal temperature of the sensor electronics from Modbus
    register 0x0404 (two-word float). Used primarily for diagnostic purposes
    and thermal management.

    Args:
        temp_sensor (minimalmodbus.Instrument): The connected YCR sensor.

    Returns:
        float: Sensor body temperature in degrees Celsius. Returns math.nan on error.
    """
    try:
        regs = temp_sensor.read_registers(0x0404, 2)
        return _regs_to_float_be_lowfirst(regs)
    except (TimeoutError, OSError, minimalmodbus.ModbusException):
        return float('nan')


if __name__ == "__main__":
    ycr_sensor = ycr_open()

    try:
        # Optionally set parameters here:
        # ycr_set_laser(ycr_sensor, on=True)  # Turn laser ON
        # ycr_set_laser(ycr_sensor, on=False)  # Turn laser OFF
        ycr_set_emissivity(ycr_sensor, emissivity=0.95)  # Set emissivity
        ycr_set_avg_time(ycr_sensor, avg_time=0)  # Set averaging time

        print(f"Temperature: {ycr_read_temp(ycr_sensor):.1f} °C")
        print(f"Emissivity: {ycr_read_emissivity(ycr_sensor):.2f}")
        print(f"Averaging time: {ycr_read_avg_time(ycr_sensor):.1f} s")
        print(f"Sensor temperature: {ycr_read_body_temp(ycr_sensor):.1f} °C")
    finally:
        ycr_sensor.serial.close()
