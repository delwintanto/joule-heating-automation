"""Constant-Current (CC) GUI interface and integration functions.

This module provides the GUI for constant-current Joule heating experiments
and the callback functions for integrating with the experiment thread.

Author       : Delwin Tanto
Last updated : 09 Mar 2026
"""

import os
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from tktooltip import ToolTip

from joule_heating.devices import Devices
from joule_heating.plotting import close_plot, live_plot_update, plot_data
from joule_heating.utils import alert_cooldown_end

from .common import (
    LabeledEntry,
    RowCounter,
    check_empty_fields,
    configure_laser_button_style,
    create_laser_toggle_callback,
    load_settings,
    parse_floats,
    save_settings,
    sec_to_hhmmss,
    show_error,
)


def gui_cc(psu=None, ycr=None, optris=None):
    """Launch a GUI for Constant-Current Joule Heating experiment.

    Includes a "Test Lasers" section to verify sample alignment before starting.

    Args:
        psu (minimalmodbus.Instrument, optional): Pre-initialized PSU device instance.
        ycr (minimalmodbus.Instrument, optional): Pre-initialized YCR sensor instance.
        optris (serial.Serial, optional): Pre-initialized Optris sensor instance.

    Returns:
        tuple or None: (gui_window, devices, output, status_vars, control_vars) if experiment
            started, or None if GUI was cancelled/closed.
    """
    gui_window = tk.Tk()
    gui_window.title("Constant-Current Joule Heating")
    gui_window.resizable(False, False)
    gui_window.geometry("+0+0")  # Position at top-left corner

    row = RowCounter()
    ttk.Label(
        gui_window,
        text="Constant-Current Joule Heating Experiment",
        font=("TkDefaultFont", 12),
    ).grid(row=row.next(), column=0, columnspan=3, padx=5, pady=10)

    ttk.Label(
        gui_window,
        text="Enter all parameters before starting.\n"
        "Verify equipment limits in your main script or manuals.\n"
        "Incorrect settings may cause failure.",
    ).grid(row=row.next(), column=0, columnspan=3, sticky=tk.W, padx=5, pady=(0, 10))

    # Device state for laser testing
    devices = Devices(psu, ycr, optris)
    lasers_on = [False]  # Mutable container to track laser state

    # Laser test controls (alignment)
    laser_row = row.next()
    ttk.Label(gui_window, text="Laser Test (for alignment)").grid(
        row=laser_row, column=0, sticky=tk.W, padx=5, pady=(0, 10)
    )

    # Configure style for laser button
    configure_laser_button_style()

    btn_toggle = ttk.Button(gui_window, text="Toggle Lasers ON/OFF")
    btn_toggle.config(command=create_laser_toggle_callback(devices, lasers_on, btn_toggle))
    btn_toggle.grid(row=laser_row, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=(0, 10))
    ToolTip(
        btn_toggle,
        msg="Toggle both lasers on/off for sample alignment verification.",
        delay=0.3,
    )

    # Input fields
    fields = {
        "Sample Name": (
            tk.StringVar(),
            "Enter a unique name for your sample.",
        ),
        "Currents (A)": (
            tk.StringVar(),
            "Current sequence for each heating step.\n"
            "Use commas for multiple values, e.g., 1.5,2.0,2.5.",
        ),
        "Durations (s)": (
            tk.StringVar(),
            "Duration for each current step.\nUse commas for multiple values, e.g., 10,15,20.",
        ),
        "Max Voltage (V)": (
            tk.StringVar(),
            "Maximum voltage limit the PSU will supply.",
        ),
    }

    entries = {}
    for label, (var, tooltip) in fields.items():
        entries[label] = LabeledEntry(gui_window, label + ":", row.next(), var=var, tooltip=tooltip)

    # -------------------- Status Display Section --------------------

    # Create a labeled frame for status display
    status_frame = ttk.LabelFrame(gui_window, text="Experiment Status", padding=10)
    status_frame.grid(row=row.next(), column=0, columnspan=3, sticky=tk.EW, padx=10, pady=10)

    # Initialize status variables
    status_vars = {
        "phase": tk.StringVar(value="Ready"),
        "temperature": tk.StringVar(value="--"),
        "max_temperature": tk.StringVar(value="--"),
        "current": tk.StringVar(value="--"),
        "voltage": tk.StringVar(value="--"),
        "resistance": tk.StringVar(value="--"),
        "time_remaining": tk.StringVar(value="--"),
    }

    # Create status labels
    status_labels = [
        ("Phase:", status_vars["phase"]),
        ("Temperature:", status_vars["temperature"]),
        ("Max Temperature:", status_vars["max_temperature"]),
        ("Current:", status_vars["current"]),
        ("Voltage:", status_vars["voltage"]),
        ("Resistance:", status_vars["resistance"]),
        ("Time:", status_vars["time_remaining"]),
    ]

    for i, (label_text, var) in enumerate(status_labels):
        ttk.Label(status_frame, text=label_text, font=("TkDefaultFont", 9, "bold")).grid(
            row=i, column=0, sticky=tk.W, padx=5, pady=2
        )
        ttk.Label(status_frame, textvariable=var, font=("TkDefaultFont", 9)).grid(
            row=i, column=1, sticky=tk.W, padx=5, pady=2
        )

    # -------------------- Control Variables --------------------

    control_vars = {
        "skip_requested": tk.BooleanVar(value=False),
        "stop_requested": tk.BooleanVar(value=False),
        "start_requested": tk.BooleanVar(value=False),
        "experiment_running": tk.BooleanVar(value=False),
        "skip_button": None,  # Will be set when button is created
        "stop_button": None,  # Will be set when button is created
        "entries": entries,  # Store references to all entry widgets
        "lasers_on": lasers_on,  # Store laser state for completion callback
        "laser_button": btn_toggle,  # Store laser button reference for completion callback
    }

    # Dictionary to store output values
    output = {
        "sample": None,
        "currents": [],
        "durations": [],
        "voltage": None,
    }

    def start():
        """Handle the start button click event."""
        try:
            # Check for missing entries
            missing = check_empty_fields(fields)
            if missing:
                return show_error(f"Missing fields: {', '.join(missing)}")

            # Get all values from field entries
            vals = {label: entries[label].get() for label in fields}

            # Store and validate the parameters
            output["sample"] = vals["Sample Name"]
            output["currents"] = parse_floats(vals["Currents (A)"])
            output["durations"] = parse_floats(vals["Durations (s)"])
            output["voltage"] = float(vals["Max Voltage (V)"])

            # Validation checks
            if len(output["currents"]) != len(output["durations"]):
                raise ValueError("Mismatch in number of currents and durations.")
            if not all(x > 0 for x in output["durations"]):
                raise ValueError("Duration values must be positive.")
            if output["voltage"] <= 0:
                raise ValueError("Voltage must be positive.")
            if not all(x >= 0 for x in output["currents"]):
                raise ValueError("Current values cannot be negative.")

            # Confirm before starting
            total_time = sec_to_hhmmss(sum(output["durations"]))
            if not messagebox.askyesno(
                "Confirm",
                f"Approximate length of the experiment: {total_time}\nStart experiment?",
            ):
                return

            # Set experiment running state
            control_vars["start_requested"].set(True)
            control_vars["experiment_running"].set(True)

            # Disable all input fields
            for entry in entries.values():
                entry.entry.config(state="disabled")

            # Disable all buttons except skip and stop
            for widget in gui_window.winfo_children():
                if isinstance(widget, ttk.Button):
                    if widget.cget("text") in ("Skip Current Step (F5)", "Stop Experiment (F6)"):
                        widget.config(state="normal")
                    else:
                        widget.config(state="disabled")

            # Update status
            status_vars["phase"].set("Initializing...")

        except ValueError as e:
            show_error(str(e))

    # -------------------- Button Creation --------------------

    button_row = row.next()

    # Save button
    btn_save = ttk.Button(
        gui_window,
        text="Save Parameters (Ctrl+S)",
        command=lambda: save_settings({label: entries[label].get() for label in fields}),
    )
    btn_save.grid(row=button_row, column=0, columnspan=3, sticky=tk.EW, padx=10, pady=2)
    ToolTip(btn_save, msg="Save parameters to a file.", delay=0.3)

    # Load button
    button_row = row.next()
    btn_load = ttk.Button(
        gui_window,
        text="Load Parameters (Ctrl+L)",
        command=lambda: load_settings({label: entries[label].var for label in fields}),
    )
    btn_load.grid(row=button_row, column=0, columnspan=3, sticky=tk.EW, padx=10, pady=2)
    ToolTip(btn_load, msg="Load parameters from a file.", delay=0.3)

    # Start button
    button_row = row.next()
    btn_start = ttk.Button(gui_window, text="Start Experiment (F2)", command=start)
    btn_start.grid(row=button_row, column=0, columnspan=3, sticky=tk.EW, padx=10, pady=(10, 2))
    ToolTip(btn_start, msg="Start the experiment with the entered parameters.", delay=0.3)

    # Skip button
    button_row = row.next()
    btn_skip = ttk.Button(
        gui_window,
        text="Skip Current Step (F5)",
        command=lambda: control_vars["skip_requested"].set(True),
        state="disabled",
    )
    btn_skip.grid(row=button_row, column=0, columnspan=3, sticky=tk.EW, padx=10, pady=2)
    ToolTip(
        btn_skip,
        msg="Skip the current heating step and move to the next one.",
        delay=0.3,
    )
    control_vars["skip_button"] = btn_skip  # Store reference

    def request_stop():
        """Request full experiment stop and log to terminal once."""
        if not control_vars["stop_requested"].get():
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Experiment stopped by user.")
            alert_cooldown_end()
        control_vars["stop_requested"].set(True)

    # Stop button
    button_row = row.next()
    btn_stop = ttk.Button(
        gui_window,
        text="Stop Experiment (F6)",
        command=request_stop,
        state="disabled",
    )
    btn_stop.grid(row=button_row, column=0, columnspan=3, sticky=tk.EW, padx=10, pady=2)
    ToolTip(btn_stop, msg="Stop the experiment immediately.", delay=0.3)
    control_vars["stop_button"] = btn_stop  # Store reference

    # -------------------- Keyboard Shortcuts --------------------

    def _kb_start(_):
        if not control_vars["experiment_running"].get():
            start()

    def _kb_skip(_):
        if control_vars["experiment_running"].get():
            control_vars["skip_requested"].set(True)

    def _kb_stop(_):
        if control_vars["experiment_running"].get():
            request_stop()

    def _kb_save(_):
        if not control_vars["experiment_running"].get():
            save_settings({label: entries[label].get() for label in fields})

    def _kb_load(_):
        if not control_vars["experiment_running"].get():
            load_settings({label: entries[label].var for label in fields})

    gui_window.bind("<F2>", _kb_start)
    gui_window.bind("<F5>", _kb_skip)
    gui_window.bind("<F6>", _kb_stop)
    gui_window.bind("<Control-s>", _kb_save)
    gui_window.bind("<Control-l>", _kb_load)

    # -------------------- Window Close Handler --------------------

    def on_close_attempt():
        """Handle window close attempt - prevent closing during experiment."""
        if control_vars["experiment_running"].get():
            show_error("Cannot close window while experiment is running!")
        else:
            gui_window.destroy()

    gui_window.protocol("WM_DELETE_WINDOW", on_close_attempt)

    # Footer
    tk.Label(
        gui_window,
        text=f"{os.path.basename(__file__)} | Author: Delwin Tanto",
        font=("TkDefaultFont", 7),
    ).grid(row=999, column=0, columnspan=3, sticky=tk.SW, padx=5)

    return gui_window, output, status_vars, control_vars


