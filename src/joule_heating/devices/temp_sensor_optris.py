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
- Emissivity    : 0.3
- Transmission  : 0.8

Usage:
    python temp_sensor_optris.py
or import the functions in your own code.

Author       : Delwin Tanto
Last updated : 09 Oct 2025
"""

import math
import serial
from .device_registry import DEVICE_HWIDS
from .port_detect import find_port_by_hwid


# Constants
HWID_SUBSTR = DEVICE_HWIDS["OPTRIS_SENSOR"]  # OPTCTL3MLCF4 hardware ID substring
EMISSIVITY = 0.3
TRANSMISSION = 0.8
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
        print(f"Optris sensor is initialised on port {port}.")
        return temp_sensor
    except serial.SerialException as e:
        raise OptrisIRError(f"Failed to initialise OPTCTL3MLCF4: {e}") from e


# -------------------- Write commands --------------------

def _checksum_xor(*bytes_iter):
    """Compute XOR checksum over all command bytes.

    Computes the XOR of all input bytes as a guard against corrupted
    bytes during serial transmission to the sensor.

    Args:
        bytes_iter: Variable number of integers (0..255) to XOR together.

    Returns:
        int: Single checksum byte in the range 0..255.
    """
    cs = 0
    for b in bytes_iter:
        cs ^= (b & 0xFF)
    return cs


def _optris_write_word_2byte(temp_sensor, cmd, value_u16, checksum=CHECKSUM):
    """Send a SET command with 16-bit payload and read 2-byte echo.

    Sends a binary frame containing a command byte and 16-bit value to the
    sensor, optionally with XOR checksum protection. Reads back the device's
    2-byte acknowledgement (typically echoing the set value).

    Args:
        temp_sensor (serial.Serial): Open serial connection to Optris sensor.
        cmd (int): SET command byte (e.g., 0x84 for emissivity).
        value_u16 (int): Payload value in range 0..65535.
        checksum (bool): If True, append XOR checksum byte to frame.

    Returns:
        int: Device's 16-bit reply (typically echoes the set value).

    Raises:
        OptrisIRError: If fewer than 2 bytes are received from sensor.
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
        raise OptrisIRError(
            f"Expected 2 bytes after SET, received {len(data)}")
    return (data[0] << 8) | data[1]


