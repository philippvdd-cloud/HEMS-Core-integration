"""Distributes a signed power goal across devices."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .models.device_state import DeviceState
from .models.power_goal import PowerGoal
from .models.power_request import PowerRequest


@dataclass(slots=True, frozen=True)
class DevicePriority:
    """Participation entry for a single device in the Scheduler.

    ``priority`` is only used by :data:`DistributionStrategy.PRIORITY`
    (higher values are served first). It is ignored by
    :data:`DistributionStrategy.EQUAL`.
    """

    device_id: str
    priority: int


class DistributionStrategy(str, Enum):
    """How the Scheduler splits a goal across multiple devices."""

    #: Serve devices strictly in priority order; a device only
    #: receives power once every higher-priority device is maxed out.
    PRIORITY = "priority"

    #: Split the goal evenly across all participating devices. Any
    #: remainder a capacity-limited device can't take is redistributed
    #: evenly among the remaining devices (a "water filling" split),
    #: so no single device is favored over the others.
    EQUAL = "equal"


class Scheduler:
    """Turns a single power goal into per-device PowerRequests.

    A positive goal means "please absorb this much extra power"
    (e.g. charge a battery to avoid feeding PV surplus into the grid
    for free). A negative goal means "please deliver this much power"
    (e.g. discharge a battery to avoid importing from the grid).
    """

    def schedule(
        self,
        goal: PowerGoal,
        states: dict[str, DeviceState],
        priorities: list[DevicePriority],
        strategy: DistributionStrategy = DistributionStrategy.EQUAL,
    ) -> list[PowerRequest]:
        """Return the PowerRequests needed to realize the goal.

        An idle goal (``goal.is_idle``) means "the grid is balanced" -
        any device that is still actively charging/discharging is
        explicitly released back to 0 rather than left alone, so a
        previous command doesn't linger once it's no longer needed.
        This release step is the same regardless of ``strategy``.
        """

        if goal.is_idle:
            return self._release_active_devices(states, priorities, goal)

        if strategy == DistributionStrategy.PRIORITY:
            return self._schedule_priority(goal, states, priorities)

        return self._schedule_equal(goal, states, priorities)

    # -- Priority strategy -------------------------------------------

    def _schedule_priority(
        self,
        goal: PowerGoal,
        states: dict[str, DeviceState],
        priorities: list[DevicePriority],
    ) -> list[PowerRequest]:
        """Serve devices strictly in descending priority order."""

        remaining = goal.power
        requests: list[PowerRequest] = []

        ordered = sorted(
            priorities,
            key=lambda item: item.priority,
            reverse=True,
        )

        for entry in ordered:
            if remaining == 0.0:
                break

            state = states.get(entry.device_id)

            if state is None or not state.available:
                continue

            allocation = self._headroom_allocation(remaining, state)

            if (
                allocation == 0.0
                or 0.0 < abs(allocation) < state.capabilities.min_power
            ):
                continue

            requests.append(
                PowerRequest(
                    device_id=entry.device_id,
                    power=state.current_power + allocation,
                    priority=entry.priority,
                    reason=goal.reason,
                )
            )

            remaining -= allocation

        return requests

    # -- Equal (water-filling) strategy -------------------------------

    def _schedule_equal(
        self,
        goal: PowerGoal,
        states: dict[str, DeviceState],
        priorities: list[DevicePriority],
    ) -> list[PowerRequest]:
        """Split the goal evenly across all participating devices."""

        allocations = self._water_fill(
            goal.power,
            states,
            [entry.device_id for entry in priorities],
        )

        requests: list[PowerRequest] = []

        for entry in priorities:
            allocation = allocations.get(entry.device_id, 0.0)

            if allocation == 0.0:
                continue

            state = states[entry.device_id]

            if abs(allocation) < state.capabilities.min_power:
                continue

            requests.append(
                PowerRequest(
                    device_id=entry.device_id,
                    power=state.current_power + allocation,
                    priority=entry.priority,
                    reason=goal.reason,
                )
            )

        return requests

    @staticmethod
    def _water_fill(
        goal_power: float,
        states: dict[str, DeviceState],
        device_ids: list[str],
    ) -> dict[str, float]:
        """Distribute |goal_power| evenly, redistributing any spillover.

        Devices that hit their capacity limit before getting their
        equal share drop out; the remaining goal is re-split evenly
        among the devices that still have headroom, repeating until
        the goal is fully placed or nobody has headroom left.
        """

        positive = goal_power > 0
        remaining = abs(goal_power)

        candidates: list[tuple[str, float]] = []

        for device_id in device_ids:
            state = states.get(device_id)

            if state is None or not state.available:
                continue

            headroom = Scheduler._headroom(state, positive)

            if headroom > 0.0:
                candidates.append((device_id, headroom))

        allocation: dict[str, float] = {
            device_id: 0.0 for device_id, _ in candidates
        }

        active = candidates

        while active and remaining > 1e-9:
            share = remaining / len(active)
            still_active: list[tuple[str, float]] = []
            placed_this_round = 0.0

            for device_id, headroom in active:
                already = allocation[device_id]
                take = min(share, headroom - already)
                allocation[device_id] = already + take
                placed_this_round += take

                if allocation[device_id] < headroom - 1e-9:
                    still_active.append((device_id, headroom))

            remaining -= placed_this_round

            if placed_this_round <= 1e-9:
                break

            active = still_active

        sign = 1.0 if positive else -1.0

        return {
            device_id: sign * amount
            for device_id, amount in allocation.items()
            if amount > 0.0
        }

    @staticmethod
    def _headroom(state: DeviceState, positive: bool) -> float:
        """Return how much more power this device can take on.

        ``positive`` selects the direction: True for charge/absorb
        headroom, False for discharge/deliver headroom.
        """

        caps = state.capabilities

        if positive:
            if not caps.can_charge:
                return 0.0
            return max(0.0, caps.max_charge_power - max(state.current_power, 0.0))

        if not caps.can_discharge:
            return 0.0
        return max(0.0, caps.max_discharge_power - max(-state.current_power, 0.0))

    @staticmethod
    def _headroom_allocation(remaining: float, state: DeviceState) -> float:
        """Return the signed allocation for a single device (priority mode)."""

        positive = remaining > 0
        headroom = Scheduler._headroom(state, positive)
        magnitude = min(abs(remaining), headroom)

        return magnitude if positive else -magnitude

    @staticmethod
    def _release_active_devices(
        states: dict[str, DeviceState],
        priorities: list[DevicePriority],
        goal: PowerGoal,
    ) -> list[PowerRequest]:
        """Command every currently active device back down to 0 power."""

        requests: list[PowerRequest] = []

        for entry in priorities:
            state = states.get(entry.device_id)

            if state is None or not state.available:
                continue

            if state.current_power == 0.0:
                continue

            requests.append(
                PowerRequest(
                    device_id=entry.device_id,
                    power=0.0,
                    priority=entry.priority,
                    reason=goal.reason,
                )
            )

        return requests
