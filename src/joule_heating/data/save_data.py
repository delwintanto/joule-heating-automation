"""Streaming CSV writer with Windows-friendly hidden + advisory lock.

This module implements a streaming CSV writer that keeps a temporary
``.partial`` file open during an experiment run and atomically renames it to
the final CSV when complete. It attempts to set the file hidden attribute on
Windows and acquires an advisory lock while writing.

Usage:

    from joule_heating.data import CsvWriter

    writer = CsvWriter("my_sample")
    writer.start()
    writer.row(elapsed, temp, current, voltage, resistance)
    path = writer.finalise()
"""

import contextlib
import csv
import ctypes
import os
import pathlib

try:
    import msvcrt
except ImportError:  # pragma: no cover - non-Windows fallback
    msvcrt = None

from .file_name import generate_filename

STREAM_FLUSH_EVERY = 1  # set to 10+ if you want fewer disk writes


def _set_hidden_attribute(path: pathlib.Path, attribute: int) -> None:
    """Set a Windows file attribute when the platform supports it."""
    with contextlib.suppress(AttributeError, OSError):
        ctypes.windll.kernel32.SetFileAttributesW(str(path), attribute)


def _lock_file(file_handle) -> None:
    """Apply a Windows advisory lock when ``msvcrt`` is available."""
    if msvcrt is None:
        return
    with contextlib.suppress(OSError):
        msvcrt.locking(file_handle.fileno(), msvcrt.LK_NBLCK, 0x7FFFFFFF)


def _unlock_file(file_handle) -> None:
    """Release a Windows advisory lock when ``msvcrt`` is available."""
    if msvcrt is None:
        return
    with contextlib.suppress(OSError):
        msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 0x7FFFFFFF)


class CsvWriter:
    """Streaming CSV writer with atomic rename and Windows file locking.

    Each instance manages its own file handle and state, allowing multiple
    concurrent writers (e.g., tuning data and experiment data).

    Args:
        sample_name (str): Sample identifier used to create the filename.
        tuning (bool): If True the filename will indicate tuning data.
    """

    def __init__(self, sample_name: str, tuning: bool = False) -> None:
        self._sample_name = sample_name
        self._tuning = tuning
        self._fh = None
        self._writer = None
        self._tmp_path = None
        self._final_path = None
        self._n = 0
        self._t0 = None

    def start(self) -> None:
        """Open a temporary, locked CSV file and write the header row.

        Creates a final filename via :func:`file_name.generate_filename`,
        opens a ``.partial`` temporary file for streaming writes, attempts to set
        the Windows hidden attribute, locks the file, and writes the CSV header.

        If this writer already has an open file, it is finalised first.

        Returns:
            None
        """
        final_path = pathlib.Path(generate_filename(self._sample_name, self._tuning))
        tmp_path = final_path.with_name(final_path.name + ".partial")
        tmp_path.parent.mkdir(parents=True, exist_ok=True)

        if self._fh:
            with contextlib.suppress(OSError):
                self.finalise()

        # Remove stale .partial file from previous failed run if it exists
        with contextlib.suppress(OSError, PermissionError):
            tmp_path.unlink(missing_ok=True)

        fh = open(tmp_path, "w", encoding="utf-8-sig", newline="")  # noqa: SIM115

        # Hidden attribute (Windows)
        _set_hidden_attribute(tmp_path, 0x02)

        # Advisory lock for the whole run (Windows)
        fh.seek(0, os.SEEK_SET)
        _lock_file(fh)

        w = csv.writer(fh)
        w.writerow(["Time (s)", "Temperature (°C)", "Current (A)", "Voltage (V)", "Resistance (Ω)"])
        fh.flush()

        self._fh = fh
        self._writer = w
        self._tmp_path = tmp_path
        self._final_path = final_path
        self._n = 0
        self._t0 = None

    def row(
        self, elapsed_s: float, t_meas: float, i_meas: float, v_meas: float, r_meas: float
    ) -> None:
        """Append a measurement row to the open CSV stream.

        The first written timestamp is normalised to zero. Rows are flushed to
        disk every ``STREAM_FLUSH_EVERY`` rows.

        Args:
            elapsed_s (float): Elapsed seconds timestamp.
            t_meas (float): Temperature in °C.
            i_meas (float): Current in A.
            v_meas (float): Voltage in V.
            r_meas (float): Resistance in Ω.

        Returns:
            None
        """
        if not self._writer:
            return

        if self._t0 is None:
            self._t0 = elapsed_s
        t_out = elapsed_s - self._t0

        self._writer.writerow([t_out, t_meas, i_meas, v_meas, r_meas])
        self._n += 1
        if self._n % STREAM_FLUSH_EVERY == 0:
            self._fh.flush()

    def finalise(self) -> str | None:
        """Finalize the stream: unlock, close and atomically rename.

        Returns:
            str or None: The final CSV path if a file was finalised, otherwise None.
        """
        if not self._fh:
            return None
        try:
            _unlock_file(self._fh)
            self._fh.close()
            os.replace(self._tmp_path, self._final_path)

            # Remove Hidden attribute (Windows)
            _set_hidden_attribute(self._final_path, 0x80)
            return str(self._final_path)
        finally:
            self._fh = None
            self._writer = None
            self._tmp_path = None
            self._final_path = None
            self._n = 0
            self._t0 = None
