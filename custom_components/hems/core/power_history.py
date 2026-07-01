"""Power history for HEMS."""

from __future__ import annotations

from collections import deque
from statistics import mean


class PowerHistory:
    """Store historical power values."""

    def __init__(
        self,
        max_samples: int = 300,
    ) -> None:
        """Initialize history."""

        self._history: deque[float] = deque(
            maxlen=max_samples,
        )

    def add(
        self,
        value: float,
    ) -> None:
        """Add a new sample."""

        self._history.append(value)

    def clear(self) -> None:
        """Clear history."""

        self._history.clear()

    @property
    def values(self) -> tuple[float, ...]:
        """Return all stored values."""

        return tuple(self._history)

    @property
    def latest(self) -> float:
        """Return latest value."""

        if not self._history:
            return 0.0

        return self._history[-1]

    @property
    def minimum(self) -> float:
        """Return minimum value."""

        if not self._history:
            return 0.0

        return min(self._history)

    @property
    def maximum(self) -> float:
        """Return maximum value."""

        if not self._history:
            return 0.0

        return max(self._history)

    @property
    def average(self) -> float:
        """Return average value."""

        if not self._history:
            return 0.0

        return mean(self._history)

    @property
    def samples(self) -> int:
        """Return number of stored samples."""

        return len(self._history)

    @property
    def is_full(self) -> bool:
        """Return True when history is full."""

        return len(self._history) == self._history.maxlen
