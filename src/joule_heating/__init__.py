"""Joule Heating Automation Package.

A comprehensive package for automating Joule heating experiments with power supply
control, temperature sensing, data acquisition, and analysis.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("joule-heating-automation")
except PackageNotFoundError:
    # Package not installed, use fallback
    __version__ = "unknown"
