"""garak adapter errors."""

from __future__ import annotations


class GarakIntegrationError(RuntimeError):
    """Base error for garak adapter failures."""


class GarakUnavailableError(GarakIntegrationError):
    """Raised when garak is not importable or executable."""


class GarakScanValidationError(GarakIntegrationError):
    """Raised when a garak scan request is invalid."""