# -------------------- GUI Integration Callbacks --------------------


def create_gui_callbacks_cc(gui_window, status_vars, control_vars):
    """Create callback functions for GUI integration with CC experiments.

    Args:
        gui_window (tk.Tk): Main GUI window.
        status_vars (dict): Dictionary of GUI status variables.
        control_vars (dict): Dictionary of GUI control variables.

    Returns:
        tuple: (update_status, check_skip) callback functions.
    """

    def update_status(
        phase, temperature, max_temperature, current, voltage, resistance, time_remaining
    ):
        """Update GUI status display from experiment thread.

        Args:
            phase (str): Current experiment phase (e.g., "Heating - Step 1/3").
            temperature (str): Temperature reading with units.
            max_temperature (str): Maximum temperature reached so far.
            current (str): Current reading with units.
            voltage (str): Voltage reading with units.
            resistance (str): Resistance reading with units.
            time_remaining (str): Time remaining/elapsed with units.

        Returns:
            None
        """
        gui_window.after(0, lambda: status_vars["phase"].set(phase))
        gui_window.after(0, lambda: status_vars["temperature"].set(temperature))
        gui_window.after(0, lambda: status_vars["max_temperature"].set(max_temperature))
        gui_window.after(0, lambda: status_vars["current"].set(current))
        gui_window.after(0, lambda: status_vars["voltage"].set(voltage))
        gui_window.after(0, lambda: status_vars["resistance"].set(resistance))
        gui_window.after(0, lambda: status_vars["time_remaining"].set(time_remaining))

    def check_skip():
        """Check if skip or stop was requested in the GUI.

        Returns:
            bool: True if skip or stop was requested, False otherwise.
        """
        if control_vars["stop_requested"].get():
            return True  # Don't clear - persists to stop all remaining steps
        if control_vars["skip_requested"].get():
            control_vars["skip_requested"].set(False)
            return True
        return False

    return update_status, check_skip


