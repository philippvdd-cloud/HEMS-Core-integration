"""API factory for HEMS."""

from __future__ import annotations

import aiohttp

from ..const import API_TIMEOUT, DEFAULT_PORT
from .client import HttpClient
from .ecotracker import EcoTrackerApi


def create_api(
    session: aiohttp.ClientSession,
    host: str,
    port: int = DEFAULT_PORT,
) -> EcoTrackerApi:
    """Create a configured EcoTracker API instance."""

    client = HttpClient(
        session=session,
        base_url=f"http://{host}:{port}",
        timeout=API_TIMEOUT,
    )

    return EcoTrackerApi(client)
