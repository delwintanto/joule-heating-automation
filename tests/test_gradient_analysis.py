"""Tests for joule_heating.analysis.gradient_analysis — pure math functions."""

import numpy as np
import pytest

from joule_heating.analysis.gradient_analysis import (
    calculate_amplitude,
    calculate_period,
    detect_peaks_and_valleys,
    detect_sharp_temp_rise,
)

# -------------------- detect_sharp_temp_rise --------------------


class TestDetectSharpTempRise:
    def test_sharp_rise_detected(self):
        t = np.array([0, 1, 2, 3, 4])
        temp = np.array([20, 20, 20, 350, 350])
        idx = detect_sharp_temp_rise(t, temp, rise_threshold=300, max_rise_time=2)
        assert idx is not None
        assert temp[idx] - temp[0] >= 300

    def test_no_rise_returns_none(self):
        t = np.arange(10, dtype=float)
        temp = np.full(10, 25.0)
        assert detect_sharp_temp_rise(t, temp) is None

    def test_gradual_rise_below_threshold(self):
        # Temperature rises 290°C — just below default 300 threshold
        t = np.arange(10, dtype=float)
        temp = np.linspace(20, 310, 10)  # 290 spread over 9s
        assert detect_sharp_temp_rise(t, temp, rise_threshold=300, max_rise_time=2) is None

    def test_rise_too_slow(self):
        # 400°C rise but over 5s, with max_rise_time=2
        t = np.array([0, 1, 2, 3, 4, 5], dtype=float)
        temp = np.array([20, 100, 200, 300, 400, 420], dtype=float)
        assert detect_sharp_temp_rise(t, temp, rise_threshold=400, max_rise_time=2) is None

    def test_single_element(self):
        assert detect_sharp_temp_rise(np.array([0.0]), np.array([100.0])) is None


# -------------------- calculate_period --------------------


class TestCalculatePeriod:
    def test_evenly_spaced_peaks(self):
        x = np.arange(100, dtype=float)
        peaks = [10, 30, 50, 70]  # period = 20
        assert calculate_period(peaks, x) == pytest.approx(20.0)

    def test_single_peak_returns_zero(self):
        x = np.arange(10, dtype=float)
        assert calculate_period([5], x) == 0

    def test_no_peaks_returns_zero(self):
        x = np.arange(10, dtype=float)
        assert calculate_period([], x) == 0

    def test_two_peaks(self):
        x = np.arange(50, dtype=float)
        assert calculate_period([10, 25], x) == pytest.approx(15.0)

    def test_uneven_spacing(self):
        x = np.arange(100, dtype=float)
        peaks = [10, 20, 50]  # diffs: 10, 30 → mean 20
        assert calculate_period(peaks, x) == pytest.approx(20.0)


# -------------------- calculate_amplitude --------------------


class TestCalculateAmplitude:
    def test_simple_peak_valley(self):
        x = np.arange(10, dtype=float)
        y = np.array([0, 5, 10, 5, 0, 5, 10, 5, 0, 5], dtype=float)
        peaks = [2]
        valleys = [4]
        amp = calculate_amplitude(peaks, valleys, x, y)
        assert amp == pytest.approx(5.0)  # |10 - 0| / 2

    def test_empty_peaks_returns_zero(self):
        x = np.arange(10, dtype=float)
        y = np.zeros(10)
        assert calculate_amplitude([], [3, 5], x, y) == 0

    def test_empty_valleys_returns_zero(self):
        x = np.arange(10, dtype=float)
        y = np.zeros(10)
        assert calculate_amplitude([2, 4], [], x, y) == 0

    def test_no_valid_pairs(self):
        # Valley before peak — no valley after peak
        x = np.arange(10, dtype=float)
        y = np.zeros(10)
        peaks = [8]
        valleys = [2]
        assert calculate_amplitude(peaks, valleys, x, y) == 0


# -------------------- detect_peaks_and_valleys --------------------


class TestDetectPeaksAndValleys:
    def test_sinusoidal_finds_extrema(self):
        t = np.linspace(0, 4 * np.pi, 500)
        temp = 100 + 20 * np.sin(t)
        result = detect_peaks_and_valleys(t, temp, window=21, polyorder=2, prom=1.0)
        assert len(result["combined_maxima"]) >= 1
        assert len(result["combined_minima"]) >= 1
        assert "temp_smooth" in result
        assert "gradient" in result

    def test_flat_data_no_peaks(self):
        t = np.arange(100, dtype=float)
        temp = np.full(100, 50.0)
        result = detect_peaks_and_valleys(t, temp, window=21, polyorder=2, prom=1.0)
        assert len(result["combined_maxima"]) == 0
        assert len(result["combined_minima"]) == 0

    def test_result_keys_present(self):
        t = np.arange(100, dtype=float)
        temp = np.random.default_rng(42).normal(50, 0.1, 100)
        result = detect_peaks_and_valleys(t, temp)
        expected_keys = {
            "time",
            "temperature",
            "combined_maxima",
            "combined_minima",
            "temp_smooth",
            "gradient",
            "start_idx",
            "peak_valley_pairs",
        }
        assert set(result.keys()) == expected_keys

    def test_monotonic_increase_few_valleys(self):
        t = np.arange(100, dtype=float)
        temp = np.linspace(20, 500, 100)
        result = detect_peaks_and_valleys(t, temp, window=21, polyorder=2, prom=1.0)
        # Savitzky-Golay edge artifacts may produce a small number of minima
        assert len(result["combined_minima"]) <= 2
