"""Constant-current Joule heating experiment automation with GUI.

This script automates Direct Joule Synthesis (DJS) experiments by controlling a power
supply unit (PSU) and IR temperature sensors. The PSU supplies a constant current to
the Joule heating setup for user-specified durations, depending on the material type
and desired sintering.

Features:
    - Interactive GUI for parameter entry and experiment control
    - Real-time status display and live plotting during experiment
    - Background threading to keep GUI responsive
    - Skip functionality for individual heating steps
    - Automatic data acquisition and CSV export
    - Final summary plot generation

Main Functions:
    - run_djs_cc: Execute constant-current heating phase (DJS = Direct Joule Synthesis)
    - cooldown: Monitor and record cooldown phase
    - run_experiment_thread: Orchestrate full experiment workflow

Author       : Delwin Tanto
Last updated : 21 Jan 2026
"""

import time
from datetime import datetime
from tkinter import messagebox

import pandas as pd

from joule_heating.data import print_steps, print_summary, save_finalise, save_row, save_start
from joule_heating.devices import (
    PSUError,
    TemperatureSensorError,
    close_all,
    etm_read_current,
    etm_read_voltage,
    etm_set_current,
    etm_set_onoff,
    etm_set_voltage,
    init_devices,
    read_temperature,
)
from joule_heating.gui import (
    create_experiment_complete_callback_cc,
    create_gui_callbacks_cc,
    create_plot_callbacks_cc,
    gui_cc,
)
from joule_heating.gui.common import create_experiment_monitor, create_experiment_starter
from joule_heating.utils import (
    alert_cooldown_end,
    alert_step_start,
    position_console_window,
    prevent_sleep,
)
from joule_heating.utils.skip_step import register_sigint_handler, stop_event

# Constants
MAX_TEMP = 1200  # Max temp limit (°C) for safety
MIN_TEMP = 50  # Min temp limit (°C) for stopping cooldown
LOOP_INTERVAL = 0.1  # Loop interval to prevent CPU overload (s)
COOLDOWN_BUFFER = 10  # Extra seconds to wait after T drops below MIN_TEMP


# -------------------- Helper functions --------------------


def _read_data(power_supply, ycr_sensor, optris_sensor):
    """Read temperature, voltage and current, and compute resistance.

    Attempts to read temperature via :func:`temp_sensor_utils.read_temperature`.

    Args:
        power_supply (minimalmodbus.Instrument): PSU device instance.
        ycr_sensor (minimalmodbus.Instrument): YCR IR sensor instance.
        optris_sensor (serial.Serial): Optris IR sensor instance.

    Returns:
        tuple: ``(temperature, voltage, current, resistance)`` where resistance
            is ``voltage / current`` or ``float("inf")`` when current is zero.
    """
    t_read = read_temperature(ycr_sensor, optris_sensor)
    v_read = etm_read_voltage(power_supply) if power_supply else 0.0
    i_read = etm_read_current(power_supply) if power_supply else 0.0
    r_read = v_read / i_read if i_read != 0 else float("inf")
    return t_read, v_read, i_read, r_read


def _append_data(data, time_start, time_now, t_read, v_read, i_read, r_read):
    """Append a measurement row to the in-memory data dictionary.

    The function appends values to lists keyed by 'time', 'temperature',
    'voltage', 'current' and 'resistance'. Time is normalised so
    that the first recorded timestamp equals zero. This data dictionary
    serves as the source for CSV file writing and plotting.

    Args:
        data (dict): Data dictionary with keys 'time', 'temperature', 'voltage',
            'current', and 'resistance', each containing a list of measurements.
        time_start (float): Start time of the experiment (monotonic time).
        time_now (float): Current time (monotonic time).
        t_read (float): Temperature reading in °C.
        v_read (float): Voltage reading in V.
        i_read (float): Current reading in A.
        r_read (float): Resistance reading in Ω.

    Returns:
        None
    """
    # data dict (CSV source)
    data["time"].append(time_now - time_start)
    data["temperature"].append(t_read)
    data["voltage"].append(v_read)
    data["current"].append(i_read)
    data["resistance"].append(r_read)


