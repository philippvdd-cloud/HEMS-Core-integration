"""Base entity for the HEMS integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import (
    DeviceEntryType,
    DeviceInfo,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, VERSION
from .coordinator import HemsCoordinator


class HemsEntity(CoordinatorEntity[HemsCoordinator]):
    """Base entity for all HEMS entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HemsCoordinator,
    ) -> None:
        """Initialize entity."""

        super().__init__(coordinator)

        # Use the config entry id as the identifier so that each
        # configured EcoTracker gets its own device, instead of every
        # entry colliding on a single shared "hems" device.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            model="HEMS Core",
            name=coordinator.config_entry.title,
            sw_version=VERSION,
        )
