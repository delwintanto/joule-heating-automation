"""PID-Controlled GUI interface for Joule heating experiments.

This module provides the GUI for PID-controlled temperature experiments
with support for both auto-tuning and manual PID parameter entry.

Author       : Delwin Tanto
Last updated : 10 Dec 2025
"""

import os
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from tktooltip import ToolTip

from joule_heating.devices import TemperatureSensorError, enable_lasers
from joule_heating.plotting import close_plot, plot_data, update_live_plot

from .common import (
    LabeledEntry,
    RowCounter,
    check_empty_fields,
    create_radio_button,
    load_settings,
    parse_floats,
    save_settings,
    sec_to_hhmmss,
    show_error,
)


def gui_pid(psu=None, ycr=None, optris=None):
    """
    Launch a GUI for PID-controlled Joule Heating experiment.

    Includes a "Test Lasers" section to verify sample alignment before starting.

    Args:
        psu (minimalmodbus.Instrument, optional): Pre-initialized PSU device instance.
        ycr (minimalmodbus.Instrument, optional): Pre-initialized YCR sensor instance.
        optris (serial.Serial, optional): Pre-initialized Optris sensor instance.

    Returns:
        tuple or None: (gui_window, devices, output, status_vars, control_vars, tuning_mode,
            input_mode, field_widgets, common_fields, discrete_fields, continuous_fields, pid_vars)
            if experiment started, or None if GUI was cancelled/closed.
    """

    gui_window = tk.Tk()
    gui_window.title("PID-Controlled Joule Heating")
    gui_window.resizable(False, False)
    gui_window.geometry("+0+0")  # Position at top-left corner

    # Create scrollable container
    canvas = tk.Canvas(gui_window, width=410, height=700, highlightthickness=0)
    scrollbar = ttk.Scrollbar(gui_window, orient="vertical", command=canvas.yview)
    container = ttk.Frame(canvas)

    container.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    canvas.create_window((0, 0), window=container, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Bind mousewheel for scrolling
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    row = RowCounter()
    ttk.Label(
        container,
        text="PID-Controlled Joule Heating Experiment",
        font=("TkDefaultFont", 12),
    ).grid(row=row.next(), column=0, columnspan=3, padx=5, pady=10)

    ttk.Label(
        container,
        text="Enter all parameters before starting.\n"
        "Verify equipment limits in your main script or manuals.\n"
        "Incorrect settings may cause failure.",
    ).grid(row=row.next(), column=0, columnspan=3, sticky=tk.W, padx=5, pady=(0, 10))

    # Variables for radio buttons
    tuning_mode = tk.IntVar(value=0)
    input_mode = tk.StringVar(value="Discrete")

    # Device state for laser testing
    devices = {"psu": psu, "ycr": ycr, "optris": optris}
    lasers_on = [False]  # Mutable container to track laser state

    create_radio_button(
        container,
        "Temperature Input Mode:",
        [
            ("Discrete", "Discrete mode requires a list of temperatures and durations."),
            (
                "Continuous",
                "Continuous mode requires a start, end, and step temperature.",
            ),
        ],
        input_mode,
        row,
    )

    # Laser test controls (alignment)
    laser_row = row.next()
    ttk.Label(container, text="Laser Test (for alignment)").grid(
        row=laser_row, column=0, sticky=tk.W, padx=5, pady=(0, 10)
    )

    def toggle_lasers():
        """Toggle lasers on/off for sample alignment."""
        if not devices["ycr"] and not devices["optris"]:
            show_error("Temperature sensors not initialized. Cannot toggle lasers.")
            return
        try:
            lasers_on[0] = not lasers_on[0]
            enable_lasers(
                ycr_sensor=devices["ycr"], optris_sensor=devices["optris"], on=lasers_on[0]
            )
            # Update button appearance based on laser state
            if lasers_on[0]:
                btn.config(style="LaserOn.TButton")
            else:
                btn.config(style="TButton")
        except TemperatureSensorError as e:
            show_error(f"Failed to toggle lasers: {e}")

    # Configure style for laser button
    style = ttk.Style()
    style.configure("LaserOn.TButton", background="#FF0000", foreground="black")

    btn = ttk.Button(container, text="Toggle Lasers ON/OFF", command=toggle_lasers)
    btn.grid(row=laser_row, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=(0, 10))
    ToolTip(
        btn,
        msg="Toggle both lasers on/off for sample alignment verification.",
        delay=0.3,
    )

    # Define all possible input fields
    common_fields = {
        "Sample Name": (tk.StringVar(), "Enter a unique name for your sample."),
        "Max Current (A)": (tk.StringVar(), "Current limit the PSU will supply."),
        "Max Voltage (V)": (tk.StringVar(), "Voltage limit the PSU will supply."),
        "Cool-Down Duration (s)": (
            tk.StringVar(),
            "Duration for cooldown after the final Joule Heating step ends.\n"
            "Make sure to set this long enough to record the temperature during cool down.\n"
            "Set this to zero if not required.",
        ),
    }

    discrete_fields = {
        "Temperatures (°C)": (
            tk.StringVar(),
            "Setpoint temperature(s).\nUse commas for multiple values, e.g., 500,600,700.",
        ),
        "Durations (s)": (
            tk.StringVar(),
            "Duration for each temperature step.\nUse commas for multiple values, e.g., 10,15,20.",
        ),
    }

    continuous_fields = {
        "Start Temp (°C)": (
            tk.StringVar(),
            "Initial temperature(s) for the continuous ramp."
            "\nUse commas for multiple values, e.g., 500,600,700.",
        ),
        "Initial Heating Duration (s)": (
            tk.StringVar(),
            "Duration for the initial heating step(s)."
            "\nUse commas for multiple values, e.g., 10,15,20.",
        ),
        "End Temp (°C)": (tk.StringVar(), "Final temperature for the continuous ramp."),
        "Step Temp (°C)": (tk.StringVar(), "Temperature step for the continuous ramp."),
        "Step Duration (s)": (tk.StringVar(), "Duration for each temperature step."),
    }

    pid_vars = {
        "Kp": (tk.StringVar(), "Proportional gain for the PID controller."),
        "Ki": (tk.StringVar(), "Integral gain for the PID controller."),
        "Kd": (tk.StringVar(), "Derivative gain for the PID controller."),
        "Tuning Duration (s)": (
            tk.StringVar(),
            "Duration for relay feedback test.\n"
            "Allow enough time for the oscillations to be detected.\n"
            "Note: longer tuning time will result in "
            "increased temperature with diminishing return.",
        ),
    }

    field_widgets = {}  # Store references to all field widgets

    def draw_fields(vars_dict, start_row):
        """
        Helper function to create input fields.
        Return the next available row after these fields.
        """
        for i, (label, (var, tooltip)) in enumerate(vars_dict.items(), start=start_row):
            field_widgets[label] = LabeledEntry(
                container, label + ":", i, col=0, colspan=2, var=var, tooltip=tooltip
            )
        return start_row + len(vars_dict)

    def refresh_fields(*_):
        """Refresh the GUI fields based on the selected input mode."""

        # Clear existing fields
        for widget in field_widgets.values():
            widget.label.grid_remove()
            widget.entry.grid_remove()
        field_widgets.clear()

        # Clear any existing tuning widgets
        for child in container.winfo_children():
            if isinstance(child, ttk.Label) and child.cget("text") == "Tuning:":
                child.grid_remove()
            if isinstance(child, ttk.Radiobutton) and child.cget("text") in (
                "Auto",
                "Manual",
            ):
                child.grid_remove()

        # Draws common fields
        dynamic_row = RowCounter(start=row.value)
        draw_fields(common_fields, dynamic_row.value)
        dynamic_row.next(len(common_fields))

        # Draws mode specific fields
        mode_fields = discrete_fields if input_mode.get() == "Discrete" else continuous_fields
        draw_fields(mode_fields, dynamic_row.value)
        dynamic_row.next(len(mode_fields))

        # Tuning mode selection
        ttk.Label(container, text="Tuning:").grid(
            row=dynamic_row.next(), column=0, sticky=tk.W, padx=5, pady=2
        )

        for i, (text, val) in enumerate([("Auto", 0), ("Manual", 1)], 1):
            rb = ttk.Radiobutton(container, text=text, variable=tuning_mode, value=val)
            rb.grid(row=dynamic_row.value - 1, column=i, sticky=tk.W, padx=5, pady=2)
            tooltip_msg = (
                "Uses relay feedback to automatically tune the PID controller.\n"
                "Select this option if PID gains are unknown."
                if val == 0
                else "Manually enter PID gains.\nSelect this option if PID gains are known."
            )
            ToolTip(
                rb,
                msg=tooltip_msg,
                delay=0.3,
            )

        # Draws PID fields based on tuning mode
        if tuning_mode.get() == 1:
            draw_fields({k: pid_vars[k] for k in ("Kp", "Ki", "Kd")}, dynamic_row.next(3))
        else:
            draw_fields(
                {"Tuning Duration (s)": pid_vars["Tuning Duration (s)"]},
                dynamic_row.next(),
            )

        return dynamic_row.value + len(pid_vars)

    def load_and_refresh():
        """Load parameters from a file and refreshes the GUI fields."""
        load_settings(
            {
                **{k: v[0] for k, v in common_fields.items()},
                "Input Mode": input_mode,
                "Tuning Mode": tuning_mode,
                **{k: v[0] for k, v in discrete_fields.items()},
                **{k: v[0] for k, v in continuous_fields.items()},
                **{k: v[0] for k, v in pid_vars.items()},
            }
        )
        refresh_fields()

    # Sets up mode change callbacks
    input_mode.trace_add("write", refresh_fields)
    tuning_mode.trace_add("write", refresh_fields)
    last_row = refresh_fields()

    # -------------------- Status Display Section --------------------

    # Create a labeled frame for status display
    status_frame = ttk.LabelFrame(container, text="Experiment Status", padding=10)
    status_frame.grid(row=last_row + 1, column=0, columnspan=3, sticky=tk.EW, padx=10, pady=10)

    # Initialize status variables
    status_vars = {
        "phase": tk.StringVar(value="Ready"),
        "temperature": tk.StringVar(value="--"),
        "setpoint": tk.StringVar(value="--"),
        "current": tk.StringVar(value="--"),
        "voltage": tk.StringVar(value="--"),
        "resistance": tk.StringVar(value="--"),
        "time_remaining": tk.StringVar(value="--"),
    }

    # Create status labels
    status_labels = [
        ("Phase:", status_vars["phase"]),
        ("Temperature:", status_vars["temperature"]),
        ("Setpoint:", status_vars["setpoint"]),
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
        "skip_step": tk.BooleanVar(value=False),
        "experiment_running": tk.BooleanVar(value=False),
        "skip_button": None,  # Will be set when button is created
        "field_widgets": field_widgets,  # Store references to all field widgets
    }

    # Dictionary to store the output values
    output = {
        "sample": None,
        "temps": [],
        "durs": None,
        "current": None,
        "voltage": None,
        "cooldown": None,
        "kp": None,
        "ki": None,
        "kd": None,
        "tuning_time": None,
        "tuning_method": None,
    }

    def start():
        """Handle the start button click event."""
        try:
            # Checks for missing entries
            missing = (
                check_empty_fields(common_fields)
                + check_empty_fields(
                    discrete_fields if input_mode.get() == "Discrete" else continuous_fields
                )
                + check_empty_fields(
                    {k: pid_vars[k] for k in ("Kp", "Ki", "Kd")}
                    if tuning_mode.get() == 1
                    else {"Tuning Duration (s)": pid_vars["Tuning Duration (s)"]}
                )
            )

            if missing:
                return show_error(f"Missing fields: {', '.join(missing)}")

            # Gets all values from the common field entries
            vals = {k: v[0].get().strip() for k, v in common_fields.items()}

            # Store and validate the common parameters
            output["sample"] = vals["Sample Name"]
            output["current"] = float(vals["Max Current (A)"])
            output["voltage"] = float(vals["Max Voltage (V)"])
            output["cooldown"] = float(vals["Cool-Down Duration (s)"])
            if output["cooldown"] < 0:
                raise ValueError("Cooldown must be positive.")

            # PSU voltage and current validation
            if output["voltage"] < 0 or output["current"] < 0:
                raise ValueError("Voltage and current cannot be negative.")

            # Handles temperature input based on the selected mode
            if input_mode.get() == "Discrete":
                # Discrete mode - parse lists of temperatures and durations
                temps, durs = [parse_floats(v[0].get()) for v in discrete_fields.values()]
                if len(temps) != len(durs):
                    raise ValueError("Mismatch in temperatures and durations.")
                if not all(x > 0 for x in durs):
                    raise ValueError("Duration values cannot be negative.")
                output["temps"], output["durs"] = temps, durs
            else:
                # Continuous mode - calculates temperatures from range
                s = parse_floats(continuous_fields["Start Temp (°C)"][0].get())
                s_dur = parse_floats(continuous_fields["Initial Heating Duration (s)"][0].get())
                e = float(continuous_fields["End Temp (°C)"][0].get())
                st = float(continuous_fields["Step Temp (°C)"][0].get())
                dur = float(continuous_fields["Step Duration (s)"][0].get())

                if len(s) != len(s_dur):
                    raise ValueError("Mismatch in starting temperatures and durations.")
                if s[-1] == e and st != 0:
                    raise ValueError("Zero temperature difference with non-zero step.")
                if st == 0 and s[-1] != e:
                    raise ValueError("Non-zero temp range needs step.")
                st = abs(st) if s[-1] < e else -abs(st)
                steps = int((e - s[-1]) / st) + 1
                output["temps"] = s + [round(s[-1] + (i + 1) * st, 1) for i in range(steps - 1)]
                output["durs"] = s_dur + [dur] * (steps - 1)

            # Handles PID parameters based on tuning mode
            if tuning_mode.get() == 1:
                output["kp"], output["ki"], output["kd"] = [
                    float(pid_vars[k][0].get()) for k in ("Kp", "Ki", "Kd")
                ]
                output["tuning_method"] = "Manual tuning"
            else:
                output["tuning_time"] = float(pid_vars["Tuning Duration (s)"][0].get())
                output["tuning_method"] = "Auto tuning"

            # Confirms before starting the experiment
            total_time = sec_to_hhmmss(
                sum(output["durs"])
                + output["cooldown"]
                + (0 if tuning_mode.get() else output["tuning_time"])
            )

            tuning_method = "manually entered PID gains" if tuning_mode.get() else "auto-tuning"
            if not messagebox.askyesno(
                "Confirm",
                f"Approximate length of the experiment: {total_time}\n"
                f"Start experiment with {tuning_method}?",
            ):
                return

            # Set experiment running state
            control_vars["experiment_running"].set(True)

            # Disable all input fields
            for widget in field_widgets.values():
                widget.entry.config(state="disabled")

            # Disable mode radio buttons
            for child in gui_window.winfo_children():
                if isinstance(child, ttk.Radiobutton):
                    child.config(state="disabled")

            # Disable all buttons except skip
            for widget in gui_window.winfo_children():
                if isinstance(widget, ttk.Button):
                    if widget.cget("text") == "Skip Current Step (F5)":
                        widget.config(state="normal")
                    else:
                        widget.config(state="disabled")

            # Update status
            status_vars["phase"].set("Initializing...")

            print(f"Starting experiment for sample: {output['sample']}")

        except ValueError as e:
            show_error(str(e))

    # -------------------- Button Creation --------------------

    button_row = last_row + 2

    # Save button
    btn_save = ttk.Button(
        container,
        text="Save Parameters (Ctrl+S)",
        command=lambda: save_settings(
            {
                **{k: v[0].get() for k, v in common_fields.items()},
                "Input Mode": input_mode.get(),
                "Tuning Mode": "Manual" if tuning_mode.get() else "Auto",
                **{k: v[0].get() for k, v in discrete_fields.items()},
                **{k: v[0].get() for k, v in continuous_fields.items()},
                **{k: v[0].get() for k, v in pid_vars.items()},
            }
        ),
    )
    btn_save.grid(row=button_row, column=0, columnspan=3, sticky=tk.EW, padx=10, pady=2)
    ToolTip(btn_save, msg="Save parameters to a file.", delay=0.3)

    # Load button
    button_row += 1
    btn_load = ttk.Button(container, text="Load Parameters (Ctrl+L)", command=load_and_refresh)
    btn_load.grid(row=button_row, column=0, columnspan=3, sticky=tk.EW, padx=10, pady=2)
    ToolTip(btn_load, msg="Load parameters from a file.", delay=0.3)

    # Start button
    button_row += 1
    btn_start = ttk.Button(container, text="Start Experiment (F2)", command=start)
    btn_start.grid(row=button_row, column=0, columnspan=3, sticky=tk.EW, padx=10, pady=(10, 2))
    ToolTip(btn_start, msg="Start the experiment with the entered parameters.", delay=0.3)

    # Skip button
    button_row += 1
    btn_skip = ttk.Button(
        container,
        text="Skip Current Step (F5)",
        command=lambda: control_vars["skip_step"].set(True),
        state="disabled",
    )
    btn_skip.grid(row=button_row, column=0, columnspan=3, sticky=tk.EW, padx=10, pady=2)
    ToolTip(
        btn_skip,
        msg="Skip the current heating step and move to the next one.",
        delay=0.3,
    )
    control_vars["skip_button"] = btn_skip  # Store reference

    # -------------------- Keyboard Shortcuts --------------------

    gui_window.bind("<F2>", lambda e: start())
    gui_window.bind(
        "<F5>",
        lambda e: control_vars["skip_step"].set(True),
    )
    gui_window.bind(
        "<Control-s>",
        lambda e: save_settings(
            {
                **{k: v[0].get() for k, v in common_fields.items()},
                "Input Mode": input_mode.get(),
                "Tuning Mode": "Manual" if tuning_mode.get() else "Auto",
                **{k: v[0].get() for k, v in discrete_fields.items()},
                **{k: v[0].get() for k, v in continuous_fields.items()},
                **{k: v[0].get() for k, v in pid_vars.items()},
            }
        ),
    )
    gui_window.bind("<Control-l>", lambda e: load_and_refresh())

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
        container,
        text=f"{os.path.basename(__file__)} | Author: Delwin Tanto",
        font=("TkDefaultFont", 7),
    ).grid(row=999, column=0, columnspan=3, sticky=tk.SW, padx=5)

    return (
        gui_window,
        output,
        status_vars,
        control_vars,
        tuning_mode,
        input_mode,
        field_widgets,
        common_fields,
        discrete_fields,
        continuous_fields,
        pid_vars,
    )


