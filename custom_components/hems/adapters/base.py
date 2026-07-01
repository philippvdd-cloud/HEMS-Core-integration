"""Base interface every HEMS device adapter must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models.device_state import DeviceState


class DeviceAdapter(ABC):
    """Abstract base class for a controllable device adapter.

    A concrete adapter wraps exactly one controllable device (for
    example one Zendure battery, one EV charger). HEMS Core only ever
    interacts with devices through this interface, so it never needs
    to know which manufacturer or protocol is behind it.
    """

    #: Stable identifier for this device within HEMS. Does not need
    #: to match the underlying manufacturer's identifier.
    device_id: str

    @abstractmethod
    async def async_get_state(self) -> DeviceState:
        """Return the current state of the device."""

    @abstractmethod
    async def async_set_power(self, power: float) -> None:
        """Request the device to move towards the given signed power.

        ``power`` is the absolute target power in watts: positive
        means charge/consume, negative means discharge/export.

        Adapters are responsible for clamping the requested power to
        their own device's real-world capabilities before issuing the
        underlying command (HA service call, REST call, MQTT publish,
        ...).
        """