def create_experiment_complete_callback_cc(
    gui_window, status_vars, control_vars, experiment_started
):
    """Create callback for experiment completion in CC mode.

    Args:
        gui_window (tk.Tk): Main GUI window.
        status_vars (dict): Dictionary of GUI status variables.
        control_vars (dict): Dictionary of GUI control variables.
        experiment_started (list): Single-element list to track experiment state.

    Returns:
        callable: Function to call when experiment completes.
    """

    def on_experiment_complete():
        """Re-enable GUI controls after experiment completes."""

        def reset_gui():
            # Reset experiment state
            experiment_started[0] = False
            control_vars["experiment_running"].set(False)

            # Re-enable all input fields
            for entry in control_vars["entries"].values():
                entry.entry.config(state="normal")

            # Re-enable all buttons except skip and stop
            for widget in gui_window.winfo_children():
                if isinstance(widget, ttk.Button):
                    if widget.cget("text") not in (
                        "Skip Current Step (F5)",
                        "Stop Experiment (F6)",
                    ):
                        widget.config(state="normal")
                    else:
                        widget.config(state="disabled")

            # Reset stop and laser state
            control_vars["stop_requested"].set(False)
            control_vars["start_requested"].set(False)
            control_vars["lasers_on"][0] = False
            control_vars["laser_button"].config(style="TButton")

            # Reset status displays
            status_vars["phase"].set("Ready")
            status_vars["temperature"].set("--")
            status_vars["max_temperature"].set("--")
            status_vars["current"].set("--")
            status_vars["voltage"].set("--")
            status_vars["resistance"].set("--")
            status_vars["time_remaining"].set("--")

            print(
                f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                "Experiment completed! You can start a new experiment.\n"
            )

        gui_window.after(0, reset_gui)

    return on_experiment_complete


