"""
A tiny module to find the serial port of a device by matching a unique hardware ID substring.
"""

import serial.tools.list_ports
from .device_registry import DEVICE_NAMES


def find_port_by_hwid(hwid_substr):
    """Find the serial port of a device by matching hardware ID substring.

    Scans all connected serial ports and returns the port name whose hardware ID
    contains the provided substring (case-insensitive comparison).

    Args:
        hwid_substr (str): Unique substring of the target device's hardware ID.

    Returns:
        str: Device port name (e.g. ``'COM10'`` on Windows or ``'/dev/ttyUSB0'`` on Linux).

    Raises:
        RuntimeError: If no ports match, if multiple ports match, or if the substring is empty.
    """
    key = (hwid_substr or "").lower()
    if not key:
        raise RuntimeError(
            "HWID substring is empty; set HWID_SUBSTR to something specific.")
    matches = [
        port.device
        for port in serial.tools.list_ports.comports()
        if key in (port.hwid or "").lower()
    ]
    if not matches:
        device_name = DEVICE_NAMES.get(hwid_substr, "device")
        raise RuntimeError(
            f"No {device_name} detected. Ensure it is connected properly and powered on")
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple ports matched HWID substring {hwid_substr!r}: {matches}")
    return matches[0]
