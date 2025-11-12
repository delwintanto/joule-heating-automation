"""Prevent system sleep during long-running experiments.

This module provides cross-platform functionality to prevent system sleep
(display, idle, and disk sleep) during long-running processes.
It automatically handles cleanup when the process ends.

Example:
    Basic usage as a context manager:
    >>> from system_sleep import prevent_sleep
    >>> with prevent_sleep():
    ...     # Your long-running code here

    Manual control alternative:
    >>> keeper = keep_awake()
    >>> # Do work here
    >>> keeper.stop()

The module uses native system APIs and falls back to harmless no-op behavior
if platform-specific methods aren't available.

Platform Support:
    - Windows: Uses SetThreadExecutionState API
    - macOS: Uses caffeinate command
    - Linux: Uses xset command (if available)

Author       : Delwin Tanto
Last updated : 18 Jun 2025
"""

import platform
import ctypes
import subprocess
from typing import Optional
from contextlib import contextmanager


class _SystemSleepManager:
    """Platform-specific implementation to prevent system sleep.

    Provides methods to disable and restore system sleep on Windows (via
    SetThreadExecutionState), macOS (via caffeinate), and Linux (via xset).

    Args:
        enable (bool): If ``True`` start preventing sleep immediately on init.

    Attributes:
        system (str): Detected OS: ``'Windows'``, ``'Darwin'``, or ``'Linux'``.
        _process (Optional[subprocess.Popen]): Subprocess handle for macOS caffeinate.
        _prev_state (Optional[int]): Previous execution state (Windows only).
    """

    def __init__(self, enable=True):
        """Initialise sleep prevention for the current platform.

        Args:
            enable (bool): If ``True`` starts preventing sleep immediately.
        """
        self.system = platform.system()  # Detect the current OS
        self._process: Optional[subprocess.Popen] = None  # For macOS caffeinate
        self._prev_state: Optional[int] = None  # For Windows execution state

        if enable:
            self.start()  # Automatically start preventing sleep

    def start(self):
        """Begin preventing system sleep.

        Platform-specific implementations:
            - **Windows**: Uses ``SetThreadExecutionState`` API
            - **macOS**: Launches ``caffeinate`` subprocess
            - **Linux**: Uses ``xset`` commands (if available)

        Returns:
            None
        """
        if self.system == "Windows":
            # ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            self._prev_state = ctypes.windll.kernel32.SetThreadExecutionState(
                0x80000002
            )
        elif self.system == "Darwin":
            self._process = subprocess.Popen(
                ["caffeinate", "-dimsu"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif self.system == "Linux":
            try:
                subprocess.run(
                    ["xset", "s", "off"],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                subprocess.run(
                    ["xset", "-dpms"],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except (subprocess.SubprocessError, FileNotFoundError):
                pass

    def stop(self):
        """Allow system sleep again.

        Platform-specific cleanup:
            - **Windows**: Restores previous execution state
            - **macOS**: Terminates caffeinate process
            - **Linux**: Restores screensaver and DPMS (if possible)

        Returns:
            None

        Notes:
            Safe to call multiple times or if ``start()`` was not called.
        """
        if self.system == "Windows" and self._prev_state is not None:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)  # ES_CONTINUOUS
        elif self.system == "Darwin" and self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self._process.kill()
        elif self.system == "Linux":
            try:
                subprocess.run(
                    ["xset", "s", "on"],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                subprocess.run(
                    ["xset", "+dpms"],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except (subprocess.SubprocessError, FileNotFoundError):
                pass

    def __enter__(self):
        """Context manager entry point.

        Returns:
            _SystemSleepManager: The instance itself.
        """
        return self

    def __exit__(
        self,
        exc_type,
        exc_val,
        exc_tb,
    ):
        """Context manager exit point - ensure sleep is re-enabled.
        
        Args:
            exc_type: Exception type if any occurred.
            exc_val: Exception value if any occurred.
            exc_tb: Exception traceback if any occurred.
        """
        self.stop()


@contextmanager
def prevent_sleep():
    """Context manager to prevent system sleep during critical operations.

    This is the preferred way to use this module as it ensures proper cleanup.

    Example:
        >>> with prevent_sleep():
        ...     run_long_experiment()  # System will stay awake here
        # System can sleep again here

    Notes:
        - On Windows: Prevents display and system sleep
        - On macOS: Runs caffeinate with display, idle, and disk prevention
        - On Linux: Disables screensaver and DPMS (if xset available)
        - Automatically cleans up when block exits

    Yields:
        None: The context manager doesn't yield any value.
    """
    manager = _SystemSleepManager()
    try:
        yield
    finally:
        manager.stop()


def keep_awake():
    """Alternative API that requires manual stop.

    Returns:
        _SystemSleepManager: An instance that must be manually stopped.

    Example:
        >>> keeper = keep_awake()
        >>> # Do work here
        >>> keeper.stop()  # Must call this when done
    """
    return _SystemSleepManager()


if __name__ == "__main__":
    import time

    print("Preventing system sleep for 10 seconds...")
    with prevent_sleep():
        time.sleep(10)
    print("Done. System can now sleep again.")
