"""Monte Carlo based preflop solver service."""
from __future__ import annotations

import math
import random
import time
from collections import Counter
from itertools import combinations
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, conlist, validator

app = FastAPI(title="Texas Preflop Solver", version="solver-mc-0.1")


ALL_RANKS = "23456789TJQKA"
ALL_SUITS = "cdhs"
ALL_CARDS = [r + s for r in ALL_RANKS for s in ALL_SUITS]
RANK_TO_VALUE = {rank: index + 2 for index, rank in enumerate(ALL_RANKS)}


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
    try:
        result, actual_iterations, duration_ms = _simulate(
            hero_cards,
            request.players,
            iterations,
            request.max_time_ms,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_cards", "detail": str(exc)}) from exc

    win_prob = result["win"]
    tie_prob = result["tie"]
    loss_prob = max(0.0, 1.0 - win_prob - tie_prob)
    ev_bb = _estimate_ev(win_prob, loss_prob, request.players)
    recommendation = _recommendation(win_prob)
    confidence = _confidence(win_prob, actual_iterations, duration_ms, request.max_time_ms)

    return SolverResponse(
        win_prob=round(win_prob, 4),
        tie_prob=round(tie_prob, 4),
        loss_prob=round(loss_prob, 4),
        ev_bb=round(ev_bb, 3),
        recommendation=recommendation,
        confidence=round(confidence, 3),
        iterations=actual_iterations,
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
    base = max_time_ms * 60
    scaled = int(base / max(players, 2))
    return int(max(3000, min(50000, scaled)))


def _simulate(
    hero_cards: List[str],
    players: int,
    iterations: int,
    max_time_ms: int,
) -> tuple[dict[str, float], int, int]:
    deck_cards = [card for card in ALL_CARDS if card not in hero_cards]

    wins = 0
    ties = 0
    completed = 0
    start = time.perf_counter()

    for _ in range(iterations):
        deck = deck_cards.copy()
        random.shuffle(deck)

        board = deck[:5]
        index = 5

        hero_value = _best_hand_value(hero_cards + board)

        opponent_values = []
        for _opponent in range(players - 1):
            opp_cards = deck[index : index + 2]
            index += 2
            opponent_values.append(_best_hand_value(opp_cards + board))

        max_opponent = max(opponent_values) if opponent_values else -1

        if hero_value > max_opponent:
            wins += 1
        elif hero_value == max_opponent:
            tied = opponent_values.count(hero_value)
            ties += 1.0 / (tied + 1)

        completed += 1
        if completed % 100 == 0:
            elapsed_ms = (time.perf_counter() - start) * 1000
            if elapsed_ms >= max_time_ms:
                break

    total = float(max(completed, 1))
    duration_ms = int((time.perf_counter() - start) * 1000)
    return (
        {
            "win": wins / total,
            "tie": ties / total,
        },
        completed,
        duration_ms,
    )


def _estimate_ev(win_prob: float, loss_prob: float, players: int) -> float:
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


def _confidence(win_prob: float, iterations: int, duration_ms: int, max_time_ms: int) -> float:
    variance = win_prob * (1 - win_prob)
    std_error = math.sqrt(variance / max(iterations, 1))
    confidence = 1 - std_error * 3  # 3-sigma interval
    confidence = max(0.5, min(0.99, confidence))
    # Slight boost if runtime hit the max duration
    if duration_ms >= 0.9 * max_time_ms:
        confidence = min(0.99, confidence + 0.02)
    return confidence


def _best_hand_value(cards: List[str]) -> tuple:
    best = None
    for combo in combinations(cards, 5):
        value = _hand_value(combo)
        if best is None or value > best:
            best = value
    return best or (0, )


def _hand_value(cards: tuple[str, ...]) -> tuple:
    ranks = [RANK_TO_VALUE[card[0]] for card in cards]
    suits = [card[1] for card in cards]

    rank_counter = Counter(ranks)
    counts = sorted(rank_counter.items(), key=lambda item: (item[1], item[0]), reverse=True)
    ordered_ranks = sorted(ranks, reverse=True)

    is_flush = len(set(suits)) == 1
    straight_high = _straight_high(ranks)

    if is_flush and straight_high is not None:
        return (8, straight_high)

    if counts[0][1] == 4:
        four_rank = counts[0][0]
        kicker = max(rank for rank in ranks if rank != four_rank)
        return (7, four_rank, kicker)

    if counts[0][1] == 3 and len(counts) > 1 and counts[1][1] >= 2:
        return (6, counts[0][0], counts[1][0])

    if is_flush:
        return (5, ) + tuple(ordered_ranks)

    if straight_high is not None:
        return (4, straight_high)

    if counts[0][1] == 3:
        kickers = sorted((rank for rank in ranks if rank != counts[0][0]), reverse=True)
        return (3, counts[0][0]) + tuple(kickers)

    if counts[0][1] == 2 and len(counts) > 1 and counts[1][1] == 2:
        high_pair = counts[0][0]
        low_pair = counts[1][0]
        kicker = max(rank for rank in ranks if rank not in {high_pair, low_pair})
        ordered_pairs = tuple(sorted([high_pair, low_pair], reverse=True))
        return (2, ) + ordered_pairs + (kicker, )

    if counts[0][1] == 2:
        pair_rank = counts[0][0]
        kickers = sorted((rank for rank in ranks if rank != pair_rank), reverse=True)
        return (1, pair_rank) + tuple(kickers)

    return (0, ) + tuple(ordered_ranks)


def _straight_high(ranks: List[int]) -> Optional[int]:
    unique = sorted(set(ranks))
    if 14 in unique:
        unique.append(1)
    unique = sorted(unique)
    for i in range(len(unique) - 4):
        window = unique[i : i + 5]
        if window == list(range(window[0], window[0] + 5)):
            return window[-1] if window[-1] != 1 else 5
    return None


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("solver_service.app:app", host="0.0.0.0", port=9000, reload=False)