# -------------------- Joule heating --------------------


def run_djs_cc(
    power_supply,
    ycr_sensor,
    optris_sensor,
    currs,
    durrs,
    v_set,
    fig,
    ax1,
    ax2,
    ax3,
    line1,
    line2,
    line3,
    status_callback=None,
    skip_check_callback=None,
    update_plot_callback=None,
):
    """Run the constant-current Joule Heating experiment.

    For each (current, duration) pair the function configures the PSU,
    records temperature/voltage/current/resistance at ``LOOP_INTERVAL`` and
    streams rows via :func:`save_data.save_row`. Live plots are updated throughout.

    Args:
        power_supply: PSU device instance (minimalmodbus.Instrument).
        ycr_sensor: YCR IR temperature sensor instance.
        optris_sensor: Optris IR sensor instance.
        currs (list[float]): Sequence of current setpoints (A).
        durrs (list[float]): Sequence of durations (s) matching ``currs``.
        v_set (float): Voltage limit (V).
        fig, ax1, ax2, ax3: Matplotlib figure and axes for live plotting.
        line1, line2, line3: Line objects used to display data.
        status_callback (callable, optional): Function to update GUI status with
            (phase, temp, max_temp, current, voltage, resistance, time_remaining).
        skip_check_callback (callable, optional): Function that returns True if skip requested.
        update_plot_callback (callable, optional): Function to update plot from main thread.

    Returns:
        tuple: ``(time_start, data)`` where ``time_start`` is the monotonic start
        time and ``data`` is a dict of lists containing the recorded series.
    """
    # Initialise empty data lists where measurements will be stored in
    data = {k: []
            for k in ["temperature", "time", "voltage", "current", "resistance"]}

    time_start = None  # Start time of the experiment
    total_steps = len(currs)
    max_temperature = 0.0  # Track maximum temperature reached

    print(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        "Starting heating. \033[1;31mDO NOT TOUCH!\033[0m"
    )

    for idx, (i_set, durr) in enumerate(zip(currs, durrs), start=1):
        end_time = time.monotonic() + durr
        alert_step_start()  # Play alert sound

        try:
            etm_set_voltage(power_supply, voltage=v_set)
            etm_set_current(power_supply, current=i_set)
            etm_set_onoff(power_supply, on=True)
        except PSUError:
            continue

        # Collect data during the experiment
        while time.monotonic() <= end_time:
            try:
                time_now = time.monotonic()

                # Check if skip was requested via GUI callback or SIGINT
                skip_requested = (
                    skip_check_callback and skip_check_callback()
                ) or stop_event.is_set()
                if skip_requested:
                    stop_event.clear()
                    print(
                        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                        f"Step {idx} skipped by user."
                    )
                    break

                if time_start is None:
                    time_start = time_now  # Record the start time of the experiment

                t_read, v_read, i_read, r_read = _read_data(
                    power_supply, ycr_sensor, optris_sensor)
                _append_data(data, time_start, time_now,
                             t_read, v_read, i_read, r_read)
                save_row(time_now - time_start, t_read, i_read, v_read, r_read)

                # Track maximum temperature
                max_temperature = max(max_temperature, t_read)

                # PSU OFF if temperature exceeds limit
                etm_set_onoff(power_supply, on=t_read < MAX_TEMP)

                # Update live plot from main thread if callback provided
                if update_plot_callback:
                    update_plot_callback(
                        fig, (ax1, ax2, ax3), (line1, line2, line3), data)

                # Update GUI status if callback provided
                if status_callback:
                    status_callback(
                        phase=f"Heating - Step {idx}/{total_steps}",
                        temperature=f"{t_read:.1f}°C",
                        max_temperature=f"{max_temperature:.1f}°C",
                        current=f"{i_read:.1f} A",
                        voltage=f"{v_read:.2f} V",
                        resistance=f"{r_read:.2f} Ω",
                        time_remaining=f"{max(0, int(end_time - time_now))} s remaining",
                    )

                time.sleep(LOOP_INTERVAL)  # Sleep to prevent CPU overload
            except KeyboardInterrupt:
                # Ensure the stop_event is set so other loops observe the request
                stop_event.set()

        # Update live plot from main thread if callback provided
        if update_plot_callback:
            update_plot_callback(fig, (ax1, ax2, ax3),
                                 (line1, line2, line3), data)

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Heating completed!")
    return time_start, data


