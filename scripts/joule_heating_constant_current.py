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
from temp_sensor_optris import optris_open, optris_set_laser, OptrisIRError
from temp_sensor_utils import read_temperature
from temp_sensor_ycr import ycr_open, ycr_set_laser, YCRIRError


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
            is ``voltage / current`` or ``float('inf')`` when current is zero.
    """
    t_read = read_temperature(ycr_sensor, optris_sensor)
    v_read = etm_read_voltage(power_supply)
    i_read = etm_read_current(power_supply)
    r_read = v_read / i_read if i_read != 0 else float("inf")
    return t_read, v_read, i_read, r_read


def _append_data(data, time_start, time_now, t_read, v_read, i_read, r_read):
    """Append a measurement row to the in-memory data dictionary.

    The function appends values to lists keyed by 'time', 'temperature',
    'voltage', 'current' and 'resistance'. Time is normalised so
    that the first recorded timestamp equals zero.

    Args:
        data (dict): Data dictionary to append to. Expected keys are
            'time', 'temperature', 'voltage', 'current',
            and ``'resistance'`` with list values.
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


def _update_plot(fig, axes, lines, data):
    """Update the live plot with the latest data buffers.

    Args:
        fig (matplotlib.figure.Figure): The figure instance.
        axes (tuple): Tuple of three Axes objects (temp, current, resistance).
        lines (tuple): Tuple of three Line2D objects corresponding to the axes.
        data (dict): Data buffers with keys ``'time'``, ``'temperature'``,
            ``'current'``, and ``'resistance'``.

    Returns:
        None
    """
    live_plot_updt(
        fig, axes[0], axes[1], axes[2], 
        lines[0], lines[1], lines[2],
        data["time"], data["temperature"], data["current"], data["resistance"],
    )

# -------------------- Joule heating --------------------

def joule_heating_run(
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

    Returns:
        tuple: ``(time_start, data)`` where ``time_start`` is the monotonic start
        time and ``data`` is a dict of lists containing the recorded series.
    """
    # Initialise empty data lists where measurements will be stored in
    data = {k: [] for k in ["temperature", "time", "voltage", "current", "resistance"]}

    ycr_set_laser(ycr_sensor, on=True)  # Turn ON the YCR IR sensor laser pointer
    optris_set_laser(optris_sensor, on=True)  # Turn ON the Optris IR sensor laser pointer

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

                t_read, v_read, i_read, r_read = _read_data(power_supply, ycr_sensor, optris_sensor)
                _append_data(data, time_start, time_now, t_read, v_read, i_read, r_read)
                save_row(time_now - time_start, t_read, i_read, v_read, r_read)

                if t_read >= MAX_TEMP:
                    etm_set_onoff(power_supply, on=False)  # PSU OFF if temperature exceeds limit

                _update_plot(fig, (ax1, ax2, ax3), (line1, line2, line3), data)  # Update live plot

                print(
                    f"\r\033[1mStep {idx}/{total_steps}\033[0m - "
                    f"\033[38;2;0;176;240mI: {i_read:>4.1f} A\033[0m | "
                    f"{temp_colour(t_read, MIN_TEMP, MAX_TEMP)}"
                    f"T: {t_read:>6.1f}°C\033[0m | "
                    f"\033[38;2;255;192;0mR: {r_read:>5.2f} Ω\033[0m | "
                    f"t: {max(0, int(end_time - time_now)):>3} s | "
                    "\033[2mCtrl+C to skip\033[0m".ljust(20),
                    end="",
                    flush=True,
                )
                time.sleep(LOOP_INTERVAL)  # Sleep to prevent CPU overload
            except KeyboardInterrupt:
                break

        _update_plot(fig, (ax1, ax2, ax3), (line1, line2, line3), data)  # Update live plot
        print(
            f"\n\033[1;32m[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            "Heating completed!\033[0m"
        )
    return time_start, data


def cooldown(
    power_supply,
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
):
    """Record cooldown data until the temperature remains below threshold.

    The function appends readings to ``data`` and stops once the measured
    temperature stays below ``MIN_TEMP`` for ``COOLDOWN_BUFFER`` seconds, or
    when the user interrupts with Ctrl+C.

    Args:
        power_supply: PSU device instance.
        ycr_sensor: YCR IR sensor instance.
        optris_sensor: Optris IR sensor instance.
        data (dict): Data dictionary to append cooldown values.
        fig, ax1, ax2, ax3, line1, line2, line3: Plot objects used by the live plot.
        time_start (float): Monotonic start time of the experiment.

    Returns:
        dict: The updated ``data`` dictionary.
    """
    threshold_detected_time = None
    cool_start = time.monotonic()
    print(
        f"\nStarting cooldown until {COOLDOWN_BUFFER} s "
        "after T drops below threshold..."
    )

    while True:
        try:
            time_now = time.monotonic()
            t_read, v_read, i_read, r_read = _read_data(power_supply, ycr_sensor, optris_sensor)
            _append_data(data, time_start, time_now, t_read, v_read, i_read, r_read)
            save_row(time_now - time_start, t_read, i_read, v_read, r_read)

            _update_plot(fig, (ax1, ax2, ax3), (line1, line2, line3), data)  # Update live plot

            print(
                "\r\033[1;34mCooldown\033[0m - "
                f"{temp_colour(t_read, MIN_TEMP, MAX_TEMP)}"
                f"T: {t_read:>6.1f}°C\033[0m | "
                f"t elapsed: {time_now - cool_start:>3.0f} s | "
                "\033[2mCtrl+C to end\033[0m".ljust(20),
                end="",
                flush=True,
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
            break
    print(
            f"\n\033[1;32m[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            "Cooldown completed!\033[0m"
        )
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

    # Initialise communication with IR temperature sensors and power supply
    try:
        ycr_temp_sensor = ycr_open()
        optris_temp_sensor = optris_open()
        psu = etm_open()
    except (YCRIRError, OptrisIRError, PSUError) as e:
        raise SystemExit(f"Error initializing devices: {e}")

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
                ycr_temp_sensor,
                optris_temp_sensor,
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
            ycr_temp_sensor,
            optris_temp_sensor,
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
        try:
            final_csv_path = save_finalise()  # Finalise and save data
            etm_set_onoff(psu, on=False)
            ycr_set_laser(ycr_temp_sensor, on=False)
            optris_set_laser(optris_temp_sensor, on=False)
            close_plot()
        except (OSError, YCRIRError, OptrisIRError, PSUError) as e:
            print(f"Error during cleanup: {e}")

    if final_csv_path:
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
