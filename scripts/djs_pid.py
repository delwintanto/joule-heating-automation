"""
This script controls the temperature of a Joule heating sample through PID control.
It initialises communication with IR temp sensor and PSU, tunes the PID gains, runs
the experiment, and saves the data to a .csv file. It also displays a live plot of
temperature, current, and resistance during the experiment.

Author       : Delwin Tanto
Last updated : 04 Nov 2025
"""

import os
import time
from collections import deque
from datetime import datetime
from tkinter import messagebox

import pandas as pd
from simple_pid import PID

from colour_map import temp_colour
import gradient_analysis as ga
from device_utils import close_all, init_devices, enable_lasers
from gui import gui_pid
from plot import plot_data, live_plot_init, update_live_plot
from power_supply_etm import (
    etm_set_onoff,
    etm_set_current,
    etm_set_voltage,
    etm_read_voltage,
)
from print_summary import print_summary, print_steps
from save_data import save_start, save_row, save_finalise
from signal_utils import register_sigint_handler, stop_event
from system_sleep import prevent_sleep
from temp_sensor_utils import read_temperature


# Constants
MAX_TEMP = 1200  # Max temperature limit (°C) for safety
MIN_TEMP = 30  # Min temp limit (°C) for colour mapping
LOOP_INTERVAL = 0.1  # Loop interval to prevent CPU overload (s)
# YCR sensor minimum operating range (°C); use Optris below this
YCR_MIN_RANGE = 300


# -------------------- Joule heating --------------------

