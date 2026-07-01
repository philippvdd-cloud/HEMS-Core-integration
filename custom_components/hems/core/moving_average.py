"""Moving average filter."""

from __future__ import annotations

from .filter import Filter


class MovingAverageFilter(Filter):
    """Simple moving average."""

    @property
    def value(self) -> float:
        """Return filtered value."""

        if self.count == 0:
            return 0.0

        return sum(self.values) / self.count
