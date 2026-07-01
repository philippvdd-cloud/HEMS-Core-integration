"""EcoTracker REST API."""

from __future__ import annotations

from ..models import PowerData
from .client import HttpClient
from .exceptions import HemsInvalidResponseError


class EcoTrackerApi:
    """EcoTracker REST API."""

    def __init__(self, client: HttpClient) -> None:
        """Initialize the EcoTracker API."""

        self._client = client

    async def async_get_power(self) -> PowerData:
        """Return current grid power."""

        data = await self._client.get("v1/json")

        try:
            return PowerData(
                power=float(data["power"]),
            )

        except (KeyError, TypeError, ValueError) as err:
            raise HemsInvalidResponseError(
                "Invalid EcoTracker response."
            ) from err
