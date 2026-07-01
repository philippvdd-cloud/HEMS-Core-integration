"""Tests for the EnergyManager signal processing pipeline."""

from __future__ import annotations

from custom_components.hems.energy_manager import EnergyManager
from custom_components.hems.models import GridDirection, PowerData


def test_first_reading_is_not_ramped_from_zero() -> None:
    """Regression test for the rate-limiter startup bug.

    The very first measurement after Home Assistant starts must be
    reflected (almost) immediately, not clamped near zero.
    """

    manager = EnergyManager()

    state = manager.update(PowerData(power=3000.0))

    assert state.power > 0.0


def test_constant_load_settles_and_is_stable() -> None:
    """A constant load should settle at its true value and be stable."""

    manager = EnergyManager()

    state = None
    for _ in range(20):
        state = manager.update(PowerData(power=3000.0))

    assert state is not None
    assert abs(state.power - 3000.0) < 1.0
    assert state.direction == GridDirection.IMPORT
    assert state.import_power == state.power
    assert state.export_power == 0.0
    assert state.stable is True


def test_small_noise_around_zero_is_idle() -> None:
    """Sensor noise within the deadband should report as idle."""

    manager = EnergyManager()

    state = None
    for value in (5.0, -3.0, 4.0, -2.0, 3.0):
        state = manager.update(PowerData(power=value))

    assert state is not None
    assert state.direction == GridDirection.IDLE
    assert state.power == 0.0


def test_export_is_detected() -> None:
    """Negative power should be reported as export (feed-in)."""

    manager = EnergyManager()

    state = None
    for _ in range(20):
        state = manager.update(PowerData(power=-1500.0))

    assert state is not None
    assert state.direction == GridDirection.EXPORT
    assert state.export_power > 0.0
    assert state.import_power == 0.0


def test_reset_clears_state() -> None:
    """After reset, filters behave as if freshly initialized."""

    manager = EnergyManager()

    for _ in range(10):
        manager.update(PowerData(power=3000.0))

    manager.reset()

    assert manager.sample_count == 0

    # First reading after reset must again pass through unclamped.
    state = manager.update(PowerData(power=2000.0))
    assert state.power > 0.0
