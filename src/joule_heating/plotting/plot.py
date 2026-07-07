"""Module for plotting Joule heating experiment data using matplotlib.
Result is a 2x2 grid of subplots for Temperature, Voltage, Current, and Resistance.
"""

import contextlib
import math
from typing import Any, NamedTuple

import matplotlib.pyplot as plt


class LivePlot(NamedTuple):
    """Container for matplotlib live plot objects.

    Attributes:
        fig: Matplotlib Figure object.
        axes: Tuple of (ax_temp, ax_current, ax_resistance) Axes.
        lines: Tuple of (line_temp, line_current, line_resistance) Line2D objects.
    """

    fig: object
    axes: tuple
    lines: tuple


def _plot_set_position(position):
    """Set the position/geometry of the current Matplotlib figure window.

    Args:
        position (str): Geometry string, e.g. ``"+50+50"`` or ``"800x600+100+100"``.

    Notes:
        On backends that do not support GUI window manipulation this function
        will fail silently.
    """
    with contextlib.suppress(AttributeError, RuntimeError):
        plt.get_current_fig_manager().window.wm_geometry(position)


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


def live_plot_init(sample_name: str, position: str = "+30+30") -> "LivePlot":
    """Initialise the figure and axes for live plotting.

    Creates a matplotlib figure with three overlaid y-axes for temperature,
    current, and resistance data. The plot is configured for live updates
    during experiment execution.

    Args:
        sample_name (str): Title for the figure (typically sample identifier).
        position (str, optional): Window position geometry string (e.g., "+30+30").
            Default is "+30+30".

    Returns:
        LivePlot: Named tuple with ``fig`` (Figure), ``axes`` (tuple of 3 Axes for
            temperature, current, and resistance), and ``lines`` (tuple of 3 Line2D objects).
    """
    fig, ax1 = plt.subplots(figsize=(8.2, 4))
    plt.get_current_fig_manager().set_window_title("Live Plot")
    fig.suptitle(sample_name, fontsize=13, weight="bold")

    ax1.set_xlabel("Time (s)", fontsize=9)
    ax1.tick_params(axis="x", labelsize=9)

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
    _plot_set_position(position)

    return LivePlot(fig, (ax1, ax2, ax3), (lines[0], lines[1], lines[2]))


def live_plot_update(
    live_plot: "LivePlot",
    *,
    data: dict | None = None,
    x: list | None = None,
    y1: list | None = None,
    y2: list | None = None,
    y3: list | None = None,
) -> None:
    """Update the live plot with the latest experiment data.

    Accepts either a ``data`` dictionary with keys ``'time'``,
    ``'temperature'``, ``'current'`` and ``'resistance'``, or explicit
    lists via ``x``, ``y1``, ``y2``, ``y3``.

    Args:
        live_plot (LivePlot): Live plot container (fig, axes, lines).
        data (dict, optional): Source data dictionary (preferred for experiments).
        x, y1, y2, y3 (list, optional): Explicit lists for time, temp, current, resistance.

    Returns:
        None
    """
    if data is not None:
        x = data["time"]
        y1 = data["temperature"]
        y2 = data["current"]
        y3 = data["resistance"]

    if any(v is None for v in (x, y1, y2, y3)):
        raise ValueError("Either provide `data` or all of x, y1, y2, y3")

    fig, axes, lines = live_plot

    for line, y in zip(lines, (y1, y2, y3), strict=True):
        line.set_data(x, y)

    # Ensure x-axis scales dynamically
    ax1 = axes[0]
    if len(x) > 1:
        if len(x) > 500:
            ax1.set_xlim(x[-500], x[-1])
        else:
            ax1.set_xlim(x[0], x[-1])
    else:
        ax1.set_xlim(0, 1)

    for ax, y in zip(axes, (y1, y2, y3), strict=True):
        valid_y = [val for val in y if _is_finite_number(val)]
        if valid_y:
            ymin, ymax = min(valid_y), max(valid_y)
            padding = 0.05 * (ymax - ymin) if ymax != ymin else 1
            ax.set_ylim(ymin - padding, ymax + padding)

    fig.canvas.draw()
    fig.canvas.flush_events()


def plot_data(
    df: Any,
    columns: list[str] | None = None,
    sample_name: str | None = None,
    position: str = "+30+30",
) -> None:
    """Plot time-series data from a Joule heating experiment.

    Args:
        df (pd.DataFrame): DataFrame containing experiment data.
        columns (list[str], optional): Columns to plot. Defaults to Temperature,
            Voltage, Current and Resistance.
        sample_name (str, optional): Title for the plot.
        position (str, optional): Window position geometry string. Defaults to "+30+30".

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

    fig, axes = plt.subplots(len(columns), 1, figsize=(8.2, 6), sharex=True)
    _plot_set_position(position)  # Position the window

    # Plot data against time
    for ax, column in zip(axes, columns, strict=True):
        ax.plot(df["Time (s)"], df[column], color=colour_map.get(column, "k"))
        ax.set_ylabel(column, fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=9)
        ax.grid(True, axis="both", linestyle="--", alpha=0.4)
        ax.set_xlim(left=0)

    for ax in axes[:-1]:
        ax.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
        ax.spines["bottom"].set_visible(False)

    axes[-1].set_xlabel("Time (s)", fontsize=9)
    fig.suptitle(sample_name, fontsize=13, weight="bold")
    plt.tight_layout()
    plt.show(block=True)


def close_plot() -> None:
    """Close the current matplotlib figure.

    Returns:
        None
    """
    plt.close()
