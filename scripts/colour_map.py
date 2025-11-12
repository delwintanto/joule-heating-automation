"""
Colour map for temperature values using ANSI escape codes.
From yellow (low) to red (high).

Author       : Delwin Tanto
Last updated : 04 Nov 2025
"""


def temp_colour(temp, min_temp, max_temp):
    """Return an ANSI escape code for colouring temperature values.

    Maps the input temperature to a gradient from yellow (low) through orange
    to red (high). Returns a grey code for NaN values.

    Args:
        temp (float): Temperature in °C, or NaN.
        min_temp (float): Minimum temperature for mapping range.
        max_temp (float): Maximum temperature for mapping range.

    Returns:
        str: ANSI 256-colour escape code string (e.g. ``"\\033[38;5;226m"``).
    """
    if temp != temp:
        return "\033[38;5;240m"  # Grey for NaN

    # Clamp T (for colour only) within desired range
    temp_clamped = max(min(temp, max_temp), min_temp)

    # Calculate how far the T is between min and max as 0-1 value
    ratio = (temp_clamped - min_temp) / (max_temp - min_temp)

    # Map T range to 256 colour codes
    colours = [226, 220, 214, 208, 202, 196]  # Yellow to orange to red
    colour_idx = min(int(ratio * (len(colours) - 1)), len(colours) - 1)
    colour_code = colours[colour_idx]
    return f"\033[38;5;{colour_code}m"
