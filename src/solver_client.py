"""HTTP client for the external preflop solver service."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

import httpx

from .exceptions import SolverServiceError, SolverTimeoutError
from .heuristics import Card


@dataclass
class SolverEvaluation:
    win_probability: float
    tie_probability: float
    loss_probability: float
    expected_value_bb: float
    recommendation: str | None
    confidence: float | None
    iterations: int | None
    solver_version: str | None


class SolverClient:
    """Thin wrapper around the solver HTTP API."""

    def __init__(self, base_url: str, headers: Optional[Dict[str, str]] = None) -> None:
        if base_url.endswith("/"):
            base_url = base_url[:-1]
        self._base_url = base_url
        self._headers = headers or {}

    async def evaluate(
        self,
        cards: Sequence[Card],
        players: int,
        timeout_ms: int,
    ) -> Tuple[SolverEvaluation, int]:
        url = f"{self._base_url}/v1/preflop/evaluate"
        payload = {
            "ranks": [card.rank for card in cards],
            "suits": [card.suit for card in cards],
            "players": players,
            "max_time_ms": timeout_ms,
        }

        timeout_seconds = timeout_ms / 1000.0 + 0.1
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(url, json=payload, headers=self._headers)
        except httpx.TimeoutException as exc:  # pragma: no cover - httpx handles real timeout
            raise SolverTimeoutError() from exc
        except httpx.HTTPError as exc:  # pragma: no cover - defensive guard
            raise SolverServiceError(status_code=500, message=str(exc)) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)

        if response.status_code == httpx.codes.REQUEST_TIMEOUT:
            raise SolverTimeoutError()
        if 500 <= response.status_code < 600:
            raise SolverServiceError(status_code=response.status_code)
        if response.status_code != 200:
            raise SolverServiceError(status_code=response.status_code, message=response.text)

        body = response.json()
        evaluation = SolverEvaluation(
            win_probability=body.get("win_prob", 0.0),
            tie_probability=body.get("tie_prob", 0.0),
            loss_probability=body.get("loss_prob", 0.0),
            expected_value_bb=body.get("ev_bb", 0.0),
            recommendation=body.get("recommendation"),
            confidence=body.get("confidence"),
            iterations=body.get("iterations"),
            solver_version=body.get("solver_version"),
        )
        return evaluation, latency_ms

    async def aclose(self) -> None:  # pragma: no cover - nothing persistent to close
        return None
