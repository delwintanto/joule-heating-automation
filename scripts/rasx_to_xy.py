"""
Convert Rigaku .rasx XRD files into .xy format.

This script:
1. Opens one or more .rasx files selected via a file dialog.
2. Treats each .rasx file as a ZIP archive and extracts the Profile*.txt file.
3. Parses the two-column numeric data (typically 2θ and intensity).
4. Saves the data as a .xy file with the same base name in the same folder.

Usage:
    python rasx_to_xy.py

Author       : Delwin Tanto
Last updated : 04 Sep 2025
"""

import os
import zipfile
from tkinter import Tk, filedialog

def parse_profile_lines(lines):
    """
    Parse lines of text from a Rigaku Profile*.txt file into numeric data.

    Each valid line should contain at least two numeric values, typically:
        2theta intensity

    Args:
        lines (list[str]): Raw lines from the profile file.

    Returns:
        list[tuple[float, float]]: Parsed (x, y) data points.
    """
    data = []
    for line in lines:
        line = line.strip().replace('\ufeff', '')  # Remove BOM if present
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            try:
                data.append((float(parts[0]), float(parts[1])))
            except ValueError:
                continue
    return data

def rasx_to_xy(rasx_path):
    """
    Convert a single Rigaku .rasx file into .xy format.

    The function looks inside the .rasx ZIP for Profile*.txt files,
    parses the first one found, and saves its numeric contents
    into an .xy file with the same base name.

    Args:
        rasx_path (str): Path to the .rasx file.

    Side Effects:
        Creates a .xy file in the same directory.
    """
    xy_path = os.path.splitext(rasx_path)[0] + ".xy"

    with zipfile.ZipFile(rasx_path, 'r') as z:
        # Try to locate the Profile file
        profile_files = [f for f in z.namelist() if "Profile" in f and f.endswith(".txt")]
        if not profile_files:
            print(f"No Profile file found in {rasx_path}")
            return
        profile_file = profile_files[0]

        with z.open(profile_file) as f:
            lines = f.read().decode("utf-8", errors="ignore").splitlines()

    # Clean and parse data
    data = parse_profile_lines(lines)

    if not data:
        print(f"No numeric data in {rasx_path}")
        return

    # Write to .xy file
    with open(xy_path, "w", encoding="utf-8") as f:
        f.writelines(f"{x:.5f} {y:.5f}\n" for x, y in data)

    print(f"File converted to {xy_path}")

def main():
    """
    Launch the file selection dialog and convert selected .rasx files.

    Opens a Tkinter file dialog for choosing one or more .rasx files,
    then converts each into .xy using rasx_to_xy().
    """
    Tk().withdraw()
    file_paths = filedialog.askopenfilenames(
        title="Select .rasx files",
        filetypes=[("Rigaku XRD files", "*.rasx")]
    )

    if not file_paths:
        print("No files selected.")
        return

    for rasx_path in file_paths:
        try:
            rasx_to_xy(rasx_path)
        except (zipfile.BadZipFile, KeyError, UnicodeDecodeError, OSError) as e:
            print(f"Failed to process {rasx_path}: {e}")

if __name__ == "__main__":
    main()
