"""Texas Preflop API service (solver-integrated)."""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Dict, Optional, Union
from uuid import uuid4

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .exceptions import (
    PreflopValidationError,
    SolverServiceError,
    SolverTimeoutError,
)
from .heuristics import (
    Card,
    HeuristicEvaluation,
    evaluate as heuristic_evaluate,
    format_cards,
    parse_cards,
)
from .solver_client import SolverClient, SolverEvaluation

LOGGER = logging.getLogger("texas_preflop")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="Texas Preflop API", version="solver-v1")


@dataclass
class Settings:
    solver_base_url: str
    default_timeout_ms: int
    chen_fallback_enabled: bool
    solver_headers: Dict[str, str]

    @classmethod
    def from_env(cls) -> "Settings":
        base_url = os.getenv("SOLVER_BASE_URL")
        if not base_url:
            raise RuntimeError("SOLVER_BASE_URL environment variable must be set")
        default_timeout = int(os.getenv("DEFAULT_TIMEOUT_MS", "800"))
        chen_fallback = os.getenv("CHEN_FALLBACK_ENABLED", "true").lower() != "false"
        api_key = os.getenv("SOLVER_API_KEY")
        api_header = os.getenv("SOLVER_API_KEY_HEADER", "Authorization")
        api_scheme = os.getenv("SOLVER_API_KEY_SCHEME", "Bearer")
        headers: Dict[str, str] = {}
        if api_key:
            header_value = f"{api_scheme} {api_key}".strip()
            headers[api_header] = header_value
        return cls(
            solver_base_url=base_url,
            default_timeout_ms=default_timeout,
            chen_fallback_enabled=chen_fallback,
            solver_headers=headers,
        )


def get_settings() -> Settings:
    if not hasattr(app.state, "settings"):
        app.state.settings = Settings.from_env()
    return app.state.settings


class FallbackInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    reason: str


class EvaluationResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    cards: str
    players: int
    method: str
    win_probability: float = Field(alias="winProbability")
    tie_probability: float = Field(alias="tieProbability")
    loss_probability: float = Field(alias="lossProbability")
    expected_value_bb: float = Field(alias="expectedValueBb")
    percentile: float
    recommendation: str
    confidence: float
    tips: str
    solver_latency_ms: int = Field(alias="solverLatencyMs")
    iterations: Optional[int]
    fallback: Optional[FallbackInfo]
    score: Optional[int] = None  # legacy field retained for backward compatibility


class ErrorResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    error: str
    detail: Optional[str] = None
    trace_id: Optional[str] = Field(default=None, alias="trace_id")


@app.on_event("startup")
async def startup_event() -> None:
    settings = get_settings()
    LOGGER.info(
        "service=texas-preflop method=solver version=%s solver_base_url=%s",
        app.version,
        settings.solver_base_url,
    )
    app.state.solver_client = SolverClient(settings.solver_base_url, headers=settings.solver_headers)


@app.on_event("shutdown")
async def shutdown_event() -> None:  # pragma: no cover - TestClient handles cleanup
    solver_client: SolverClient | None = getattr(app.state, "solver_client", None)
    if solver_client is not None:
        await solver_client.aclose()


@app.get(
    "/preflop",
    response_model=EvaluationResponse,
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
)
async def preflop(
    cards: Optional[str] = Query(None, description="Two comma-separated cards, e.g. 'As,Ad'"),
    players: Optional[str] = Query(None, description="Number of players at the table (2-10)"),
    mode: Optional[str] = Query(None, description="Evaluation mode: solver (default) or heuristic"),
    timeout_ms: Optional[str] = Query(None, alias="timeoutMs", description="Solver timeout in milliseconds (100-2000)"),
) -> Union[EvaluationResponse, JSONResponse]:
    trace_id = str(uuid4())

    try:
        parsed_cards = _parse_cards(cards)
        player_count = _parse_players(players)
        mode_value = _parse_mode(mode)
        timeout_value = _parse_timeout(timeout_ms)
    except PreflopValidationError as exc:
        status = 422 if exc.error_code == "missing_cards" else 400
        return _error_response(status, exc.error_code, exc.detail)

    if timeout_value < 600:
        LOGGER.warning("trace_id=%s event=low_timeout timeout_ms=%s", trace_id, timeout_value)

    if mode_value == "heuristic":
        evaluation = _build_heuristic_response(parsed_cards, player_count, "chen:v1", "mode=heuristic")
        return evaluation

    solver_client: SolverClient = app.state.solver_client
    settings = get_settings()

    try:
        solver_result, latency_ms = await solver_client.evaluate(parsed_cards, player_count, timeout_value)
        response = _build_solver_response(parsed_cards, player_count, solver_result, latency_ms)
        LOGGER.info(
            "event=preflop_evaluated trace_id=%s cards=%s players=%s method=solver latency_ms=%s",
            trace_id,
            format_cards(parsed_cards),
            player_count,
            latency_ms,
        )
        return response
    except SolverTimeoutError:
        LOGGER.warning(
            "event=solver_timeout trace_id=%s cards=%s players=%s timeout_ms=%s",
            trace_id,
            format_cards(parsed_cards),
            player_count,
            timeout_value,
        )
        if not settings.chen_fallback_enabled:
            return _error_response(504, "solver_timeout", trace_id=trace_id)
        return _build_heuristic_response(parsed_cards, player_count, "solver:v1+fallback", "timeout")
    except SolverServiceError as exc:
        LOGGER.error(
            "event=solver_error trace_id=%s cards=%s players=%s status=%s",
            trace_id,
            format_cards(parsed_cards),
            player_count,
            exc.status_code,
        )
        if not settings.chen_fallback_enabled:
            return _error_response(502, "solver_unavailable", trace_id=trace_id)
        return _build_heuristic_response(parsed_cards, player_count, "solver:v1+fallback", "solver_error")
    except Exception:  # pragma: no cover - defensive guard
        LOGGER.exception("event=preflop_unhandled trace_id=%s", trace_id)
        return _error_response(500, "internal_error", trace_id=trace_id)


