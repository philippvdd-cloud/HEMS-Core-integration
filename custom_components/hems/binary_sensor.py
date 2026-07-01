"""Binary sensor platform for the HEMS integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import HemsCoordinator
from .entity import HemsEntity
from .models import GridState


@dataclass(frozen=True, kw_only=True)
class HemsBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Description of a HEMS binary sensor."""

    value_fn: Callable[[GridState], bool]


BINARY_SENSOR_DESCRIPTIONS: tuple[HemsBinarySensorEntityDescription, ...] = (
    HemsBinarySensorEntityDescription(
        key="grid_stable",
        translation_key="grid_stable",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.stable,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HEMS binary sensors."""

    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        [
            HemsBinarySensor(
                coordinator=coordinator,
                description=description,
            )
            for description in BINARY_SENSOR_DESCRIPTIONS
        ]
    )


class HemsBinarySensor(HemsEntity, BinarySensorEntity):
    """Representation of a HEMS binary sensor."""

    entity_description: HemsBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: HemsCoordinator,
        description: HemsBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""

        super().__init__(coordinator)

        self.entity_description = description

        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{description.key}"
        )

    @property
    def is_on(self) -> bool:
        """Return True if the grid power is currently stable."""

        return self.entity_description.value_fn(
            self.coordinator.data
        )
