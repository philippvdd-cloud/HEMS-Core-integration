"""Device state models for the HEMS device orchestration layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class DeviceCapabilities:
    """Static capabilities of a controllable device.

    All power values are in watts and unsigned (magnitudes only).
    """

    can_charge: bool
    can_discharge: bool
    min_power: float
    max_charge_power: float
    max_discharge_power: float


@dataclass(slots=True, frozen=True)
class DeviceState:
    """A snapshot of a controllable device's current status.

    ``current_power`` is signed: positive means the device is
    currently charging/consuming, negative means it is
    discharging/exporting.
    """

    device_id: str
    available: bool
    current_power: float
    soc: float | None
    capabilities: DeviceCapabilities
