"""Generic async HTTP client."""

from __future__ import annotations

from typing import Any

import aiohttp

from .exceptions import HemsConnectionError, HemsResponseError


class HttpClient:
    """Generic asynchronous HTTP client."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        timeout: int = 5,
    ) -> None:
        """Initialize HTTP client."""

        self._session = session
        self._base_url = base_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def get(self, endpoint: str) -> Any:
        """Perform HTTP GET request."""

        url = f"{self._base_url}/{endpoint.lstrip('/')}"

        try:
            async with self._session.get(
                url,
                timeout=self._timeout,
            ) as response:
                response.raise_for_status()

                try:
                    return await response.json()

                except Exception as err:
                    raise HemsResponseError(
                        "Response is not valid JSON."
                    ) from err

        except aiohttp.ClientError as err:
            raise HemsConnectionError(
                f"Unable to connect to {url}"
            ) from err
