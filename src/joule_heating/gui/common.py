"""Common GUI components and utilities for Joule heating experiments.

This module provides shared widgets, helper functions, and utilities used
by both constant-current (CC) and PID GUI interfaces.

Author       : Delwin Tanto
Last updated : 10 Dec 2025
"""

import json
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from tktooltip import ToolTip

# Default directory for saving/loading parameters
DEFAULTDIR = r"C:\Users\delwintanto\Documents\Joule_Heating_Data\Experiment Parameters"


# -------------------- Widget Classes --------------------


class LabeledEntry:
    """A composite widget combining a label and an entry field with optional tooltip.

    Attributes:
        var (tk.StringVar): Variable linked to the entry.
        label (ttk.Label): The label component.
        entry (ttk.Entry): The entry field component.
    """

    def __init__(self, master, label, row, col=0, colspan=2, var=None, width=40, tooltip=None):
        """Initialise the LabeledEntry widget and place it in the GUI.

        Args:
            master (tk.Widget): Parent container for the widget.
            label (str): Text to display in the label.
            row (int): Grid row for widget placement.
            col (int, optional): Starting column (default is 0).
            colspan (int, optional): Column span for the entry (default is 2).
            var (tk.StringVar, optional): External variable to bind (default is new StringVar).
            width (int, optional): Width of the entry field (default is 40).
            tooltip (str, optional): Tooltip message for the entry.
        """
        self.var = var or tk.StringVar()
        self.label = ttk.Label(master, text=label)
        self.entry = ttk.Entry(master, textvariable=self.var, width=width)
        self.label.grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
        self.entry.grid(row=row, column=col + 1, columnspan=colspan, sticky=tk.EW, padx=5, pady=2)
        if tooltip:
            ToolTip(self.entry, msg=tooltip, delay=0.3)

    def get(self):
        """Return the trimmed text value from the entry field.

        Returns:
            str: The cleaned string from the entry.
        """
        return self.var.get().strip()

    def set(self, value):
        """Set the value displayed in the entry widget.

        Args:
            value (str): The value to insert into the entry.
        """
        self.var.set(value)


class RowCounter:
    """A helper class to track and increment row indices for placing widgets.

    Attributes:
        value (int): The current row value.
    """

    def __init__(self, start=0):
        """Initialise the RowCounter with a starting value.

        Args:
            start (int): Initial row index.
        """
        self.value = start

    def next(self, step=1):
        """Return the current row index and increment by ``step``.

        Args:
            step (int): Step size for incrementing (default is 1).

        Returns:
            int: The current row index before incrementing.
        """
        val = self.value
        self.value += step
        return val


# -------------------- Utility Functions --------------------


def parse_floats(input_str):
    """Convert a comma-separated string to a list of floats.

    Args:
        input_str (str): Comma-separated numbers as a string.

    Returns:
        list[float]: List of parsed float values.

    Raises:
        ValueError: If any value cannot be converted to a float.
    """
    return list(map(float, input_str.split(",")))


def show_error(msg):
    """Display an error message dialog.

    Args:
        msg (str): Error message to display.
    """
    messagebox.showerror("Error", msg)


def show_info(msg):
    """Display an informational message dialog.

    Args:
        msg (str): Information message to display.
    """
    messagebox.showinfo("Information", msg)


def check_empty_fields(field_dict):
    """Identify which labeled fields are empty.

    Args:
        field_dict (dict): Mapping from label text to ``(tk.Variable, tooltip)``.

    Returns:
        list[str]: Labels with any parenthetical content removed (e.g., units,
            hints) for fields whose variables are empty.
    """
    return [
        re.sub(r"\s*\([^)]*\)", "", label)
        for label, (var, _) in field_dict.items()
        if not var.get().strip()
    ]


