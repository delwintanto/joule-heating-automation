"""Joule Heating Automation Package.

A comprehensive package for automating Joule heating experiments with power supply
control, temperature sensing, data acquisition, and analysis.

Author       : Delwin Tanto
Last updated : 15 Dec 2025
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("joule-heating-automation")
except PackageNotFoundError:
    # Package not installed, use fallback
    __version__ = "unknown"
