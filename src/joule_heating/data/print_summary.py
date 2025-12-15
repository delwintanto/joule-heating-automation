
"""Utilities for printing concise experiment summaries to the console.

This module provides helper functions used by the Joule heating scripts to
display a short summary after an experiment finishes, and to print a compact
representation of the set of heating steps used.

The functions intentionally only print to stdout and do not modify any data.

Author       : Delwin Tanto
Last updated : 06 Nov 2025
"""


def print_summary(
    sample_id,
    saved_data,
    final_csv_path,
    pid_curr=None,
    pid_volt=None,
    pid_gains=None,
):
    """Print a short summary of the experiment results.

    Args:
        sample_id (str): Identifier used for the experiment/sample.
        saved_data (pandas.DataFrame): DataFrame containing the recorded experiment data.
        final_csv_path (str): Path to the final CSV file that was written.
        pid_curr (float, optional): If provided, prints the PID-controlled max current.
        pid_volt (float, optional): If provided, prints the PID-controlled max voltage.
        pid_gains (tuple[float, float, float], optional): (Kp, Ki, Kd) to display.

    Returns:
        None: The function prints directly to stdout.

    Notes:
        - This function only prints information; it does not raise exceptions.
    """
    print("\nSummary:")
    print("=" * 50)
    print(f"{'Sample name:':<22} {sample_id}")

    if pid_curr is not None:
        print(f"{'Max current (A):':<22} {pid_curr}")
    if pid_volt is not None:
        print(f"{'Max voltage (V):':<22} {pid_volt}")
    if pid_gains is not None:
        kp, ki, kd = pid_gains
        print(f"{'PID gains:':<22} Kp: {kp:.3f}, Ki: {ki:.3f}, Kd: {kd:.3f}")

    print(
        f"{'Total time (s):':<22} "
        f"{saved_data['Time (s)'].max():.2f}" if len(saved_data) else 'NaN'
    )
    temp_max = saved_data["Temperature (°C)"].max(skipna=True)
    print(
        f"{'Max temperature (°C):':<22} "
        f"{temp_max:.2f}" if temp_max == temp_max else 'NaN'
    )
    print(f"{'Data file:':<22} {final_csv_path}")
    print("-" * 50)


def print_steps(col1, col2, cc=True):
    """Print the heating phases in a human readable table.

    This prints either a constant-current style table (step, current, duration)
    or a PID/temperature style table (step, set temperature, duration) depending
    on the `cc` flag.

    Args:
        col1 (iterable): First column values (currents or temperatures).
        col2 (iterable): Second column values (durations in seconds).
        cc (bool): If True interpret columns as (current, duration). If False,
                   interpret columns as (temperature, duration).

    Returns:
        None: The function prints directly to stdout.
    """
    print("\nHeating Phases:")
    print("-" * 50)
    if cc:
        print(f"{'Step':<10} {'Current (A)':<18} {'Duration (s)':<18}")
        print("-" * 50)
        for i, (v1, v2) in enumerate(zip(col1, col2), start=1):
            print(f"{i:<10} {v1:<18} {v2:<18}")
    else:
        print(f"{'Step':<10} {'Set Temp (°C)':<18} {'Duration (s)':<18}")
        print("-" * 50)

        # Convert to lists for easier manipulation
        col1_list, col2_list = list(col1), list(col2)
        ramps = _detect_ramp_pattern(col1_list, col2_list)

        i = 0
        while i < len(col1_list):
            # Check if current index starts a ramp
            ramp = next((r for r in ramps if r[0] == i), None)

            if ramp:
                *_, length = ramp

                for j in range(min(5, length)):  # Print first 5 steps
                    print(
                        f"{i + j + 1:<10} {col1_list[i + j]:<18} {col2_list[i + j]:<18}")

                if length > 10:  # Compressed middle section
                    print(" " * 10 + "...")

                # Print last 5 steps if long enough
                for j in range(max(5, length - 5), length):
                    print(
                        f"{i + j + 1:<10} {col1_list[i + j]:<18} {col2_list[i + j]:<18}")

                i += length  # Skip entire ramp
            else:
                # Not part of a ramp
                print(f"{i + 1:<10} {col1_list[i]:<18} {col2_list[i]:<18}")
                i += 1
    print("=" * 50)


def _detect_ramp_pattern(temps, durs, min_ramp_length=10, tolerance=1e-6):
    """Detect sequences of consistent temperature ramps.

    A ramp is defined as a contiguous sequence where the temperature difference
    between successive steps is approximately constant (within ``tolerance``)
    and the durations are approximately constant. This helper is used to
    compress long ramp sequences for concise printing.

    Args:
        temps (list[float]): List of temperature setpoints.
        durs (list[float]): List of durations corresponding to each temperature.
        min_ramp_length (int): Minimum number of steps to consider a ramp.
        tolerance (float): Tolerance for float comparison.

    Returns:
        list[tuple]: Detected ramps, each as ``(start_index, delta_temp, duration, ramp_length)``.
    """

    ramps, x = [], 0

    n = len(temps)

    while x < n - min_ramp_length:
        delta_temp = temps[x + 1] - temps[x]
        durr = durs[x + 1]
        y = x + 2

        while (
            y < n
            and abs((temps[y] - temps[y - 1]) - delta_temp) < tolerance
            and abs(durs[y] - durr) < tolerance
        ):
            y += 1

        ramp_len = y - x
        if ramp_len >= min_ramp_length:
            ramps.append((x, delta_temp, durr, ramp_len))
            x = y  # Skip past the ramp
        else:
            x += 1

    return ramps