def _parse_cards(raw: Optional[str]) -> list[Card]:
    if raw is None:
        raise PreflopValidationError("missing_cards", "cards parameter is required")
    return parse_cards(raw)


def _parse_players(raw: Optional[str]) -> int:
    if raw is None or raw == "":
        return 2
    try:
        value = int(raw)
    except ValueError as exc:
        raise PreflopValidationError("invalid_players", "players must be an integer") from exc
    if value < 2 or value > 10:
        raise PreflopValidationError("invalid_players", "players must be between 2 and 10")
    return value


def _parse_mode(raw: Optional[str]) -> str:
    if raw is None or raw == "":
        return "solver"
    value = raw.strip().lower()
    if value not in {"solver", "heuristic"}:
        raise PreflopValidationError("invalid_query", "mode must be 'solver' or 'heuristic'")
    return value


def _parse_timeout(raw: Optional[str]) -> int:
    settings = get_settings()
    if raw is None or raw == "":
        return settings.default_timeout_ms
    try:
        value = int(raw)
    except ValueError as exc:
        raise PreflopValidationError("invalid_query", "timeoutMs must be an integer") from exc
    if value < 100 or value > 2000:
        raise PreflopValidationError("invalid_query", "timeoutMs must be between 100 and 2000")
    return value


def _build_solver_response(
    cards: list[Card],
    players: int,
    solver_result: SolverEvaluation,
    latency_ms: int,
) -> EvaluationResponse:
    win_probability = solver_result.win_probability
    percentile = _solver_percentile(win_probability, players)
    recommendation = _resolve_recommendation(solver_result, win_probability)
    tips = _tips_from_recommendation(recommendation, percentile)
    confidence = solver_result.confidence or round(min(0.99, percentile + 0.05), 2)

    return EvaluationResponse(
        cards=format_cards(cards),
        players=players,
        method="solver:v1",
        winProbability=round(win_probability, 4),
        tieProbability=round(solver_result.tie_probability, 4),
        lossProbability=round(solver_result.loss_probability, 4),
        expectedValueBb=round(solver_result.expected_value_bb, 2),
        percentile=round(percentile, 2),
        recommendation=recommendation,
        confidence=round(confidence, 2),
        tips=tips,
        solverLatencyMs=latency_ms,
        iterations=solver_result.iterations,
        fallback=None,
        score=None,
    )


def _build_heuristic_response(
    cards: list[Card],
    players: int,
    method: str,
    fallback_reason: Optional[str],
) -> EvaluationResponse:
    evaluation: HeuristicEvaluation = heuristic_evaluate(cards, players)
    fallback_payload = FallbackInfo(reason=fallback_reason) if fallback_reason else None

    return EvaluationResponse(
        cards=format_cards(cards),
        players=players,
        method=method,
        winProbability=round(evaluation.win_probability, 2),
        tieProbability=round(evaluation.tie_probability, 2),
        lossProbability=round(evaluation.loss_probability, 2),
        expectedValueBb=round(evaluation.expected_value_bb, 2),
        percentile=round(evaluation.percentile, 2),
        recommendation=evaluation.recommendation,
        confidence=round(evaluation.confidence, 2),
        tips=evaluation.tips,
        solverLatencyMs=0,
        iterations=None,
        fallback=fallback_payload,
        score=evaluation.score,
    )


def _solver_percentile(win_probability: float, players: int) -> float:
    adjusted = win_probability - 0.03 * max(0, players - 2)
    return max(adjusted, 0.05)


def _resolve_recommendation(solver_result: SolverEvaluation, win_probability: float) -> str:
    if solver_result.recommendation:
        return solver_result.recommendation.lower()
    if win_probability >= 0.75:
        return "raise"
    if win_probability >= 0.55:
        return "call"
    return "fold"


def _tips_from_recommendation(recommendation: str, percentile: float) -> str:
    if recommendation == "raise" and percentile >= 0.85:
        return "Premium pair, play aggressively"
    if recommendation == "raise":
        return "Strong value hand, apply pressure"
    if recommendation == "call" and percentile >= 0.55:
        return "Playable hand, proceed with pot control"
    if recommendation == "call":
        return "Speculative hand, proceed with caution"
    return "Low equity hand, fold preflop"


def _error_response(status_code: int, error_code: str, detail: Optional[str] = None, trace_id: Optional[str] = None) -> JSONResponse:
    payload = {"error": error_code}
    if detail is not None:
        payload["detail"] = detail
    if trace_id is not None:
        payload["trace_id"] = trace_id
    return JSONResponse(status_code=status_code, content=payload)


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    import uvicorn

    uvicorn.run("src.app:app", host="0.0.0.0", port=8080, reload=False)
