"""Tests for NamedTuples: Devices, Measurement, ExperimentCallbacks."""

from joule_heating.devices import Devices, Measurement
from joule_heating.gui.common import ExperimentCallbacks


class TestDevices:
    def test_construction_and_access(self):
        d = Devices(power_supply="psu", ycr_sensor="ycr", optris_sensor="opt")
        assert d.power_supply == "psu"
        assert d.ycr_sensor == "ycr"
        assert d.optris_sensor == "opt"

    def test_tuple_unpacking(self):
        psu, ycr, opt = Devices("p", "y", "o")
        assert psu == "p"
        assert ycr == "y"
        assert opt == "o"

    def test_none_sensors(self):
        d = Devices(power_supply="psu", ycr_sensor=None, optris_sensor=None)
        assert d.ycr_sensor is None
        assert d.optris_sensor is None


class TestMeasurement:
    def test_fields(self):
        m = Measurement(temperature=100.0, voltage=5.0, current=3.0, resistance=1.67)
        assert m.temperature == 100.0
        assert m.voltage == 5.0
        assert m.current == 3.0
        assert m.resistance == 1.67

    def test_zero_current_inf_resistance(self):
        m = Measurement(temperature=25.0, voltage=0.0, current=0.0, resistance=float("inf"))
        assert m.resistance == float("inf")


class TestExperimentCallbacks:
    def test_defaults_all_none(self):
        cb = ExperimentCallbacks()
        assert cb.status is None
        assert cb.skip_check is None
        assert cb.update_plot is None

    def test_custom_callbacks(self):
        def status_fn(**_kw):
            pass

        def skip_fn():
            return False

        cb = ExperimentCallbacks(status=status_fn, skip_check=skip_fn)
        assert cb.status is status_fn
        assert cb.skip_check is skip_fn
        assert cb.update_plot is None
