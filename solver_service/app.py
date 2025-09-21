"""Monte Carlo based preflop solver service."""
from __future__ import annotations

import math
import random
import time
from typing import List, Optional

import eval7
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, conlist, validator

app = FastAPI(title="Texas Preflop Solver", version="solver-mc-0.1")


ALL_RANKS = "23456789TJQKA"
ALL_SUITS = "cdhs"
ALL_CARDS = [r + s for r in ALL_RANKS for s in ALL_SUITS]


class SolverRequest(BaseModel):
    ranks: conlist(str, min_length=2, max_length=2)
    suits: conlist(str, min_length=2, max_length=2)
    players: int = Field(..., ge=2, le=10)
    max_time_ms: int = Field(800, ge=100, le=5000)

    @validator("ranks")
    def validate_ranks(cls, value: List[str]) -> List[str]:
        upper = [rank.upper() for rank in value]
        for rank in upper:
            if rank not in ALL_RANKS:
                raise ValueError(f"invalid rank '{rank}'")
        return upper

    @validator("suits")
    def validate_suits(cls, value: List[str]) -> List[str]:
        lower = [suit.lower() for suit in value]
        for suit in lower:
            if suit not in ALL_SUITS:
                raise ValueError(f"invalid suit '{suit}'")
        return lower

    @validator("players")
    def validate_players(cls, value: int) -> int:
        if value < 2 or value > 10:
            raise ValueError("players must be between 2 and 10")
        return value

    @validator("max_time_ms")
    def validate_timeout(cls, value: int) -> int:
        if value < 100:
            raise ValueError("max_time_ms must be >= 100")
        return value


class SolverResponse(BaseModel):
    win_prob: float
    tie_prob: float
    loss_prob: float
    ev_bb: float
    recommendation: str
    confidence: float
    iterations: int
    solver_version: str


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


@app.post("/v1/preflop/evaluate", response_model=SolverResponse, responses={
    400: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
})
async def evaluate(request: SolverRequest) -> SolverResponse:
    try:
        hero_cards = _build_hero_hand(request.ranks, request.suits)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_cards", "detail": str(exc)}) from exc

    iterations = _iterations_for_budget(request.max_time_ms, request.players)
    start = time.perf_counter()
    try:
        result = _simulate(hero_cards, request.players, iterations)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_cards", "detail": str(exc)}) from exc
    duration_ms = int((time.perf_counter() - start) * 1000)

    win_prob = result["win"]
    tie_prob = result["tie"]
    loss_prob = max(0.0, 1.0 - win_prob - tie_prob)
    ev_bb = _estimate_ev(win_prob, loss_prob, request.players)
    recommendation = _recommendation(win_prob)
    confidence = _confidence(win_prob, iterations, duration_ms)

    return SolverResponse(
        win_prob=round(win_prob, 4),
        tie_prob=round(tie_prob, 4),
        loss_prob=round(loss_prob, 4),
        ev_bb=round(ev_bb, 3),
        recommendation=recommendation,
        confidence=round(confidence, 3),
        iterations=iterations,
        solver_version="solver-mc-0.1",
    )


def _build_hero_hand(ranks: List[str], suits: List[str]) -> List[str]:
    cards = []
    for rank, suit in zip(ranks, suits):
        card = f"{rank.upper()}{suit.lower()}"
        if card not in ALL_CARDS:
            raise ValueError(f"unsupported card '{card}'")
        cards.append(card)
    if cards[0] == cards[1]:
        raise ValueError("duplicate cards are not allowed")
    return cards


def _iterations_for_budget(max_time_ms: int, players: int) -> int:
    base = max_time_ms * 80  # heuristic: ~80 sims per ms under typical load
    scaled = int(base / players)
    return int(max(5000, min(60000, scaled)))


def _simulate(hero_cards: List[str], players: int, iterations: int) -> dict[str, float]:
    hero_eval_cards = [eval7.Card(card) for card in hero_cards]
    deck_cards = [card for card in ALL_CARDS if card not in hero_cards]
    deck_template = [eval7.Card(card) for card in deck_cards]

    wins = 0
    ties = 0

    for _ in range(iterations):
        deck = deck_template.copy()
        random.shuffle(deck)

        board = deck[:5]
        index = 5

        hero_value = eval7.evaluate(hero_eval_cards + board)

        opponent_values = []
        for _opponent in range(players - 1):
            opp_cards = deck[index : index + 2]
            index += 2
            opponent_values.append(eval7.evaluate(opp_cards + board))

        max_opponent = max(opponent_values) if opponent_values else -1

        if hero_value > max_opponent:
            wins += 1
        elif hero_value == max_opponent:
            # Count ties when hero matches the best opponent hand
            tied = opponent_values.count(hero_value)
            ties += 1.0 / (tied + 1)

    total = float(iterations)
    return {
        "win": wins / total,
        "tie": ties / total,
    }


def _estimate_ev(win_prob: float, loss_prob: float, players: int) -> float:
    # Simplified EV estimation: assume pot of players big blinds, hero invests 1 bb.
    pot = players
    expected_win = win_prob * pot
    expected_loss = loss_prob
    return expected_win - expected_loss


def _recommendation(win_prob: float) -> str:
    if win_prob >= 0.7:
        return "raise"
    if win_prob >= 0.5:
        return "call"
    return "fold"


def _confidence(win_prob: float, iterations: int, duration_ms: int) -> float:
    variance = win_prob * (1 - win_prob)
    std_error = math.sqrt(variance / max(iterations, 1))
    confidence = 1 - std_error * 3  # 3-sigma interval
    confidence = max(0.5, min(0.99, confidence))
    # Slight boost if runtime hit the max duration
    if duration_ms >= 0.9 * (iterations / 80):
        confidence = min(0.99, confidence + 0.02)
    return confidence


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("solver_service.app:app", host="0.0.0.0", port=9000, reload=False)
