"""
Optris CT / CTlaser / CTvideo binary protocol reader/writer

Features:
- Read: temperature (°C), emissivity, transmission, laser state
- Set: emissivity, transmission, "Smart Averaging" time
- Toggle: laser ON/OFF, "Smart Averaging" ON/OFF, panel lock/unlock

Default settings (see device manual):
- Baud rate     : 115200
- Framing       : 8 data bits, no parity, 1 stop bit (8N1)
- Timeout       : 0.5 seconds
- Emissivity    : 0.75
- Transmission  : 0.9

Usage:
    python temp_sensor_optris.py
or import the functions in your own code.

Author       : Delwin Tanto
Last updated : 09 Oct 2025
"""

import math
import serial
from port_detect import find_port_by_hwid


# Constants
HWID_SUBSTR = "10C4:834B"  # OPTCTL3MLCF4 hardware ID substring
EMISSIVITY = 0.75
TRANSMISSION = 0.9
CHECKSUM = True  # Whether to use checksum for SET commands


# -------------------- Custom exception --------------------

class OptrisIRError(Exception):
    """Base exception for IR sensor related errors."""
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


# -------------------- Initialisation --------------------

def optris_open(port=None, baud=115200):
    """
    Open and return a serial connection to the Optris sensor.

    Args:
        port: Explicit COM port (e.g., 'COM10'). If None, the function looks up
              the port by HWID using 'find_port_by_hwid(HWID_SUBSTR)'.
        baud: Baud rate to use (default is DEFAULT_BAUD defined above).

    Returns:
        An open 'serial.Serial' instance configured for 8N1.

    Raises:
        RuntimeError: If the port cannot be discovered by HWID.
        serial.SerialException: If the port cannot be opened.
    """
    if port is None:
        port = find_port_by_hwid(HWID_SUBSTR)

    try:
        temp_sensor = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.5,
            write_timeout=0.5,
        )
        print(f"\033[32mOPTCTL3MLCF4 is initialised on port {port}.\033[0m")
        return temp_sensor
    except serial.SerialException as e:
        raise OptrisIRError(f"Failed to initialise OPTCTL3MLCF4: {e}") from e


# -------------------- Write commands --------------------

def _checksum_xor(*bytes_iter):
    """
    Compute XOR checksum over all command bytes to guard
    against corrupted bytes.

    Args:
        bytes_iter: Iterable of ints (0..255) to XOR.

    Returns:
        Single checksum byte (0..255).
    """
    cs = 0
    for b in bytes_iter:
        cs ^= (b & 0xFF)
    return cs


def _optris_write_word_2byte(temp_sensor, cmd, value_u16, checksum=CHECKSUM):
    """
    Send a SET command with a 16-bit payload; read back the 2-byte echo/answer.

    Args:
        temp_sensor: Open serial connection to the Optris sensor.
        cmd: SET command byte (e.g., 0x84 for emissivity, 0x85 for transmission).
        value_u16: Payload value 0..65535 (will be split into hi/lo).
        checksum: Whether to append XOR checksum byte.

    Returns:
        The device's 16-bit reply (often echoes the set value).

    Raises:
        OptrisIRError: If fewer than 2 bytes are received.
    """
    hi, lo = (value_u16 >> 8) & 0xFF, value_u16 & 0xFF
    frame = bytearray([cmd, hi, lo])
    if checksum:
        frame.append(_checksum_xor(*frame))
    temp_sensor.reset_input_buffer()
    temp_sensor.reset_output_buffer()
    temp_sensor.write(frame)
    data = temp_sensor.read(2)
    if len(data) != 2:
        raise OptrisIRError(f"Expected 2 bytes after SET, received {len(data)}")
    return (data[0] << 8) | data[1]


