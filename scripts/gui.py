"""Graphical interfaces for entering Joule Heating experiment parameters.

- :func:`gui_cc` for constant-current experiments
- :func:`gui_pid` for PID-controlled temperature experiments

Both functions are intended to be used by the main scripts and return a
tuple of parameters or ``(None, ... )`` when cancelled.

Author       : Delwin Tanto
Last updated : 04 Nov 2025
"""

import json
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tktooltip import ToolTip


DEFAULTDIR = r"C:\Users\delwintanto\Documents\Joule_Heating_Data\Experiment Parameters"


class LabeledEntry:
    """
    A composite widget combining a label and an entry field with optional tooltip.

    Attributes:
        var (tk.StringVar): Variable linked to the entry.
        label (ttk.Label): The label component.
        entry (ttk.Entry): The entry field component.
    """

    def __init__(
        self, master, label, row, col=0, colspan=2, var=None, width=40, tooltip=None
    ):
        """
        Initialise the LabeledEntry widget and places it in the GUI.

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
        self.entry.grid(
            row=row, column=col + 1, columnspan=colspan, sticky=tk.EW, padx=5, pady=2
        )
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
    """
    A helper class to track and increment row indices for placing widgets.

    Attributes:
        value (int): The current row value.
    """

    def __init__(self, start=0):
        """Initialise the RowCounter with a starting value.

        Args:
            start (int): Initial row index.
        """
        self.value = start  # Current row value

    def next(self, step=1):
        """Return the current row index and increment by ``step``.

        Args:
            step (int): Step size for incrementing (default is 1).

        Returns:
            int: The current row index before incrementing.
        """
        val = self.value
        self.value += step  # Advance the row value by the step
        return val  # But return the previous value for placement


def _parse_floats(input_str):
    """Convert a comma-separated string to a list of floats.

    Args:
        input_str (str): Comma-separated numbers as a string.

    Returns:
        list[float]: List of parsed float values.
    """
    return list(map(float, input_str.split(",")))


def _show_error(msg):
    """Display an error message dialog.

    Args:
        msg (str): Error message to display.
    """
    messagebox.showerror("Input Error", msg)


def _show_info(msg):
    """Display an informational message dialog.

    Args:
        msg (str): Information message to display.
    """
    messagebox.showinfo("Information", msg)


def _check_empty_fields(field_dict):
    """Identify which labeled fields are empty.

    Args:
        field_dict (dict): Mapping from label text to ``(tk.Variable, tooltip)``.

    Returns:
        list[str]: Labels (without unit hints) whose variables are empty.
    """
    return [
        re.sub(r"\s*\([^)]*\)", "", label)
        for label, (var, _) in field_dict.items()
        if not var.get().strip()
    ]


def _save_settings(file_vars):
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

    # Ensure extension is present (based on selection)
    if not os.path.splitext(file_path)[1]:  # No extension
        if file_path.endswith(".json"):
            ext = ".json"
        elif file_path.endswith(".txt"):
            ext = ".txt"
        else:
            # Default to .txt if not manually specified
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
        _show_info("Parameters saved successfully!")
    except IOError as e:
        _show_error(f"Error saving file: {e}")


def _load_settings(target_vars):
    """Load parameters from a JSON or text file into target tk.Variable instances.

    Args:
        target_vars (dict): Mapping of parameter names to ``tk.Variable`` instances.
    """
    file_path = filedialog.askopenfilename(
        initialdir=DEFAULTDIR,
        filetypes=[("Text Files", "*.txt"),
                   ("JSON Files", "*.json"), ("All Files", "*.*")]
    )
    if not file_path:
        return

    ext = os.path.splitext(file_path)[1].lower()
    try:
        # Load from JSON
        if ext == ".json":
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
        # Load from text file
        else:
            data = {}
            with open(file_path, "r", encoding="utf-8") as file:
                for line in file:
                    if ": " in line:
                        parts = line.strip().split(": ", 1)
                        if len(parts) == 2:
                            key, value = parts
                            data[key] = value

        # Update the target variables with loaded data
        for key, value in data.items():
            if key in target_vars:
                var = target_vars[key]
                if isinstance(var, tk.StringVar):
                    var.set(value)
                elif isinstance(var, tk.IntVar):
                    var.set(1 if value.lower() == "manual" else 0)
        _show_info("Parameters loaded successfully!")
    except IOError as e:
        _show_error(f"Error loading file: {e}")


def _radio_button(master, label_text, options, var, row_counter):
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
        row=row, column=0, sticky=tk.W, padx=5, pady=2)
    for i, (text, tooltip) in enumerate(options, 1):
        rb = ttk.Radiobutton(
            master,
            text=text,
            variable=var,
            value=text.split()[0] if label_text.startswith(
                "Temperature") else text
        )
        rb.grid(row=row, column=i, sticky=tk.W, padx=5, pady=2)
        ToolTip(rb, msg=tooltip, delay=0.3)


def _sec_to_hhmmss(seconds_float):
    """Convert seconds to an "HH:MM:SS" formatted string.

    Args:
        seconds_float (float): Time in seconds.

    Returns:
        str: Time formatted as ``HH:MM:SS``.
    """
    h, m = divmod(int(round(seconds_float)), 3600)
    m, s = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def gui_cc():
    """
    Launch a GUI for entering basic Joule Heating experiment parameters.

    Returns:
        tuple: (sample name, currents list, durations list, voltage),
               or (None, None, None, None) if cancelled.
    """
    gui = tk.Tk()
    gui.title("Joule Heating Experiment")
    gui.resizable(False, False)

    row = RowCounter()
    ttk.Label(
        gui,
        text="Enter all parameters before starting.\n"
        "Check equipment manuals before running.\n"
        "Incorrect settings may cause failure.\n"
        "Specs:\nWhite PSU: 0-20 A, 0-60 V\nBlack PSU: 0-50 A, 0-50 V\n"
        "*If input exceeds limits, max will be used."
    ).grid(row=row.next(), column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)

    # Creates input fields
    entries = {
        "Sample Name": LabeledEntry(
            gui, "Sample Name:", row.next(), tooltip="Enter a unique name for your sample."
        ),
        "Currents (A)": LabeledEntry(
            gui,
            "Currents (A):",
            row.next(),
            tooltip="Current to be supplied to the sample.\n"
            "Use commas for multiple values (e.g., 10,15,20).",
        ),
        "Durations (s)": LabeledEntry(
            gui,
            "Durations (s):",
            row.next(),
            tooltip="Duration for each current step.\n"
            "Use commas for multiple values (e.g., 10,15,20).",
        ),
        "Max Voltage (V)": LabeledEntry(
            gui, "Max Voltage (V):", row.next(), tooltip="Voltage limit the PSU will supply."
        ),
    }

    # Dictionary to store the output values
    output = {k: None for k in ["sample", "currents", "durations", "voltage"]}
    experiment_started = False  # Flag to track if experiment was properly started

    def start():
        """Handle the start button click event."""
        nonlocal experiment_started
        try:
            # Checks for missing entries
            missing = _check_empty_fields(
                {k: (e.var, None) for k, e in entries.items()})
            if missing:
                return _show_error(f"Missing fields: {', '.join(missing)}")

            # Obtains and processes all values from the entries
            vals = {k: e.get() for k, e in entries.items()}
            currents = _parse_floats(vals["Currents (A)"])
            durations = _parse_floats(vals["Durations (s)"])
            voltage = float(vals["Max Voltage (V)"])

            # Validates the inputs
            if len(currents) != len(durations):
                return _show_error("Current and duration counts must match.")
            if any(x < 0 for x in currents + durations) or voltage < 0:
                return _show_error("No values can be negative.")

            # Store the validated values
            output.update(
                {
                    "sample": vals["Sample Name"],
                    "currents": currents,
                    "durations": durations,
                    "voltage": voltage,
                }
            )

            if not messagebox.askyesno(
                "Confirm",
                f"Approximate length of the experiment: {_sec_to_hhmmss(sum(durations) + 240)}\n"
                "Start experiment with the entered parameters?"
            ):
                return

            experiment_started = True  # Sets flag when experiment is properly started
            _show_info(
                "Starting experiment.\nDo not touch the sample or power supply!")
            gui.destroy()
        except ValueError:
            _show_error("Check number formatting. Use commas between values.")

    # Creates buttons
    buttons = [
        ("Save Parameters", lambda: _save_settings({k: e.get() for k, e in entries.items()}),
         "Save parameters to a text file."),
        ("Load Parameters", lambda: _load_settings({k: e.var for k, e in entries.items()}),
         "Load parameters from a text file."),
        ("Start Experiment", start, "Start the experiment with the entered parameters."),
    ]

    for text, cmd, tip in buttons:
        btn = ttk.Button(gui, text=text, command=cmd)
        btn.grid(
            row=row.next(),
            column=0,
            columnspan=3,
            sticky=tk.EW,
            padx=10,
            pady=10 if text == "Start Experiment" else (2, 0),
        )
        ToolTip(btn, msg=tip, delay=0.3)

    tk.Label(
        gui,
        text=f"{os.path.basename(__file__)} | Author: Delwin Tanto",
        font=("TkDefaultFont", 7),
    ).grid(row=row.value, column=0, columnspan=3, sticky=tk.SW, padx=5)

    gui.mainloop()

    # Returns None for all values if window was closed without starting experiment
    if not experiment_started:
        return (None,) * len(output)
    return tuple(output.values())


def gui_pid(start_experiment_callback=None):
    """
    Launch a GUI for PID-controlled Joule Heating experiment.

    Args:
        start_experiment_callback (callable, optional): Function to call with experiment parameters.

    Returns:
        tuple: Parameters including sample name, temps, durations, current, voltage, cooldown,
               PID constants or tuning time, and tuning method, or all None if cancelled.
    """
    gui = tk.Tk()
    gui.title("GUI")
    gui.resizable(False, False)
    gui.geometry("")

    row = RowCounter()
    ttk.Label(gui, text="Joule Heating Experiment Parameters", font=("TkDefaultFont", 12)).grid(
        row=row.next(), column=0, columnspan=3, padx=5, pady=10
    )
    ttk.Label(
        gui,
        text="Enter all parameters before starting.\n"
        "Verify equipment limits in your main script or manuals.\n"
        "Incorrect settings may cause failure.",
    ).grid(row=row.next(), column=0, columnspan=3, sticky=tk.W, padx=5, pady=(0, 10))

    # Variables for radio buttons
    tuning_mode = tk.IntVar(value=0)
    input_mode = tk.StringVar(value="Discrete")

    _radio_button(
        gui,
        "Temperature Input Mode:",
        [
            ("Discrete", "Discrete mode requires a list of temperatures and durations."),
            ("Continuous", "Continuous mode requires a start, end, and step temperature."),
        ],
        input_mode,
        row,
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
                gui, label + ":", i, col=0, colspan=2, var=var, tooltip=tooltip
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
        for child in gui.winfo_children():
            if isinstance(child, ttk.Label) and child.cget("text") == "Tuning:":
                child.grid_remove()
            if isinstance(child, ttk.Radiobutton) and child.cget("text") in ("Auto", "Manual"):
                child.grid_remove()

        # Draws common fields
        dynamic_row = RowCounter(start=row.value)
        draw_fields(common_fields, dynamic_row.value)
        dynamic_row.next(len(common_fields))

        # Draws mode specific fields
        mode_fields = (
            discrete_fields if input_mode.get() == "Discrete" else continuous_fields
        )
        draw_fields(mode_fields, dynamic_row.value)
        dynamic_row.next(len(mode_fields))

        # Tuning mode selection
        ttk.Label(gui, text="Tuning:").grid(
            row=dynamic_row.next(), column=0, sticky=tk.W, padx=5, pady=2
        )

        for i, (text, val) in enumerate([("Auto", 0), ("Manual", 1)], 1):
            rb = ttk.Radiobutton(
                gui, text=text, variable=tuning_mode, value=val)
            rb.grid(row=dynamic_row.value - 1, column=i,
                    sticky=tk.W, padx=5, pady=2)
            tooltip_msg = (
                "Uses relay feedback to automatically tune the PID controller.\n"
                "Select this option if PID gains are unknown."
                if val == 0 else
                "Manually enter PID gains.\nSelect this option if PID gains are known."
            )
            ToolTip(
                rb,
                msg=tooltip_msg,
                delay=0.3,
            )

        # Draws PID fields based on tuning mode
        if tuning_mode.get() == 1:
            draw_fields({k: pid_vars[k] for k in (
                "Kp", "Ki", "Kd")}, dynamic_row.next(3))
        else:
            draw_fields(
                {"Tuning Duration (s)": pid_vars["Tuning Duration (s)"]}, dynamic_row.next(
                )
            )

        return dynamic_row.value + len(pid_vars)

    def load_and_refresh():
        """Load parameters from a file and refreshes the GUI fields."""
        _load_settings(
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
    refresh_fields()

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
    }
    experiment_started = False  # Flag to track if experiment was properly started

    def start():
        """Handle the start button click event."""
        nonlocal experiment_started
        try:
            # Checks for missing entries
            missing = (
                _check_empty_fields(common_fields) +
                _check_empty_fields(
                    discrete_fields if input_mode.get() == "Discrete"
                    else continuous_fields
                ) +
                _check_empty_fields(
                    {k: pid_vars[k] for k in ("Kp", "Ki", "Kd")} if tuning_mode.get() == 1
                    else {"Tuning Duration (s)": pid_vars["Tuning Duration (s)"]}
                )
            )

            if missing:
                return _show_error(f"Missing fields: {', '.join(missing)}")

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
                temps, durs = [_parse_floats(v[0].get())
                               for v in discrete_fields.values()]
                if len(temps) != len(durs):
                    raise ValueError("Mismatch in temperatures and durations.")
                if not all(x > 0 for x in durs):
                    raise ValueError("Duration values cannot be negative.")
                output["temps"], output["durs"] = temps, durs
            else:
                # Continuous mode - calculates temperatures from range
                s = _parse_floats(
                    continuous_fields["Start Temp (°C)"][0].get())
                s_dur = _parse_floats(
                    continuous_fields["Initial Heating Duration (s)"][0].get())
                e = float(continuous_fields["End Temp (°C)"][0].get())
                st = float(continuous_fields["Step Temp (°C)"][0].get())
                dur = float(continuous_fields["Step Duration (s)"][0].get())

                if len(s) != len(s_dur):
                    raise ValueError(
                        "Mismatch in starting temperatures and durations.")
                if s[-1] == e and st != 0:
                    raise ValueError(
                        "Zero temperature difference with non-zero step.")
                if st == 0 and s[-1] != e:
                    raise ValueError("Non-zero temp range needs step.")
                st = abs(st) if s[-1] < e else -abs(st)
                steps = int((e - s[-1]) / st) + 1
                output["temps"] = s + [round(s[-1] + (i + 1) * st, 1)
                                       for i in range(steps - 1)]
                output["durs"] = s_dur + [dur] * (steps - 1)

            # Handles PID parameters based on tuning mode
            if tuning_mode.get() == 1:
                output["kp"], output["ki"], output["kd"] = [
                    float(pid_vars[k][0].get()) for k in ("Kp", "Ki", "Kd")
                ]
            else:
                output["tuning_time"] = float(
                    pid_vars["Tuning Duration (s)"][0].get())

            # Confirms before starting the experiment
            total_time = _sec_to_hhmmss(
                sum(output["durs"])
                + output["cooldown"]
                + (0 if tuning_mode.get() else output["tuning_time"])
            )

            if not messagebox.askyesno(
                "Confirm",
                f"Approximate length of the experiment: {total_time}\n"
                "Start experiment with "
                f"{"manually entered PID gains" if tuning_mode.get() else "auto-tuning"}?",
            ):
                return

            experiment_started = True
            _show_info(
                "Starting experiment.\nDo not touch the sample or power supply!")
            gui.destroy()

            # Calls the callback function if provided
            if start_experiment_callback:
                start_experiment_callback(
                    *output.values(),
                    "Manual tuning" if tuning_mode.get() else "Auto tuning",
                )

        except ValueError as e:
            _show_error(str(e))

    # Gets the next available row after all the fields
    last_row = refresh_fields()

    # Creates buttons
    buttons = [
        ("Save Parameters", lambda: _save_settings({
            **{k: v[0].get() for k, v in common_fields.items()},
            "Input Mode": input_mode.get(),
            "Tuning Mode": "Manual" if tuning_mode.get() else "Auto",
            **{k: v[0].get() for k, v in discrete_fields.items()},
            **{k: v[0].get() for k, v in continuous_fields.items()},
            **{k: v[0].get() for k, v in pid_vars.items()},
        }), "Save parameters to a text file."),
        ("Load Parameters", load_and_refresh, "Load parameters from a text file."),
        ("Start Experiment", start, "Start the experiment with the entered parameters."),
    ]

    for i, (text, cmd, tip) in enumerate(buttons, start=1):
        btn = ttk.Button(gui, text=text, command=cmd)
        btn.grid(
            row=last_row + i,
            column=0,
            columnspan=3,
            sticky=tk.EW,
            padx=10,
            pady=10 if text == "Start Experiment" else (2, 0),
        )
        ToolTip(btn, msg=tip, delay=0.3)

    tk.Label(
        gui,
        text=f"{os.path.basename(__file__)} | Author: Delwin Tanto",
        font=("TkDefaultFont", 7),
    ).grid(row=999, column=0, columnspan=3, sticky=tk.SW, padx=5)

    gui.mainloop()

    # Return None for all values if window was closed without starting experiment
    if not experiment_started:
        return (None,) * (len(output) + 1)
    return (
        *output.values(),
        "Manual tuning" if tuning_mode.get() else "Auto tuning",
    )


if __name__ == "__main__":
    # For testing purposes, uncomment one of these:
    # result = gui_cc()
    result = gui_pid()
    print(result)
