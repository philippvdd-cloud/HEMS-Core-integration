"""Registry and dispatcher for HEMS device adapters."""

from __future__ import annotations

import logging

from .adapters.base import DeviceAdapter
from .models.device_state import DeviceState
from .models.power_request import PowerRequest

_LOGGER = logging.getLogger(__name__)


class DeviceManager:
    """Keeps track of all registered device adapters.

    This is the only place in HEMS Core that knows concrete adapter
    instances. The Scheduler and DecisionEngine only work with
    :class:`DeviceState` and :class:`PowerRequest`.
    """

    def __init__(self) -> None:
        """Initialize an empty device manager."""

        self._adapters: dict[str, DeviceAdapter] = {}

    def register(self, adapter: DeviceAdapter) -> None:
        """Register (or replace) an adapter."""

        self._adapters[adapter.device_id] = adapter

    def unregister(self, device_id: str) -> None:
        """Remove a previously registered adapter, if present."""

        self._adapters.pop(device_id, None)

    @property
    def device_ids(self) -> tuple[str, ...]:
        """Return the ids of all currently registered devices."""

        return tuple(self._adapters)

    async def async_get_states(self) -> dict[str, DeviceState]:
        """Return the current state of every registered device.

        Devices that fail to report their state are skipped (and
        logged) rather than failing the whole update, so one broken
        device doesn't block orchestration of the others.
        """

        states: dict[str, DeviceState] = {}

        for device_id, adapter in self._adapters.items():
            try:
                states[device_id] = await adapter.async_get_state()

            except Exception:  # noqa: BLE001 - isolate per-device failures
                _LOGGER.exception(
                    "Failed to read state for device '%s'",
                    device_id,
                )

        return states

    async def async_apply(
        self,
        requests: list[PowerRequest],
    ) -> None:
        """Apply a list of power requests to their target devices."""

        for request in requests:
            adapter = self._adapters.get(request.device_id)

            if adapter is None:
                _LOGGER.warning(
                    "Ignoring power request for unknown device '%s'",
                    request.device_id,
                )
                continue

            try:
                await adapter.async_set_power(request.power)

            except Exception:  # noqa: BLE001 - isolate per-device failures
                _LOGGER.exception(
                    "Failed to apply power request to device '%s'",
                    request.device_id,
                )
