"""Utility functions for generating safe, unique filenames for Joule Heating experiment data.

This module provides the `generate_filename()` function, which:
- Creates a data directory inside the user's Documents folder (~/Documents/Joule_Heating_Data).
- Generates a CSV filename using the current date and a user-provided sample name.
- Sanitizes the sample name by replacing illegal characters (<>:"/\\|?* and spaces) with "_"
  to ensure compatibility across operating systems (especially Windows).
- Optionally appends a "_tuning_data" suffix if the file is used for tuning experiments.
- Ensures uniqueness by appending incremental counter if a file with the same name already exists.

Author       : Delwin Tanto
Last updated : 10 Oct 2025
"""

import datetime
import os
import re


def generate_filename(
    sample_name,
    tuning=False,
):
    """Generate a unique filename for storing experimental data.

    The function creates a timestamped CSV filename in a standard Joule Heating
    data directory and sanitises the sample name by replacing illegal filesystem
    characters (``<>:"/\\|?* ``) with underscores to ensure cross-platform
    compatibility. If the filename already exists, a numeric counter is appended.

    Args:
        sample_name (str): Human-readable name of the sample.
        tuning (bool): If ``True`` the filename will include a ``_tuning_data`` suffix.

    Returns:
        str: Full path to the generated (or pre-existing) CSV filename.
    """
    file_path = os.path.join(os.path.expanduser("~"), "Documents", "Joule_Heating_Data")
    os.makedirs(file_path, exist_ok=True)

    # Sanitise sample_name (remove invalid Windows chars and spaces)
    safe_name = re.sub(r'[<>:"/\\|?* ]', "_", sample_name)

    date_str = datetime.datetime.now().strftime("%Y%m%d")
    suffix = "_tuning_data" if tuning else ""
    file_name = os.path.join(file_path, f"{date_str}_{safe_name}{suffix}.csv")

    # Append a counter if file name already exists
    if os.path.exists(file_name):
        base, ext = os.path.splitext(file_name)
        file_name = next(
            (
                f"{base}_{counter}{ext}"
                for counter in range(1, 9999)
                if not os.path.exists(f"{base}_{counter}{ext}")
            ),
            file_name,
        )
    return file_name
