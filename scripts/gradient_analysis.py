"""Detect and analyse temperature peaks, valleys, and thermal transitions in time-series data.

This script processes temperature vs. time data to identify:
- Sharp temperature rises (transient detection)
- Peaks and valleys (local maxima/minima)
- Oscillation periods and amplitudes
- Gradient-based slope changes

Key features include:
- Savitzky-Golay smoothing for noise reduction
- Gradient analysis for rate-of-change detection
- Combined prominence-based and gradient-based extrema detection
- Automated plotting of results with original vs. smoothed data

Usage:
=====
1. **As a standalone script** (interactive file picker):
    ```bash
    python gradient_analysis.py
    ```
    Prompts for a CSV file with columns: 'Time (s)' and 'Temperature (°C)'.

2. **As an importable module** (for programmatic use):
    ```python
    from gradient_analysis import (
        detect_peaks_and_valleys,
        calculate_period,
        calculate_amplitude,
        plot_data,
    )
    
    # Example usage:
    results = detect_peaks_and_valleys(time_array, temp_array)
    period = calculate_period(results["combined_maxima"], time_array)
    amplitude = calculate_amplitude(
        results["combined_maxima"],
        results["combined_minima"],
        time_array,
        temp_array,
    )
    plot_data(time_array, results)
    ```

Author       : Delwin Tanto
Last updated : 04 Nov 2025
"""

import numpy as np
from scipy.signal import argrelextrema, find_peaks, savgol_filter


def detect_sharp_temp_rise(
    time_data, temp_data, rise_threshold=300.0, max_rise_time=2.0
):
    """
    Detect the first occurrence of a sharp temperature rise.

    Args:
        time_data (array-like): Array of time values.
        temp_data (array-like): Array of temperature values.
        rise_threshold (float): Minimum temperature increase to detect.
        max_rise_time (float): Maximum allowed time span for the rise.

    Returns:
        int or None: Index of the detected rise or None if not found.
    """
    for i, t_start in enumerate(time_data):
        j_indices = np.where(
            (time_data > t_start) & (time_data - t_start <= max_rise_time)
        )[0]
        # Check if there is a sharp jump in temperature
        if len(j_indices) > 0:
            temp_diff = temp_data[j_indices] - temp_data[i]
            if np.any(temp_diff >= rise_threshold):
                return j_indices[np.argmax(temp_diff >= rise_threshold)]
    return None


