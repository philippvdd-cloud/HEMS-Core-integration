"""Tests for the DecisionEngine grid-following rules."""

from __future__ import annotations

from custom_components.hems.decision_engine import (
    DEFAULT_REACTION_THRESHOLD,
    DecisionEngine,
)
from custom_components.hems.models import GridDirection, GridState


def _grid_state(power: float) -> GridState:
    """Build a GridState consistent with the given signed power."""

    if power > 0:
        direction = GridDirection.IMPORT
    elif power < 0:
        direction = GridDirection.EXPORT
    else:
        direction = GridDirection.IDLE

    return GridState(
        power=power,
        import_power=power if power > 0 else 0.0,
        export_power=-power if power < 0 else 0.0,
        direction=direction,
        stable=True,
        trend=0.0,
        samples=10,
    )


# -- Default engine (export_allowance=0.0, zero feed-in) --------------


def test_export_produces_positive_absorb_goal() -> None:
    """PV surplus should produce a goal to absorb (charge) power."""

    engine = DecisionEngine()

    goal = engine.decide(_grid_state(-1500.0))

    assert goal.power == 1500.0
    assert goal.reason == "avoid_excess_feed_in"


def test_import_produces_negative_deliver_goal() -> None:
    """Grid import should produce a goal to deliver (discharge) power."""

    engine = DecisionEngine()

    goal = engine.decide(_grid_state(800.0))

    assert goal.power == -800.0
    assert goal.reason == "avoid_grid_import"


def test_idle_produces_grid_balanced_release_goal() -> None:
    """An idle grid state produces an explicit release-to-zero goal."""

    engine = DecisionEngine()

    goal = engine.decide(_grid_state(0.0))

    assert goal.power == 0.0
    assert goal.reason == "grid_balanced"


def test_small_import_below_threshold_produces_release_goal() -> None:
    """Import below DEFAULT_REACTION_THRESHOLD is treated as balanced."""

    engine = DecisionEngine()

    small_power = DEFAULT_REACTION_THRESHOLD - 1.0

    goal = engine.decide(_grid_state(small_power))

    assert goal.power == 0.0
    assert goal.reason == "grid_balanced"


def test_small_export_below_threshold_is_within_allowance() -> None:
    """With the default (zero) allowance, tiny export still counts as
    "within allowance" rather than triggering a charge goal."""

    engine = DecisionEngine()

    small_power = -(DEFAULT_REACTION_THRESHOLD - 1.0)

    goal = engine.decide(_grid_state(small_power))

    assert goal.power == 0.0
    assert goal.reason == "within_export_allowance"


def test_custom_deadband_overrides_default() -> None:
    """A custom deadband can be narrower or wider than the default."""

    strict_engine = DecisionEngine(deadband=5.0)

    # 20W would be ignored by the default threshold, but not by a
    # tighter, custom deadband of 5W.
    goal = strict_engine.decide(_grid_state(20.0))

    assert goal.power == -20.0
    assert goal.reason == "avoid_grid_import"


# -- Export allowance (e.g. "up to 800W feed-in is fine") -------------


def test_export_within_allowance_produces_no_charge_goal() -> None:
    """Surplus at or below the allowance should not trigger charging."""

    engine = DecisionEngine(export_allowance=800.0)

    for power in (-100.0, -500.0, -800.0):
        goal = engine.decide(_grid_state(power))
        assert goal.power == 0.0
        assert goal.reason == "within_export_allowance"


def test_export_above_allowance_charges_only_the_excess() -> None:
    """Only the surplus beyond the allowance should be charged.

    Matches a real-world scenario: 2344W PV, 600W house consumption
    -> 1744W surplus, 800W allowed to flow to the grid, 944W charged.
    """

    engine = DecisionEngine(export_allowance=800.0)

    goal = engine.decide(_grid_state(-1744.0))

    assert goal.power == 944.0
    assert goal.reason == "avoid_excess_feed_in"


def test_import_is_unaffected_by_export_allowance() -> None:
    """The export allowance must not change import (deficit) behavior:
    battery should cover the full deficit regardless of PV allowance."""

    engine = DecisionEngine(export_allowance=800.0)

    goal = engine.decide(_grid_state(650.0))

    assert goal.power == -650.0
    assert goal.reason == "avoid_grid_import"


def test_no_pv_at_all_discharges_full_house_consumption() -> None:
    """With zero PV, the entire house consumption shows up as import
    and must be fully covered by the batteries."""

    engine = DecisionEngine(export_allowance=800.0)

    goal = engine.decide(_grid_state(900.0))

    assert goal.power == -900.0
    assert goal.reason == "avoid_grid_import"