def save_settings(file_vars):
    """Save the given parameter dictionary to a JSON or text file.

    Args:
        file_vars (dict): Parameters to save.
    """
    file_path = filedialog.asksaveasfilename(
        initialdir=DEFAULTDIR,
        defaultextension=".txt",
        filetypes=[("Text Files", "*.txt"), ("JSON Files", "*.json")],
    )
    if not file_path:
        return

    # Ensure extension is present
    if not os.path.splitext(file_path)[1]:
        if file_path.endswith(".json"):
            ext = ".json"
        elif file_path.endswith(".txt"):
            ext = ".txt"
        else:
            ext = ".txt"
        file_path += ext
    ext = os.path.splitext(file_path)[1].lower()

    try:
        # Save to JSON
        if ext == ".json":
            with open(file_path, "w", encoding="utf-8") as file:
                json.dump(file_vars, file, indent=4)
        # Save to text file
        else:
            with open(file_path, "w", encoding="utf-8", newline="") as file:
                file.writelines(f"{key}: {value}\n" for key, value in file_vars.items())
        show_info("Parameters saved successfully!")
    except OSError as e:
        show_error(f"Error saving file: {e}")


def load_settings(target_vars):
    """Load parameters from a JSON or text file into target tk.Variable instances.

    Args:
        target_vars (dict): Mapping of parameter names to ``tk.Variable`` instances.
    """
    file_path = filedialog.askopenfilename(
        initialdir=DEFAULTDIR,
        filetypes=[
            ("Text Files", "*.txt"),
            ("JSON Files", "*.json"),
            ("All Files", "*.*"),
        ],
    )
    if not file_path:
        return

    ext = os.path.splitext(file_path)[1].lower()
    try:
        # Load from JSON
        if ext == ".json":
            with open(file_path, encoding="utf-8") as file:
                data = json.load(file)
        # Load from text file
        else:
            data = {}
            with open(file_path, encoding="utf-8") as file:
                for line in file:
                    if ": " in line:
                        parts = line.strip().split(": ", 1)
                        if len(parts) == 2:
                            key, value = parts
                            data[key] = value

        # Legacy key mappings for backward compatibility
        legacy_key_map = {
            "Start Duration (s)": "Initial Heating Duration (s)",
            "Initial Duration (s)": "Initial Heating Duration (s)",
        }

        # Update the target variables with loaded data
        for key, value in data.items():
            # Check for legacy key names
            mapped_key = legacy_key_map.get(key, key)

            if mapped_key in target_vars:
                var = target_vars[mapped_key]
                if isinstance(var, tk.StringVar):
                    var.set(value)
                elif isinstance(var, tk.IntVar):
                    var.set(1 if value.lower() == "manual" else 0)
        show_info("Parameters loaded successfully!")
    except OSError as e:
        show_error(f"Error loading file: {e}")


def create_radio_button(master, label_text, options, var, row_counter):
    """Create a radio button group with tooltips.

    Args:
        master (tk.Widget): Parent widget.
        label_text (str): Label for the radio group.
        options (list[tuple[str,str]]): Options as (label, tooltip) pairs.
        var (tk.Variable): Variable to bind selected value.
        row_counter (RowCounter): Row counter for widget placement.
    """
    row = row_counter.next()
    ttk.Label(master, text=label_text).grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
    for i, (text, tooltip) in enumerate(options, 1):
        rb = ttk.Radiobutton(
            master,
            text=text,
            variable=var,
            value=text.split()[0] if label_text.startswith("Temperature") else text,
        )
        rb.grid(row=row, column=i, sticky=tk.W, padx=5, pady=2)
        ToolTip(rb, msg=tooltip, delay=0.3)


def sec_to_hhmmss(seconds_float):
    """Convert seconds to an "HH:MM:SS" formatted string.

    Args:
        seconds_float (float): Time in seconds.

    Returns:
        str: Time formatted as ``HH:MM:SS``.
    """
    h, m = divmod(int(round(seconds_float)), 3600)
    m, s = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