def detect_peaks_and_valleys(
    time_data,
    temp_data,
    window=21,
    polyorder=2,
    extrema_order=20,
    prom=0.5,
    min_drop=1,
    lookback=50,
):
    """Detects peaks and valleys in temperature time-series data.

    The function performs the following steps:
    1. Smooths the temperature data using Savitzky-Golay filter
    2. Calculates the gradient of the smoothed temperature
    3. Identifies peaks and valleys using prominence-based detection
    4. Detects significant slope changes by analyzing gradient extrema
    5. Combines all detected features into comprehensive results

    Args:
        time_data (array-like): Time values in seconds.
        temp_data (array-like): Temperature values in °C.
        window (int, optional): Window length for Savitzky-Golay filter. Must be odd number.
        polyorder (int, optional): Polynomial order for Savitzky-Golay filter.
        extrema_order (int, optional): Order parameter for gradient extrema detection.
        prom (float, optional): Minimum prominence for peak detection.
        min_drop (float, optional): Minimum gradient drop for significant slope change.
        lookback (int, optional): Lookback window for finding preceding maxima.

    Returns:
        dict: Dictionary containing detection results with keys:
            - 'combined_maxima': Combined peaks and halfway points
            - 'combined_minima': Combined valleys and gradient minima
            - 'temp_smooth': Smoothed temperature values
            - 'gradient': Calculated gradient values
    """
    t = np.asarray(time_data)
    temperature = np.asarray(temp_data)

    start_idx = detect_sharp_temp_rise(t, temperature)
    if start_idx is not None:
        t = t[start_idx:]
        temperature = temperature[start_idx:]

    # Smooth the temperature data
    temp_smooth = savgol_filter(temperature, window_length=window, polyorder=polyorder)
    gradient = np.gradient(temp_smooth, t)

    # Detect peaks and valleys directly from smoothed temperature
    peaks, _ = find_peaks(temp_smooth, prominence=prom)
    valleys, _ = find_peaks(-temp_smooth, prominence=prom)

    # Find all consecutive peak-valley pairs (in order)
    peak_valley_pairs = []
    for peak in peaks:
        # Find valleys that come after this peak
        subsequent_valleys = valleys[valleys > peak]
        if len(subsequent_valleys) > 0:
            # Take the first valley after the peak
            peak_valley_pairs.append((peak, subsequent_valleys[0]))

    # Local minima in gradient
    all_gradient_minima = argrelextrema(
        np.abs(gradient), np.less, order=extrema_order
    )[0]

    # Find the last maxima before each minima
    all_drop_points = []
    for min_idx in all_gradient_minima:
        # Look back a limited window to find the preceding maximum
        window_start = max(0, min_idx - lookback)
        window_gradient = gradient[window_start:min_idx]

        if len(window_gradient) > 0:
            # Find local maxima in this window
            local_max_idx = np.argmax(window_gradient)
            max_idx = window_start + local_max_idx

            # Check if the drop is significant enough
            if (gradient[max_idx] - gradient[min_idx]) > min_drop:
                all_drop_points.append(max_idx)

    # Find the earliest peak-valley pair start time
    if len(peak_valley_pairs) > 0:
        first_pair_start = min(
            [pair[0] for pair in peak_valley_pairs]
        )  # first peak time
    else:
        first_pair_start = len(t)  # if no pairs, set to end of data

    # Filter to only keep points before the first peak-valley pairs
    gradient_minima = all_gradient_minima[all_gradient_minima < first_pair_start]
    drop_points = [p for p in all_drop_points if p < first_pair_start]

    # Pair each drop_point (gradient_maxima) with the next gradient_minima
    gradient_maxima = []
    for max_idx in drop_points:
        next_min_candidates = gradient_minima[gradient_minima > max_idx]
        if len(next_min_candidates) > 0:
            gradient_maxima.append(max_idx)

    # Combine gradient_maxima with peaks, and gradient_minima with valleys
    combined_maxima = np.sort(
        np.unique(np.concatenate((gradient_maxima, peaks)))
    ).astype(int)
    combined_minima = np.sort(
        np.unique(np.concatenate((gradient_minima, valleys)))
    ).astype(int)

    return {
        "time": t,
        "temperature": temperature,
        "combined_maxima": combined_maxima,
        "combined_minima": combined_minima,
        "temp_smooth": temp_smooth,
        "gradient": gradient,
        "start_idx": start_idx,
        "peak_valley_pairs": peak_valley_pairs
    }


def calculate_period(peaks, x):
    """Calculates the average period between consecutive peaks.

    Args:
        peaks (array-like): Indices of detected peaks.
        x (array-like): Time values corresponding to the peaks.

    Returns:
        float: Average period in seconds. Returns 0 if fewer than 2 peaks are detected.
    """
    return np.mean(np.diff([x[p] for p in peaks])) if len(peaks) >= 2 else 0


def calculate_amplitude(peaks, valleys, x, y):
    """Calculates the average amplitude between consecutive peaks and valleys.

    The amplitude is calculated as half the difference between adjacent peak and valley values.

    Args:
        peaks (array-like): Indices of detected peaks.
        valleys (array-like): Indices of detected valleys.
        x (array-like): Time values corresponding to the data points.
        y (array-like): Temperature values corresponding to the data points.

    Returns:
        float: Average amplitude in °C. Returns 0 if no valid peak-valley pairs are found.
    """
    if len(peaks) == 0 or len(valleys) == 0:
        return 0

    # Sort peaks and valleys by time (x-axis)
    peaks_sorted = sorted(peaks, key=lambda p: x[p])
    valleys_sorted = sorted(valleys, key=lambda v: x[v])

    # Calculate the amplitude as the average of peak-to-valley differences
    amplitudes = []
    valley_iter = iter(valleys_sorted)
    next_valley = next(valley_iter, None)  # First valley

    for idx, p in enumerate(peaks_sorted):
        while next_valley is not None and x[next_valley] <= x[p]:
            next_valley = next(valley_iter, None)

        if next_valley is None:
            break  # No valleys left

        # Skip if valley is after the NEXT peak (not adjacent)
        if idx + 1 < len(peaks_sorted) and x[next_valley] > x[peaks_sorted[idx + 1]]:
            continue

        # Compute amplitude when valid valley found
        amplitudes.append(abs(y[p] - y[next_valley]) / 2)

    return np.mean(amplitudes) if amplitudes else 0


