"""Tests for the log-log regression, which is how the platform tells a
quadratic solution from a linear one using only timings. Uses fake timings
with known exponents."""

import math

import pytest

from benchmarks import detect_complexity
from ml import predict_next

SIZES = [100, 500, 1000, 3000, 7000, 15000]


def timings(exponent, constant=1e-6, log_factor=False):
    rows = []
    for n in SIZES:
        ms = constant * (n**exponent)
        if log_factor:
            ms *= math.log2(n)
        rows.append({"n": n, "ms": ms, "ok": True})
    return rows


@pytest.mark.parametrize(
    "exponent,expected",
    [(1.0, "O(n)"), (2.0, "O(n²)"), (3.0, "O(n³)"), (0.0, "O(1)")],
)
def test_recovers_the_exponent(exponent, expected):
    result = detect_complexity(timings(exponent))
    assert result["best"] == expected
    assert result["slope"] == pytest.approx(exponent, abs=0.05)


def test_constant_factors_do_not_change_the_verdict():
    """A slow O(n) solution shouldn't be mistaken for a fast O(n²) one. That's
    why the fit is done in log space."""
    slow_linear = detect_complexity(timings(1.0, constant=1.0))
    fast_quadratic = detect_complexity(timings(2.0, constant=1e-9))
    assert slow_linear["best"] == "O(n)"
    assert fast_quadratic["best"] == "O(n²)"


def test_linearithmic_is_distinguished_from_linear():
    assert detect_complexity(timings(1.0, log_factor=True))["slope"] > (
        detect_complexity(timings(1.0))["slope"]
    )


def test_clean_fit_reports_high_confidence():
    assert detect_complexity(timings(2.0))["confidence"] > 90


def test_too_few_points_returns_nothing():
    assert detect_complexity(timings(2.0)[:2]) is None


def test_failed_runs_are_excluded():
    rows = timings(1.0)
    rows[2] = {"n": 1000, "ms": None, "ok": False}
    rows[3] = {"n": 3000, "ms": 5.0, "ok": False}
    assert detect_complexity(rows)["best"] == "O(n)"


def test_predicts_a_quadratic_blowup_before_running_it():
    """The early timeout check should fire on a quadratic solution and not on
    a linear one."""
    quadratic = timings(2.0, constant=1e-3)[:3]
    assert predict_next(quadratic, 15000)["will_timeout"] is True

    linear = timings(1.0, constant=1e-5)[:3]
    assert predict_next(linear, 15000)["will_timeout"] is False
