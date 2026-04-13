"""Tests for joule_heating.data — file_name, CsvWriter, print helpers."""

import os
from datetime import datetime
from unittest.mock import patch

import pandas as pd
import pytest

from joule_heating.data.file_name import generate_filename
from joule_heating.data.print_summary import (
    _detect_ramp_pattern,
    print_steps,
    print_summary,
)
from joule_heating.data.save_data import CsvWriter

# -------------------- generate_filename --------------------


class TestGenerateFilename:
    def test_sanitises_special_chars(self, tmp_path):
        with patch("joule_heating.data.file_name.os.path.expanduser", return_value=str(tmp_path)):
            path = generate_filename('my<>:"/\\|?* sample')
        basename = os.path.basename(path)
        assert "<" not in basename
        assert ">" not in basename
        assert " " not in basename
        assert "?" not in basename
        assert "*" not in basename

    def test_tuning_suffix(self, tmp_path):
        with patch("joule_heating.data.file_name.os.path.expanduser", return_value=str(tmp_path)):
            path = generate_filename("sample", tuning=True)
        assert "_tuning_data" in os.path.basename(path)

    def test_no_tuning_suffix(self, tmp_path):
        with patch("joule_heating.data.file_name.os.path.expanduser", return_value=str(tmp_path)):
            path = generate_filename("sample", tuning=False)
        assert "_tuning_data" not in os.path.basename(path)

    def test_csv_extension(self, tmp_path):
        with patch("joule_heating.data.file_name.os.path.expanduser", return_value=str(tmp_path)):
            path = generate_filename("test")
        assert path.endswith(".csv")

    def test_date_prefix(self, tmp_path):
        with patch("joule_heating.data.file_name.os.path.expanduser", return_value=str(tmp_path)):
            path = generate_filename("test")
        date_str = datetime.now().strftime("%Y%m%d")
        assert date_str in os.path.basename(path)

    def test_creates_directory(self, tmp_path):
        target = tmp_path / "sub"
        with patch("joule_heating.data.file_name.os.path.expanduser", return_value=str(target)):
            generate_filename("test")
        assert (target / "Documents" / "Joule_Heating_Data").is_dir()

    def test_counter_on_duplicate(self, tmp_path):
        with patch("joule_heating.data.file_name.os.path.expanduser", return_value=str(tmp_path)):
            first = generate_filename("dup")
            # Create the first file so the second call sees a collision
            os.makedirs(os.path.dirname(first), exist_ok=True)
            open(first, "w", encoding="utf-8").close()  # noqa: SIM115
            second = generate_filename("dup")
        assert second != first
        assert "_1" in os.path.basename(second)


# -------------------- _detect_ramp_pattern --------------------


class TestDetectRampPattern:
    def test_no_ramp_short_list(self):
        temps = [100, 200, 300]
        durs = [10, 10, 10]
        assert _detect_ramp_pattern(temps, durs) == []

    def test_detects_uniform_ramp(self):
        # 15 steps of +10°C each, all 5s → one ramp
        temps = [100 + 10 * i for i in range(15)]
        durs = [5] * 15
        ramps = _detect_ramp_pattern(temps, durs, min_ramp_length=10)
        assert len(ramps) == 1
        start, delta, dur, length = ramps[0]
        assert start == 0
        assert delta == pytest.approx(10.0)
        assert dur == pytest.approx(5.0)
        assert length == 15

    def test_ramp_boundary_exactly_min_length(self):
        # Function requires n > min_ramp_length for loop entry, so use 11 elements
        temps = [100 + 5 * i for i in range(11)]
        durs = [3] * 11
        ramps = _detect_ramp_pattern(temps, durs, min_ramp_length=10)
        assert len(ramps) == 1

    def test_ramp_boundary_just_below_min(self):
        temps = [100 + 5 * i for i in range(9)]
        durs = [3] * 9
        ramps = _detect_ramp_pattern(temps, durs, min_ramp_length=10)
        assert len(ramps) == 0

    def test_two_distinct_ramps(self):
        # Ramp 1: 12 steps +10°C, then single step, then ramp 2: 12 steps +5°C
        ramp1 = [100 + 10 * i for i in range(12)]
        spacer = [500]
        ramp2 = [600 + 5 * i for i in range(12)]
        temps = ramp1 + spacer + ramp2
        durs = [5] * len(temps)
        ramps = _detect_ramp_pattern(temps, durs, min_ramp_length=10)
        assert len(ramps) == 2

    def test_empty_lists(self):
        assert _detect_ramp_pattern([], []) == []

    def test_negative_ramp(self):
        temps = [500 - 10 * i for i in range(12)]
        durs = [5] * 12
        ramps = _detect_ramp_pattern(temps, durs, min_ramp_length=10)
        assert len(ramps) == 1
        assert ramps[0][1] == pytest.approx(-10.0)


# -------------------- print_summary --------------------


class TestPrintSummary:
    def test_basic_output(self, capsys):
        data = pd.DataFrame(
            {
                "Time (s)": [0, 1, 2, 3],
                "Temperature (°C)": [20, 100, 200, 150],
            }
        )
        print_summary("sample_A", data, "/tmp/test.csv")
        out = capsys.readouterr().out
        assert "sample_A" in out
        assert "200.00" in out  # max temp
        assert "/tmp/test.csv" in out

    def test_pid_info_printed(self, capsys):
        data = pd.DataFrame(
            {
                "Time (s)": [0, 1],
                "Temperature (°C)": [20, 100],
            }
        )
        print_summary("s", data, "p.csv", pid_curr=5.0, pid_volt=3.0, pid_gains=(1.0, 0.5, 0.1))
        out = capsys.readouterr().out
        assert "5.0" in out
        assert "3.0" in out
        assert "Kp" in out


class TestPrintSteps:
    def test_cc_mode(self, capsys):
        print_steps([10, 20], [60, 120], cc=True)
        out = capsys.readouterr().out
        assert "Current (A)" in out
        assert "10" in out
        assert "120" in out

    def test_pid_mode(self, capsys):
        print_steps([200, 300], [60, 60], cc=False)
        out = capsys.readouterr().out
        assert "Set Temp" in out


# -------------------- CsvWriter --------------------


class TestCsvWriter:
    def test_finalise_without_start_returns_none(self):
        writer = CsvWriter("test_sample")
        assert writer.finalise() is None

    def test_start_write_finalise(self, tmp_path):
        with patch("joule_heating.data.file_name.os.path.expanduser", return_value=str(tmp_path)):
            writer = CsvWriter("csv_test")
            writer.start()
            writer.row(0.0, 100.0, 5.0, 3.0, 0.6)
            writer.row(0.1, 105.0, 5.0, 3.1, 0.62)
            path = writer.finalise()

        assert path is not None
        assert os.path.isfile(path)
        assert path.endswith(".csv")

        # Verify content
        data = pd.read_csv(path)
        assert len(data) == 2
        assert "Temperature (°C)" in data.columns

    def test_double_finalise_returns_none(self, tmp_path):
        with patch("joule_heating.data.file_name.os.path.expanduser", return_value=str(tmp_path)):
            writer = CsvWriter("double_fin")
            writer.start()
            writer.row(0.0, 50.0, 1.0, 2.0, 2.0)
            first = writer.finalise()
            second = writer.finalise()

        assert first is not None
        assert second is None

    def test_row_before_start_is_noop(self):
        writer = CsvWriter("no_start")
        # Should not raise
        writer.row(0.0, 100.0, 5.0, 3.0, 0.6)
