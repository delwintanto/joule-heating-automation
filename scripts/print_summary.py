

def print_summary(
    sample_id,
    saved_data,
    final_csv_path,
    pid_curr=None,
    pid_volt=None,
    pid_gains=None,
):
    """
    Print a summary of the experiment results.
    """
    print("\nSummary:")
    print("=" * 50)
    print(f"{'Sample name:':<20} {sample_id}")

    if pid_curr is not None:
        print(f"{'Max current (A):':<20} {pid_curr}")
    if pid_volt is not None:
        print(f"{'Max voltage (V):':<20} {pid_volt}")
    if pid_gains is not None:
        kp, ki, kd = pid_gains
        print(f"{'PID gains:':<20} Kp: {kp:.3f}, Ki: {ki:.3f}, Kd: {kd:.3f}")

    print(
        f"{'Total time (s):':<20} "
        f"{saved_data['Time (s)'].max() if len(saved_data) else 'NaN'}"
    )
    temp_max = saved_data["Temperature (°C)"].max(skipna=True)
    print(
        f"{'Max temperature (°C):':<20} "
        f"{f'{temp_max:.2f}' if temp_max == temp_max else 'NaN'}"
    )
    print(f"{'Data file:':<20} {final_csv_path}")
    print("-" * 50)


def print_steps(col1, col2, cc=True):
    """
    Print the heating phases of the experiment.
    """
    print("\nHeating Phases:")
    print("-" * 50)
    if cc:
        print(f"{'Step':<8} {'Current (A)':<14} {'Duration (s)':<14}")
        print("-" * 50)
        for i, (v1, v2) in enumerate(zip(col1, col2), start=1):
            print(f"{i:<8} {v1:<14} {v2:<14}")
    else:
        print(f"{'Step':<8} {'Set Temp (°C)':<14} {'Duration (s)':<14}")
        print("-" * 50)

        # Convert to lists for easier manipulation
        col1_list, col2_list = list(col1), list(col2)
        ramps = _detect_ramp_pattern(col1_list, col2_list)

        i = 0
        while i < len(col1_list):
            # Check if current index starts a ramp
            ramp = next((r for r in ramps if r[0] == i), None)

            if ramp:
                start, delta, dur, length = ramp

                for j in range(min(5, length)):  # Print first 5 steps
                    print(f"{i + j + 1:<8} {col1_list[i + j]:<14} {col2_list[i + j]:<12}")

                if length > 10:  # Compressed middle section
                    print(" " * 8 + "...")

                for j in range(max(5, length - 5), length):  # Print last 5 steps if long enough
                    print(f"{i + j + 1:<8} {col1_list[i + j]:<14} {col2_list[i + j]:<12}")

                i += length  # Skip entire ramp
            else:
                # Not part of a ramp
                print(f"{i + 1:<8} {col1_list[i]:<14} {col2_list[i]:<12}")
                i += 1
    print("=" * 50)


def _detect_ramp_pattern(temps, durs, min_ramp_length=10, tolerance=1e-6):
        """
        Detect sequences of consistent temperature ramps in the experiment.

        Args:
            temps (list[float]): List of temperature setpoints.
            durs (list[float]): List of durations corresponding to each temperature.
            min_ramp_length (int): Minimum number of steps to consider a ramp.
            tolerance (float): Tolerance for float comparison.

        Returns:
            list[tuple]: List of detected ramps as (start_index, delta_temp, duration,
                            ramp_length).
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