# -------------------- GUI Integration Callbacks --------------------


def create_gui_callbacks_pid(gui_window, status_vars, control_vars):
    """Create callback functions for GUI integration with PID experiments.

    Args:
        gui_window (tk.Tk): Main GUI window.
        status_vars (dict): Dictionary of GUI status variables.
        control_vars (dict): Dictionary of GUI control variables.

    Returns:
        tuple: (update_status, check_skip) callback functions.
    """

    def update_status(phase, temperature, setpoint, current, voltage, resistance, time_remaining):
        """Update GUI status display from experiment thread.

        Args:
            phase (str): Current experiment phase (e.g., "Heating - Step 1/3", "Auto-Tuning").
            temperature (str): Temperature reading with units.
            setpoint (str): Setpoint temperature with units.
            current (str): Current reading with units.
            voltage (str): Voltage reading with units.
            resistance (str): Resistance reading with units.
            time_remaining (str): Time remaining/elapsed with units.

        Returns:
            None
        """
        gui_window.after(0, lambda: status_vars["phase"].set(phase))
        gui_window.after(0, lambda: status_vars["temperature"].set(temperature))
        gui_window.after(0, lambda: status_vars["setpoint"].set(setpoint))
        gui_window.after(0, lambda: status_vars["current"].set(current))
        gui_window.after(0, lambda: status_vars["voltage"].set(voltage))
        gui_window.after(0, lambda: status_vars["resistance"].set(resistance))
        gui_window.after(0, lambda: status_vars["time_remaining"].set(time_remaining))

    def check_skip():
        """Check if skip button was pressed in the GUI.

        Returns:
            bool: True if skip was requested, False otherwise.
        """
        if control_vars["skip_step"].get():
            control_vars["skip_step"].set(False)
            return True
        return False

    return update_status, check_skip


