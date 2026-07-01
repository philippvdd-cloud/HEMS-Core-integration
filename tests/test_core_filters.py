"""Tests for the low-level signal processing primitives in core/."""

from __future__ import annotations

from custom_components.hems.core.deadband_filter import DeadbandFilter
from custom_components.hems.core.filter import Filter
from custom_components.hems.core.hysteresis_filter import HysteresisFilter
from custom_components.hems.core.median_filter import MedianFilter
from custom_components.hems.core.moving_average import MovingAverageFilter
from custom_components.hems.core.power_history import PowerHistory
from custom_components.hems.core.rate_limiter import RateLimiter


def test_deadband_suppresses_small_values() -> None:
    """Values inside the deadband collapse to zero."""

    deadband = DeadbandFilter(deadband=20.0)

    assert deadband.apply(5.0) == 0.0
    assert deadband.apply(-19.9) == 0.0
    assert deadband.apply(20.0) == 0.0
    assert deadband.apply(20.1) == 20.1
    assert deadband.apply(-50.0) == -50.0


def test_hysteresis_ignores_small_changes() -> None:
    """Small oscillations around the last output are ignored."""

    hysteresis = HysteresisFilter(hysteresis=30.0)

    assert hysteresis.apply(100.0) == 100.0  # first value always applied
    assert hysteresis.apply(110.0) == 100.0  # change < hysteresis
    assert hysteresis.apply(140.0) == 140.0  # change >= hysteresis

    hysteresis.reset()
    assert hysteresis.apply(0.0) == 0.0


def test_rate_limiter_passes_first_value_unchanged() -> None:
    """Regression test: the very first reading must not be clamped."""

    limiter = RateLimiter(max_delta=100.0)

    # Without this behaviour, a real-world 3000W reading right after
    # HA startup would take ~30 update cycles to "ramp up".
    assert limiter.apply(3000.0) == 3000.0


def test_rate_limiter_clamps_subsequent_jumps() -> None:
    """After the first value, changes are limited to max_delta."""

    limiter = RateLimiter(max_delta=100.0)

    assert limiter.apply(0.0) == 0.0
    assert limiter.apply(1000.0) == 100.0
    assert limiter.apply(1000.0) == 200.0
    assert limiter.apply(-1000.0) == 100.0


def test_rate_limiter_reset() -> None:
    """After reset, the next value is passed through unchanged again."""

    limiter = RateLimiter(max_delta=100.0)
    limiter.apply(1000.0)
    limiter.reset()

    assert limiter.apply(5000.0) == 5000.0


def test_median_filter() -> None:
    """Median filter returns the median of the current window."""

    median = MedianFilter(window_size=3)

    median.add(10.0)
    median.add(100.0)
    median.add(20.0)

    assert median.value == 20.0


def test_moving_average_filter() -> None:
    """Moving average returns the mean of the current window."""

    average = MovingAverageFilter(window_size=4)

    for value in (10.0, 20.0, 30.0, 40.0):
        average.add(value)

    assert average.value == 25.0


def test_filter_window_behaviour() -> None:
    """The rolling window drops the oldest sample once full."""

    window = Filter(window_size=2)

    window.add(1.0)
    window.add(2.0)
    window.add(3.0)

    assert window.values == (2.0, 3.0)
    assert window.is_full is True
    assert window.latest == 3.0


def test_power_history_aggregates() -> None:
    """PowerHistory tracks min/max/average/sample count correctly."""

    history = PowerHistory(max_samples=3)

    for value in (100.0, 200.0, 300.0, 400.0):
        history.add(value)

    # Oldest sample (100.0) has been evicted (maxlen=3).
    assert history.samples == 3
    assert history.minimum == 200.0
    assert history.maximum == 400.0
    assert history.average == 300.0
    assert history.latest == 400.0
    assert history.is_full is True