def _optris_write_word_1byte(temp_sensor, cmd, value, checksum=CHECKSUM):
    """
    Send a SET command with an 8-bit payload; read back the 1-byte echo/answer.

    Args:
        temp_sensor: Open serial connection to the Optris sensor.
        cmd: SET command byte (e.g., 0xA5 for laser ON/OFF).
        value: 1 for ON, 0 for OFF.
        checksum: Whether to append XOR checksum byte.

    Returns:
        The device's 8-bit reply (often echoes the set value).

    Raises:
        OptrisIRError: If fewer than 1 byte is received.
    """
    frame = bytearray([cmd, value])
    if checksum:
        frame.append(_checksum_xor(*frame))
    temp_sensor.reset_input_buffer()
    temp_sensor.reset_output_buffer()
    temp_sensor.write(frame)
    data = temp_sensor.read(1)
    if len(data) != 1:
        raise OptrisIRError(f"Expected 1 byte after SET, received {len(data)}")
    return data[0]


def optris_set_emissivity(temp_sensor, *, emissivity, checksum=CHECKSUM):
    """
    Set emissivity; returns the value echoed by the device.

    Args:
        temp_sensor: Open serial connection to the Optris sensor.
        emissivity: Desired emissivity in [0.0, 1.0].
        checksum: Whether to append the XOR checksum byte.

    Returns:
        The emissivity confirmed by the device.
    """
    if not 0.0 <= emissivity <= 1.0:
        raise OptrisIRError("Emissivity must be between 0 and 1")
    raw = int(round(emissivity * 1000))
    echoed = _optris_write_word_2byte(temp_sensor, 0x84, raw, checksum)  # SET emissivity
    return echoed / 1000.0


def optris_set_transmission(temp_sensor, *, transmission, checksum=CHECKSUM):
    """
    Set transmission; returns the value echoed by the device.

    Args:
        temp_sensor: Open serial connection to the Optris sensor.
        transmission: Desired transmission in [0.0, 1.0].
        checksum: Whether to append the XOR checksum byte.

    Returns:
        The transmission confirmed by the device.
    """
    if not 0.0 <= transmission <= 1.0:
        raise OptrisIRError("Transmission must be between 0 and 1")
    raw = int(round(transmission * 1000))
    echoed = _optris_write_word_2byte(temp_sensor, 0x85, raw, checksum)  # SET transmission
    return echoed / 1000.0


def optris_set_laser(temp_sensor, *, on, checksum=CHECKSUM):
    """
    Switch the laser ON/OFF.
    Sends 0xA5 <1|0> [checksum]; expects 1-byte echo (1=ON, 0=OFF).

    Args:
        temp_sensor: Open serial connection to the Optris sensor.
        on: True → ON, False → OFF.
        checksum: Append XOR checksum if True.

    Returns:
        The laser state confirmed by the device (True=ON, False=OFF).
    """
    return _optris_write_word_1byte(
        temp_sensor, 0xA5, 1 if on else 0, checksum
    )  # SET laser ON/OFF


def optris_set_avg_time(temp_sensor, *, avg_time, checksum=CHECKSUM):
    """
    Set the Optris "Smart Averaging" time window.
    "Smart Averaging" is an optional internal preprocessing method 
    to smooth out temperature readings.

    Args:
        temp_sensor: Open serial connection to the Optris sensor.
        avg_time: Desired average time (seconds).
        checksum: Whether to append the XOR checksum byte.

    Returns:
        The "Smart Averaging" time confirmed by the device.
    """
    if not 0.0 <= avg_time <= 6553.5:
        raise OptrisIRError("avg_time must be between 0.0 and 6553.5")
    raw = int(round(avg_time * 10))
    echoed = _optris_write_word_2byte(temp_sensor, 0x86, raw, checksum)  # SET averaging time
    return echoed / 10.0


def optris_set_avg_mode(temp_sensor, *, on, checksum=CHECKSUM):
    """
    Set the Optris "Smart Averaging" mode ON or OFF.
    "Smart Averaging" is an optional internal preprocessing method 
    to smooth out temperature readings.

    Args:
        temp_sensor: Open serial connection to the Optris sensor.
        on: True → ON, False → OFF.
        checksum: Append XOR checksum if True.

    Returns:
        The "Smart Averaging" state confirmed by the device (True=ON, False=OFF).
    """
    return _optris_write_word_1byte(
        temp_sensor, 0x9C, 1 if on else 0, checksum
    )  # SET avg mode ON/OFF


