"""
Colour map for temperature values using ANSI escape codes.
From yellow (low) to red (high).

Author       : Delwin Tanto
Last updated : 04 Nov 2025
"""


def temp_colour(temp, min_temp, max_temp):
    """
    Return ANSI escape colour code based on temperature value.

    Args:
        temp (float): Temperature in °C.
        min_temp (float): Minimum temperature for colour mapping.
        max_temp (float): Maximum temperature for colour mapping.

    Returns:
        str: ANSI colour escape code.
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