if __name__ == "__main__":
    import tkinter as tk
    from tkinter import filedialog
    import matplotlib.pyplot as plt
    import pandas as pd

    # Simple file picker
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="Select a CSV File",
        filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*")),
    )

    if file_path:
        df = pd.read_csv(file_path)

        if "Time (s)" in df.columns and "Temperature (°C)" in df.columns:
            time = df["Time (s)"].values
            temp = df["Temperature (°C)"].values
            results = detect_peaks_and_valleys(time, temp)

            print("Combined maxima:", results["combined_maxima"])
            print(
                "Type and dtype:",
                type(results["combined_maxima"]),
                results["combined_maxima"].dtype,
            )

            # Calculate period and amplitude
            period = calculate_period(results["combined_maxima"], time)
            amplitude = calculate_amplitude(
                results["combined_maxima"], results["combined_minima"], time, temp
            )

            print(f"Average period: {period:.2f} seconds")
            print(f"Average amplitude: {amplitude:.2f} °C")
            print(f"Number of peak and valley pairs detected: {len(results["peak_valley_pairs"])}")

            def _plot_data(t, analysed_data):
                """Plots temperature data with detected features and gradient.

                Creates a dual-axis plot showing:
                - Original and smoothed temperature data
                - Detected maxima and minima points
                - Temperature gradient (rate of change)

                Args:
                    analysed_data (dict): Detection results from detect_peaks_and_valleys().
                """
                temp_data = analysed_data["temperature"]
                temp_smooth = analysed_data["temp_smooth"]
                time_data = analysed_data["time"]
                gradient = analysed_data["gradient"]

                _, ax1 = plt.subplots(figsize=(12, 6))
                ax1.plot(time_data, temp_data, label="Original Temperature (°C)", color="black")
                ax1.plot(time_data, temp_smooth, label="Smoothed Temperature (°C)", color="gray")

                ax1.scatter(
                    np.array(time_data)[analysed_data["combined_maxima"]],
                    np.array(temp_data)[analysed_data["combined_maxima"]],
                    marker="P",
                    color="red",
                    s=120,
                    label="Peaks",
                )

                ax1.scatter(
                    np.array(time_data)[analysed_data["combined_minima"]],
                    np.array(temp_data)[analysed_data["combined_minima"]],
                    marker="X",
                    color="blue",
                    s=120,
                    label="Valleys",
                )

                if analysed_data["start_idx"] is not None:
                    ax1.axvline(
                        t[analysed_data["start_idx"]],
                        color="green",
                        linestyle="--",
                        label="Transition Start",
                    )

                ax1.set_xlabel("Time (s)")
                ax1.set_ylabel("Temperature (°C)")
                ax1.legend()
                ax1.grid(True)
                ax1.set_title("Temperature vs Time")

                ax2 = ax1.twinx()
                ax2.plot(
                    time_data,
                    gradient,
                    label="Gradient (°C/s)",
                    color="red",
                    linestyle="--",
                    alpha=0.7,
                )
                ax2.set_ylabel("Gradient (°C/s)", color="red")
                ax2.tick_params(axis="y", labelcolor="red")

                plt.tight_layout()
                plt.show()

            _plot_data(time, results)
        else:
            print("CSV must contain 'Time (s)' and 'Temperature (°C)' columns!")
    else:
        print("No file selected.")