def optris_set_lock(temp_sensor, *, lock, checksum=CHECKSUM):
    """Lock or unlock the panel keys.

    Args:
        temp_sensor: Open serial connection to the Optris sensor.
        lock: True to lock the keys; False to unlock.
        checksum: Append XOR checksum if True.

    Returns:
        The panel lock state confirmed by the device (True=locked, False=unlocked).
    """
    return _optris_write_word_1byte(
        temp_sensor, 0x44, 1 if lock else 0, checksum
    )  # SET panel lock/unlock


# -------------------- Read commands --------------------

def _optris_read_word_2byte(temp_sensor, cmd_byte):
    """
    Send a one-byte read command and return the 16-bit big-endian reply.

    This follows the Optris binary protocol for single-device. 
    The sensor should reply with exactly 2 bytes.

    Args:
        temp_sensor: Open serial connection to the Optris sensor.
        cmd_byte: The one-byte command to send (e.g., 0x01 for process temp).

    Returns:
        The raw 16-bit integer in the range 0..65535.
    """
    try:
        temp_sensor.reset_input_buffer()
        temp_sensor.reset_output_buffer()
        temp_sensor.write(bytes([cmd_byte]))
        data = temp_sensor.read(2)
        if len(data) != 2:
            return math.nan
        return (data[0] << 8) | data[1]
    except (serial.SerialException, TimeoutError):
        return math.nan


def _optris_read_word_1byte(temp_sensor, cmd_byte):
    """
    Send a one-byte read command and return the one-byte reply.

    This follows the Optris binary protocol for single-device. 
    The sensor should reply with exactly 1 byte.

    Args:
        temp_sensor: Open serial connection to the Optris sensor.
        cmd_byte: The one-byte command to send (e.g., 0x1C for avg mode).

    Returns:
        The raw 8-bit integer in the range 0..255 or False if error.
    """
    try:
        temp_sensor.reset_input_buffer()
        temp_sensor.reset_output_buffer()
        temp_sensor.write(bytes([cmd_byte]))
        data = temp_sensor.read(1)
        if len(data) != 1:
            return False
        return data[0] == 1
    except (serial.SerialException, TimeoutError):
        return False


def optris_read_process_temp(temp_sensor):
    """
    Read and return the process temperature as degrees Celsius.
    Pre-processing such as averaging may be applied (read manual).

    Args:
        temp_sensor: Open serial connection to the Optris sensor.

    Returns:
        Temperature in °C (float).
    """
    raw = _optris_read_word_2byte(temp_sensor, 0x01)  # READ proccess temperature
    return (raw - 1000) / 10.0


def optris_read_head_temp(temp_sensor):
    """
    Read and return the head temperature as degrees Celsius.
    Used for safety purposes to avoid overheating the sensor head.

    Args:
        temp_sensor: Open serial connection to the Optris sensor.

    Returns:
        Temperature in °C (float).
    """
    raw = _optris_read_word_2byte(temp_sensor, 0x02)  # READ head temperature
    return (raw - 1000) / 10.0


def optris_read_box_temp(temp_sensor):
    """
    Read and return the box temperature as degrees Celsius.
    Used for safety purposes to avoid overheating the sensor box.

    Args:
        temp_sensor: Open serial connection to the Optris sensor.

    Returns:
        Temperature in °C (float).
    """
    raw = _optris_read_word_2byte(temp_sensor, 0x03)  # READ box temperature
    return (raw - 1000) / 10.0


def optris_read_actual_temp(temp_sensor):
    """
    Read and return the actual temperature as degrees Celsius
    without any preprocessing such as averaging.

    Args:
        temp_sensor: Open serial connection to the Optris sensor.

    Returns:
        Temperature in °C (float).
    """
    raw = _optris_read_word_2byte(temp_sensor, 0x81)  # READ actual temperature
    return (raw - 1000) / 10.0


def optris_read_emissivity(temp_sensor):
    """
    Read emissivity as a float in [0.0, 1.0].

    Args:
        temp_sensor: Open serial connection to the Optris sensor.

    Returns:
        emissivity = raw / 1000.
    """
    raw = _optris_read_word_2byte(temp_sensor, 0x04)  # READ emissivity
    return raw / 1000.0


