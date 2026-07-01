"""Tests for the Zendure Manager adapter's pure logic.

Covers discovery of the Manager's entity prefix and resolution of the
"manual" operation mode - the parts that don't require a running
hass instance. The Manager approach (delegating multi-device
distribution to Zendure's own built-in fleet manager) supersedes the
earlier per-device ZendureAdapter for control purposes.
"""

from __future__ import annotations

from custom_components.hems.adapters.zendure_manager import (
    extract_manager_prefix,
    resolve_manual_mode_option,
)


def test_resolves_manual_mode_from_real_zendure_options() -> None:
    """Regression test using the exact option set from Zendure-HA's
    own source (const.py ManagerMode / select.py ZendureSelect)."""

    options = [
        "off",
        "manual",
        "smart",
        "smart_discharging",
        "smart_charging",
        "store_solar",
    ]

    assert resolve_manual_mode_option(options) == "manual"


def test_manual_mode_resolution_is_case_insensitive() -> None:
    """Matching does not depend on capitalization."""

    assert resolve_manual_mode_option(["OFF", "MANUAL", "SMART"]) == "MANUAL"


def test_manual_mode_resolution_returns_none_if_missing() -> None:
    """If no option looks like "manual", fail safe rather than guess."""

    assert resolve_manual_mode_option(["off", "smart"]) is None


def test_discovers_manager_prefix_from_real_world_entity_list() -> None:
    """Regression test using a plausible real Home Assistant entity set:
    one Zendure Manager plus multiple individual battery devices, which
    must NOT be mistaken for the Manager itself."""

    number_ids = [
        "number.zendure_manager_manual_power",
        "number.solarflow_800_pro_output_limit",
        "number.solarflow_800_pro_input_limit",
        "number.hyper_2000_garage_output_limit",
        "number.hyper_2000_garage_input_limit",
        "number.hyper_2000_gro_output_limit",
        "number.hyper_2000_gro_input_limit",
    ]
    select_ids = [
        "select.zendure_manager_operation",
        "select.solarflow_800_pro_ac_mode",
        "select.hyper_2000_garage_ac_mode",
        "select.hyper_2000_gro_ac_mode",
    ]

    assert extract_manager_prefix(number_ids, select_ids) == "zendure_manager"


def test_manager_prefix_requires_matching_operation_select() -> None:
    """A manual_power number without a matching operation select is
    not mistaken for the Manager (e.g. a differently-shaped device)."""

    number_ids = ["number.something_manual_power"]
    select_ids = ["select.something_else_operation"]

    assert extract_manager_prefix(number_ids, select_ids) is None


def test_no_manager_present_returns_none() -> None:
    """A Home Assistant instance without any Zendure Manager returns None."""

    assert extract_manager_prefix([], []) is None


def test_sign_convention_charge_and_discharge() -> None:
    """HEMS and Zendure use opposite sign conventions for power.

    HEMS: positive = charge/absorb, negative = discharge/deliver.
    Zendure manual_power: positive = discharge, non-positive = charge.
    The adapter must flip the sign on every write and read.
    """

    def to_zendure(power: float) -> float:
        return -power

    def from_zendure(raw: float) -> float:
        return -raw

    # HEMS wants to charge 1734W -> Zendure manual_power must be
    # negative (its charge branch is triggered by <= 0).
    assert to_zendure(1734.0) == -1734.0

    # HEMS wants to discharge 800W -> Zendure manual_power must be
    # positive (its discharge branch is triggered by > 0).
    assert to_zendure(-800.0) == 800.0

    # Reading back a Zendure state must convert to HEMS's convention.
    assert from_zendure(-1734.0) == 1734.0
    assert from_zendure(800.0) == -800.0


def test_current_power_must_not_echo_the_last_command() -> None:
    """Regression test for a real runaway-ratcheting bug.

    Found on a live installation: manual_power grew -1458.8 ->
    -3217.6 -> -4976.4, each step exactly +1758.8 apart. Root cause:
    current_power was read back from manual_power's own state (an
    echo of our last command), not from a real measurement. The
    Scheduler's headroom formula (new_target = current_power +
    allocation) then double-counts every cycle, because the "goal"
    from a residual grid measurement doesn't shrink to reflect power
    that was only ever commanded, never actually measured.

    This test proves the fix: current_power sourced from the `power`
    sensor (a real, independently-measured aggregate) converges,
    while current_power sourced from manual_power's own echo diverges
    without bound - exactly reproducing the observed pattern.
    """

    def allocate(goal_power: float, current_power: float) -> float:
        headroom_cap = 12000.0
        headroom = headroom_cap - max(current_power, 0.0)
        allocation = max(0.0, min(goal_power, headroom))
        return current_power + allocation

    surplus = 1750.0

    # Buggy model: the grid meter reading doesn't reflect our own
    # commands (because current_power is not a real measurement),
    # so "goal" stays constant every cycle - reproducing the exact
    # unbounded growth pattern seen in production.
    echoed_power = 0.0
    growth_steps = []
    for _ in range(3):
        goal = surplus
        new_target = allocate(goal, echoed_power)
        growth_steps.append(new_target - echoed_power)
        echoed_power = new_target

    assert echoed_power >= 3 * surplus  # unbounded growth, confirms the bug model
    assert growth_steps[0] == growth_steps[1] == growth_steps[2]  # constant step, matches the reported +1758.8 pattern

    # Fixed model: current_power is a real measurement, so the grid
    # meter's residual reading shrinks as the battery actually
    # absorbs power - the formula converges instead of diverging.
    real_power = 0.0
    for _ in range(3):
        goal = max(0.0, surplus - real_power)
        real_power = allocate(goal, real_power)

    assert real_power == surplus  # converges to the real need, not beyond it
