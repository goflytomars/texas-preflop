# Texas Preflop API

FastAPI service exposing the Texas Preflop evaluation endpoint. In the solver-integrated build the
service calls an external solver to obtain accurate win/tie/loss probabilities and expected value,
falling back to a Chen 公式近似 when the solver is unavailable.

## Requirements
- Python 3.10+
- Dependencies installed via `pip install -r requirements.txt` *(see quick start below)*
- Environment variable `SOLVER_BASE_URL` pointing to the solver service (e.g. `http://localhost:9000`); defaults to `http://solver.mock` when unset (Chen fallback only)
- Optional: `SOLVER_API_KEY`, `SOLVER_API_KEY_HEADER` (default `Authorization`), `SOLVER_API_KEY_SCHEME` (default `Bearer`) if authentication is required

## Quick Start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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

## Continuous Integration (GitHub Actions)

- Workflow file: `.github/workflows/ci.yml`
- Triggers on pushes/PRs to `main`, installs dependencies, and runs `python -m unittest src.test_app`
- Secrets you can set in **Repository Settings → Secrets and variables → Actions**:
  - `SOLVER_BASE_URL` *(optional)* – CI falls back to `http://solver.mock` when unset
  - `SOLVER_API_KEY`, `SOLVER_API_KEY_HEADER`, `SOLVER_API_KEY_SCHEME` *(optional)* for authenticated solvers
- To extend with real solver tests, provide the actual endpoint/credentials in secrets and add a
  step invoking `python -m src.cli` or live `/preflop` requests.

## Deploying on Render

1. 登录 [Render](https://dashboard.render.com/)，选择 **New → Web Service**，并连接本仓库（分支 `main`）。
2. 在 *Environment* 选择 **Python 3**，填写：
   - **Build Command** `pip install -r requirements.txt`
   - **Start Command** `uvicorn src.app:app --host 0.0.0.0 --port $PORT`
3. 在 Render 的 **Environment Variables** 中配置：
   - `SOLVER_BASE_URL`（以及 `SOLVER_API_KEY` 等，如果需要）。
4. 点击 **Create Web Service**，Render 会自动构建并部署；完成后可通过提供的 URL 访问 `/preflop`。
5. 若日志显示 solver 超时，确认环境变量指向正确的求解器，或暂时允许 fallback（默认启用）。

### 部署真实求解器（solver_service）

1. 在同一个仓库下的 `solver_service/` 提供了 Monte Carlo 版求解器。
2. 在 Render 新建一个 Web Service：
   - **Build Command** `pip install -r solver_service/requirements.txt`
   - **Start Command** `uvicorn solver_service.app:app --host 0.0.0.0 --port $PORT`
3. 部署完成后记下 Render 分配的 URL（例如 `https://preflop-solver.onrender.com`）。
4. 回到主服务（Texas Preflop API）的环境变量配置，将 `SOLVER_BASE_URL` 设置为该 URL（无需结尾 `/v1/...`）。
5. 保存后主服务会自动重启，此时访问 `/preflop` 将直接调用真实求解器，`method` 字段会显示 `solver:v1`。

## Frontend (React)

项目包含一个位于 `frontend/` 的 Vite + React 前端，可用于与 API 交互。

### 本地运行

```bash
cd frontend
npm install
# 可选：配置 API 地址（默认 https://your-preflop-service.onrender.com）
echo "VITE_API_BASE_URL=https://<your-render-main-service>" > .env.local
npm run dev
```

启动后访问 `http://localhost:5173`，输入起手牌与玩家数即可调用 `/preflop` 接口。

### Render 上部署前端

1. 在 Render 新建 **Static Site**，选择本仓库（分支 `main`）。
2. Build Command：`npm --prefix frontend install && npm --prefix frontend run build`
3. Publish Directory：`frontend/dist`
4. 在 **Environment Variables** 中配置 `VITE_API_BASE_URL=https://<your-main-service>`。
5. 部署完成后即可得到对外访问的 UI。
