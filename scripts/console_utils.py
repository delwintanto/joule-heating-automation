"""Console window utilities for Windows.

This module provides utilities for manipulating the console window on Windows,
such as positioning and resizing.

Author       : Delwin Tanto
Last updated : 11 Dec 2025
"""


import ctypes


def position_console_window(x, y, width, height):
    """Position the console window (Windows only).

    Args:
        x (int): X position in pixels.
        y (int): Y position in pixels.
        width (int): Width in pixels.
        height (int): Height in pixels.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32

        # Get console window handle
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            # MoveWindow: hwnd, x, y, width, height, repaint
            user32.MoveWindow(hwnd, x, y, width, height, True)
            return True
    except (AttributeError, OSError):
        pass
    return False