def cooldown(
    ycr_sensor,
    optris_sensor,
    data,
    fig,
    ax1,
    ax2,
    ax3,
    line1,
    line2,
    line3,
    time_start,
    max_temperature,
    status_callback=None,
    skip_check_callback=None,
    update_plot_callback=None,
):
    """Record cooldown data until the temperature remains below threshold.

    The function appends readings to ``data`` and stops once the measured
    temperature stays below ``MIN_TEMP`` for ``COOLDOWN_BUFFER`` seconds, or
    when the user interrupts with Ctrl+C.

    Args:
        ycr_sensor: YCR IR sensor instance.
        optris_sensor: Optris IR sensor instance.
        data (dict): Data dictionary to append cooldown values.
        fig, ax1, ax2, ax3, line1, line2, line3: Plot objects used by the live plot.
        time_start (float): Monotonic start time of the experiment.
        max_temperature (float): Maximum temperature reached during heating.
        status_callback (callable, optional): Function to update GUI status.
        skip_check_callback (callable, optional): Function that returns True if skip requested.
        update_plot_callback (callable, optional): Function to update plot from main thread.

    Returns:
        dict: The updated ``data`` dictionary.
    """
    threshold_detected_time = None
    cool_start = time.monotonic()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting cooldown...")
    alert_step_start()  # Play alert sound

    while True:
        try:
            time_now = time.monotonic()

            # Check if skip was requested via GUI callback or SIGINT
            skip_requested = (
                skip_check_callback and skip_check_callback()) or stop_event.is_set()
            if skip_requested:
                stop_event.clear()
                break

            t_read, v_read, i_read, r_read = _read_data(
                None, ycr_sensor, optris_sensor)
            _append_data(data, time_start, time_now,
                         t_read, v_read, i_read, r_read)
            save_row(time_now - time_start, t_read, i_read, v_read, r_read)

            # Update live plot from main thread if callback provided
            if update_plot_callback:
                update_plot_callback(fig, (ax1, ax2, ax3),
                                     (line1, line2, line3), data)

            elapsed = int(time_now - cool_start)

            # Update GUI status if callback provided
            if status_callback:
                status_callback(
                    phase="Cooldown",
                    temperature=f"{t_read:.1f}°C",
                    max_temperature=f"{max_temperature:.1f}°C",
                    current="0 A",
                    voltage="0 V",
                    resistance=f"{r_read:.2f} Ω" if r_read != float(
                        "inf") else "∞ Ω",
                    time_remaining=f"{elapsed} s elapsed",
                )

            temp_low = pd.isna(t_read) or t_read <= MIN_TEMP

            if temp_low:
                if threshold_detected_time is None:
                    threshold_detected_time = time_now
                elif time_now - threshold_detected_time > COOLDOWN_BUFFER:
                    break
            elif threshold_detected_time is not None:
                threshold_detected_time = None

            time.sleep(LOOP_INTERVAL)  # Sleep to prevent CPU overload
        except KeyboardInterrupt:
            stop_event.set()

    alert_cooldown_end()  # Play alert sound
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Cooldown completed!")
    return data


