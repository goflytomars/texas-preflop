"""Custom exception types for the Texas Preflop service."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class PreflopValidationError(Exception):
    """Raised when an incoming request fails validation."""

    error_code: str
    detail: Optional[str] = None

    def __post_init__(self) -> None:  # pragma: no cover - simple wiring
        super().__init__(self.detail or self.error_code)


class SolverTimeoutError(Exception):
    """Raised when the external solver times out."""


class SolverServiceError(Exception):
    """Raised when the external solver returns an error response."""

    def __init__(self, status_code: int, message: str | None = None) -> None:
        self.status_code = status_code
        super().__init__(message or f"solver responded with status {status_code}")