def create_experiment_complete_callback_pid(
    gui_window, status_vars, control_vars, experiment_started, field_widgets
):
    """Create callback for experiment completion in PID mode.

    Args:
        gui_window (tk.Tk): Main GUI window.
        status_vars (dict): Dictionary of GUI status variables.
        control_vars (dict): Dictionary of GUI control variables.
        experiment_started (list): Single-element list to track experiment state.
        field_widgets (dict): Dictionary of field widgets to re-enable.

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
            for widget in field_widgets.values():
                widget.entry.config(state="normal")

            # Re-enable mode radio buttons
            for child in gui_window.winfo_children():
                if isinstance(child, ttk.Radiobutton):
                    child.config(state="normal")

            # Re-enable all buttons except skip
            for widget in gui_window.winfo_children():
                if isinstance(widget, ttk.Button):
                    if widget.cget("text") != "Skip Current Step (F5)":
                        widget.config(state="normal")
                    else:
                        widget.config(state="disabled")

            # Reset status displays
            status_vars["phase"].set("Ready")
            status_vars["temperature"].set("--")
            status_vars["setpoint"].set("--")
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


def create_plot_callbacks_pid(gui_window, plot_position="+30+30"):
    """Create callbacks for plot operations on main thread for PID experiments.

    Args:
        gui_window (tk.Tk): Main GUI window.
        plot_position (str): Position string for plot window (e.g., "+100+0").

    Returns:
        tuple: (update_plot, show_final_plot, close_live_plot) callback functions.
    """

    def update_plot(fig, axes, lines, data):
        """Update live plot from main thread.

        Args:
            fig (matplotlib.figure.Figure): Figure object.
            axes (tuple): Tuple of axes objects.
            lines (tuple): Tuple of line objects.
            data (dict): Data dictionary with measurements.

        Returns:
            None
        """
        gui_window.after(0, lambda: update_live_plot(fig, axes, lines, data=data))

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