def create_plot_callbacks_cc(gui_window, plot_position="+30+30"):
    """Create callbacks for plot operations on main thread for CC experiments.

    Args:
        gui_window (tk.Tk): Main GUI window.
        plot_position (str, optional): Position for final plot window. Defaults to "+30+30".

    Returns:
        tuple: (update_plot, show_final_plot, close_live_plot) callback functions.
    """

    def update_plot(live_plot, data):
        """Update live plot from main thread.

        Args:
            live_plot (LivePlot): Live plot container.
            data (dict): Data dictionary with measurements.
        """
        gui_window.after(0, lambda: live_plot_update(live_plot, data=data))

    def show_final_plot(saved_data, sample_name):
        """Show final summary plot from main thread.

        Args:
            saved_data (pd.DataFrame): Experiment data.
            sample_name (str): Sample name for plot title.

        Returns:
            None
        """
        gui_window.after(
            0,
            lambda: plot_data(
                saved_data,
                columns=["Temperature (°C)", "Current (A)", "Resistance (Ω)"],
                sample_name=sample_name,
                position=plot_position,
            ),
        )

    def close_live_plot():
        """Close live plot window from main thread.

        Returns:
            None
        """
        gui_window.after(0, close_plot)

    return update_plot, show_final_plot, close_live_plot
