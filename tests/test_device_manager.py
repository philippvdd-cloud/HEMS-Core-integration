"""Tests for the DeviceManager registry/dispatcher."""

from __future__ import annotations

from custom_components.hems.adapters.base import DeviceAdapter
from custom_components.hems.device_manager import DeviceManager
from custom_components.hems.models import (
    DeviceCapabilities,
    DeviceState,
    PowerRequest,
)


class _MockAdapter(DeviceAdapter):
    """A fake device adapter for testing the DeviceManager."""

    def __init__(self, device_id: str, fail: bool = False) -> None:
        self.device_id = device_id
        self._fail = fail
        self.current_power = 0.0
        self.set_calls: list[float] = []

    async def async_get_state(self) -> DeviceState:
        if self._fail:
            raise RuntimeError("simulated read failure")

        return DeviceState(
            device_id=self.device_id,
            available=True,
            current_power=self.current_power,
            soc=50.0,
            capabilities=DeviceCapabilities(
                can_charge=True,
                can_discharge=True,
                min_power=50.0,
                max_charge_power=2000.0,
                max_discharge_power=2000.0,
            ),
        )

    async def async_set_power(self, power: float) -> None:
        if self._fail:
            raise RuntimeError("simulated write failure")

        self.set_calls.append(power)
        self.current_power = power


async def test_register_and_get_states() -> None:
    """Registered adapters show up in async_get_states()."""

    manager = DeviceManager()
    adapter = _MockAdapter("battery_1")
    manager.register(adapter)

    assert manager.device_ids == ("battery_1",)

    states = await manager.async_get_states()

    assert "battery_1" in states
    assert states["battery_1"].device_id == "battery_1"


async def test_unregister_removes_device() -> None:
    """Unregistering a device removes it from the manager."""

    manager = DeviceManager()
    manager.register(_MockAdapter("battery_1"))
    manager.unregister("battery_1")

    assert manager.device_ids == ()


async def test_apply_dispatches_to_correct_adapter() -> None:
    """async_apply() calls async_set_power on the right adapter."""

    manager = DeviceManager()
    adapter = _MockAdapter("battery_1")
    manager.register(adapter)

    await manager.async_apply(
        [PowerRequest(device_id="battery_1", power=750.0, priority=1, reason="x")]
    )

    assert adapter.set_calls == [750.0]


async def test_apply_ignores_unknown_device() -> None:
    """A PowerRequest for an unregistered device is safely ignored."""

    manager = DeviceManager()

    # Should not raise.
    await manager.async_apply(
        [PowerRequest(device_id="ghost", power=100.0, priority=1, reason="x")]
    )


async def test_failing_adapter_does_not_break_get_states() -> None:
    """A device that fails to report its state is skipped, not fatal."""

    manager = DeviceManager()
    manager.register(_MockAdapter("broken", fail=True))
    manager.register(_MockAdapter("healthy"))

    states = await manager.async_get_states()

    assert "broken" not in states
    assert "healthy" in states


async def test_failing_adapter_does_not_break_apply() -> None:
    """A device that fails to accept a power request doesn't crash apply()."""

    manager = DeviceManager()
    broken = _MockAdapter("broken", fail=True)
    healthy = _MockAdapter("healthy")
    manager.register(broken)
    manager.register(healthy)

    # Should not raise, even though "broken" raises internally.
    await manager.async_apply(
        [
            PowerRequest(device_id="broken", power=100.0, priority=1, reason="x"),
            PowerRequest(device_id="healthy", power=200.0, priority=1, reason="x"),
        ]
    )

    assert healthy.set_calls == [200.0]