def _optris_write_word_1byte(temp_sensor, cmd, value, checksum=CHECKSUM):
    """Send a SET command with 8-bit payload and read 1-byte echo.

    Sends a binary frame containing a command byte and 8-bit value to the
    sensor, optionally with XOR checksum protection. Reads back the device's
    1-byte acknowledgement (typically echoing the set value).

    Args:
        temp_sensor (serial.Serial): Open serial connection to Optris sensor.
        cmd (int): SET command byte (e.g., 0xA5 for laser ON/OFF).
        value (int): Payload value; typically 1 for ON, 0 for OFF.
        checksum (bool): If True, append XOR checksum byte to frame.

    Returns:
        int: Device's 8-bit reply (typically echoes the set value).

    Raises:
        OptrisIRError: If fewer than 1 byte is received from sensor.
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
    """Set the sensor emissivity value.

    Sends a SET command to configure the emissivity (how well the material
    emits infrared radiation), which is used to convert raw sensor readings
    to accurate temperature values.

    Args:
        temp_sensor (serial.Serial): Open serial connection to Optris sensor.
        emissivity (float): Desired emissivity in range [0.0, 1.0].
        checksum (bool): If True, append XOR checksum byte to frame.

    Returns:
        float: The emissivity confirmed by the device (range [0.0, 1.0]).

    Raises:
        OptrisIRError: If emissivity is outside valid range [0.0, 1.0].
    """
    if not 0.0 <= emissivity <= 1.0:
        raise OptrisIRError("Emissivity must be between 0 and 1")
    raw = int(round(emissivity * 1000))
    echoed = _optris_write_word_2byte(
        temp_sensor, 0x84, raw, checksum)  # SET emissivity
    return echoed / 1000.0


def optris_set_transmission(temp_sensor, *, transmission, checksum=CHECKSUM):
    """Set the atmospheric transmission value.

    Sends a SET command to configure the transmission (how well light passes
    through the atmosphere/window between sensor and target), which corrects
    for atmospheric absorption in temperature measurements.

    Args:
        temp_sensor (serial.Serial): Open serial connection to Optris sensor.
        transmission (float): Desired transmission in range [0.0, 1.0].
        checksum (bool): If True, append XOR checksum byte to frame.

    Returns:
        float: The transmission confirmed by the device (range [0.0, 1.0]).

    Raises:
        OptrisIRError: If transmission is outside valid range [0.0, 1.0].
    """
    if not 0.0 <= transmission <= 1.0:
        raise OptrisIRError("Transmission must be between 0 and 1")
    raw = int(round(transmission * 1000))
    echoed = _optris_write_word_2byte(
        temp_sensor, 0x85, raw, checksum)  # SET transmission
    return echoed / 1000.0


def optris_set_laser(temp_sensor, *, on, checksum=CHECKSUM):
    """Control the laser pointer (ON or OFF).

    Sends command 0xA5 to toggle the built-in laser pointer. The laser helps
    with targeting the measurement area on the sample surface. Returns the
    laser state confirmed by the device.

    Args:
        temp_sensor (serial.Serial): Open serial connection to Optris sensor.
        on (bool): True to turn laser ON, False to turn laser OFF.
        checksum (bool): If True, append XOR checksum byte to frame.

    Returns:
        bool: Laser state confirmed by the device (True=ON, False=OFF).
    """
    return _optris_write_word_1byte(
        temp_sensor, 0xA5, 1 if on else 0, checksum
    )  # SET laser ON/OFF


def optris_set_avg_time(temp_sensor, *, avg_time, checksum=CHECKSUM):
    """Set the Smart Averaging time window.

    Configures the duration of the "Smart Averaging" preprocessing method,
    which smooths out rapid temperature fluctuations to provide more stable
    readings. Higher values = more smoothing but slower response.

    Args:
        temp_sensor (serial.Serial): Open serial connection to Optris sensor.
        avg_time (float): Desired averaging window in seconds, range [0.0, 6553.5].
        checksum (bool): If True, append XOR checksum byte to frame.

    Returns:
        float: The Smart Averaging time confirmed by the device (in seconds).

    Raises:
        OptrisIRError: If avg_time is outside valid range [0.0, 6553.5].
    """
    if not 0.0 <= avg_time <= 6553.5:
        raise OptrisIRError("avg_time must be between 0.0 and 6553.5")
    raw = int(round(avg_time * 10))
    echoed = _optris_write_word_2byte(
        temp_sensor, 0x86, raw, checksum)  # SET averaging time
    return echoed / 10.0


def optris_set_avg_mode(temp_sensor, *, on, checksum=CHECKSUM):
    """Enable or disable Smart Averaging mode.

    Controls whether the "Smart Averaging" preprocessing method is active.
    When enabled, rapid temperature fluctuations are smoothed out using the
    configured averaging time window. Useful for high-noise environments.

    Args:
        temp_sensor (serial.Serial): Open serial connection to Optris sensor.
        on (bool): True to enable Smart Averaging, False to disable.
        checksum (bool): If True, append XOR checksum byte to frame.

    Returns:
        bool: Smart Averaging state confirmed by device (True=ON, False=OFF).
    """
    return _optris_write_word_1byte(
        temp_sensor, 0x9C, 1 if on else 0, checksum
    )  # SET avg mode ON/OFF


def optris_set_lock(temp_sensor, *, lock, checksum=CHECKSUM):
    """Lock or unlock the sensor panel keys.

    Controls whether the physical panel keys on the sensor are functional.
    Locking prevents accidental parameter changes during unattended operation.

    Args:
        temp_sensor (serial.Serial): Open serial connection to Optris sensor.
        lock (bool): True to lock panel keys, False to unlock.
        checksum (bool): If True, append XOR checksum byte to frame.

    Returns:
        bool: Panel lock state confirmed by device (True=locked, False=unlocked).
    """
    return _optris_write_word_1byte(
        temp_sensor, 0x44, 1 if lock else 0, checksum
    )  # SET panel lock/unlock


# -------------------- Read commands --------------------

def _optris_read_word_2byte(temp_sensor, cmd_byte):
    """Send a read command and return 16-bit big-endian reply.

    Follows the Optris binary protocol for single-device communication.
    Sends a one-byte read command and expects exactly 2 bytes in response.
    Returns NaN if communication fails (timeout or wrong byte count).

    Args:
        temp_sensor (serial.Serial): Open serial connection to Optris sensor.
        cmd_byte (int): Read command byte (e.g., 0x01 for process temperature).

    Returns:
        int: Raw 16-bit integer in range 0..65535, or math.nan on error.
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
    """Send a read command and return 1-byte boolean reply.

    Follows the Optris binary protocol for single-device communication.
    Sends a one-byte read command and expects exactly 1 byte in response.
    Interprets the byte as a boolean (1=True, 0=False). Returns False if
    communication fails (timeout or wrong byte count).

    Args:
        temp_sensor (serial.Serial): Open serial connection to Optris sensor.
        cmd_byte (int): Read command byte (e.g., 0x1C for avg mode).

    Returns:
        bool: True if byte equals 1, False otherwise or on error.
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
    """Read the process (pre-processed) temperature.

    Reads the temperature value after any internal preprocessing (e.g.,
    Smart Averaging) has been applied by the sensor. This is the typical
    value to use for feedback control or logging.

    Args:
        temp_sensor (serial.Serial): Open serial connection to Optris sensor.

    Returns:
        float: Temperature in degrees Celsius.
    """
    raw = _optris_read_word_2byte(
        temp_sensor, 0x01)  # READ proccess temperature
    return (raw - 1000) / 10.0


def optris_read_head_temp(temp_sensor):
    """Read the sensor head temperature for safety monitoring.

    Reads the internal temperature of the sensor's optical head. Used to
    detect overheating and trigger protective shutdown if the head exceeds
    safe operating temperature limits.

    Args:
        temp_sensor (serial.Serial): Open serial connection to Optris sensor.

    Returns:
        float: Sensor head temperature in degrees Celsius.
    """
    raw = _optris_read_word_2byte(temp_sensor, 0x02)  # READ head temperature
    return (raw - 1000) / 10.0


def optris_read_box_temp(temp_sensor):
    """Read the sensor electronics box temperature for safety monitoring.

    Reads the internal temperature of the electronics enclosure. Used to
    detect overheating and trigger protective shutdown if the box exceeds
    safe operating temperature limits during extended operation.

    Args:
        temp_sensor (serial.Serial): Open serial connection to Optris sensor.

    Returns:
        float: Sensor box temperature in degrees Celsius.
    """
    raw = _optris_read_word_2byte(temp_sensor, 0x03)  # READ box temperature
    return (raw - 1000) / 10.0


def optris_read_actual_temp(temp_sensor):
    """Read the raw actual temperature without preprocessing.

    Reads the unprocessed temperature measurement directly from the sensor.
    Useful for diagnostics and validation, as it is not affected by Smart
    Averaging or other internal smoothing filters.

    Args:
        temp_sensor (serial.Serial): Open serial connection to Optris sensor.

    Returns:
        float: Raw temperature in degrees Celsius.
    """
    raw = _optris_read_word_2byte(temp_sensor, 0x81)  # READ actual temperature
    return (raw - 1000) / 10.0


def optris_read_emissivity(temp_sensor):
    """Read the current emissivity setting.

    Retrieves the currently configured emissivity value used by the sensor
    for temperature calculations. Emissivity is a material property that
    affects the accuracy of IR temperature measurements.

    Args:
        temp_sensor (serial.Serial): Open serial connection to Optris sensor.

    Returns:
        float: Emissivity value in range [0.0, 1.0].
    """
    raw = _optris_read_word_2byte(temp_sensor, 0x04)  # READ emissivity
    return raw / 1000.0


def optris_read_transmission(temp_sensor):
    """Read the current atmospheric transmission setting.

    Retrieves the currently configured transmission value that corrects for
    atmospheric absorption between the sensor and target. Transmission
    affects the accuracy of temperature measurements over distance.

    Args:
        temp_sensor (serial.Serial): Open serial connection to Optris sensor.

    Returns:
        float: Transmission value in range [0.0, 1.0].
    """
    raw = _optris_read_word_2byte(temp_sensor, 0x05)  # READ transmission
    return raw / 1000.0


def optris_read_laser(temp_sensor):
    """Read the laser pointer status.

    Reads the current state of the built-in laser pointer used for
    targeting the measurement area on the sample surface.

    Args:
        temp_sensor (serial.Serial): Open serial connection to Optris sensor.

    Returns:
        bool: True if laser is ON, False if laser is OFF.

    Raises:
        TimeoutError: If fewer than 1 byte is received within timeout period.
    """
    return _optris_read_word_1byte(temp_sensor, 0x25)  # READ laser status


def optris_read_avg_time(temp_sensor):
    """Read the Smart Averaging time window setting.

    Retrieves the duration of the internal "Smart Averaging" preprocessing
    window. This controls how much temporal smoothing is applied to
    temperature readings.

    Args:
        temp_sensor (serial.Serial): Open serial connection to Optris sensor.

    Returns:
        float: Averaging time window in seconds.
    """
    raw = _optris_read_word_2byte(temp_sensor, 0x06)  # READ averaging time
    return raw / 10.0


def optris_read_avg_mode(temp_sensor):
    """Read the Smart Averaging mode status.

    Reads whether the "Smart Averaging" preprocessing method is currently
    enabled or disabled. When enabled, temperature readings are smoothed
    using the configured averaging time window.

    Args:
        temp_sensor (serial.Serial): Open serial connection to Optris sensor.

    Returns:
        bool: True if Smart Averaging is ON, False if OFF.
    """
    return _optris_read_word_1byte(temp_sensor, 0x1C)  # READ avg mode


def optris_read_lock(temp_sensor):
    """Read the panel key lock status.

    Reads whether the physical panel keys on the sensor are currently
    locked or available for user input.

    Args:
        temp_sensor (serial.Serial): Open serial connection to Optris sensor.

    Returns:
        bool: True if panel keys are locked, False if unlocked.
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

        print(
            f"Emissivity          : {optris_read_emissivity(optris_sensor):.3f}")
        print(
            f"Transmission        : {optris_read_transmission(optris_sensor):.3f}")
        print(
            f"Process temperature : {optris_read_process_temp(optris_sensor):.1f} °C")
        print(
            f"Head temperature    : {optris_read_head_temp(optris_sensor):.1f} °C")
        print(
            f"Box temperature     : {optris_read_box_temp(optris_sensor):.1f} °C")
        print(
            f"Actual temperature  : {optris_read_actual_temp(optris_sensor):.1f} °C")
        print(
            f"Laser status        : {'ON' if optris_read_laser(optris_sensor) else 'OFF'}")
        print(
            f"Avg time            : {optris_read_avg_time(optris_sensor):.1f} s")
        print(
            f"Avg mode            : {'ON' if optris_read_avg_mode(optris_sensor) else 'OFF'}")
        print(
            f"Panel lock          : "
            f"{'LOCKED' if optris_read_lock(optris_sensor) else 'UNLOCKED'}"
        )
    finally:
        optris_sensor.close()
