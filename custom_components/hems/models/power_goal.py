"""The output of the DecisionEngine: a signed power goal."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class PowerGoal:
    """A signed power goal to be distributed across devices by the Scheduler.

    Positive = "please absorb this much power" (avoid feed-in).
    Negative = "please deliver this much power" (avoid grid import).
    Zero = "the grid is balanced" - the Scheduler treats this as an
    explicit instruction to release any active device back to 0.
    """

    power: float
    reason: str

    @property
    def is_idle(self) -> bool:
        """Return True if this goal represents a balanced grid."""

        return self.power == 0.0

    @property
    def is_charge(self) -> bool:
        """Return True if this goal asks devices to absorb power."""

        return self.power > 0.0

    @property
    def is_discharge(self) -> bool:
        """Return True if this goal asks devices to deliver power."""

        return self.power < 0.0
