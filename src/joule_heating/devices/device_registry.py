"""Central registry of device hardware IDs and metadata.

This module provides a single source of truth for hardware identification
strings used for automatic device detection via serial port scanning.

Author       : Delwin Tanto
Last updated : 15 Dec 2025
"""

# Hardware ID substrings for device detection
DEVICE_HWIDS = {
    "PSU": "AB0P06NMA",  # eTM-5050PC power supply
    "YCR_SENSOR": "AQ03H99EA",  # YCR-D30180AR IR thermometer
    "OPTRIS_SENSOR": "10C4:834B",  # Optris OPTCTL3MLCF4 IR thermometer
}
