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
    """
    Convert two 16-bit registers [low_addr_word, high_addr_word] into float32.
    Assumes big-endian within each 16-bit word, and low-address word is the LSW.
    """
    raw = (regs[1] << 16) | regs[0]
    return struct.unpack('>f', struct.pack('>I', raw))[0]


def _float_to_regs_be_lowfirst(value):
    """
    Convert float32 to two 16-bit registers [low_addr_word, high_addr_word].
    Big-endian within word, low-address word is LSW (common Modbus convention).
    """
    b = struct.pack('>f', float(value))  # 4 bytes, big-endian
    hi = (b[0] << 8) | b[1]              # high 16 bits
    lo = (b[2] << 8) | b[3]              # low 16 bits
    return [lo, hi]                      # [low_addr_word, high_addr_word]


# -------------------- Initialisation --------------------

def ycr_open(port=None, slave_address=1):
    """
    Open a serial port to the YCR-D30180AR IR thermometer.

    Args:
        port (str, optional): Explicit COM port (e.g., 'COM10'). If None, the function looks up
                              the port by HWID using 'find_port_by_hwid(HWID_SUBSTR)'.
        slave_address (int, optional): Modbus slave address. Defaults to 1.

    Returns:
        minimalmodbus.Instrument: The connected device.

    Raises:
        RuntimeError: If the port cannot be discovered by HWID.
        SystemExit: If connection fails after all retry attempts.
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
    """
    Read temperature from the YCR-D30180AR IR thermometer and apply calibration.

    Args:
        temp_sensor (Instrument): The IR sensor.

    Returns:
        float: Current temperature in °C.
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
    """
    Read emissivity setting from the YCR-D30180AR IR thermometer.

    Args:
        temp_sensor (Instrument): The IR sensor.
        
    Returns:
        float: Emissivity value (0.1 to 1.0).
    """
    try:
        regs = temp_sensor.read_registers(0x0402, 2)
        return _regs_to_float_be_lowfirst(regs)
    except (TimeoutError, OSError, minimalmodbus.ModbusException):
        return float('nan')


def ycr_set_emissivity(temp_sensor, *, emissivity):
    """
    Set emissivity of the YCR-D30180AR IR thermometer.

    Args:
        temp_sensor (Instrument): The IR sensor.
        
    Returns:
        float: Emissivity value (0.1 to 1.0).
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
    """
    Turn the laser pointer on the IR sensor ON/OFF.

    Args:
        temp_sensor (Instrument): The IR sensor.
        on (bool): True to turn ON, False to turn OFF.
    """
    try:
        temp_sensor.write_register(0x0438, 1 if on else 0)
    except (TimeoutError, OSError, minimalmodbus.ModbusException):
        pass


# -------------------- Averaging --------------------

def ycr_read_avg_time(temp_sensor):
    """
    Read averaging time of the IR sensor. The averaging time is the time
    over which the sensor averages the temperature readings.
    
    Args:
        temp_sensor (Instrument): The IR sensor.

    Returns:
        float: Averaging time in seconds (0 to 999.9).
    """
    try:
        regs = temp_sensor.read_registers(0x0414, 2)
        return _regs_to_float_be_lowfirst(regs)
    except (TimeoutError, OSError, minimalmodbus.ModbusException):
        return float('nan')

def ycr_set_avg_time(temp_sensor, *, avg_time):
    """
    Set averaging time of the IR sensor.
    
    Args:
        temp_sensor (Instrument): The IR sensor.
        avg_time (float): Averaging time in seconds (0 to 999.9).

    Raises:
        YCRIRError: If avg_time is out of range.
    """
    if not (avg_time == 0 or 0.1 <= avg_time <= 999.9):
        raise YCRIRError("Averaging time must be 0 (real-time) or between 0.1 and 999.9 seconds")

    try:
        regs = _float_to_regs_be_lowfirst(avg_time)
        temp_sensor.write_registers(0x0414, regs)
    except (TimeoutError, OSError, minimalmodbus.ModbusException):
        pass


# -------------------- Sensor temperature --------------------

def ycr_read_body_temp(temp_sensor):
    """
    Read the sensor body temperature. Mainly for diagnostic purposes.
    
    Args:
        temp_sensor (Instrument): The IR sensor.
        
    Returns:
        float: Sensor body temperature in °C.
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
