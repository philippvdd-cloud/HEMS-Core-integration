"""Tests for the HEMS data models."""

from __future__ import annotations

from custom_components.hems.models import GridDirection, GridState, PowerData


def test_power_data_import() -> None:
    """Positive power means grid import."""

    data = PowerData(power=1500.0)

    assert data.grid_import == 1500.0
    assert data.grid_export == 0.0
    assert data.is_importing is True
    assert data.is_exporting is False
    assert data.absolute_power == 1500.0


def test_power_data_export() -> None:
    """Negative power means grid export (feed-in)."""

    data = PowerData(power=-800.0)

    assert data.grid_import == 0.0
    assert data.grid_export == 800.0
    assert data.is_importing is False
    assert data.is_exporting is True
    assert data.absolute_power == 800.0


def test_grid_state_direction_helpers() -> None:
    """GridState exposes the same is_importing/is_exporting semantics."""

    importing = GridState(
        power=500.0,
        import_power=500.0,
        export_power=0.0,
        direction=GridDirection.IMPORT,
        stable=True,
        trend=0.0,
        samples=10,
    )

    exporting = GridState(
        power=-500.0,
        import_power=0.0,
        export_power=500.0,
        direction=GridDirection.EXPORT,
        stable=True,
        trend=0.0,
        samples=10,
    )

    idle = GridState(
        power=0.0,
        import_power=0.0,
        export_power=0.0,
        direction=GridDirection.IDLE,
        stable=True,
        trend=0.0,
        samples=10,
    )

    assert importing.is_importing is True
    assert importing.is_exporting is False

    assert exporting.is_importing is False
    assert exporting.is_exporting is True

    assert idle.is_importing is False
    assert idle.is_exporting is False
    assert idle.absolute_power == 0.0
