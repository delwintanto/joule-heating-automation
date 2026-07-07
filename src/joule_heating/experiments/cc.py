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
    - run_djs_cc: Execute constant-current heating phase
    - cooldown: Monitor and record cooldown phase
    - run_experiment_thread: Orchestrate full experiment workflow
"""

import math
import time
from datetime import datetime
from tkinter import messagebox

import pandas as pd

from joule_heating.data import CsvWriter, print_steps, print_summary
from joule_heating.devices import (
    Measurement,
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
from joule_heating.gui.common import (
    ExperimentCallbacks,
    create_experiment_monitor,
    create_experiment_starter,
)
from joule_heating.utils import (
    alert_cooldown_end,
    alert_step_start,
    position_console_window,
    prevent_sleep,
)
from joule_heating.utils.skip_step import register_sigint_handler

# Constants
MAX_TEMP = 1200  # Max temp limit (°C) for safety
MIN_TEMP = 50  # Min temp limit (°C) for stopping cooldown
LOOP_INTERVAL = 0.1  # Loop interval to prevent CPU overload (s)
COOLDOWN_BUFFER = 10  # Extra seconds to wait after T drops below MIN_TEMP


# -------------------- Helper functions --------------------


def _read_data(devices):
    """Read temperature, voltage and current, and compute resistance.

    Args:
        devices (Devices): Device handles container.

    Returns:
        tuple: ``(temperature, voltage, current, resistance)`` where resistance
            is ``voltage / current`` or ``float("inf")`` when current is zero.
    """
    t_read = read_temperature(devices.ycr_sensor, devices.optris_sensor)
    v_read = etm_read_voltage(devices.power_supply) if devices.power_supply else 0.0
    i_read = etm_read_current(devices.power_supply) if devices.power_supply else 0.0
    r_read = v_read / i_read if i_read != 0 else float("inf")
    return Measurement(t_read, v_read, i_read, r_read)


def _append_data(data, time_start, time_now, m):
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
        m (Measurement): Measurement reading.

    Returns:
        None
    """
    # data dict (CSV source)
    data["time"].append(time_now - time_start)
    data["temperature"].append(m.temperature)
    data["voltage"].append(m.voltage)
    data["current"].append(m.current)
    data["resistance"].append(m.resistance)


# -------------------- Joule heating --------------------


