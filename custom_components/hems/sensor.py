"""Sensor platform for the HEMS integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import HemsCoordinator
from .entity import HemsEntity
from .models import GridState


@dataclass(frozen=True, kw_only=True)
class HemsSensorEntityDescription(SensorEntityDescription):
    """Description of a HEMS sensor."""

    value_fn: Callable[[GridState], float | str]


SENSOR_DESCRIPTIONS: tuple[HemsSensorEntityDescription, ...] = (
    HemsSensorEntityDescription(
        key="grid_power",
        translation_key="grid_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.power,
    ),
    HemsSensorEntityDescription(
        key="grid_import",
        translation_key="grid_import",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.import_power,
    ),
    HemsSensorEntityDescription(
        key="grid_export",
        translation_key="grid_export",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.export_power,
    ),
    HemsSensorEntityDescription(
        key="grid_trend",
        translation_key="grid_trend",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.trend,
    ),
    HemsSensorEntityDescription(
        key="grid_direction",
        translation_key="grid_direction",
        device_class=SensorDeviceClass.ENUM,
        options=["import", "export", "idle"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.direction.value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HEMS sensors."""

    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        [
            HemsSensor(
                coordinator=coordinator,
                description=description,
            )
            for description in SENSOR_DESCRIPTIONS
        ]
    )


class HemsSensor(HemsEntity, SensorEntity):
    """Representation of a HEMS sensor."""

    entity_description: HemsSensorEntityDescription

    _attr_suggested_display_precision = 0

    def __init__(
        self,
        coordinator: HemsCoordinator,
        description: HemsSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator)

        self.entity_description = description

        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{description.key}"
        )

    @property
    def native_value(self) -> float | str:
        """Return the current sensor value."""

        return self.entity_description.value_fn(
            self.coordinator.data
        )