def run_experiment_thread(
    power_supply,
    ycr_sensor,
    optris_sensor,
    sample_id,
    currents,
    durations,
    max_volt,
    status_callback,
    skip_check_callback,
    completion_callback,
    figure,
    ax_temp,
    ax_current,
    ax_resistance,
    line_temp,
    line_current,
    line_resistance,
    update_plot_callback,
    show_final_plot_callback,
    close_live_plot_callback,
):
    """Run the full experiment in a background thread.

    This function orchestrates the entire experiment workflow including heating,
    cooldown, data saving, and plot generation. It runs in a separate thread to
    keep the GUI responsive.

    Args:
        power_supply (minimalmodbus.Instrument): PSU device instance.
        ycr_sensor (minimalmodbus.Instrument): YCR IR sensor instance.
        optris_sensor (serial.Serial): Optris IR sensor instance.
        sample_id (str): Sample name for data files.
        currents (list[float]): Sequence of current setpoints (A).
        durations (list[float]): Sequence of durations (s).
        max_volt (float): Maximum voltage limit (V).
        status_callback (callable): Function to update GUI status display.
        skip_check_callback (callable): Function to check if skip requested.
        completion_callback (callable): Function to call when experiment completes.
        figure (matplotlib.figure.Figure): Live plot figure object.
        ax_temp (matplotlib.axes.Axes): Temperature axis.
        ax_current (matplotlib.axes.Axes): Current axis.
        ax_resistance (matplotlib.axes.Axes): Resistance axis.
        line_temp (matplotlib.lines.Line2D): Temperature line object.
        line_current (matplotlib.lines.Line2D): Current line object.
        line_resistance (matplotlib.lines.Line2D): Resistance line object.
        update_plot_callback (callable): Function to update live plot from main thread.
        show_final_plot_callback (callable): Function to show final plot from main thread.
        close_live_plot_callback (callable): Function to close live plot from main thread.

    Returns:
        None
    """
    final_csv_path = None
    saved_data = None

    try:
        with prevent_sleep():  # Prevent system sleep during experiment
            save_start(sample_id)  # Prepare to save data

            try:
                # Joule heating phase
                start_time, h_data = run_djs_cc(
                    power_supply,
                    ycr_sensor,
                    optris_sensor,
                    currents,
                    durations,
                    max_volt,
                    figure,
                    ax_temp,
                    ax_current,
                    ax_resistance,
                    line_temp,
                    line_current,
                    line_resistance,
                    status_callback=status_callback,
                    skip_check_callback=skip_check_callback,
                    update_plot_callback=update_plot_callback,
                )

                # Shut down the power supply
                etm_set_onoff(power_supply, on=False)

                # Cooldown phase
                h_data = cooldown(
                    ycr_sensor,
                    optris_sensor,
                    h_data,
                    figure,
                    ax_temp,
                    ax_current,
                    ax_resistance,
                    line_temp,
                    line_current,
                    line_resistance,
                    start_time,
                    max(h_data["temperature"]) if h_data["temperature"] else 0,
                    status_callback=status_callback,
                    skip_check_callback=skip_check_callback,
                    update_plot_callback=update_plot_callback,
                )
            finally:
                try:
                    final_csv_path = save_finalise()  # Finalise and save data
                except OSError as e:
                    print(f"Error saving final data: {e}")
                    final_csv_path = None

                # Close live plot window first (before final plot)
                if close_live_plot_callback:
                    close_live_plot_callback()

                if final_csv_path and final_csv_path != "None":
                    saved_data = pd.read_csv(final_csv_path)

                    # Print some information about the experiment
                    print_summary(sample_id, saved_data, final_csv_path)
                    print_steps(currents, durations, cc=True)

                    # Show final plot from main thread (blocks until user closes it)
                    if show_final_plot_callback:
                        show_final_plot_callback(saved_data, sample_id)
    finally:
        # Fail-safe: Always turn off devices (skip plot - already closed by callback)
        close_all(power_supply, ycr_sensor, optris_sensor, skip_plot=True)

        # Notify GUI that experiment is complete
        if completion_callback:
            completion_callback()


