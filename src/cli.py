"""Utility CLI for Texas Preflop service operations."""
from __future__ import annotations

import argparse
import asyncio
import os

from .heuristics import parse_cards
from .solver_client import SolverClient


async def _solve(cards: str, players: int, timeout_ms: int) -> None:
    base_url = os.getenv("SOLVER_BASE_URL")
    if not base_url:
        raise SystemExit("SOLVER_BASE_URL environment variable must be set")
    headers = {}
    api_key = os.getenv("SOLVER_API_KEY")
    api_header = os.getenv("SOLVER_API_KEY_HEADER", "Authorization")
    api_scheme = os.getenv("SOLVER_API_KEY_SCHEME", "Bearer")
    if api_key:
        headers[api_header] = f"{api_scheme} {api_key}".strip()

    cards_parsed = parse_cards(cards)
    client = SolverClient(base_url, headers=headers)
    result, latency_ms = await client.evaluate(cards_parsed, players, timeout_ms)

    print("Solver response:")
    print(f"  win_prob       : {result.win_probability:.4f}")
    print(f"  tie_prob       : {result.tie_probability:.4f}")
    print(f"  loss_prob      : {result.loss_probability:.4f}")
    print(f"  expected_value : {result.expected_value_bb:.4f} bb")
    print(f"  recommendation : {result.recommendation}")
    print(f"  confidence     : {result.confidence}")
    print(f"  iterations     : {result.iterations}")
    print(f"  solver_version : {result.solver_version}")
    print(f"  latency_ms     : {latency_ms}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Texas Preflop solver smoke test")
    parser.add_argument("cards", help="Two comma-separated cards, e.g. As,Ad")
    parser.add_argument("players", type=int, nargs="?", default=2, help="Number of players (2-10)")
    parser.add_argument("timeout_ms", type=int, nargs="?", default=800, help="Solver timeout in ms")
    args = parser.parse_args(argv)

    if args.players < 2 or args.players > 10:
        raise SystemExit("players must be between 2 and 10")
    if args.timeout_ms < 100:
        raise SystemExit("timeout_ms must be >= 100")

    asyncio.run(_solve(args.cards, args.players, args.timeout_ms))


if __name__ == "__main__":  # pragma: no cover
    main()