def auto_tune_pid(
    sample_name,
    ycr_sensor,
    optris_sensor,
    power_supply,
    tuning_durr,
    i_set,
    v_set,
    fig,
    ax_temp,
    ax_curr,
    ax_res,
    line_temp,
    line_curr,
    line_res,
    lp_time,
    lp_temp,
    lp_curr,
    lp_res,
):
    """Tune PID parameters using relay feedback (Ziegler–Nichols method).

    The function performs a relay-feedback test by switching the PSU current on
    and off and recording the resulting temperature oscillations. It analyses
    the recorded time series to estimate oscillation period and amplitude, then
    computes PID gains using Ziegler–Nichols formulas.

    Args:
        sample_name (str): Name of the sample.
        ycr_sensor (Instrument): YCR IR temperature sensor (for high temperatures).
        optris_sensor (serial.Serial): Optris IR sensor (for low temperatures).
        power_supply (Instrument): Power supply unit.
        tuning_durr (int): Tuning duration in seconds.
        i_set (float): Maximum current limit.
        v_set (float): Voltage setting.
        fig, ax_temp, ax_curr, ax_res: Matplotlib figure and axes.
        line_temp, line_curr, line_res: Plot lines for live plot.
        lp_time, lp_temp, lp_curr, lp_res: Data buffers for live plot.

    Returns:
        tuple: ``(kp, ki, kd, lp_time, lp_temp, lp_curr, lp_res, time_start)``
            where ``kp/ki/kd`` are computed PID gains and the other values are
            updated buffers and the observed start time of the tuning.
    """
    save_start(sample_name, tuning=True)  # Initialise save file

    print(f"\nStarting Relay Feedback Test for {tuning_durr} s...")

    # Step 1: Apply an alternating current and records the temperature oscillations
    switch_interval = 5  # Seconds to switch between high and low current
    time_start = time.monotonic()

    etm_set_voltage(power_supply, voltage=v_set)
    etm_set_onoff(power_supply, on=True)

    while (elapsed := time.monotonic() - time_start) < tuning_durr:
        try:
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

            print(
                f"\r\033[34mI: {i_read:>5.2f} A\033[0m | "
                f"{temp_colour(t_read, MIN_TEMP, MAX_TEMP)}T: {t_read:>6.1f}°C\033[0m | "
                f"\033[33mt elapsed: {elapsed:>3.0f} s\033[0m | "
                "\033[2mCtrl+C to skip\033[0m".ljust(20),
                end="",
                flush=True,
            )

            # Log data and updates the live plot
            lp_time.append(elapsed)
            lp_temp.append(t_read)
            lp_curr.append(i_read)
            lp_res.append(r_read)
            update_live_plot(
                fig,
                (ax_temp, ax_curr, ax_res),
                (line_temp, line_curr, line_res),
                x=lp_time,
                y1=lp_temp,
                y2=lp_curr,
                y3=lp_res,
            )
            save_row(elapsed, t_read, i_read, v_read, r_read)
            time.sleep(LOOP_INTERVAL)  # Sleep to prevent CPU overload
        except KeyboardInterrupt:
            stop_event.set()

    tuning_csv_path = save_finalise()
    print(f"\nTuning data: {tuning_csv_path}")
    print("\nShutting down the power supply while PID gains calculation is running...")
    etm_set_onoff(power_supply, on=False)

    # Step 2: Find the oscillation period (Tu) and ultimate gain (Ku)
    tuning_data = ga.detect_peaks_and_valleys(lp_time, lp_temp)
    period = ga.calculate_period(tuning_data["combined_maxima"], lp_time)
    amplitude = ga.calculate_amplitude(
        tuning_data["combined_maxima"],
        tuning_data["combined_minima"],
        lp_time,
        lp_temp
    )

    # Plot the peaks and valleys on the live plot
    ax_temp.plot(
        [lp_time[p] for p in tuning_data["combined_maxima"]],
        [lp_temp[p] for p in tuning_data["combined_maxima"]],
        "ro"
    )
    ax_temp.plot(
        [lp_time[v] for v in tuning_data["combined_minima"]],
        [lp_temp[v] for v in tuning_data["combined_minima"]],
        "gx"
    )
    fig.canvas.draw()
    fig.canvas.flush_events()

    if amplitude and period:
        ku = (4 * i_set) / (3.141592653589793 * amplitude)

        # Step 3: Apply Ziegler-Nichols formulas to calculate Kp, Ki, and Kd
        kp = 0.6 * ku
        ki = 1.2 * ku / period
        kd = 0.075 * ku * period

        print("\033[1;32mAuto-tuning complete!\033[0m")

    else:
        kp, ki, kd = 0.5, 0.1, 0.1  # Default PID gains if no oscillations detected
        if messagebox.askyesno(
            "Auto-Tuning Failed",
            "Could not detect oscillations. Do you want to use default PID gains "
            f"(Kp: {kp}, Ki: {ki}, Kd: {kd})?"
        ):
            messagebox.showinfo(
                "Information",
                "Running experiment now."
            )
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

    Returns:
        tuple: The final PID gains ``(Kp, Ki, Kd)`` used by the experiment.
    """
    # Store cumulative time, temperature, and resistance data for the live plot
    lp_dataset = {
        key: deque(maxlen=500)
        for key in ["temperature", "time", "current", "resistance"]
    }

    (
        fig,
        ax_temp,
        ax_curr,
        ax_res,
        line_temp,
        line_curr,
        line_res,
    ) = live_plot_init(sample_name)

    # Turn on both sensor lasers
    enable_lasers(ycr_sensor, optris_sensor, on=True)

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
            fig,
            ax_temp,
            ax_curr,
            ax_res,
            line_temp,
            line_curr,
            line_res,
            lp_dataset["time"],
            lp_dataset["temperature"],
            lp_dataset["current"],
            lp_dataset["resistance"],
        )

        if messagebox.askyesno(
            "Auto-Tuning Completed",
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            "PID gains tuning completed. "
            "Do you want to continue with the same sample?"
        ):
            messagebox.showinfo("Information", "Running experiment now.")
        else:
            etm_set_onoff(power_supply, on=False)
            messagebox.showinfo(
                "Information",
                "Please put in your new sample and press OK to continue."
            )

    print(
        f"\033[33mPID Gains -> Kp: {kp:.3f}, Ki: {ki:.3f}, Kd: {kd:.3f}\n\033[0m")

    # Initialise PID controller with manual or tuned gains
    pid = PID(Kp=kp, Ki=ki, Kd=kd)
    pid.output_limits = (0, i_set)  # Ensure output stays within the PSU range
    pid.sample_time = LOOP_INTERVAL  # Stable updates

    save_start(sample_name, tuning=False)

    etm_set_onoff(power_supply, on=True)
    etm_set_voltage(power_supply, voltage=v_set)

    # Set the starting time for the live plot
    time_start = time.monotonic() if tuning == "Manual tuning" else time_start
    skip_count = deque(maxlen=3)  # Count how many times user pressed CTRL + C
    total_steps = len(temp_sp)

    for idx, (setpoint, duration) in enumerate(zip(temp_sp, durr_sp), start=1):
        pid.setpoint = setpoint
        time_now = time.monotonic()
        end_time = time_now + duration

        while time_now <= end_time:
            try:
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

                update_live_plot(
                    fig,
                    (ax_temp, ax_curr, ax_res),
                    (line_temp, line_curr, line_res),
                    data={
                        "time": lp_dataset["time"],
                        "temperature": lp_dataset["temperature"],
                        "current": lp_dataset["current"],
                        "resistance": lp_dataset["resistance"],
                    },
                )
                print(
                    f"\r\033[1mStep {idx}/{total_steps} - "
                    f"SP: {setpoint:>5}°C/{duration:>5} s\033[0m | "
                    f"\033[34mI: {curr:>5.2f} A\033[0m | "
                    f"{temp_colour(t_read, MIN_TEMP, MAX_TEMP)}T: {t_read:>6.1f}°C\033[0m | "
                    f"t: {max(0, int(end_time - time_now)):>3} s | "
                    "\033[2mCtrl+C to skip\033[0m".ljust(20),
                    end="",
                    flush=True,
                )
                time.sleep(LOOP_INTERVAL)  # Sleep to prevent CPU overload
                time_now = time.monotonic()

            except KeyboardInterrupt:
                # Keep consistent: set the stop flag so other loops see it
                stop_event.set()
                skip_count.append(time.monotonic())

        if len(skip_count) == 3 and (skip_count[-1] - skip_count[0] <= 5):
            break  # Exit heating loop entirely if CTRL+C is pressed 3x within 5 s

    print(
        f"\n\033[1;32m[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        "Heating completed!\033[0m"
    )

    etm_set_onoff(power_supply, on=False)

    if cooldown_dur > 0:
        print(f"\nStarting cooldown phase for {cooldown_dur} s...")
        end_time_cooldown = time.monotonic() + cooldown_dur
        while time.monotonic() <= end_time_cooldown:
            try:
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

                update_live_plot(
                    fig,
                    (ax_temp, ax_curr, ax_res),
                    (line_temp, line_curr, line_res),
                    data={
                        "time": lp_dataset["time"],
                        "temperature": lp_dataset["temperature"],
                        "current": lp_dataset["current"],
                        "resistance": lp_dataset["resistance"],
                    },
                )
                print(
                    "\r\033[1;34mCooldown\033[0m - "
                    f"\r\033[34mI: {i_read:>5.2f} A\033[0m | "
                    f"{temp_colour(t_read, MIN_TEMP, MAX_TEMP)}T: {t_read:>6.1f}°C\033[0m | "
                    f"t: {max(0, int(end_time_cooldown - timestamp)):>3} s | "
                    "\033[2mCtrl+C to end\033[0m".ljust(20),
                    end="",
                    flush=True,
                )
            except KeyboardInterrupt:
                stop_event.set()

        print(
            f"\n\033[1;32m[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            "Cooldown completed!\033[0m"
        )
    return kp, ki, kd


if __name__ == "__main__":
    # Register SIGINT handler so Ctrl+C sets `stop_event` and requests skip/stop.
    with register_sigint_handler():
        os.system("cls" if os.name == "nt" else "clear")
        print(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            "Starting the PID controlled Joule heating program...\n"
        )

        with prevent_sleep():  # Prevent system sleep during experiment
            (
                sample_id,
                sp_temp,
                heating_times,
                max_current,
                max_voltage,
                cooldown_duration,
                kp_gain,
                ki_gain,
                kd_gain,
                tuning_dur,
                tuning_method,
            ) = gui_pid()  # Get user inputs from GUI

            if sample_id is None:
                raise SystemExit("Program stopped.")

            # Initialise temperature sensors and power supply
            psu, ycr_temp_sensor, optris_temp_sensor = init_devices()

            try:
                # Run the experiment
                kp_gain, ki_gain, kd_gain = run_djs_pid(
                    sample_id,
                    kp_gain,
                    ki_gain,
                    kd_gain,
                    tuning_dur,
                    ycr_temp_sensor,
                    optris_temp_sensor,
                    psu,
                    sp_temp,
                    heating_times,
                    max_current,
                    max_voltage,
                    cooldown_duration,
                    tuning_method,
                )
            finally:
                try:
                    final_csv_path = save_finalise()  # Finalise and save data
                except OSError as e:
                    print(f"Error saving final data: {e}")

                close_all(psu, ycr_temp_sensor, optris_temp_sensor)

                if final_csv_path:
                    saved_data = pd.read_csv(final_csv_path)
                    print_summary(
                        sample_id,
                        saved_data,
                        final_csv_path,
                        pid_curr=max_current,
                        pid_volt=max_voltage,
                        pid_gains=(kp_gain, ki_gain, kd_gain),
                    )
                    print_steps(sp_temp, heating_times, cc=False)

                    plot_data(
                        saved_data,
                        columns=[
                            "Temperature (°C)", "Current (A)", "Resistance (Ω)"],
                        sample_name=sample_id,
                    )
