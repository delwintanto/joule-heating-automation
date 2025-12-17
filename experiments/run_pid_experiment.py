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
    - run_djs_pid: Execute PID-controlled heating and cooldown (DJS = Direct Joule Synthesis)
    - run_experiment_thread: Orchestrate full experiment workflow

Author       : Delwin Tanto
Last updated : 16 Dec 2025
"""

import threading
import time
from collections import deque
from datetime import datetime
from tkinter import messagebox

import pandas as pd
from simple_pid import PID

import joule_heating.analysis.gradient_analysis as ga
from joule_heating.data import print_steps, print_summary, save_finalise, save_row, save_start
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
from joule_heating.plotting import live_plot_init
from joule_heating.utils import position_console_window, prevent_sleep
from joule_heating.utils.skip_step import register_sigint_handler, stop_event

# Constants
MAX_TEMP = 1200  # Max temperature limit (°C) for safety
MIN_TEMP = 50  # Min temp limit (°C) for colour mapping
LOOP_INTERVAL = 0.1  # Loop interval to prevent CPU overload (s)


# -------------------- Joule heating --------------------


def auto_tune_pid(
    sample_name,
    ycr_sensor,
    optris_sensor,
    power_supply,
    tuning_durr,
    i_set,
    v_set,
    lp_time,
    lp_temp,
    lp_curr,
    lp_res,
    status_callback=None,
    skip_check_callback=None,
    update_plot_callback=None,
):
    """Tune PID parameters using relay feedback (Ziegler–Nichols method).

    The function performs a relay-feedback test by switching the PSU current on
    and off and recording the resulting temperature oscillations. It analyses
    the recorded time series to estimate oscillation period and amplitude, then
    computes PID gains using Ziegler–Nichols formulas.

    Args:
        sample_name (str): Name of the sample.
        ycr_sensor (minimalmodbus.Instrument): YCR IR temperature sensor (for high temperatures).
        optris_sensor (serial.Serial): Optris IR sensor (for low temperatures).
        power_supply (minimalmodbus.Instrument): Power supply unit.
        tuning_durr (int): Tuning duration in seconds.
        i_set (float): Maximum current limit in amperes.
        v_set (float): Voltage setting in volts.
        lp_time, lp_temp, lp_curr, lp_res (list): Data buffers for live plot.
        status_callback (callable, optional): Function to update GUI status display.
        skip_check_callback (callable, optional): Function to check if skip requested.
        update_plot_callback (callable, optional): Function to update live plot.

    Returns:
        tuple: ``(kp, ki, kd, lp_time, lp_temp, lp_curr, lp_res, time_start)``
            where ``kp/ki/kd`` are computed PID gains (or None if tuning fails),
            and the other values are updated buffers and the observed start time.

    Note:
        If tuning is interrupted (via skip or SIGINT) or if oscillations cannot
        be detected, the function returns ``(None, None, None, ...)`` for the PID gains.
        Temperature safety checks stop tuning if temperature exceeds MAX_TEMP.
    """
    save_start(sample_name, tuning=True)  # Initialise save file

    print(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        f"Starting Relay Feedback Test for {tuning_durr} s. "
        "\033[1;31mDO NOT TOUCH!\033[0m!"
    )

    # Step 1: Apply an alternating current and records the temperature oscillations
    switch_interval = 5  # Seconds to switch between high and low current
    time_start = time.monotonic()

    etm_set_voltage(power_supply, voltage=v_set)
    etm_set_onoff(power_supply, on=True)

    while (elapsed := time.monotonic() - time_start) < tuning_durr:
        # Check for skip request
        if skip_check_callback and skip_check_callback():
            break

        # If SIGINT was received, skip auto-tuning early
        if stop_event.is_set():
            stop_event.clear()
            break

        # Alternate between high and low current
        i_read = i_set if int(elapsed / switch_interval) % 2 == 0 else 0
        etm_set_current(power_supply, current=i_read)
        t_read = read_temperature(ycr_sensor, optris_sensor)
        v_read = etm_read_voltage(power_supply)
        r_read = v_read / i_read if i_read != 0 else float("inf")

        if t_read > MAX_TEMP:
            print(
                "\033[1;31mTemperature exceeded safe limit! "
                "Stopping auto-tuning...\033[0m"
            )
            break

        # Update GUI status
        if status_callback:
            status_callback(
                phase="Auto-Tuning",
                temperature=f"{t_read:.1f}°C",
                setpoint="-",
                current=f"{i_read:.2f} A",
                voltage=f"{v_read:.2f} V",
                resistance=f"{r_read:.2f} Ω" if r_read != float(
                    "inf") else "∞ Ω",
                time_remaining=f"{max(0, int(tuning_durr - elapsed))} s remaining",
            )

        # Log data and updates the live plot
        lp_time.append(elapsed)
        lp_temp.append(t_read)
        lp_curr.append(i_read)
        lp_res.append(r_read)

        if update_plot_callback:
            update_plot_callback(
                time_data=list(lp_time),
                temp_data=list(lp_temp),
                curr_data=list(lp_curr),
                res_data=list(lp_res),
            )

        save_row(elapsed, t_read, i_read, v_read, r_read)
        time.sleep(LOOP_INTERVAL)  # Sleep to prevent CPU overload

    tuning_csv_path = save_finalise()
    print("Calculating PID gains...")
    etm_set_onoff(power_supply, on=False)

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
    return kp, ki, kd, lp_time, lp_temp, lp_curr, lp_res, time_start


def run_djs_pid(
    sample_name,
    kp,
    ki,
    kd,
    tuning_durr,
    ycr_sensor,
    optris_sensor,
    power_supply,
    temp_sp,
    durr_sp,
    i_set,
    v_set,
    cooldown_dur,
    tuning,
    status_callback=None,
    skip_check_callback=None,
    update_plot_callback=None,
):
    """Run the Joule heating experiment using a PID controller.

    The function sets up a PID controller with the provided gains or tunes
    them using ``auto_tune_pid`` when requested. It performs temperature
    control by adjusting the PSU current and records data for plotting and
    saving.

    Args:
        sample_name (str): Sample identifier.
        kp, ki, kd (float): PID gain parameters.
        tuning_durr (int): Tuning duration in seconds.
        ycr_sensor (Instrument): YCR IR temperature sensor (for high temperatures).
        optris_sensor (serial.Serial): Optris IR sensor (for low temperatures).
        power_supply (Instrument): Power supply unit.
        temp_sp (list): Temperature setpoints.
        durr_sp (list): Durations for each setpoint.
        i_set (float): Max current in A.
        v_set (float): Voltage in V.
        cooldown_dur (float): Duration of cooldown phase.
        tuning (str): Tuning method ("Auto tuning" or "Manual tuning").
        status_callback (callable, optional): Function to update GUI status display.
        skip_check_callback (callable, optional): Function to check if skip requested.
        update_plot_callback (callable, optional): Function to update live plot.

    Returns:
        tuple: The final PID gains ``(Kp, Ki, Kd)`` used by the experiment.
    """
    # Store cumulative time, temperature, and resistance data for the live plot
    lp_dataset = {
        key: deque(maxlen=500) for key in ["temperature", "time", "current", "resistance"]
    }

    # Initialize time_start (will be set by auto_tune_pid or manual timing)
    time_start = None

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
        ) = auto_tune_pid(
            sample_name,
            ycr_sensor,
            optris_sensor,
            power_supply,
            tuning_durr,
            i_set,
            v_set,
            lp_dataset["time"],
            lp_dataset["temperature"],
            lp_dataset["current"],
            lp_dataset["resistance"],
            status_callback,
            skip_check_callback,
            update_plot_callback,
        )

        if messagebox.askyesno(
            "Auto-Tuning Completed",
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            "PID gains tuning completed. "
            "Do you want to continue with the same sample?",
        ):
            messagebox.showinfo("Information", "Running experiment now.")
        else:
            etm_set_onoff(power_supply, on=False)
            messagebox.showinfo(
                "Information", "Please put in your new sample and press OK to continue."
            )

    print(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        "Starting experiment. \033[1;31mDO NOT TOUCH!\033[0m!"
    )

    # Initialise PID controller with manual or tuned gains
    pid = PID(Kp=kp, Ki=ki, Kd=kd)
    pid.output_limits = (0, i_set)  # Ensure output stays within the PSU range
    pid.sample_time = LOOP_INTERVAL  # Stable updates

    save_start(sample_name, tuning=False)

    etm_set_onoff(power_supply, on=True)
    etm_set_voltage(power_supply, voltage=v_set)

    # Set the starting time for the live plot (or use time from auto-tuning)
    if time_start is None:
        time_start = time.monotonic()
    skip_count = deque(maxlen=3)  # Count how many times user pressed CTRL + C
    total_steps = len(temp_sp)

    for idx, (setpoint, duration) in enumerate(zip(temp_sp, durr_sp), start=1):
        pid.setpoint = setpoint
        time_now = time.monotonic()
        end_time = time_now + duration

        while time_now <= end_time:
            # Check for skip request
            if skip_check_callback and skip_check_callback():
                print(
                    f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]"
                    f"Step {idx} skipped by user."
                )
                break

            # If SIGINT was received, request to skip this heating step.
            if stop_event.is_set():
                stop_event.clear()
                break

            t_read = read_temperature(ycr_sensor, optris_sensor)

            # Set current based on PID output
            curr = 0 if t_read >= MAX_TEMP else pid(t_read)
            etm_set_current(power_supply, current=curr)

            v_read = etm_read_voltage(power_supply)
            r_read = v_read / curr if curr != 0 else float("inf")

            elapsed = time_now - time_start
            save_row(elapsed, t_read, curr, v_read, r_read)

            # Append new data to the live plot dataset
            for k, v in zip(lp_dataset.keys(), [t_read, elapsed, curr, r_read]):
                lp_dataset[k].append(v)

            # Update GUI status
            if status_callback:
                status_callback(
                    phase=f" Heating - Step {idx}/{total_steps}",
                    temperature=f"{t_read:.1f}°C",
                    setpoint=f"{setpoint}°C",
                    current=f"{curr:.2f} A",
                    voltage=f"{v_read:.2f} V",
                    resistance=f"{r_read:.2f} Ω" if r_read != float(
                        "inf") else "∞ Ω",
                    time_remaining=f"{max(0, int(end_time - time_now))} s remaining",
                )

            if update_plot_callback:
                update_plot_callback(
                    time_data=list(lp_dataset["time"]),
                    temp_data=list(lp_dataset["temperature"]),
                    curr_data=list(lp_dataset["current"]),
                    res_data=list(lp_dataset["resistance"]),
                )

            time.sleep(LOOP_INTERVAL)  # Sleep to prevent CPU overload
            time_now = time.monotonic()

        if len(skip_count) == 3 and (skip_count[-1] - skip_count[0] <= 5):
            break  # Exit heating loop entirely if CTRL+C is pressed 3x within 5 s

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Heating completed!")

    etm_set_onoff(power_supply, on=False)

    if cooldown_dur > 0:
        print(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            f"Starting cooldown phase for {cooldown_dur} s..."
        )
        end_time_cooldown = time.monotonic() + cooldown_dur
        while time.monotonic() <= end_time_cooldown:
            # Check for skip request
            if skip_check_callback and skip_check_callback():
                break

            # If SIGINT was received, request to end cooldown early.
            if stop_event.is_set():
                stop_event.clear()
                break

            t_read = read_temperature(ycr_sensor, optris_sensor)
            i_read, v_read, r_read = 0, 0, float("inf")

            timestamp = time.monotonic()
            elapsed = timestamp - time_start
            save_row(elapsed, t_read, i_read, v_read, r_read)

            # Update the live plot
            for k, v in zip(lp_dataset.keys(), [t_read, elapsed, i_read, r_read]):
                lp_dataset[k].append(v)

            # Update GUI status
            if status_callback:
                status_callback(
                    phase="Cooldown",
                    temperature=f"{t_read:.1f}°C",
                    setpoint="-",
                    current=f"{i_read:.2f} A",
                    voltage=f"{v_read:.2f} V",
                    resistance="∞ Ω",
                    time_remaining=f"{max(0, int(end_time_cooldown - timestamp))} s remaining",
                )

            if update_plot_callback:
                update_plot_callback(
                    time_data=list(lp_dataset["time"]),
                    temp_data=list(lp_dataset["temperature"]),
                    curr_data=list(lp_dataset["current"]),
                    res_data=list(lp_dataset["resistance"]),
                )

            time.sleep(LOOP_INTERVAL)

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Cooldown completed!")
    return kp, ki, kd


def run_experiment_thread(
    power_supply,
    ycr_sensor,
    optris_sensor,
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
    started_flag,
    status_callback,
    skip_check_callback,
    on_experiment_complete_callback,
    fig,
    axes,
    lines,
    update_plot_callback,
    show_final_plot_callback,
    close_live_plot_callback,
):
    """Run PID experiment in background thread with GUI integration.

    This function orchestrates the entire PID experiment workflow by:
    1. Running auto-tuning (if selected) or manual PID experiment
    2. Handling experiment completion and GUI re-enabling
    3. Displaying final summary plots

    Args:
        power_supply (minimalmodbus.Instrument): PSU device instance.
        ycr_sensor (minimalmodbus.Instrument): YCR IR sensor instance.
        optris_sensor (serial.Serial): Optris IR sensor instance.
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
        started_flag (list): Single-element list acting as flag to prevent multiple runs.
        status_callback (callable): Function to update GUI status display.
        skip_check_callback (callable): Function to check if skip requested.
        on_experiment_complete_callback (callable): Function to call when experiment finishes.
        fig (matplotlib.figure.Figure): Live plot figure object.
        axes (tuple): Tuple of axes objects for live plot.
        lines (tuple): Tuple of line objects for live plot.
        update_plot_callback (callable): Function to update live plot in main thread.
        show_final_plot_callback (callable): Function to display final summary plot.
        close_live_plot_callback (callable): Function to close live plot window.
    """
    final_csv_path = None
    saved_data = None

    def update_plot(time_data, temp_data, curr_data, res_data):
        """Thread-safe callback to update live plot."""
        update_plot_callback(
            fig,
            axes,
            lines,
            data={
                "time": time_data,
                "temperature": temp_data,
                "current": curr_data,
                "resistance": res_data,
            },
        )

    try:
        with prevent_sleep():  # Prevent system sleep during experiment
            # Run the PID experiment
            final_kp, final_ki, final_kd = run_djs_pid(
                sample_name=sample_name,
                kp=kp,
                ki=ki,
                kd=kd,
                tuning_durr=tuning_time,
                ycr_sensor=ycr_sensor,
                optris_sensor=optris_sensor,
                power_supply=power_supply,
                temp_sp=temps,
                durr_sp=durs,
                i_set=current,
                v_set=voltage,
                cooldown_dur=cooldown,
                tuning=tuning_method,
                status_callback=status_callback,
                skip_check_callback=skip_check_callback,
                update_plot_callback=update_plot,
            )

            # Save and display final results
            try:
                final_csv_path = save_finalise()
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
        # Fail-safe: Always turn off devices (skip plot - already closed by callback)
        close_all(power_supply, ycr_sensor, optris_sensor, skip_plot=True)

        # Re-enable GUI after experiment completes
        if on_experiment_complete_callback:
            on_experiment_complete_callback()
        started_flag[0] = False


# -------------------- Main Program --------------------
if __name__ == "__main__":
    # Register SIGINT handler so Ctrl+C sets `stop_event` and requests skip/stop.
    with register_sigint_handler():
        print(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            "Starting the PID-controlled Joule heating program. Please fill in the GUI."
        )

        # Initialise communication with IR temperature sensors and power supply
        try:
            psu, ycr_temp_sensor, optris_temp_sensor = init_devices()
        except (PSUError, TemperatureSensorError) as e:
            # Device initialization failed - show error dialog
            messagebox.showerror(
                "Device Connection Error",
                f"Failed to initialise devices:\n\n{str(e)}.\n\n" "Press OK to exit.",
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
            tuning_mode,
            input_mode,
            field_widgets,
            common_fields,
            discrete_fields,
            continuous_fields,
            pid_vars,
        ) = gui_pid(psu, ycr_temp_sensor, optris_temp_sensor)

        if output is None:
            close_all(psu, ycr_temp_sensor, optris_temp_sensor)
            raise SystemExit("Program stopped.")

        # Position console window to the right of GUI immediately
        gui_window.update_idletasks()  # Ensure geometry is updated
        gui_x = gui_window.winfo_x()
        gui_width = gui_window.winfo_width()
        position_console_window(gui_x + gui_width + 10, 520, 800, 300)

        # Create GUI callback functions
        update_status, check_skip = create_gui_callbacks_pid(
            gui_window, status_vars, control_vars)

        # Flag to prevent multiple simultaneous runs
        experiment_started = [False]

        # Create experiment completion callback
        on_experiment_complete = create_experiment_complete_callback_pid(
            gui_window, status_vars, control_vars, experiment_started, field_widgets
        )

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

            # Get experiment parameters
            sample_name = output["sample"]
            temps = output["temps"]
            durs = output["durs"]
            current = output["current"]
            voltage = output["voltage"]
            cooldown = output["cooldown"]
            kp = output.get("kp", 0.5)
            ki = output.get("ki", 0.1)
            kd = output.get("kd", 0.1)
            tuning_time = output.get("tuning_time", 0)

            # Calculate position for live plot (to the right of GUI)
            gui_window.update_idletasks()  # Ensure geometry is updated
            # 10px gap, aligned to top
            plot_position = f"+{gui_window.winfo_width() + 10}+0"

            # Initialise live plot
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

            # Create plot callbacks with access to live plot context
            (
                update_plot,
                show_final_plot,
                close_live_plot,
            ) = create_plot_callbacks_pid(gui_window, plot_position)

            # Start experiment in background thread
            experiment_thread = threading.Thread(
                target=run_experiment_thread,
                args=(
                    psu,
                    ycr_temp_sensor,
                    optris_temp_sensor,
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
                    tuning_mode,
                    experiment_started,
                    update_status,
                    check_skip,
                    on_experiment_complete,
                    figure,
                    (ax_temp, ax_curr, ax_res),
                    (line_temp, line_curr, line_res),
                    update_plot,
                    show_final_plot,
                    close_live_plot,
                ),
                daemon=True,
            )
            experiment_thread.start()

        def check_experiment_start():
            """Check if experiment should start and launch it."""
            if (
                control_vars["experiment_running"].get()
                and output["sample"] is not None
                and not experiment_started[0]
            ):
                start_experiment()
            gui_window.after(100, check_experiment_start)

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
