"""Tests for the Scheduler power distribution logic."""

from __future__ import annotations

from custom_components.hems.models import DeviceCapabilities, DeviceState, PowerGoal
from custom_components.hems.scheduler import (
    DevicePriority,
    DistributionStrategy,
    Scheduler,
)


def _battery(
    device_id: str,
    current_power: float = 0.0,
    max_charge: float = 2000.0,
    max_discharge: float = 2000.0,
    min_power: float = 50.0,
    available: bool = True,
) -> DeviceState:
    """Build a simple battery-like DeviceState for tests."""

    return DeviceState(
        device_id=device_id,
        available=available,
        current_power=current_power,
        soc=50.0,
        capabilities=DeviceCapabilities(
            can_charge=True,
            can_discharge=True,
            min_power=min_power,
            max_charge_power=max_charge,
            max_discharge_power=max_discharge,
        ),
    )


def _goal(power: float, reason: str = "avoid_feed_in") -> PowerGoal:
    """Build a PowerGoal for tests."""

    return PowerGoal(power=power, reason=reason)


# -- Release to zero (shared by both strategies) --------------------


def test_idle_goal_releases_active_devices() -> None:
    """An idle goal (power=0.0) explicitly releases devices back to 0."""

    scheduler = Scheduler()

    requests = scheduler.schedule(
        goal=PowerGoal(power=0.0, reason="grid_balanced"),
        states={"battery_1": _battery("battery_1", current_power=-800.0)},
        priorities=[DevicePriority(device_id="battery_1", priority=1)],
    )

    assert len(requests) == 1
    assert requests[0].power == 0.0
    assert requests[0].reason == "grid_balanced"


def test_idle_goal_produces_no_requests_when_already_idle() -> None:
    """Devices already at 0 power are not re-commanded needlessly."""

    scheduler = Scheduler()

    requests = scheduler.schedule(
        goal=PowerGoal(power=0.0, reason="grid_balanced"),
        states={"battery_1": _battery("battery_1", current_power=0.0)},
        priorities=[DevicePriority(device_id="battery_1", priority=1)],
    )

    assert requests == []


def test_idle_goal_only_releases_active_devices_among_many() -> None:
    """With multiple devices, only the actively engaged ones are released."""

    scheduler = Scheduler()

    states = {
        "battery_a": _battery("battery_a", current_power=600.0),
        "battery_b": _battery("battery_b", current_power=0.0),
    }

    requests = scheduler.schedule(
        goal=PowerGoal(power=0.0, reason="grid_balanced"),
        states=states,
        priorities=[
            DevicePriority(device_id="battery_a", priority=10),
            DevicePriority(device_id="battery_b", priority=5),
        ],
    )

    assert len(requests) == 1
    assert requests[0].device_id == "battery_a"
    assert requests[0].power == 0.0


# -- Equal (water-filling) strategy - the default --------------------


def test_equal_strategy_is_the_default() -> None:
    """schedule() uses DistributionStrategy.EQUAL unless told otherwise."""

    scheduler = Scheduler()

    states = {
        "a": _battery("a", max_charge=2000.0),
        "b": _battery("b", max_charge=2000.0),
    }
    priorities = [
        DevicePriority(device_id="a", priority=1),
        DevicePriority(device_id="b", priority=1),
    ]

    requests = scheduler.schedule(_goal(1000.0), states, priorities)
    by_device = {r.device_id: r.power for r in requests}

    assert by_device == {"a": 500.0, "b": 500.0}


def test_equal_strategy_splits_evenly_with_headroom_to_spare() -> None:
    """Three devices with plenty of headroom each get an equal third."""

    scheduler = Scheduler()

    states = {
        "a": _battery("a", max_charge=2000.0),
        "b": _battery("b", max_charge=2000.0),
        "c": _battery("c", max_charge=2000.0),
    }
    priorities = [
        DevicePriority(device_id="a", priority=1),
        DevicePriority(device_id="b", priority=1),
        DevicePriority(device_id="c", priority=1),
    ]

    requests = scheduler.schedule(
        _goal(1500.0), states, priorities,
        strategy=DistributionStrategy.EQUAL,
    )
    by_device = {r.device_id: r.power for r in requests}

    assert by_device == {"a": 500.0, "b": 500.0, "c": 500.0}


