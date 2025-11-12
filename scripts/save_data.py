"""
Windows-focused streaming CSV writer with Hidden + advisory lock.
Works on Windows; on POSIX it will still stream but without Windows Hidden attribute.

Author       : Delwin Tanto
Last updated : 06 Oct 2025
"""

import csv
import ctypes
import msvcrt
import os
import pathlib

from file_name import generate_filename

_STATE = {"fh": None, "writer": None, "tmp_path": None, "final_path": None, "n": 0, "t0": None}
STREAM_FLUSH_EVERY = 1  # set to 10+ if you want fewer disk writes

def save_start(sample_name, tuning=False):
    """
    Open a hidden + locked temp CSV, write header and column names, keep handle open.
    filename_fn: callable like generate_filename(sample_name) -> full final path (str or Path)
    """
    final_path = pathlib.Path(generate_filename(sample_name, tuning))
    tmp_path = final_path.with_name(final_path.name + ".partial")
    tmp_path.parent.mkdir(parents=True, exist_ok=True)

    if _STATE["fh"]:
        try:
            save_finalise()
        except OSError:
            pass

    fh = open(tmp_path, "w", encoding="utf-8-sig", newline="")

    # Hidden attribute (Windows)
    try:
        ctypes.windll.kernel32.SetFileAttributesW(str(tmp_path), 0x02)
    except OSError:
        pass

    # Advisory lock for the whole run (Windows)
    fh.seek(0, os.SEEK_SET)
    try:
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 0x7FFFFFFF)
    except OSError:
        pass

    w = csv.writer(fh)

    # Column header row (order matches your DataFrame usage)
    w.writerow(["Time (s)", "Temperature (°C)", "Current (A)", "Voltage (V)", "Resistance (Ω)"])
    fh.flush()

    _STATE.update({
        "fh": fh,
        "writer": w,
        "tmp_path": tmp_path,
        "final_path": final_path,
        "n": 0,
        "t0": None,
    })


def save_row(elapsed_s, t_meas, i_meas, v_meas, r_meas):
    """Append a row; flush every STREAM_FLUSH_EVERY rows."""
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
    """Unlock, close, and atomically rename '.partial' -> final CSV. Returns final path or None."""
    s = _STATE
    if not s["fh"]:
        return None
    try:
        try:
            msvcrt.locking(s["fh"].fileno(), msvcrt.LK_UNLCK, 0x7FFFFFFF)
        except OSError:
            pass
        s["fh"].close()
        os.replace(s["tmp_path"], s["final_path"])

        # Remove Hidden attribute (Windows)
        try:
            ctypes.windll.kernel32.SetFileAttributesW(str(s["final_path"]), 0x80)
        except OSError:
            pass
        return str(s["final_path"])
    finally:
        _STATE.update({
            "fh": None,
            "writer": None,
            "tmp_path": None,
            "final_path": None,
            "n": 0,
            "t0": None,
        })
