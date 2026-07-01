"""Exceptions for API communication."""

from __future__ import annotations


class HemsApiError(Exception):
    """Base API exception."""


class HemsConnectionError(HemsApiError):
    """Connection failed."""


class HemsAuthenticationError(HemsApiError):
    """Authentication failed."""


class HemsResponseError(HemsApiError):
    """Unexpected response."""


class HemsInvalidResponseError(HemsApiError):
    """The device returned an unexpected response."""