def run_djs_cc(
    devices,
    currs,
    durrs,
    v_set,
    csv_writer,
    live_plot,
    stop_event,
    callbacks=ExperimentCallbacks(),
):
    """Run the constant-current Joule Heating experiment.

    For each (current, duration) pair the function configures the PSU,
    records temperature/voltage/current/resistance at ``LOOP_INTERVAL`` and
    streams rows via ``csv_writer``. Live plots are updated throughout.

    Args:
        devices (Devices): Device handles container.
        currs (list[float]): Sequence of current setpoints (A).
        durrs (list[float]): Sequence of durations (s) matching ``currs``.
        v_set (float): Voltage limit (V).
        csv_writer (CsvWriter): Streaming CSV writer instance.
        live_plot (LivePlot): Live plot container (fig, axes, lines).
        stop_event (threading.Event): Event set on SIGINT to request skip/stop.
        callbacks (ExperimentCallbacks): Experiment control callbacks.

    Returns:
        tuple: ``(time_start, data)`` where ``time_start`` is the monotonic start
        time and ``data`` is a dict of lists containing the recorded series.
    """
    # Initialise empty data lists where measurements will be stored in
    data = {k: [] for k in ["temperature", "time", "voltage", "current", "resistance"]}

    time_start = None  # Start time of the experiment
    total_steps = len(currs)
    max_temperature = 0.0  # Track maximum temperature reached

    print(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        "Starting heating. \033[1;31mDO NOT TOUCH!\033[0m"
    )

    for idx, (i_set, durr) in enumerate(zip(currs, durrs, strict=True), start=1):
        end_time = time.monotonic() + durr
        alert_step_start()  # Play alert sound

        try:
            etm_set_voltage(devices.power_supply, voltage=v_set)
            etm_set_current(devices.power_supply, current=i_set)
            etm_set_onoff(devices.power_supply, on=True)
        except PSUError:
            continue

        # Collect data during the experiment
        next_tick = time.monotonic()
        while True:
            try:
                time_now = time.monotonic()

                # End this step using real monotonic time, not scheduled tick time.
                if time_now >= end_time:
                    break

                next_tick += LOOP_INTERVAL

                # Check if skip was requested via GUI callback or SIGINT
                skip_requested = (
                    callbacks.skip_check and callbacks.skip_check()
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

                m = _read_data(devices)
                _append_data(data, time_start, time_now, m)
                csv_writer.row(
                    time_now - time_start, m.temperature, m.current, m.voltage, m.resistance
                )

                # Track maximum temperature (guard against NaN sensor readings)
                if m.temperature == m.temperature:  # NaN != NaN
                    max_temperature = max(max_temperature, m.temperature)

                # PSU OFF if temperature exceeds limit
                etm_set_onoff(devices.power_supply, on=m.temperature < MAX_TEMP)

                # Update live plot from main thread if callback provided
                if callbacks.update_plot:
                    callbacks.update_plot(live_plot, data)

                # Update GUI status if callback provided
                if callbacks.status:
                    callbacks.status(
                        phase=f"Heating - Step {idx}/{total_steps}",
                        temperature=f"{m.temperature:.1f}°C",
                        max_temperature=f"{max_temperature:.1f}°C",
                        current=f"{m.current:.1f} A",
                        voltage=f"{m.voltage:.2f} V",
                        resistance=(
                            f"{m.resistance:.2f} Ω" if m.resistance != float("inf") else "∞ Ω"
                        ),
                        time_remaining=f"{max(0, math.ceil(end_time - time_now))} s remaining",
                    )

                time.sleep(max(0, next_tick - time.monotonic()))
            except KeyboardInterrupt:
                # Ensure the stop_event is set so other loops observe the request
                stop_event.set()

        # Update live plot from main thread if callback provided
        if callbacks.update_plot:
            callbacks.update_plot(live_plot, data)

        # Full stop requested - exit all remaining heating steps
        if callbacks.skip_check and callbacks.skip_check():
            break

    # Ensure output is disabled when heating phase ends.
    etm_set_onoff(devices.power_supply, on=False)

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Heating completed!")
    return time_start, data


def cooldown(
    devices,
    data,
    csv_writer,
    live_plot,
    time_start,
    max_temperature,
    stop_event,
    callbacks=ExperimentCallbacks(),
):
    """Record cooldown data until the temperature remains below threshold.

    Args:
        devices (Devices): Device handles container (PSU is not read during cooldown).
        data (dict): Data dictionary to append cooldown values.
        csv_writer (CsvWriter): Streaming CSV writer instance.
        live_plot (LivePlot): Live plot container (fig, axes, lines).
        time_start (float): Monotonic start time of the experiment.
        max_temperature (float): Maximum temperature reached during heating.
        stop_event (threading.Event): Event set on SIGINT to request skip/stop.
        callbacks (ExperimentCallbacks): Experiment control callbacks.

    Returns:
        dict: The updated ``data`` dictionary.
    """
    # Guard: if no data was collected during heating time_start may be None
    if time_start is None:
        time_start = time.monotonic()

    threshold_detected_time = None
    cool_start = time.monotonic()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting cooldown...")
    alert_step_start()  # Play alert sound

    next_tick = time.monotonic()
    while True:
        try:
            time_now = time.monotonic()
            next_tick += LOOP_INTERVAL

            # Check if skip was requested via GUI callback or SIGINT
            skip_requested = (
                callbacks.skip_check and callbacks.skip_check()
            ) or stop_event.is_set()
            if skip_requested:
                stop_event.clear()
                break

            m = _read_data(devices._replace(power_supply=None))
            _append_data(data, time_start, time_now, m)
            csv_writer.row(time_now - time_start, m.temperature, m.current, m.voltage, m.resistance)

            # Update live plot from main thread if callback provided
            if callbacks.update_plot:
                callbacks.update_plot(live_plot, data)

            elapsed = int(time_now - cool_start)

            # Update GUI status if callback provided
            if callbacks.status:
                callbacks.status(
                    phase="Cooldown",
                    temperature=f"{m.temperature:.1f}°C",
                    max_temperature=f"{max_temperature:.1f}°C",
                    current="0 A",
                    voltage="0 V",
                    resistance=(f"{m.resistance:.2f} Ω" if m.resistance != float("inf") else "∞ Ω"),
                    time_remaining=f"{elapsed} s elapsed",
                )

            temp_low = pd.isna(m.temperature) or m.temperature <= MIN_TEMP

            if temp_low:
                if threshold_detected_time is None:
                    threshold_detected_time = time_now
                elif time_now - threshold_detected_time > COOLDOWN_BUFFER:
                    break
            elif threshold_detected_time is not None:
                threshold_detected_time = None

            time.sleep(max(0, next_tick - time.monotonic()))
        except KeyboardInterrupt:
            stop_event.set()

    alert_cooldown_end()  # Play alert sound
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Cooldown completed!")
    return data


def run_experiment_thread(
    devices,
    sample_id,
    currents,
    durations,
    max_volt,
    stop_event,
    callbacks,
    completion_callback,
    live_plot,
    show_final_plot_callback,
    close_live_plot_callback,
):
    """Run the full experiment in a background thread.

    Args:
        devices (Devices): Device handles container.
        sample_id (str): Sample name for data files.
        currents (list[float]): Sequence of current setpoints (A).
        durations (list[float]): Sequence of durations (s).
        max_volt (float): Maximum voltage limit (V).
        stop_event (threading.Event): Event set on SIGINT to request skip/stop.
        callbacks (ExperimentCallbacks): Experiment control callbacks.
        completion_callback (callable): Function to call when experiment completes.
        live_plot (LivePlot): Live plot container (fig, axes, lines).
        show_final_plot_callback (callable): Function to show final plot from main thread.
        close_live_plot_callback (callable): Function to close live plot from main thread.
    """
    final_csv_path = None
    saved_data = None

    try:
        with prevent_sleep():  # Prevent system sleep during experiment
            csv_writer = CsvWriter(sample_id)
            csv_writer.start()

            try:
                # Joule heating phase
                start_time, h_data = run_djs_cc(
                    devices,
                    currents,
                    durations,
                    max_volt,
                    csv_writer,
                    live_plot,
                    stop_event,
                    callbacks,
                )

                # Shut down the power supply
                etm_set_onoff(devices.power_supply, on=False)

                # Cooldown phase
                h_data = cooldown(
                    devices,
                    h_data,
                    csv_writer,
                    live_plot,
                    start_time,
                    max((t for t in h_data["temperature"] if t == t), default=0.0),
                    stop_event,
                    callbacks,
                )
            finally:
                try:
                    final_csv_path = csv_writer.finalise()
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
        close_all(devices, skip_plot=True)

        # Notify GUI that experiment is complete
        if completion_callback:
            completion_callback()


# -------------------- Main Program --------------------


def main():
    """Entry point for the constant-current Joule heating experiment."""
    # Register SIGINT handler so Ctrl+C sets `stop_event` and requests skip/stop.
    with register_sigint_handler() as stop_event:
        print(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            "Starting the constant current Joule heating program. Please fill in the GUI."
        )

        # Initialise communication with IR temperature sensors and power supply
        try:
            devices = init_devices()
        except (PSUError, TemperatureSensorError) as e:
            # Device initialization failed - show error dialog
            messagebox.showerror(
                "Device Connection Error",
                f"Failed to initialise devices:\n\n{str(e)}\n\nPress OK to exit.",
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
        ) = gui_cc(devices.power_supply, devices.ycr_sensor, devices.optris_sensor)

        if output is None:
            close_all(devices)
            raise SystemExit("Program stopped.")

        # Position console window to the right of GUI immediately
        gui_window.update_idletasks()  # Ensure geometry is updated
        gui_x = gui_window.winfo_x()
        gui_width = gui_window.winfo_width()
        position_console_window(gui_x + gui_width + 10, 520, 800, 300)

        # Create GUI callback functions
        update_status, check_skip = create_gui_callbacks_cc(gui_window, status_vars, control_vars)

        # Flag to prevent multiple simultaneous runs
        experiment_started = [False]

        # Create experiment completion callback
        on_experiment_complete = create_experiment_complete_callback_cc(
            gui_window, status_vars, control_vars, experiment_started
        )

        def get_cc_experiment_args(exp_output, exp_devices, exp_callbacks, exp_live_plot):
            """Extract and organize arguments for CC experiment thread."""
            callbacks, cb_complete, cb_plot_final, cb_plot_close = exp_callbacks

            return (
                exp_devices,
                exp_output["sample"],
                exp_output["currents"],
                exp_output["durations"],
                exp_output["voltage"],
                stop_event,
                callbacks,
                cb_complete,
                exp_live_plot,
                cb_plot_final,
                cb_plot_close,
            )

        # Create start_experiment function using common factory
        start_experiment = create_experiment_starter(
            gui_window,
            control_vars,
            experiment_started,
            devices,
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
                try:
                    close_all(devices)
                finally:
                    gui_window.destroy()
            else:
                messagebox.showwarning("Warning", "Cannot close while experiment is running!")

        # Start monitoring for experiment trigger
        gui_window.after(100, check_experiment_start)

        # Set window close handler
        gui_window.protocol("WM_DELETE_WINDOW", on_close)

        # Bring GUI window to front and give it focus
        gui_window.lift()
        gui_window.focus_force()

        # Start GUI main loop
        gui_window.mainloop()


if __name__ == "__main__":
    main()
