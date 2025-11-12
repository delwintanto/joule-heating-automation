"""
XY (.xy) XRD Plotter with Optional Baseline Subtraction.

This script opens a file dialog to select one or more `.xy` files (two-column
text: 2θ, intensity), performs optional baseline estimation via asymmetric
least squares (ALS), normalizes each trace for comparability, and plots them
as vertically stacked subplots with a shared x-axis.

Key features:
- Robust parsing (gracefully handles malformed rows).
- ALS baseline estimation for background removal.
- Defensive normalization (avoids division-by-zero).
- Clean, publication-friendly plotting defaults.

Usage:
    python xy_plotter.py
Then pick one or more `.xy` files in the dialog.

Author       : Delwin Tanto
Last updated : 20 Aug 2025
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve

mpl.rcParams["savefig.dpi"] = 300


class XYFilePlotter:
    """
    GUI helper to select, parse, baseline-correct, normalize, and plot XRD .xy files.
    """

    def __init__(self):
        """
        Initialize a hidden Tk root and optional x-axis limits.
        """
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the main window

    def select_files(self):
        """
        Prompt user to select .xy files

        Returns:
            file_paths (tuple of str): Full file paths chosen by the user (empty tuple if none).
        """
        file_paths = filedialog.askopenfilenames(
            title="Select .xy files to plot",
            filetypes=[("XY Files", "*.xy"), ("All files", "*.*")],
        )
        return file_paths

    def parse_xy_file(self, file_path):
        """
        Parse .xy file and return x, y data, skipping first two rows

        Args:
            file_path (str): Path to the .xy file.

        Returns:
            x (ndarray or None): x data (2θ values).
            y (ndarray or None): y data (intensity values).
            filename (str or None): Name of the file without extension.
        """
        try:
            # Peek at first line
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                first_line = f.readline().strip().split()

            # Decide skiprows
            try:
                float(first_line[0])
                float(first_line[1])
                skiprows = 0  # numeric → new file
            except (ValueError, IndexError):
                skiprows = 2  # strings → old file

            data = np.loadtxt(file_path, skiprows=skiprows)
            x, y = data[:, 0], data[:, 1]
            filename = os.path.splitext(os.path.basename(file_path))[0]
            return x, y, filename
        except (FileNotFoundError, PermissionError, OSError, ValueError) as e:
            print(f"Error parsing file {file_path}: {e}")
            return None, None, None

    def baseline_als(self, signal, smoothness=1e5, asymmetry=0.01, max_iter=10):
        """
        Estimate the baseline of a signal using Asymmetric Least Squares (ALS) smoothing.

        Args:
            signal (ndarray): Input 1D signal (e.g. XRD intensities).
            smoothness (float): Smoothness control (lambda). Higher = smoother baseline.
            asymmetry (float): Asymmetry parameter (p). Lower = keep baseline below peaks.
            max_iter (int): Number of iterations for reweighting.

        Returns:
            baseline (ndarray): Estimated baseline of the input signal.
        """
        y = np.asarray(signal, dtype=float)  # Ensure float array
        n_points = y.size
        if n_points < 3:  # Guard against tiny arrays
            return np.zeros_like(y)

        # Second-order difference matrix for smoothness penalty
        second_diff = sparse.diags(
            [1, -2, 1], [0, -1, -2], shape=(n_points, n_points - 2)
        )

        # Start with all weights = 1
        weights = np.ones(n_points)

        for _ in range(max_iter):
            # Build diagonal weight matrix
            weight_mat = sparse.spdiags(weights, 0, n_points, n_points)

            # Regularized system to solve
            penalized_mat = weight_mat + smoothness * (second_diff @ second_diff.T)

            # Solve weighted least squares system
            baseline = spsolve(penalized_mat, weights * y)

            # Update weights: small for peaks, large for baseline
            weights = asymmetry * (y > baseline) + (1 - asymmetry) * (y < baseline)
        return baseline

    def normalize_y(self, y):
        """
        Normalize y data to the range [0, 1].

        Args:
            y (ndarray): y data to normalize.

        Returns:
            ndarray: Normalized y data.
        """
        if len(y) == 0:
            return y
        return (y - np.min(y)) / (np.max(y) - np.min(y))

    def plot_files_shared_x_axis(self, file_paths, substract_baseline=True):
        """
        Plot with separate subplots but shared x-axis for easy comparison.

        Args:
            file_paths (tuple of str): Paths to the .xy files to plot.
            substract_baseline (bool): If True, subtract baseline from y data.
            detec_peaks (bool): If True, detect peaks on the normalized plot.

        Returns:
            None: Displays the plot.
        """
        if not file_paths:
            messagebox.showinfo("Info", "No files selected!")
            return None

        n_files = len(file_paths)
        fig, axes = plt.subplots(n_files, 1, figsize=(12, 2 * n_files), sharex=True)
        axes = axes if n_files > 1 else [axes]

        colormap = plt.get_cmap("tab10")

        for i, (file_path, ax) in enumerate(zip(file_paths, axes)):
            x, y, filename = self.parse_xy_file(file_path)
            y_plot = y

            if substract_baseline:
                background = self.baseline_als(y)
                y_plot = y - background

            ax.plot(x, self.normalize_y(y_plot), color=colormap(i % 10), linewidth=0.8)
            ax.grid(which="both", axis="x", linestyle="--", alpha=0.4)
            ax.spines[["top", "right"]].set_visible(False)
            ax.set_xlim(20, 80)
            ax.xaxis.set_major_locator(mticker.MultipleLocator(10))
            ax.xaxis.set_minor_locator(mticker.MultipleLocator(5))
            ax.xaxis.set_minor_formatter(mticker.NullFormatter())
            ax.set_ylim(-0.125, 1)
            ax.tick_params(axis="y", left=False, labelleft=False)

            if n_files == 1:
                ax.set_ylabel("Norm. Intensity", fontsize=9)
            ax.legend(
                [filename],
                fontsize=9,
                frameon=False,
                handlelength=0,
                bbox_to_anchor=(1, 0),
                loc="lower right",
                borderaxespad=0,
            )

            if ax != axes[-1]:
                ax.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
                ax.spines["bottom"].set_visible(False)

        if n_files > 1:
            fig.supylabel("Normalized Intensity", x=0.02, fontsize=9)
        axes[-1].set_xlabel(r"2θ (degrees)", fontsize=9)
        axes[-1].tick_params(axis="x", labelsize=9)
        plt.tight_layout(h_pad=0)
        plt.show()

    def run(self):
        """
        Entry point for the GUI workflow:
        1) Ask user to select files
        2) Plot them with shared x-axis and ALS baseline correction
        """
        try:
            file_paths = self.select_files()
            if file_paths:
                self.plot_files_shared_x_axis(file_paths)
        except (ValueError, OSError) as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
        finally:
            self.root.destroy()


if __name__ == "__main__":
    XYFilePlotter().run()
