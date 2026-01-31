import math

import pytest


class FakeNumber:
    def __init__(self, value: object) -> None:
        if isinstance(value, FakeNumber):
            self.value = value.value
        else:
            self.value = float(value)  # type: ignore[arg-type]

    def __float__(self) -> float:  # pragma: no cover
        raise TypeError("FakeNumber cannot be coerced to float")

    def _v(self, other: object) -> float:
        return other.value if isinstance(other, FakeNumber) else float(other)  # type: ignore[arg-type]

    def subtract(self, other: object) -> "FakeNumber":
        return FakeNumber(self.value - self._v(other))

    def divide(self, other: object) -> "FakeNumber":
        return FakeNumber(self.value / self._v(other))

    def add(self, other: object) -> "FakeNumber":
        return FakeNumber(self.value + self._v(other))

    def multiply(self, other: object) -> "FakeNumber":
        return FakeNumber(self.value * self._v(other))

    def pow(self, other: object) -> "FakeNumber":
        return FakeNumber(self.value ** self._v(other))

    def exp(self) -> "FakeNumber":
        return FakeNumber(math.exp(self.value))

    def max(self, other: object) -> "FakeNumber":
        return FakeNumber(max(self.value, self._v(other)))


def test_gaussian_pheno_weekly_numeric_inputs_do_not_import_ee(monkeypatch):
    import importlib

    mod = importlib.import_module("modules.wheat_risk.labels")

    def _boom(name: str) -> object:
        assert name == "ee"
        raise AssertionError("should not import ee for numeric inputs")

    monkeypatch.setattr(mod.importlib, "import_module", _boom)

    out = mod.gaussian_pheno_weekly(0, 12)
    assert isinstance(out, float)


def test_gaussian_pheno_weekly_accepts_ee_number_total_weeks(monkeypatch):
    import importlib
    import sys
    from types import SimpleNamespace

    mod = importlib.import_module("modules.wheat_risk.labels")

    def _Number(x: object) -> FakeNumber:
        return x if isinstance(x, FakeNumber) else FakeNumber(x)

    fake_ee = SimpleNamespace(Number=_Number)
    monkeypatch.setitem(sys.modules, "ee", fake_ee)

    out = mod.gaussian_pheno_weekly(FakeNumber(0), FakeNumber(12))
    assert isinstance(out, FakeNumber)

    expected = mod.gaussian(
        0.0, a=0.0, b=1.0, m=(12.0 - 1.0) / 2.0, s=max(1.0, 12.0 / 6.0)
    )
    assert math.isclose(out.value, expected, rel_tol=0.0, abs_tol=1e-12)


def test_gaussian_pheno_weekly_bool_week_index_uses_ee_path(monkeypatch):
    import importlib
    from types import SimpleNamespace

    mod = importlib.import_module("modules.wheat_risk.labels")

    def _Number(x: object) -> FakeNumber:
        return x if isinstance(x, FakeNumber) else FakeNumber(x)

    fake_ee = SimpleNamespace(Number=_Number)

    calls = {"n": 0}

    def _import_module(name: str) -> object:
        assert name == "ee"
        calls["n"] += 1
        return fake_ee

    monkeypatch.setattr(mod.importlib, "import_module", _import_module)

    out = mod.gaussian_pheno_weekly(True, 12)
    assert calls["n"] == 1
    assert isinstance(out, FakeNumber)


def test_risk_weekly_requires_week_index_and_total_weeks_together(monkeypatch):
    import importlib

    mod = importlib.import_module("modules.wheat_risk.labels")

    def _boom(name: str) -> object:
        assert name == "ee"
        raise AssertionError("should fail fast before importing ee")

    monkeypatch.setattr(mod.importlib, "import_module", _boom)

    with pytest.raises(ValueError, match="week_index and total_weeks"):
        mod.risk_weekly(aoi=None, start="2020-01-01", end="2020-01-08", week_index=0)

    with pytest.raises(ValueError, match="week_index and total_weeks"):
        mod.risk_weekly(aoi=None, start="2020-01-01", end="2020-01-08", total_weeks=12)


def test_sigmoid_bounds_and_midpoint():
    from modules.wheat_risk.labels import sigmoid

    assert sigmoid(0.0) == 0.5
    assert 0.0 < sigmoid(-20.0) < 1e-8
    assert 1.0 - 1e-8 < sigmoid(20.0) < 1.0
    assert sigmoid(-1.0) < sigmoid(0.0) < sigmoid(1.0)


def test_gaussian_peaks_at_a_plus_b():
    from modules.wheat_risk.labels import gaussian

    a = 0.2
    b = 0.7
    m = 10.0
    s = 2.5

    assert gaussian(m, a=a, b=b, m=m, s=s) == a + b
    assert gaussian(m + s, a=a, b=b, m=m, s=s) < a + b
    assert math.isclose(
        gaussian(m + 1.0, a=a, b=b, m=m, s=s),
        gaussian(m - 1.0, a=a, b=b, m=m, s=s),
        rel_tol=0.0,
        abs_tol=1e-15,
    )
