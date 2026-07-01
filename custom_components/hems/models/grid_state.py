"""Grid state model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GridDirection(str, Enum):
    """Current grid direction."""

    IMPORT = "import"
    EXPORT = "export"
    IDLE = "idle"


@dataclass(slots=True, frozen=True)
class GridState:
    """Processed grid state."""

    power: float

    import_power: float

    export_power: float

    direction: GridDirection

    stable: bool

    trend: float

    samples: int

    @property
    def is_importing(self) -> bool:
        """Return True if the grid is currently being imported from."""
        return self.direction is GridDirection.IMPORT

    @property
    def is_exporting(self) -> bool:
        """Return True if the grid is currently being exported to."""
        return self.direction is GridDirection.EXPORT

    @property
    def absolute_power(self) -> float:
        """Return the absolute power."""
        return abs(self.power)
