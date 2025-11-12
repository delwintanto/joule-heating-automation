"""
Module for plotting Joule heating experiment data using matplotlib.
Result is a 2x2 grid of subplots for Temperature, Voltage, Current, and Resistance.

Author       : Delwin Tanto
Last updated : 04 Nov 2025
"""

import math
import matplotlib.pyplot as plt


def _plot_set_position(position):
    """Set the position/geometry of the current Matplotlib figure window.

    Args:
        position (str): Geometry string, e.g. ``"+50+50"`` or ``"800x600+100+100"``.

    Notes:
        On backends that do not support GUI window manipulation this function
        will fail silently.
    """
    try:
        plt.get_current_fig_manager().window.wm_geometry(position)
    except (AttributeError, RuntimeError):
        pass


def _is_finite_number(x):
    """Return True if ``x`` can be converted to a finite float.

    Args:
        x: Value to test for finiteness.

    Returns:
        bool: True when ``x`` is a finite number, False otherwise.
    """
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def live_plot_init(sample_name, position="+30+30"):
    """
    Initialise the figure and axes for live plotting.
    
    Args:
        sample_name: Title for the figure.
        position: Optional window position geometry.

    Returns:
        tuple: (fig, ax1, ax2, ax3, line1, line2, line3)
    """
    fig, ax1 = plt.subplots(figsize=(8, 4))
    plt.get_current_fig_manager().set_window_title("Live Plot")
    fig.suptitle(sample_name, fontsize=13, weight="bold")
    _plot_set_position(position)

    ax1.set_xlabel("Time (s)", fontsize=9)
    ax1.tick_params(axis='x', labelsize=9)

    ax2, ax3 = ax1.twinx(), ax1.twinx()
    ax3.spines["right"].set_position(("outward", 60))
    axes_info = [
        (ax1, "Temperature (°C)", "#E63946", 3),
        (ax2, "Current (A)", "#457B9D", 2),
        (ax3, "Resistance (Ω)", "#43A350", 1),
    ]

    lines = []
    for ax, label, colour, z in axes_info:
        ax.patch.set_visible(False)
        ax.set_ylabel(label, fontsize=9, color=colour)
        ax.tick_params(axis="y", labelsize=9, labelcolor=colour)
        ax.set_zorder(z)
        lines.append(ax.plot([], [], colour, label=label)[0])

    plt.tight_layout()
    plt.show(block=False)
    return fig, ax1, ax2, ax3, lines[0], lines[1], lines[2]


def live_plot_updt(
    fig,
    ax1,
    ax2,
    ax3,
    line1,
    line2,
    line3,
    x,
    y1,
    y2,
    y3,
):
    """Update the live plot with the latest experiment data.

    Args:
        fig (Figure): Matplotlib figure.
        ax1 (Axes): Axis for temperature.
        ax2 (Axes): Axis for current.
        ax3 (Axes): Axis for resistance.
        line1 (Line2D): Temperature line.
        line2 (Line2D): Current line.
        line3 (Line2D): Resistance line.
        x (list): Time values.
        y1 (list): Temperature values.
        y2 (list): Current values.
        y3 (list): Resistance values.

    Returns:
        None
    """
    for line, y in zip((line1, line2, line3), (y1, y2, y3)):
        line.set_data(x, y)  # Update the data for each line

    # Ensure x-axis scales dynamically
    if len(x) > 1:
        if len(x) > 500:
            ax1.set_xlim(x[-500], x[-1])
        else:
            ax1.set_xlim(x[0], x[-1])
    else:
        ax1.set_xlim(0, 1)

    for ax, y in zip([ax1, ax2, ax3], [y1, y2, y3]):
        valid_y = [val for val in y if _is_finite_number(val)]
        if valid_y:  # Make sure data is not empty
            ymin, ymax = min(valid_y), max(valid_y)
            padding = 0.05 * (ymax - ymin) if ymax != ymin else 1
            ax.set_ylim(ymin - padding, ymax + padding)

    fig.canvas.draw()
    fig.canvas.flush_events()


def plot_data(df, columns=None, sample_name=None):
    """Plot time-series data from a Joule heating experiment.

    Args:
        df (pd.DataFrame): DataFrame containing experiment data.
        columns (list[str], optional): Columns to plot. Defaults to Temperature,
            Voltage, Current and Resistance.
        sample_name (str, optional): Title for the plot.

    Returns:
        None
    """
    if columns is None:
        columns = ["Temperature (°C)", "Voltage (V)", "Current (A)", "Resistance (Ω)"]

    colour_map = {
        "Temperature (°C)": "#C00000",
        "Voltage (V)": "#00B050",
        "Current (A)": "#00B0F0",
        "Resistance (Ω)": "#FFC000",
    }

    fig, axes = plt.subplots(len(columns), 1, figsize=(10, 6), sharex=True)
    _plot_set_position("+30+30")  # Position the window

    # Plot data against time
    for ax, column in zip(axes, columns):
        ax.plot(df["Time (s)"], df[column], color=colour_map.get(column, "k"))
        ax.set_ylabel(column, fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=9)
        ax.grid(True, axis="both", linestyle="--", alpha=0.4)
        ax.set_xlim(left=0)

    for ax in axes[:-1]:
        ax.tick_params(axis='x', which='both', bottom=False, labelbottom=False)
        ax.spines["bottom"].set_visible(False)

    axes[-1].set_xlabel("Time (s)", fontsize=9)
    fig.suptitle(sample_name, fontsize=13, weight="bold")
    plt.tight_layout()
    plt.show()


def close_plot():
    """Close the current matplotlib figure.

    Returns:
        None
    """
    plt.close()
