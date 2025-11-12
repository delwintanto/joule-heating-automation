"""
This script automates Joule Heating experiment by controlling PSU and IR temperature sensor.

The script sets the PSU to supply a constant current to the Joule Heating setup for a user-set
amount of time, depending on the type of material and the degree of sintering the user is
looking to achieve.

The script subsequently acquires the time, temperature, current, voltage, and resistance data and
saves them to a .csv file.

Author       : Delwin Tanto
Last updated : 04 Nov 2025
"""

from datetime import datetime
import os
import time

import pandas as pd

from colour_map import temp_colour
from gui import gui_cc
from plot import plot_data, live_plot_init, live_plot_updt, close_plot
from power_supply_etm import (
    etm_open,
    etm_set_onoff,
    etm_set_current, etm_set_voltage,
    etm_read_current, etm_read_voltage,
    PSUError,
)
from print_summary import print_summary, print_steps
from save_data import save_start, save_row, save_finalise
from temp_sensor_ycr import ycr_open, ycr_set_laser, ycr_read_temp


# Constants
MAX_TEMP = 1200  # Max temp limit (°C) for safety
MIN_TEMP = 50  # Min temp limit (°C) for stopping cooldown
COOLDOWN_BUFFER = 10  # Extra seconds to wait after T drops below MIN_TEMP


# -------------------- Helper functions --------------------

def _read_data(power_supply, temp_sensor):
    """
    Read temperature, voltage, current, and calculate resistance.

    Args:
        power_supply (minimalmodbus.Instrument): PSU device instance.
        temp_sensor (minimalmodbus.Instrument): IR sensor device instance.

    Returns:
        tuple: (temperature, voltage, current, resistance)
    """
    t_read = ycr_read_temp(temp_sensor)
    v_read = etm_read_voltage(power_supply)
    i_read = etm_read_current(power_supply)
    r_read = v_read / i_read if i_read != 0 else float("inf")
    return t_read, v_read, i_read, r_read


def _append_data(data, time_start, time_now, t_read, v_read, i_read, r_read):
    """
    Append the latest readings to the data dictionary.
    
    Args:
        data (dict): Data dictionary to append to.
        time_start (float): Start time of the experiment.
        time_now (float): Current time.
        t_read (float): Temperature reading.
        v_read (float): Voltage reading.
        i_read (float): Current reading.
        r_read (float): Resistance reading.
    """
    # data dict (CSV source)
    data["time"].append(time_now - time_start)
    data["temperature"].append(t_read)
    data["voltage"].append(v_read)
    data["current"].append(i_read)
    data["resistance"].append(r_read)


# -------------------- Joule heating --------------------

def joule_heating_run(
    power_supply,
    temp_sensor,
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
):
    """
    Execute the main Joule Heating experiment loop.

    Apply sequential current settings, read live data, and update plot.

    Args:
        power_supply: PSU device.
        temp_sensor: IR temperature sensor.
        currs (list): List of current values (amps).
        durrs (list): List of durations (seconds).
        v_set (float): Voltage limit (volts).
        fig, ax1, ax2, ax3: Matplotlib figure and axes.
        line1, line2, line3: Line objects for plots.

    Returns:
        tuple: (time_start, data dictionary)
    """
    # Initialise empty data lists where measurements will be stored in
    data = {k: [] for k in ["temperature", "time", "voltage", "current", "resistance"]}

    ycr_set_laser(temp_sensor, on=True)  # Turn ON the IR sensor laser pointer

    time_start = None  # Start time of the experiment
    total_steps = len(currs)

    for idx, (i_set, durr) in enumerate(zip(currs, durrs), start=1):
        end_time = time.monotonic() + durr

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

                if time_start is None:
                    time_start = time_now  # Record the start time of the experiment

                t_read, v_read, i_read, r_read = _read_data(power_supply, temp_sensor)
                _append_data(data, time_start, time_now, t_read, v_read, i_read, r_read)
                save_row(time_now - time_start, t_read, i_read, v_read, r_read)

                if t_read >= MAX_TEMP:
                    etm_set_onoff(power_supply, on=False)  # PSU OFF if temperature exceeds limit

                # Update live plot with new data during each iteration
                live_plot_updt(
                    fig, ax1, ax2, ax3, line1, line2, line3,
                    data["time"], data["temperature"], data["current"], data["resistance"],
                )

                print(
                    f"\r\033[1mStep {idx}/{total_steps}\033[0m - "
                    f"\033[38;2;0;176;240mI: {i_read:>3} A\033[0m | "
                    f"{temp_colour(t_read, MIN_TEMP, MAX_TEMP)}"
                    f"T: {t_read:>5.1f}°C\033[0m | "
                    f"\033[38;2;255;192;0mR: {r_read:>5.2f} Ω\033[0m | "
                    f"t: {max(0, int(end_time - time_now)):>3} s | "
                    "\033[2mCtrl+C to skip\033[0m".ljust(20),
                    end="",
                    flush=True,
                )
                time.sleep(0.1)  # Sleep to prevent CPU overload
            except KeyboardInterrupt:
                break

        # Update plot even after breaking out of the inner loop
        live_plot_updt(
            fig, ax1, ax2, ax3, line1, line2, line3,
            data["time"], data["temperature"], data["current"], data["resistance"],
        )
    return time_start, data


