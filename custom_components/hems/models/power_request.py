"""The output of the Scheduler: a concrete instruction for one device."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class PowerRequest:
    """A request to move a single device towards a target power.

    ``power`` is the absolute signed target power in watts: positive
    means "charge/consume this much", negative means
    "discharge/export this much".
    """

    device_id: str
    power: float
    priority: int
    reason: str
