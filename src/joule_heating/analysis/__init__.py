"""Analysis modules for processing experiment data.

Modules:
    - gradient_analysis: Detect peaks, valleys, and calculate periods/amplitudes
"""

from .gradient_analysis import (
    calculate_amplitude,
    calculate_period,
    detect_peaks_and_valleys,
)

__all__ = [
    "detect_peaks_and_valleys",
    "calculate_period",
    "calculate_amplitude",
]
