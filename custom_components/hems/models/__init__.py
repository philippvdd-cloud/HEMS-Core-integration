"""Data models for the HEMS integration."""

from __future__ import annotations

from dataclasses import dataclass

from .device_state import DeviceCapabilities, DeviceState
from .grid_state import GridDirection, GridState
from .power_goal import PowerGoal
from .power_request import PowerRequest

__all__ = [
    "DeviceCapabilities",
    "DeviceState",
    "GridDirection",
    "GridState",
    "PowerData",
    "PowerGoal",
    "PowerRequest",
]


@dataclass(slots=True, frozen=True)
class PowerData:
    """Raw power information as read from the EcoTracker."""

    power: float

    @property
    def grid_import(self) -> float:
        """Return current grid import in watts."""
        return self.power if self.power > 0 else 0.0

    @property
    def grid_export(self) -> float:
        """Return current grid export in watts."""
        return -self.power if self.power < 0 else 0.0

    @property
    def is_importing(self) -> bool:
        """Return True if importing energy from the grid."""
        return self.power > 0

    @property
    def is_exporting(self) -> bool:
        """Return True if exporting energy to the grid."""
        return self.power < 0

    @property
    def absolute_power(self) -> float:
        """Return the absolute power."""
        return abs(self.power)
