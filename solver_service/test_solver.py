import unittest

from fastapi.testclient import TestClient

from solver_service.app import app


class SolverServiceTestCase(unittest.TestCase):
    client = TestClient(app)

    def test_basic_evaluation(self) -> None:
        payload = {
            "ranks": ["A", "A"],
            "suits": ["s", "d"],
            "players": 2,
            "max_time_ms": 800,
        }
        resp = self.client.post("/v1/preflop/evaluate", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("win_prob", data)
        self.assertGreater(data["win_prob"], 0.5)
        self.assertEqual(data["recommendation"], "raise")

    def test_invalid_card(self) -> None:
        payload = {
            "ranks": ["A", "A"],
            "suits": ["s", "s"],
            "players": 2,
            "max_time_ms": 500,
        }
        resp = self.client.post("/v1/preflop/evaluate", json=payload)
        self.assertEqual(resp.status_code, 400)

    def test_high_player_count(self) -> None:
        payload = {
            "ranks": ["7", "2"],
            "suits": ["h", "c"],
            "players": 6,
            "max_time_ms": 400,
        }
        resp = self.client.post("/v1/preflop/evaluate", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertLess(data["win_prob"], 0.5)
        self.assertIn(data["recommendation"], {"call", "fold"})


if __name__ == "__main__":
    unittest.main()