def test_equal_strategy_redistributes_capacity_limited_spillover() -> None:
    """A capacity-limited device's unmet share spills over evenly to
    the remaining devices, e.g. a small SolarFlow 800 Pro alongside
    two larger Hyper 2000 units."""

    scheduler = Scheduler()

    states = {
        "solarflow_800_pro": _battery("solarflow_800_pro", max_charge=300.0),
        "hyper_2000_garage": _battery("hyper_2000_garage", max_charge=2000.0),
        "hyper_2000_gro": _battery("hyper_2000_gro", max_charge=2000.0),
    }
    priorities = [
        DevicePriority(device_id="solarflow_800_pro", priority=1),
        DevicePriority(device_id="hyper_2000_garage", priority=1),
        DevicePriority(device_id="hyper_2000_gro", priority=1),
    ]

    requests = scheduler.schedule(
        _goal(1500.0), states, priorities,
        strategy=DistributionStrategy.EQUAL,
    )
    by_device = {r.device_id: r.power for r in requests}

    assert by_device["solarflow_800_pro"] == 300.0
    assert by_device["hyper_2000_garage"] == 600.0
    assert by_device["hyper_2000_gro"] == 600.0


def test_equal_strategy_handles_discharge() -> None:
    """A negative goal is split evenly for discharge too."""

    scheduler = Scheduler()

    states = {
        "a": _battery("a", max_discharge=1200.0),
        "b": _battery("b", max_discharge=1200.0),
    }
    priorities = [
        DevicePriority(device_id="a", priority=1),
        DevicePriority(device_id="b", priority=1),
    ]

    requests = scheduler.schedule(
        _goal(-800.0, "avoid_grid_import"), states, priorities,
        strategy=DistributionStrategy.EQUAL,
    )
    by_device = {r.device_id: r.power for r in requests}

    assert by_device == {"a": -400.0, "b": -400.0}


def test_equal_strategy_skips_allocation_below_min_power() -> None:
    """A tiny per-device share below min_power is dropped, not commanded."""

    scheduler = Scheduler()

    states = {
        "a": _battery("a", min_power=100.0),
        "b": _battery("b", min_power=100.0),
    }
    priorities = [
        DevicePriority(device_id="a", priority=1),
        DevicePriority(device_id="b", priority=1),
    ]

    # 100W total split two ways = 50W each, below each device's 100W minimum.
    requests = scheduler.schedule(
        _goal(100.0), states, priorities,
        strategy=DistributionStrategy.EQUAL,
    )

    assert requests == []


# -- Priority strategy (still available for future use) --------------


def test_priority_strategy_serves_highest_priority_first() -> None:
    """Priority strategy fills the highest-priority device before others."""

    scheduler = Scheduler()

    states = {
        "battery_a": _battery("battery_a", max_charge=1000.0),
        "battery_b": _battery("battery_b", max_charge=2000.0),
    }

    requests = scheduler.schedule(
        goal=_goal(2500.0),
        states=states,
        priorities=[
            DevicePriority(device_id="battery_a", priority=20),
            DevicePriority(device_id="battery_b", priority=10),
        ],
        strategy=DistributionStrategy.PRIORITY,
    )

    by_device = {r.device_id: r.power for r in requests}

    assert by_device["battery_a"] == 1000.0
    assert by_device["battery_b"] == 1500.0


def test_priority_strategy_negative_goal_requests_discharge() -> None:
    """A negative goal asks the priority device to deliver power."""

    scheduler = Scheduler()

    requests = scheduler.schedule(
        goal=_goal(-800.0, "avoid_grid_import"),
        states={"battery_1": _battery("battery_1", max_discharge=1200.0)},
        priorities=[DevicePriority(device_id="battery_1", priority=1)],
        strategy=DistributionStrategy.PRIORITY,
    )

    assert requests[0].power == -800.0


# -- Shared edge cases (apply to both strategies) ---------------------


def test_unavailable_device_is_skipped() -> None:
    """Devices reporting unavailable are never scheduled."""

    scheduler = Scheduler()

    requests = scheduler.schedule(
        goal=_goal(500.0),
        states={"battery_1": _battery("battery_1", available=False)},
        priorities=[DevicePriority(device_id="battery_1", priority=1)],
    )

    assert requests == []


def test_device_without_charge_capability_is_skipped_for_positive_goal() -> None:
    """A device that cannot charge is skipped when absorbing power."""

    scheduler = Scheduler()

    discharge_only = DeviceState(
        device_id="battery_1",
        available=True,
        current_power=0.0,
        soc=50.0,
        capabilities=DeviceCapabilities(
            can_charge=False,
            can_discharge=True,
            min_power=50.0,
            max_charge_power=0.0,
            max_discharge_power=2000.0,
        ),
    )

    requests = scheduler.schedule(
        goal=_goal(500.0),
        states={"battery_1": discharge_only},
        priorities=[DevicePriority(device_id="battery_1", priority=1)],
    )

    assert requests == []