# -------------------- Main Program --------------------
if __name__ == "__main__":
    # Register SIGINT handler so Ctrl+C sets `stop_event` and requests skip/stop.
    with register_sigint_handler():
        print(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            "Starting the constant current Joule heating program. Please fill in the GUI."
        )

        # Initialise communication with IR temperature sensors and power supply
        try:
            psu, ycr_temp_sensor, optris_temp_sensor = init_devices()
        except (PSUError, TemperatureSensorError) as e:
            # Device initialization failed - show error dialog
            messagebox.showerror(
                "Device Connection Error",
                f"Failed to initialise devices:\n\n{str(e)}.\n\nPress OK to exit.",
            )
            raise SystemExit(
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Program stopped."
            ) from e

        # Create GUI and get experiment parameters
        (
            gui_window,
            output,
            status_vars,
            control_vars,
        ) = gui_cc(psu, ycr_temp_sensor, optris_temp_sensor)

        if output is None:
            close_all(psu, ycr_temp_sensor, optris_temp_sensor)
            raise SystemExit("Program stopped.")

        # Position console window to the right of GUI immediately
        gui_window.update_idletasks()  # Ensure geometry is updated
        gui_x = gui_window.winfo_x()
        gui_width = gui_window.winfo_width()
        position_console_window(gui_x + gui_width + 10, 520, 800, 300)

        # Create GUI callback functions
        update_status, check_skip = create_gui_callbacks_cc(
            gui_window, status_vars, control_vars)

        # Flag to prevent multiple simultaneous runs
        experiment_started = [False]

        # Create experiment completion callback
        on_experiment_complete = create_experiment_complete_callback_cc(
            gui_window, status_vars, control_vars, experiment_started
        )

        def get_cc_experiment_args(
            exp_output, exp_devices, exp_callbacks, exp_figure, exp_axes, exp_lines
        ):
            """Extract and organize arguments for CC experiment thread."""
            power_supply, ycr_sensor, optris_sensor = exp_devices
            (
                cb_status,
                cb_skip,
                cb_complete,
                cb_plot_update,
                cb_plot_final,
                cb_plot_close,
            ) = exp_callbacks
            ax_temp, ax_curr, ax_res = exp_axes
            line_temp, line_curr, line_res = exp_lines

            return (
                power_supply,
                ycr_sensor,
                optris_sensor,
                exp_output["sample"],
                exp_output["currents"],
                exp_output["durations"],
                exp_output["voltage"],
                cb_status,
                cb_skip,
                cb_complete,
                exp_figure,
                ax_temp,
                ax_curr,
                ax_res,
                line_temp,
                line_curr,
                line_res,
                cb_plot_update,
                cb_plot_final,
                cb_plot_close,
            )

        # Create start_experiment function using common factory
        start_experiment = create_experiment_starter(
            gui_window,
            control_vars,
            experiment_started,
            (psu, ycr_temp_sensor, optris_temp_sensor),
            output,
            update_status,
            check_skip,
            on_experiment_complete,
            create_plot_callbacks_cc,
            run_experiment_thread,
            get_cc_experiment_args,
        )

        # Create experiment monitor using common factory
        check_experiment_start = create_experiment_monitor(
            gui_window, control_vars, output, start_experiment
        )

        def on_close():
            """Handle window close event."""
            if not control_vars["experiment_running"].get():
                close_all(psu, ycr_temp_sensor, optris_temp_sensor)
                gui_window.destroy()
            else:
                messagebox.showwarning(
                    "Warning", "Cannot close while experiment is running!")

        # Start monitoring for experiment trigger
        gui_window.after(100, check_experiment_start)

        # Set window close handler
        gui_window.protocol("WM_DELETE_WINDOW", on_close)

        # Bring GUI window to front and give it focus
        gui_window.lift()
        gui_window.focus_force()

        # Start GUI main loop
        gui_window.mainloop()
