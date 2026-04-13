"""PID-controlled Joule heating experiment automation with GUI.

This script automates PID-controlled Direct Joule Synthesis (DJS) experiments by
controlling a power supply unit (PSU) and IR temperature sensors. The PSU current is
adjusted via PID control to maintain target temperatures for user-specified durations.

Features:
    - Interactive GUI for parameter entry and experiment control
    - Real-time status display and live plotting during experiment
    - Background threading to keep GUI responsive
    - Skip functionality for individual heating steps
    - Auto-tuning via relay feedback (Ziegler-Nichols method)
    - Automatic data acquisition and CSV export
    - Final summary plot generation

Main Functions:
    - auto_tune_pid: Tune PID parameters using relay feedback
    - run_djs_pid: Execute PID-controlled heating and cooldown
    - run_experiment_thread: Orchestrate full experiment workflow

Author       : Delwin Tanto
Last updated : 09 Mar 2026
"""

import contextlib
import time
from collections import deque
from datetime import datetime
from tkinter import messagebox

import pandas as pd
from simple_pid import PID

import joule_heating.analysis.gradient_analysis as ga
from joule_heating.data import CsvWriter, print_steps, print_summary
from joule_heating.devices import (
    PSUError,
    TemperatureSensorError,
    close_all,
    etm_read_voltage,
    etm_set_current,
    etm_set_onoff,
    etm_set_voltage,
    init_devices,
    read_temperature,
)
from joule_heating.gui import (
    create_experiment_complete_callback_pid,
    create_gui_callbacks_pid,
    create_plot_callbacks_pid,
    gui_pid,
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
MAX_TEMP = 1200  # Max temperature limit (°C) for safety
MIN_TEMP = 50  # Min temp limit (°C) for colour mapping
LOOP_INTERVAL = 0.1  # Loop interval to prevent CPU overload (s)


# -------------------- Joule heating --------------------


def auto_tune_pid(
    sample_name,
    devices,
    tuning_durr,
    i_set,
    v_set,
    lp_time,
    lp_temp,
    lp_curr,
    lp_res,
    stop_event,
    callbacks=ExperimentCallbacks(),
):
    """Tune PID parameters using relay feedback (Ziegler–Nichols method).

    Args:
        sample_name (str): Name of the sample.
        devices (Devices): Device handles container.
        tuning_durr (int): Tuning duration in seconds.
        i_set (float): Maximum current limit in amperes.
        v_set (float): Voltage setting in volts.
        lp_time, lp_temp, lp_curr, lp_res (list): Data buffers for live plot.
        stop_event (threading.Event): Event set on SIGINT to request skip/stop.
        callbacks (ExperimentCallbacks): Experiment control callbacks.

    Returns:
        tuple: ``(kp, ki, kd, lp_time, lp_temp, lp_curr, lp_res, time_start, max_temperature,
            tuning_csv_path)`` where ``kp/ki/kd`` are computed PID gains (or None if tuning fails),
            the other values are updated buffers, the observed start time, max temperature,
            and tuning_csv_path is the path to the saved tuning CSV file with PID gains added.

    Note:
        If tuning is interrupted (via skip or SIGINT) or if oscillations cannot
        be detected, the function returns ``(None, None, None, ...)`` for the PID gains.
        Temperature safety checks stop tuning if temperature exceeds MAX_TEMP.
    """
    tuning_writer = CsvWriter(sample_name, tuning=True)
    tuning_writer.start()

    print(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        f"Starting Relay Feedback Test for {tuning_durr} s. "
        "\033[1;31mDO NOT TOUCH!\033[0m!"
    )

    # Step 1: Apply an alternating current and records the temperature oscillations
    switch_interval = 5  # Seconds to switch between high and low current
    time_start = time.monotonic()
    max_temperature = 0.0  # Track maximum temperature reached

    try:
        etm_set_voltage(devices.power_supply, voltage=v_set)
        etm_set_onoff(devices.power_supply, on=True)
    except Exception:
        tuning_writer.finalise()
        raise

    next_tick = time.monotonic()
    try:
        while (elapsed := time.monotonic() - time_start) < tuning_durr:
            next_tick += LOOP_INTERVAL
            # Check for skip request
            if callbacks.skip_check and callbacks.skip_check():
                break

            # If SIGINT was received, skip auto-tuning early
            if stop_event.is_set():
                stop_event.clear()
                break

            # Alternate between high and low current
            i_read = i_set if int(elapsed / switch_interval) % 2 == 0 else 0
            etm_set_current(devices.power_supply, current=i_read)
            t_read = read_temperature(devices.ycr_sensor, devices.optris_sensor)
            v_read = etm_read_voltage(devices.power_supply)
            r_read = v_read / i_read if i_read != 0 else float("inf")

            # Track maximum temperature (guard against NaN sensor readings)
            if t_read == t_read:  # NaN != NaN
                max_temperature = max(max_temperature, t_read)

            if t_read > MAX_TEMP:
                print("\033[1;31mTemperature exceeded safe limit! Stopping auto-tuning...\033[0m")
                break

            # Update GUI status
            if callbacks.status:
                callbacks.status(
                    phase="Auto-Tuning",
                    temperature=f"{t_read:.1f}°C",
                    max_temperature=f"{max_temperature:.1f}°C",
                    setpoint="-",
                    current=f"{i_read:.2f} A",
                    voltage=f"{v_read:.2f} V",
                    resistance=f"{r_read:.2f} Ω" if r_read != float("inf") else "∞ Ω",
                    time_remaining=f"{max(0, int(tuning_durr - elapsed))} s remaining",
                )

            # Log data and updates the live plot
            lp_time.append(elapsed)
            lp_temp.append(t_read)
            lp_curr.append(i_read)
            lp_res.append(r_read)

            if callbacks.update_plot:
                callbacks.update_plot(
                    time_data=list(lp_time),
                    temp_data=list(lp_temp),
                    curr_data=list(lp_curr),
                    res_data=list(lp_res),
                )

            tuning_writer.row(elapsed, t_read, i_read, v_read, r_read)
            time.sleep(max(0, next_tick - time.monotonic()))
    finally:
        with contextlib.suppress(PSUError):
            etm_set_onoff(devices.power_supply, on=False)
        tuning_csv_path = tuning_writer.finalise()
    print("Calculating PID gains...")

    # Step 2: Find the oscillation period (Tu) and ultimate gain (Ku)
    tuning_data = ga.detect_peaks_and_valleys(lp_time, lp_temp)
    period = ga.calculate_period(tuning_data["combined_maxima"], lp_time)
    amplitude = ga.calculate_amplitude(
        tuning_data["combined_maxima"], tuning_data["combined_minima"], lp_time, lp_temp
    )

    if amplitude and period:
        ku = (4 * i_set) / (3.141592653589793 * amplitude)

        # Step 3: Apply Ziegler-Nichols formulas to calculate Kp, Ki, and Kd
        kp = 0.6 * ku
        ki = 1.2 * ku / period
        kd = 0.075 * ku * period

        print(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            "Auto-tuning complete. "
            f"\033[33mPID Gains -> Kp: {kp:.3f}, Ki: {ki:.3f}, Kd: {kd:.3f}\n\033[0m"
            f"\nTuning data: {tuning_csv_path}"
        )

    else:
        kp, ki, kd = 0.5, 0.1, 0.1  # Default PID gains if no oscillations detected
        if messagebox.askyesno(
            "Auto-Tuning Failed",
            "Could not detect oscillations. Do you want to use default PID gains "
            f"(Kp: {kp}, Ki: {ki}, Kd: {kd})?",
        ):
            messagebox.showinfo("Information", "Running experiment now.")
        else:
            msg = (
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                "No PID gains entered. Program stopped."
            )
            messagebox.showerror("Auto-Tuning Failed", msg)
            raise SystemExit(msg)
    return (
        kp,
        ki,
        kd,
        lp_time,
        lp_temp,
        lp_curr,
        lp_res,
        time_start,
        max_temperature,
        tuning_csv_path,
    )


def run_djs_pid(
    sample_name,
    kp,
    ki,
    kd,
    tuning_durr,
    devices,
    temp_sp,
    durr_sp,
    i_set,
    v_set,
    cooldown_dur,
    tuning,
    stop_event,
    callbacks=ExperimentCallbacks(),
):
    """Run the Joule heating experiment using a PID controller.

    Args:
        sample_name (str): Sample identifier.
        kp, ki, kd (float): PID gain parameters.
        tuning_durr (int): Tuning duration in seconds.
        devices (Devices): Device handles container.
        temp_sp (list): Temperature setpoints.
        durr_sp (list): Durations for each setpoint.
        i_set (float): Max current in A.
        v_set (float): Voltage in V.
        cooldown_dur (float): Duration of cooldown phase.
        tuning (str): Tuning method ("Auto tuning" or "Manual tuning").
        stop_event (threading.Event): Event set on SIGINT to request skip/stop.
        callbacks (ExperimentCallbacks): Experiment control callbacks.

    Returns:
        tuple: ``(Kp, Ki, Kd, experiment_writer)`` where the first three are
            the final PID gains and ``experiment_writer`` is the :class:`CsvWriter`
            instance for the caller to finalise.
    """
    # Store cumulative time, temperature, and resistance data for the live plot
    lp_dataset = {
        key: deque(maxlen=500) for key in ["temperature", "time", "current", "resistance"]
    }

    # Initialize time_start (will be set by auto_tune_pid or manual timing)
    time_start = None
    max_temperature = 0.0  # Track maximum temperature reached

    # Run PID gains tuning
    if tuning == "Auto tuning":
        (
            kp,
            ki,
            kd,
            lp_dataset["time"],
            lp_dataset["temperature"],
            lp_dataset["current"],
            lp_dataset["resistance"],
            time_start,
            max_temperature,
            tuning_csv_path,
        ) = auto_tune_pid(
            sample_name,
            devices,
            tuning_durr,
            i_set,
            v_set,
            lp_dataset["time"],
            lp_dataset["temperature"],
            lp_dataset["current"],
            lp_dataset["resistance"],
            stop_event,
            callbacks,
        )

        # Add PID gains to the tuning CSV file as header comments
        try:
            with open(tuning_csv_path, encoding="utf-8-sig") as f:
                lines = f.readlines()
            with open(tuning_csv_path, "w", encoding="utf-8-sig") as f:
                f.write("PID Gains from Auto-Tuning,,,\n")
                f.write(f"Kp,{kp:.6f},,,\n")
                f.write(f"Ki,{ki:.6f},,,\n")
                f.write(f"Kd,{kd:.6f},,,\n")
                f.write(",,,\n")
                f.writelines(lines)
        except OSError as e:
            print(f"Warning: Could not add PID gains to tuning CSV: {e}")

        if messagebox.askyesno(
            "Auto-Tuning Completed",
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            "PID gains tuning completed. "
            "Do you want to continue with the same sample?",
        ):
            messagebox.showinfo("Information", "Running experiment now.")
        else:
            etm_set_onoff(devices.power_supply, on=False)
            messagebox.showinfo(
                "Information", "Please put in your new sample and press OK to continue."
            )
            max_temperature = 0.0  # Reset max temperature for heating phase

    print(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        "Starting experiment. \033[1;31mDO NOT TOUCH!\033[0m!"
    )

    # Initialise PID controller with manual or tuned gains
    pid = PID(Kp=kp, Ki=ki, Kd=kd)
    pid.output_limits = (0, i_set)  # Ensure output stays within the PSU range
    pid.sample_time = LOOP_INTERVAL  # Stable updates

    experiment_writer = CsvWriter(sample_name, tuning=False)
    experiment_writer.start()

    etm_set_onoff(devices.power_supply, on=True)
    etm_set_voltage(devices.power_supply, voltage=v_set)

    # Set the starting time for the live plot (or use time from auto-tuning)
    if time_start is None:
        time_start = time.monotonic()
        max_temperature = 0.0  # Reset max_temperature for fresh experiment if no auto-tuning
    total_steps = len(temp_sp)

    for idx, (setpoint, duration) in enumerate(zip(temp_sp, durr_sp, strict=True), start=1):
        print(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            f"Starting heating step {idx}/{total_steps}."
        )
        alert_step_start()  # Play alert sound
        pid.setpoint = setpoint
        time_now = time.monotonic()
        end_time = time_now + duration
        next_tick = time_now

        while time_now <= end_time:
            next_tick += LOOP_INTERVAL
            # Check for skip request
            if callbacks.skip_check and callbacks.skip_check():
                print(
                    f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Step {idx} skipped by user."
                )
                break

            # If SIGINT was received, request to skip this heating step.
            if stop_event.is_set():
                stop_event.clear()
                break

            t_read = read_temperature(devices.ycr_sensor, devices.optris_sensor)

            # Track maximum temperature (guard against NaN sensor readings)
            if t_read == t_read:  # NaN != NaN
                max_temperature = max(max_temperature, t_read)

            # Set current based on PID output
            curr = 0 if t_read >= MAX_TEMP else pid(t_read)
            etm_set_current(devices.power_supply, current=curr)

            v_read = etm_read_voltage(devices.power_supply)
            r_read = v_read / curr if curr != 0 else float("inf")

            elapsed = time_now - time_start
            experiment_writer.row(elapsed, t_read, curr, v_read, r_read)

            # Append new data to the live plot dataset
            for k, v in zip(lp_dataset.keys(), [t_read, elapsed, curr, r_read], strict=True):
                lp_dataset[k].append(v)

            # Update GUI status
            if callbacks.status:
                callbacks.status(
                    phase=f"Heating - Step {idx}/{total_steps}",
                    temperature=f"{t_read:.1f} °C",
                    max_temperature=f"{max_temperature:.1f} °C",
                    setpoint=f"{setpoint}°C",
                    current=f"{curr:.2f} A",
                    voltage=f"{v_read:.2f} V",
                    resistance=f"{r_read:.2f} Ω" if r_read != float("inf") else "∞ Ω",
                    time_remaining=f"{max(0, int(end_time - time_now))} s remaining",
                )

            if callbacks.update_plot:
                callbacks.update_plot(
                    time_data=list(lp_dataset["time"]),
                    temp_data=list(lp_dataset["temperature"]),
                    curr_data=list(lp_dataset["current"]),
                    res_data=list(lp_dataset["resistance"]),
                )

            time.sleep(max(0, next_tick - time.monotonic()))
            time_now = time.monotonic()

        # Full stop requested - exit all remaining heating steps
        if callbacks.skip_check and callbacks.skip_check():
            break

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Heating completed!")

    etm_set_onoff(devices.power_supply, on=False)

    if cooldown_dur > 0:
        print(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            f"Starting cooldown phase for {cooldown_dur} s..."
        )
        alert_step_start()  # Play alert sound
        end_time_cooldown = time.monotonic() + cooldown_dur
        next_tick = time.monotonic()
        while time.monotonic() <= end_time_cooldown:
            next_tick += LOOP_INTERVAL
            # Check for skip request
            if callbacks.skip_check and callbacks.skip_check():
                break

            # If SIGINT was received, request to end cooldown early.
            if stop_event.is_set():
                stop_event.clear()
                break

            t_read = read_temperature(devices.ycr_sensor, devices.optris_sensor)
            i_read, v_read, r_read = 0, 0, float("inf")

            timestamp = time.monotonic()
            elapsed = timestamp - time_start
            experiment_writer.row(elapsed, t_read, i_read, v_read, r_read)

            # Update the live plot
            for k, v in zip(lp_dataset.keys(), [t_read, elapsed, i_read, r_read], strict=True):
                lp_dataset[k].append(v)

            # Update GUI status
            if callbacks.status:
                callbacks.status(
                    phase="Cooldown",
                    temperature=f"{t_read:.1f} °C",
                    max_temperature=f"{max_temperature:.1f} °C",
                    setpoint="-",
                    current=f"{i_read:.2f} A",
                    voltage=f"{v_read:.2f} V",
                    resistance="∞ Ω",
                    time_remaining=f"{max(0, int(end_time_cooldown - timestamp))} s remaining",
                )

            if callbacks.update_plot:
                callbacks.update_plot(
                    time_data=list(lp_dataset["time"]),
                    temp_data=list(lp_dataset["temperature"]),
                    curr_data=list(lp_dataset["current"]),
                    res_data=list(lp_dataset["resistance"]),
                )

            time.sleep(max(0, next_tick - time.monotonic()))

        alert_cooldown_end()  # Play alert sound
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Cooldown completed!")
    return kp, ki, kd, experiment_writer


def run_experiment_thread(
    devices,
    sample_name,
    temps,
    durs,
    current,
    voltage,
    cooldown,
    kp,
    ki,
    kd,
    tuning_time,
    tuning_method,
    stop_event,
    callbacks,
    on_experiment_complete_callback,
    live_plot,
    show_final_plot_callback,
    close_live_plot_callback,
):
    """Run PID experiment in background thread with GUI integration.

    Args:
        devices (Devices): Device handles container.
        sample_name (str): Sample identifier.
        temps (list): Temperature setpoints.
        durs (list): Durations for each setpoint.
        current (float): Max current in A.
        voltage (float): Voltage in V.
        cooldown (float): Cooldown duration.
        kp (float): PID proportional gain.
        ki (float): PID integral gain.
        kd (float): PID derivative gain.
        tuning_time (int): Auto-tuning duration.
        tuning_method (str): "Auto tuning" or "Manual tuning".
        stop_event (threading.Event): Event set on SIGINT to request skip/stop.
        callbacks (ExperimentCallbacks): Experiment control callbacks.
        on_experiment_complete_callback (callable): Function to call when experiment finishes.
        live_plot (LivePlot): Live plot container (fig, axes, lines).
        show_final_plot_callback (callable): Function to display final summary plot.
        close_live_plot_callback (callable): Function to close live plot window.
    """
    final_csv_path = None
    saved_data = None

    experiment_writer = None

    def update_plot(time_data, temp_data, curr_data, res_data):
        """Thread-safe callback to update live plot."""
        callbacks.update_plot(
            live_plot,
            data={
                "time": time_data,
                "temperature": temp_data,
                "current": curr_data,
                "resistance": res_data,
            },
        )

    inner_callbacks = callbacks._replace(update_plot=update_plot)

    try:
        with prevent_sleep():  # Prevent system sleep during experiment
            # Run the PID experiment
            final_kp, final_ki, final_kd, experiment_writer = run_djs_pid(
                sample_name=sample_name,
                kp=kp,
                ki=ki,
                kd=kd,
                tuning_durr=tuning_time,
                devices=devices,
                temp_sp=temps,
                durr_sp=durs,
                i_set=current,
                v_set=voltage,
                cooldown_dur=cooldown,
                tuning=tuning_method,
                stop_event=stop_event,
                callbacks=inner_callbacks,
            )

            # Save and display final results
            try:
                final_csv_path = experiment_writer.finalise()
            except OSError as e:
                print(f"Error saving final data: {e}")
                final_csv_path = None

            # Close live plot first (before final plot)
            if close_live_plot_callback:
                close_live_plot_callback()

            if final_csv_path and final_csv_path != "None":
                saved_data = pd.read_csv(final_csv_path)

                # Print some information about the experiment
                print_summary(
                    sample_name,
                    saved_data,
                    final_csv_path,
                    pid_curr=current,
                    pid_volt=voltage,
                    pid_gains=(final_kp, final_ki, final_kd),
                )
                print_steps(temps, durs, cc=False)

                # Show final summary plot (blocks until user closes it)
                if show_final_plot_callback:
                    show_final_plot_callback(saved_data, sample_name)
    finally:
        # Ensure experiment CSV is finalized even if run_djs_pid raised mid-flight
        if experiment_writer is not None:
            experiment_writer.finalise()  # no-op if already finalised normally

        # Fail-safe: Always turn off devices (skip plot - already closed by callback)
        close_all(devices, skip_plot=True)

        # Re-enable GUI after experiment completes
        if on_experiment_complete_callback:
            on_experiment_complete_callback()


# -------------------- Main Program --------------------


def main():
    """Entry point for the PID-controlled Joule heating experiment."""
    # Register SIGINT handler so Ctrl+C sets `stop_event` and requests skip/stop.
    with register_sigint_handler() as stop_event:
        print(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            "Starting the PID-controlled Joule heating program. Please fill in the GUI."
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
        gui_window, output, status_vars, control_vars, field_widgets = gui_pid(
            devices.power_supply, devices.ycr_sensor, devices.optris_sensor
        )

        if output is None:
            close_all(devices)
            raise SystemExit("Program stopped.")

        # Position console window to the right of GUI immediately
        gui_window.update_idletasks()  # Ensure geometry is updated
        gui_x = gui_window.winfo_x()
        gui_width = gui_window.winfo_width()
        position_console_window(gui_x + gui_width + 10, 520, 800, 300)

        # Create GUI callback functions
        update_status, check_skip = create_gui_callbacks_pid(gui_window, status_vars, control_vars)

        # Flag to prevent multiple simultaneous runs
        experiment_started = [False]

        # Create experiment completion callback
        on_experiment_complete = create_experiment_complete_callback_pid(
            gui_window, status_vars, control_vars, experiment_started, field_widgets
        )

        def get_pid_experiment_args(exp_output, exp_devices, exp_callbacks, exp_live_plot):
            """Extract and organize arguments for PID experiment thread."""
            callbacks, cb_complete, cb_plot_final, cb_plot_close = exp_callbacks

            return (
                exp_devices,
                exp_output["sample"],
                exp_output["temps"],
                exp_output["durs"],
                exp_output["current"],
                exp_output["voltage"],
                exp_output["cooldown"],
                exp_output.get("kp", 0.5),
                exp_output.get("ki", 0.1),
                exp_output.get("kd", 0.1),
                exp_output.get("tuning_time", 0),
                exp_output.get("tuning_method", "Manual tuning"),
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
            create_plot_callbacks_pid,
            run_experiment_thread,
            get_pid_experiment_args,
        )

        # Create experiment monitor using common factory
        check_experiment_start = create_experiment_monitor(
            gui_window, control_vars, output, start_experiment, experiment_started
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
