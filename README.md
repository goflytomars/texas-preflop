# Texas Preflop API

FastAPI service exposing the Texas Preflop evaluation endpoint. In the solver-integrated build the
service calls an external solver to obtain accurate win/tie/loss probabilities and expected value,
falling back to a Chen 公式近似 when the solver is unavailable.

## Requirements
- Python 3.10+
- Dependencies installed via `pip install -r requirements.txt` *(see quick start below)*
- Environment variable `SOLVER_BASE_URL` pointing to the solver service (e.g. `http://localhost:9000`)
- Optional: `SOLVER_API_KEY`, `SOLVER_API_KEY_HEADER` (default `Authorization`), `SOLVER_API_KEY_SCHEME` (default `Bearer`) if authentication is required

## Quick Start
```bash
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn httpx
export SOLVER_BASE_URL="http://localhost:9000"
# export SOLVER_API_KEY="your-token"
# export SOLVER_API_KEY_HEADER="X-API-Key"
# export SOLVER_API_KEY_SCHEME=""  # leave blank if header expects raw token
uvicorn src.app:app --reload --host 127.0.0.1 --port 8080
```

## API
`GET /preflop`

Query parameters:
- `cards` *(required)* – two cards such as `As,Ad`
- `players` *(optional)* – integer in `[2,10]`, default `2`
- `mode` *(optional)* – `solver` (default) or `heuristic`
- `timeoutMs` *(optional)* – solver timeout 100–2000 ms, default 800

Example request:
```bash
curl "http://127.0.0.1:8080/preflop?cards=As,Ad&players=6"
```

Example response (solver success):
```json
{
  "cards": "As,Ad",
  "players": 6,
  "method": "solver:v1",
  "winProbability": 0.86,
  "tieProbability": 0.01,
  "lossProbability": 0.13,
  "expectedValueBb": 2.45,
  "percentile": 0.97,
  "recommendation": "raise",
  "confidence": 0.91,
  "tips": "Premium pair, play aggressively",
  "solverLatencyMs": 112,
  "iterations": 500000,
  "fallback": null,
  "score": null
}
```

When the solver times out or returns an error, the service automatically falls back to the Chen
heuristic and annotates the response with `method="solver:v1+fallback"` and
`fallback={"reason": "timeout" | "solver_error"}`.

## Testing
```bash
./.venv/bin/python -m unittest src.test_app
```

Automated tests cover solver success, solver timeout fallback, heuristic-only mode, and validation
errors.

## Solver Smoke Test

To exercise the real solver directly (bypassing the API layer) run:

```bash
python -m src.cli "As,Ad" 6 800
```

This will issue a request to `SOLVER_BASE_URL/v1/preflop/evaluate` using the configured credentials
and print the raw solver statistics, which is useful for verifying connectivity and credentials.
