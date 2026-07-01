"""Adapter layer for HEMS.

Every controllable device (battery, EV charger, heat pump, ...) is
exposed to HEMS Core through a :class:`DeviceAdapter`. HEMS Core
itself never talks to a manufacturer's API, cloud service, or MQTT
topic directly - it only knows this interface. Concrete adapters
(Zendure, Victron, EcoFlow, generic Home Assistant entities, ...)
translate between the two.
"""

from __future__ import annotations

from .base import DeviceAdapter
from .zendure import (
    ZendureAdapter,
    discover_zendure_device_prefixes,
    extract_device_prefixes,
)
from .zendure_manager import (
    ZendureManagerAdapter,
    discover_zendure_manager_prefix,
    extract_manager_prefix,
)

__all__ = [
    "DeviceAdapter",
    "ZendureAdapter",
    "ZendureManagerAdapter",
    "discover_zendure_device_prefixes",
    "discover_zendure_manager_prefix",
    "extract_device_prefixes",
    "extract_manager_prefix",
]
