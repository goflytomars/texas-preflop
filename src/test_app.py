import os
import unittest
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

# Ensure configuration is available before importing the app
os.environ.setdefault("SOLVER_BASE_URL", "http://solver.test")

from src.app import app, get_settings  # noqa: E402
from src.exceptions import SolverServiceError, SolverTimeoutError  # noqa: E402
from src.solver_client import SolverEvaluation  # noqa: E402


class PreflopAPITestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def setUp(self) -> None:
        if not hasattr(app.state, "settings"):
            app.state.settings = get_settings()
        self.solver_mock = AsyncMock()
        mock_client = type("MockSolverClient", (), {})()
        mock_client.evaluate = self.solver_mock
        app.state.solver_client = mock_client

    def test_solver_success_response(self) -> None:
        evaluation = SolverEvaluation(
            win_probability=0.86,
            tie_probability=0.01,
            loss_probability=0.13,
            expected_value_bb=2.45,
            recommendation="raise",
            confidence=0.91,
            iterations=500000,
            solver_version="solver-core-2025.09.1",
        )
        self.solver_mock.return_value = (evaluation, 112)

        resp = self.client.get("/preflop", params={"cards": "As,Ad", "players": "6"})
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["method"], "solver:v1")
        self.assertAlmostEqual(payload["winProbability"], 0.86, places=2)
        self.assertEqual(payload["recommendation"], "raise")
        self.assertEqual(payload["fallback"], None)
        self.assertEqual(payload["solverLatencyMs"], 112)
        self.solver_mock.assert_awaited_once()

    def test_solver_timeout_fallback(self) -> None:
        self.solver_mock.side_effect = SolverTimeoutError()

        resp = self.client.get("/preflop", params={"cards": "As,Ad", "players": "3", "timeoutMs": "500"})
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["method"], "solver:v1+fallback")
        self.assertEqual(payload["fallback"], {"reason": "timeout"})
        self.assertEqual(payload["solverLatencyMs"], 0)
        self.assertIn("score", payload)

    def test_solver_error_without_fallback(self) -> None:
        # Disable fallback and expect 502
        app.state.settings.chen_fallback_enabled = False
        self.solver_mock.side_effect = SolverServiceError(status_code=502)

        resp = self.client.get("/preflop", params={"cards": "As,Ad"})
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(resp.json()["error"], "solver_unavailable")

        # Re-enable fallback for other tests
        app.state.settings.chen_fallback_enabled = True

    def test_mode_heuristic_bypasses_solver(self) -> None:
        resp = self.client.get("/preflop", params={"cards": "7h,2c", "mode": "heuristic"})
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["method"], "chen:v1")
        self.assertEqual(payload["fallback"], {"reason": "mode=heuristic"})
        self.assertEqual(payload["players"], 2)
        self.solver_mock.assert_not_awaited()

    def test_invalid_players_returns_400(self) -> None:
        resp = self.client.get("/preflop", params={"cards": "As,Ad", "players": "11"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "invalid_players")
        self.solver_mock.assert_not_awaited()

    def test_missing_cards_returns_422(self) -> None:
        resp = self.client.get("/preflop", params={"players": "3"})
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["error"], "missing_cards")
        self.solver_mock.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
