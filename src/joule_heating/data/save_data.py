"""Streaming CSV writer with Windows-friendly hidden + advisory lock.

This module implements a small streaming CSV writer that keeps a temporary
``.partial`` file open during an experiment run and atomically renames it to
the final CSV when complete. It attempts to set the file hidden attribute on
Windows and acquires an advisory lock while writing. On POSIX systems the
module still streams data but without Windows-specific hidden attribute.

Usage:
    from joule_heating.data import save_start, save_row, save_finalise

Author       : Delwin Tanto
Last updated : 06 Oct 2025
"""

import contextlib
import csv
import ctypes
import msvcrt
import os
import pathlib

from joule_heating.data import generate_filename

_STATE = {"fh": None, "writer": None, "tmp_path": None, "final_path": None, "n": 0, "t0": None}
STREAM_FLUSH_EVERY = 1  # set to 10+ if you want fewer disk writes


def save_start(sample_name, tuning=False):
    """Open a temporary, locked CSV file and write the header row.

    The function creates a final filename via :func:`file_name.generate_filename`,
    opens a ``.partial`` temporary file for streaming writes, attempts to set the
    Windows hidden attribute, locks the file, and writes the CSV header row.

    Args:
        sample_name (str): Sample identifier used to create the filename.
        tuning (bool): If True the filename will indicate tuning data. Default is False.

    Returns:
        None

    Note:
        Opens a file handle kept in module state until :func:`save_finalise` is called.
        The file remains open for streaming writes throughout the experiment.
    """
    final_path = pathlib.Path(generate_filename(sample_name, tuning))
    tmp_path = final_path.with_name(final_path.name + ".partial")
    tmp_path.parent.mkdir(parents=True, exist_ok=True)

    if _STATE["fh"]:
        with contextlib.suppress(OSError):
            save_finalise()

    # Remove stale .partial file from previous failed run if it exists
    with contextlib.suppress(OSError, PermissionError):
        tmp_path.unlink(missing_ok=True)

    fh = open(tmp_path, "w", encoding="utf-8-sig", newline="")  # noqa: SIM115

    # Hidden attribute (Windows)
    with contextlib.suppress(OSError):
        ctypes.windll.kernel32.SetFileAttributesW(str(tmp_path), 0x02)

    # Advisory lock for the whole run (Windows)
    fh.seek(0, os.SEEK_SET)
    with contextlib.suppress(OSError):
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 0x7FFFFFFF)

    w = csv.writer(fh)

    # Column header row (order matches your DataFrame usage)
    w.writerow(["Time (s)", "Temperature (°C)", "Current (A)", "Voltage (V)", "Resistance (Ω)"])
    fh.flush()

    _STATE.update(
        {
            "fh": fh,
            "writer": w,
            "tmp_path": tmp_path,
            "final_path": final_path,
            "n": 0,
            "t0": None,
        }
    )


def save_row(elapsed_s, t_meas, i_meas, v_meas, r_meas):
    """Append a measurement row to the open CSV stream.

    The first written timestamp is normalised to zero. Rows are flushed to disk
    every ``STREAM_FLUSH_EVERY`` rows.

    Args:
        elapsed_s (float): Elapsed seconds timestamp (monotonic or wall-clock).
        t_meas (float): Temperature measurement in °C.
        i_meas (float): Current measurement in A.
        v_meas (float): Voltage measurement in V.
        r_meas (float): Resistance measurement in Ω.

    Returns:
        None

    Note:
        Must be called after :func:`save_start`. If called before initialization,
        the function silently returns without writing data.
    """
    s = _STATE
    if not s["writer"]:
        return

    # Normalise so first written timestamp becomes zero
    if s["t0"] is None:
        s["t0"] = elapsed_s
    t_out = elapsed_s - s["t0"]

    s["writer"].writerow([t_out, t_meas, i_meas, v_meas, r_meas])
    s["n"] += 1
    if s["n"] % STREAM_FLUSH_EVERY == 0:
        s["fh"].flush()


def save_finalise():
    """Finalize the stream: unlock, close and atomically rename temporary file.

    Returns:
        str or None: The final CSV path if a file was finalised, otherwise None.
    """
    s = _STATE
    if not s["fh"]:
        return None
    try:
        with contextlib.suppress(OSError):
            msvcrt.locking(s["fh"].fileno(), msvcrt.LK_UNLCK, 0x7FFFFFFF)
        s["fh"].close()
        os.replace(s["tmp_path"], s["final_path"])

        # Remove Hidden attribute (Windows)
        with contextlib.suppress(OSError):
            ctypes.windll.kernel32.SetFileAttributesW(str(s["final_path"]), 0x80)
        return str(s["final_path"])
    finally:
        _STATE.update(
            {
                "fh": None,
                "writer": None,
                "tmp_path": None,
                "final_path": None,
                "n": 0,
                "t0": None,
            }
        )
