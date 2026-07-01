"""Median filter."""

from __future__ import annotations

from statistics import median

from .filter import Filter


class MedianFilter(Filter):
    """Median filter."""

    @property
    def value(self) -> float:
        """Return filtered value."""

        if self.count == 0:
            return 0.0

        return float(median(self.values))