def optris_read_transmission(temp_sensor):
    """
    Read transmission as a float in [0.0, 1.0].

    Args:
        temp_sensor: Open serial connection to the Optris sensor.

    Returns:
        transmission = raw / 1000.
    """
    raw = _optris_read_word_2byte(temp_sensor, 0x05)  # READ transmission
    return raw / 1000.0


def optris_read_laser(temp_sensor):
    """
    Read and return the laser status as a boolean.
    Sends 0x25; expects 1 byte back (1=ON, 0=OFF).

    Args:
        temp_sensor: Open serial connection to the Optris sensor.

    Returns:
        True if laser is ON, False if OFF.

    Raises:
        TimeoutError: If fewer than 1 byte is received within timeout.
    """
    return _optris_read_word_1byte(temp_sensor, 0x25)  # READ laser status


def optris_read_avg_time(temp_sensor):
    """
    Read the Optris "Smart Averaging" time window.
    "Smart Averaging" is an optional internal preprocessing method 
    to smooth out temperature readings.

    Args:
        temp_sensor: Open serial connection to the Optris sensor.

    Returns:
        average time = raw / 10 (unit: seconds).
    """
    raw = _optris_read_word_2byte(temp_sensor, 0x06)  # READ averaging time
    return raw / 10.0


def optris_read_avg_mode(temp_sensor):
    """
    Read the Optris "Smart Averaging" mode.
    "Smart Averaging" is an optional internal preprocessing method 
    to smooth out temperature readings.

    Args:
        temp_sensor: Open serial connection to the Optris sensor.

    Returns:
        True if "Smart Averaging" is ON, False if OFF.
    """
    return _optris_read_word_1byte(temp_sensor, 0x1C)  # READ avg mode


def optris_read_lock(temp_sensor):
    """Read whether the panel keys are locked.

    Args:
        temp_sensor: Open serial connection to the Optris sensor.

    Returns:
        True if keys are locked; False if keys are available.
    """
    return _optris_read_word_1byte(temp_sensor, 0x43)  # READ panel lock


if __name__ == "__main__":
    optris_sensor = optris_open()
    try:
        # Optionally set parameters here:
        # optris_set_emissivity(optris_sensor, emissivity=EMISSIVITY)
        # optris_set_transmission(optris_sensor, transmission=TRANSMISSION)
        # optris_set_laser(optris_sensor, on=True)  # Turn laser ON
        # optris_set_laser(optris_sensor, on=False)  # Turn laser OFF
        # optris_set_avg_time(optris_sensor, avg_time=1.0)  # Set "Smart Averaging" time to 1.0 s
        # optris_set_avg_mode(optris_sensor, on=True)  # Turn "Smart Averaging" ON
        # optris_set_avg_mode(optris_sensor, on=False)  # Turn "Smart Averaging" OFF
        # optris_set_lock(optris_sensor, lock=True)  # Lock panel keys
        # optris_set_lock(optris_sensor, lock=False)  # Unlock panel keys

        print(f"Emissivity          : {optris_read_emissivity(optris_sensor):.3f}")
        print(f"Transmission        : {optris_read_transmission(optris_sensor):.3f}")
        print(f"Process temperature : {optris_read_process_temp(optris_sensor):.1f} °C")
        print(f"Head temperature    : {optris_read_head_temp(optris_sensor):.1f} °C")
        print(f"Box temperature     : {optris_read_box_temp(optris_sensor):.1f} °C")
        print(f"Actual temperature  : {optris_read_actual_temp(optris_sensor):.1f} °C")
        print(f"Laser status        : {'ON' if optris_read_laser(optris_sensor) else 'OFF'}")
        print(f"Avg time            : {optris_read_avg_time(optris_sensor):.1f} s")
        print(f"Avg mode            : {'ON' if optris_read_avg_mode(optris_sensor) else 'OFF'}")
        print(
            f"Panel lock          : "
            f"{'LOCKED' if optris_read_lock(optris_sensor) else 'UNLOCKED'}"
        )
    finally:
        optris_sensor.close()
