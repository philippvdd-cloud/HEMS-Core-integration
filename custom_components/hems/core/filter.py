"""Base filter implementation for HEMS."""

from __future__ import annotations

from collections import deque


class Filter:
    """Simple rolling window filter."""

    def __init__(self, window_size: int = 5) -> None:
        """Initialize the filter."""

        if window_size < 1:
            raise ValueError("window_size must be at least 1")

        self._values: deque[float] = deque(maxlen=window_size)

    def add(self, value: float) -> None:
        """Add a new sample."""

        self._values.append(value)

    def clear(self) -> None:
        """Clear all samples."""

        self._values.clear()

    @property
    def values(self) -> tuple[float, ...]:
        """Return all samples."""

        return tuple(self._values)

    @property
    def count(self) -> int:
        """Return number of samples."""

        return len(self._values)

    @property
    def is_full(self) -> bool:
        """Return True if the filter window is full."""

        return len(self._values) == self._values.maxlen

    @property
    def latest(self) -> float:
        """Return latest value."""

        return self._values[-1] if self._values else 0.0