def cooldown(
    power_supply,
    temp_sensor,
    data,
    fig,
    ax1,
    ax2,
    ax3,
    line1,
    line2,
    line3,
    time_start,
):
    """
    Record cooling data after the experiment.

    Automatically stop if temperature remains below threshold or time expires.

    Args:
        power_supply: PSU device.
        temp_sensor: IR sensor.
        data (dict): Data dictionary to append cooldown values.
        fig, ax1, ax2, ax3, line1, line2, line3: Matplotlib plotting objects.
        time_start (float): Start time of the experiment.

    Returns:
        tuple: Updated (data dictionary)
    """
    threshold_detected_time = None
    cool_start = time.monotonic()
    print(
        f"\n\033[1;32m[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        "Heating completed!\033[0m"
        f"\n\nStarting cooldown until {COOLDOWN_BUFFER} s "
        "after T drops below threshold..."
    )

    while True:
        try:
            time_now = time.monotonic()
            t_read, v_read, i_read, r_read = _read_data(power_supply, temp_sensor)
            _append_data(data, time_start, time_now, t_read, v_read, i_read, r_read)
            save_row(time_now - time_start, t_read, i_read, v_read, r_read)

            live_plot_updt(
                fig, ax1, ax2, ax3, line1, line2, line3,
                data["time"], data["temperature"], data["current"], data["resistance"],
            )

            print(
                "\r\033[1;34mCooldown\033[0m - "
                f"{temp_colour(t_read, MIN_TEMP, MAX_TEMP)}"
                f"T: {t_read:>5.1f}°C\033[0m | "
                f"t elapsed: {time_now - cool_start:>3.0f} s | "
                "\033[2mCtrl+C to end\033[0m".ljust(20),
                end="",
                flush=True,
            )

            temp_low = pd.isna(t_read) or t_read < MIN_TEMP

            if temp_low:
                if threshold_detected_time is None:
                    threshold_detected_time = time_now
                elif time_now - threshold_detected_time > COOLDOWN_BUFFER:
                    break
            elif threshold_detected_time is not None:
                threshold_detected_time = None

            time.sleep(0.1)  # Sleep to prevent CPU overload
        except KeyboardInterrupt:
            break
    return data


if __name__ == "__main__":
    os.system("cls" if os.name == "nt" else "clear")
    print(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        "Starting the constant current Joule heating program...\n"
    )

    sample_id, currents, durations, max_volt = gui_cc()

    if not all([sample_id, currents, durations, max_volt]):
        raise SystemExit("Program stopped.")

    # Initialise communication with IR temperature sensor and power supply
    ir_sensor = ycr_open()
    psu = etm_open()
    print()

    # Live plot
    (
        figure,
        axT,
        axI,
        axR,
        lineT,
        lineI,
        lineR,
    ) = live_plot_init(sample_id)

    save_start(sample_id)  # Prepare to save data

    try:
        # Joule heating phase
        start_time, h_data = (
            joule_heating_run(
                psu,
                ir_sensor,
                currents,
                durations,
                max_volt,
                figure,
                axT,
                axI,
                axR,
                lineT,
                lineI,
                lineR,
            )
        )

        etm_set_onoff(psu, on=False)  # Shut down the power supply

        # Cooldown phase
        h_data = cooldown(
            psu,
            ir_sensor,
            h_data,
            figure,
            axT,
            axI,
            axR,
            lineT,
            lineI,
            lineR,
            start_time,
        )
    finally:
        etm_set_onoff(psu, on=False)
        ycr_set_laser(ir_sensor, on=False)
        final_csv_path = save_finalise()  # Finalise and save data
        close_plot()

    saved_data = pd.read_csv(final_csv_path)

    # Print some information about the experiment
    print_summary(sample_id, saved_data, final_csv_path)
    print_steps(currents, durations, cc=True)

    # Plots the data
    plot_data(
        saved_data,
        columns=["Temperature (°C)", "Current (A)", "Resistance (Ω)"],
        sample_name=sample_id,
    )
