"""Common GUI components and utilities for Joule heating experiments.

This module provides shared widgets, helper functions, and utilities used
by both constant-current (CC) and PID GUI interfaces.

Author       : Delwin Tanto
Last updated : 10 Dec 2025
"""

import json
import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from tktooltip import ToolTip

from joule_heating.devices import TemperatureSensorError, enable_lasers
from joule_heating.plotting import live_plot_init

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
        self.entry.grid(row=row, column=col + 1,
                        columnspan=colspan, sticky=tk.EW, padx=5, pady=2)
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
                file.writelines(f"{key}: {value}\n" for key,
                                value in file_vars.items())
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
    ttk.Label(master, text=label_text).grid(
        row=row, column=0, sticky=tk.W, padx=5, pady=2
    )
    for i, (text, tooltip) in enumerate(options, 1):
        rb = ttk.Radiobutton(
            master,
            text=text,
            variable=var,
            value=text.split()[0]
            if label_text.startswith("Temperature")
            else text,
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


def create_laser_toggle_callback(devices, lasers_on, button):
    """Create a callback function to toggle IR sensor lasers for sample alignment.

    This factory function returns a callback that toggles the laser state and updates
    the button appearance to indicate the current laser status (red when on).

    Args:
        devices (dict): Device dictionary with keys 'ycr' and 'optris' containing
            sensor instances (or None if unavailable).
        lasers_on (list): Single-element list containing boolean laser state.
            Wrapped in list to allow mutation from within callback.
        button (ttk.Button): Button widget to update appearance based on laser state.

    Returns:
        callable: Callback function to be used as button command.

    Example:
        ```python
        devices = {"psu": psu, "ycr": ycr_sensor, "optris": optris_sensor}
        lasers_on = [False]
        btn = ttk.Button(parent, text="Toggle Lasers ON/OFF")
        btn.config(command=create_laser_toggle_callback(devices, lasers_on, btn))
        ```
    """

    def toggle_lasers():
        """Toggle lasers on/off for sample alignment."""
        if not devices["ycr"] and not devices["optris"]:
            show_error(
                "Temperature sensors not initialized. Cannot toggle lasers.")
            return
        try:
            lasers_on[0] = not lasers_on[0]
            enable_lasers(
                ycr_sensor=devices["ycr"],
                optris_sensor=devices["optris"],
                on=lasers_on[0],
            )
            # Update button appearance based on laser state
            if lasers_on[0]:
                button.config(style="LaserOn.TButton")
            else:
                button.config(style="TButton")
        except TemperatureSensorError as e:
            show_error(f"Failed to toggle lasers: {e}")

    return toggle_lasers


def configure_laser_button_style():
    """Configure ttk.Style for the laser toggle button.

    Sets up the 'LaserOn.TButton' style with red background to indicate
    when lasers are active.

    Returns:
        ttk.Style: Configured style object.
    """
    style = ttk.Style()
    style.configure("LaserOn.TButton", background="#FF0000",
                    foreground="black")
    return style


def create_experiment_starter(
    gui_window,
    control_vars,
    experiment_started,
    devices,
    output,
    update_status,
    check_skip,
    on_experiment_complete,
    create_plot_callbacks_func,
    run_experiment_thread_func,
    get_experiment_args_func,
):
    """Create a start_experiment function for launching experiments in background thread.

    This factory function generates the start_experiment callback that handles the
    common experiment startup workflow including preventing duplicate starts, creating
    live plots, and launching the background thread.

    Args:
        gui_window (tk.Tk): Main GUI window.
        control_vars (dict): Control variables dict with keys 'experiment_running', 'skip_button'.
        experiment_started (list): Single-element list tracking if experiment has started.
        devices (tuple): (psu, ycr_sensor, optris_sensor) device instances.
        output (dict): Experiment parameters from GUI.
        update_status (callable): Status update callback.
        check_skip (callable): Skip check callback.
        on_experiment_complete (callable): Completion callback.
        create_plot_callbacks_func (callable): Function that takes (gui_window, plot_position)
            and returns (update_plot, show_final_plot, close_live_plot).
        run_experiment_thread_func (callable): Target function for the experiment thread.
        get_experiment_args_func (callable): Function that takes (output, devices, callbacks,
            figure, axes, lines) and returns tuple of args for run_experiment_thread_func.

    Returns:
        callable: The start_experiment function to be used as callback.

    Example:
        ```python
        def get_cc_args(output, devices, callbacks, figure, axes, lines):
            psu, ycr, optris = devices
            update_status, check_skip, on_complete = callbacks
            update_plot, show_final, close_plot = callbacks[3:]
            return (
                psu, ycr, optris,
                output["sample"], output["currents"], output["durations"],
                output["voltage"],
                update_status, check_skip, on_complete,
                figure, *axes, *lines,
                update_plot, show_final, close_plot,
            )

        start_exp = create_experiment_starter(
            gui_window, control_vars, experiment_started,
            (psu, ycr, optris), output,
            update_status, check_skip, on_complete,
            create_plot_callbacks_cc,
            run_experiment_thread,
            get_cc_args,
        )
        ```
    """

    def start_experiment():
        """Start experiment in background thread when GUI triggers it."""
        if not control_vars["experiment_running"].get():
            return

        # Prevent starting multiple experiments
        if experiment_started[0]:
            return
        experiment_started[0] = True

        # Enable skip button
        control_vars["skip_button"].config(state="normal")

        # Calculate position for live plot (to the right of GUI)
        gui_window.update_idletasks()  # Ensure geometry is updated
        # 10px gap, aligned to top
        plot_position = f"+{gui_window.winfo_width() + 10}+0"

        # Get sample name for plot initialization
        sample_name = output.get("sample", "Unknown")

        # Create live plot on main thread
        (
            figure,
            ax_temp,
            ax_curr,
            ax_res,
            line_temp,
            line_curr,
            line_res,
        ) = live_plot_init(sample_name, position=plot_position)

        # Refocus GUI window after plot creation so keyboard shortcuts work
        gui_window.focus_force()

        # Create plot callbacks with position for final plot
        (
            update_plot,
            show_final_plot,
            close_live_plot,
        ) = create_plot_callbacks_func(gui_window, plot_position)

        # Prepare callbacks tuple
        callbacks = (update_status, check_skip, on_experiment_complete,
                     update_plot, show_final_plot, close_live_plot)

        # Get experiment-specific arguments
        axes = (ax_temp, ax_curr, ax_res)
        lines = (line_temp, line_curr, line_res)

        experiment_args = get_experiment_args_func(
            output, devices, callbacks, figure, axes, lines
        )

        # Start experiment in background thread
        experiment_thread = threading.Thread(
            target=run_experiment_thread_func,
            args=experiment_args,
            daemon=True,
        )
        experiment_thread.start()

    return start_experiment


def create_experiment_monitor(
    gui_window,
    control_vars,
    output,
    start_experiment,
    experiment_started=None,
):
    """Create a monitoring function that polls for experiment start trigger.

    This factory function generates a callback that repeatedly checks if the
    experiment should start and schedules itself to run again.

    Args:
        gui_window (tk.Tk): Main GUI window.
        control_vars (dict): Control variables dict with key 'experiment_running'.
        output (dict): Experiment parameters dict with key 'sample'.
        start_experiment (callable): Function to call when experiment should start.
        experiment_started (list, optional): Single-element list tracking if experiment
            has started. If provided, adds an additional check to prevent duplicate starts.

    Returns:
        callable: The check_experiment_start function to be scheduled with after().

    Example:
        ```python
        check_start = create_experiment_monitor(
            gui_window, control_vars, output, start_experiment
        )
        gui_window.after(100, check_start)
        ```
    """
    def check_experiment_start():
        """Monitor for experiment start trigger from GUI."""
        if experiment_started is not None:
            # Include experiment_started check (PID mode)
            if (
                control_vars["experiment_running"].get()
                and output["sample"] is not None
                and not experiment_started[0]
            ):
                start_experiment()
        else:
            # Standard check without experiment_started (CC mode)
            if (
                control_vars["experiment_running"].get()
                and output["sample"] is not None
            ):
                start_experiment()

        gui_window.after(100, check_experiment_start)

    return check_experiment_start
