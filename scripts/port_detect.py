"""
A tiny module to find the serial port of a device by matching a unique hardware ID substring.
"""

import serial.tools.list_ports


def find_port_by_hwid(hwid_substr):
    """
    Return the serial port (e.g., 'COM10') whose HWID contains 'hwid_substr'.

    Args:
        hwid_substr (str): Unique hardware ID string to match.

    Returns:
        The matching device path (e.g., 'COM10' on Windows or '/dev/ttyUSB0' on Linux).

    Raises:
        RuntimeError: If no matching port is found, or if multiple ports match.
    """
    key = (hwid_substr or "").lower()
    if not key:
        raise RuntimeError("HWID substring is empty; set HWID_SUBSTR to something specific.")
    matches = [
        port.device
        for port in serial.tools.list_ports.comports()
        if key in (port.hwid or "").lower()
    ]
    if not matches:
        raise RuntimeError(f"No serial port matched HWID substring: {hwid_substr!r}")
    if len(matches) > 1:
        raise RuntimeError(f"Multiple ports matched HWID substring {hwid_substr!r}: {matches}")
    return matches[0]
