"""Chen formula based fallback evaluation utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

from .exceptions import PreflopValidationError

RANK_ORDER = {
    "A": 14,
    "K": 13,
    "Q": 12,
    "J": 11,
    "T": 10,
    "9": 9,
    "8": 8,
    "7": 7,
    "6": 6,
    "5": 5,
    "4": 4,
    "3": 3,
    "2": 2,
}

RANK_BASE = {
    "A": 10,
    "K": 8,
    "Q": 7,
    "J": 6,
    "T": 5,
    "9": 5,
    "8": 4,
    "7": 4,
    "6": 3,
    "5": 3,
    "4": 2,
    "3": 2,
    "2": 1,
}

VALID_SUITS = {"s", "h", "d", "c"}

PERCENTILE_CUTOFFS = (
    (20, 0.99),
    (16, 0.95),
    (13, 0.90),
    (10, 0.80),
    (8, 0.70),
    (6, 0.55),
    (4, 0.40),
)


@dataclass(frozen=True)
class Card:
    rank: str
    suit: str

    def __str__(self) -> str:  # pragma: no cover - debugging helper
        return f"{self.rank}{self.suit}"


@dataclass
class HeuristicEvaluation:
    score: int
    percentile: float
    win_probability: float
    tie_probability: float
    loss_probability: float
    expected_value_bb: float
    recommendation: str
    confidence: float
    tips: str


def parse_cards(raw_cards: str) -> List[Card]:
    parts = [part.strip() for part in raw_cards.split(",") if part.strip()]
    if len(parts) != 2:
        raise PreflopValidationError("invalid_cards", "cards must contain exactly two comma-separated entries")

    cards = [normalize_card(token) for token in parts]
    if cards[0] == cards[1]:
        raise PreflopValidationError("invalid_cards", "duplicate cards are not allowed")
    return cards


def normalize_card(token: str) -> Card:
    if len(token) != 2:
        raise PreflopValidationError("invalid_cards", "card must be exactly two characters")
    rank = token[0].upper()
    suit = token[1].lower()
    if rank not in RANK_ORDER:
        raise PreflopValidationError("invalid_cards", f"unsupported rank '{token[0]}'")
    if suit not in VALID_SUITS:
        raise PreflopValidationError("invalid_cards", f"unsupported suit '{token[1]}'")
    return Card(rank=rank, suit=suit)


def chen_score(cards: Sequence[Card]) -> int:
    first, second = cards
    if first.rank == second.rank:
        base = RANK_BASE[first.rank]
        return max(5, base * 2)

    high_rank = max((first.rank, second.rank), key=lambda r: RANK_ORDER[r])
    score = RANK_BASE[high_rank]

    if first.suit == second.suit:
        score += 2

    gap = abs(RANK_ORDER[first.rank] - RANK_ORDER[second.rank])
    if gap == 1:
        score -= 1
    elif gap == 2:
        score -= 2
    elif gap >= 3:
        score -= 4

    highest_value = max(RANK_ORDER[first.rank], RANK_ORDER[second.rank])
    if gap == 1 and highest_value <= 6:
        score += 1

    return max(score, 0)


def chen_percentile(score: int, players: int) -> float:
    for threshold, percentile in PERCENTILE_CUTOFFS:
        if score >= threshold:
            base = percentile
            break
    else:
        base = 0.25

    adjusted = base - 0.04 * max(players - 2, 0)
    return max(round(adjusted, 2), 0.05)


def _recommendation_from_percentile(percentile: float) -> str:
    if percentile >= 0.70:
        return "raise"
    if percentile >= 0.40:
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


def evaluate(cards: Sequence[Card], players: int) -> HeuristicEvaluation:
    score = chen_score(cards)
    percentile = chen_percentile(score, players)
    win_probability = percentile
    tie_probability = 0.0
    loss_probability = max(0.0, round(1 - win_probability, 2))
    recommendation = _recommendation_from_percentile(percentile)
    tips = _tips_from_recommendation(recommendation, percentile)
    confidence = round(min(0.99, percentile + 0.1), 2)
    expected_value = round((percentile - 0.5) * 4, 2)

    return HeuristicEvaluation(
        score=score,
        percentile=percentile,
        win_probability=round(win_probability, 2),
        tie_probability=tie_probability,
        loss_probability=loss_probability,
        expected_value_bb=expected_value,
        recommendation=recommendation,
        confidence=max(0.0, confidence),
        tips=tips,
    )


def format_cards(cards: Iterable[Card]) -> str:
    return ",".join(f"{card.rank}{card.suit}" for card in cards)
