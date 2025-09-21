# Texas Preflop API — 产品规格（真实求解器版）

## 1. 背景与目标
Texas Preflop 现在进入“真实求解器”阶段，需要用精确计算替代 Chen 公式近似。服务必须通过后端求解器（solver）计算起手牌在不同玩家数下的胜率、期望收益（EV）、以及推荐策略，并对外提供稳定的 HTTP API。新规格面向开发人员，约束代码实现、验证用例与运维要点。

## 2. 范围
- **功能范围**
  - 暴露 `GET /preflop` 接口，默认使用真实求解器（`method=solver:v1`）。
  - 支持 2–10 名玩家的起手牌胜率评估，返回胜率、平局率、EV、分位、策略建议。
  - 在求解器超时/异常时回退到 Chen 公式，明确标识 `method` 与 `fallback_reason`。
  - 支持可选 `mode` 参数：`solver`（默认）、`heuristic`（强制使用 Chen 公式）。
  - 记录关键日志、链路追踪、求解器性能指标。
- **非功能范围**
  - 不提供用户鉴权、持久化存储、复杂多街道决策。
  - 不实现 UI，与前端或第三方集成通过文档示例完成。

## 3. API 设计
### 3.1 请求
- **Path**：`GET /preflop`
- **Query 参数**：
  - `cards` *(必填)*：`"As,Ad"`，逗号分隔两张牌，大小写不敏感。
  - `players` *(可选)*：整数，区间 `[2, 10]`，缺省为 `2`。
  - `mode` *(可选)*：`solver` 或 `heuristic`；默认 `solver`。
  - `timeoutMs` *(可选)*：求解器计算最大等待时间，整数，范围 `100–2000`，默认 `800`。

### 3.2 成功响应 (HTTP 200)
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
  "fallback": null
}
```
字段说明：
- `method`：`solver:v1`（真实求解），`chen:v1`（回退），或 `solver:v1+fallback`。
- `winProbability`/`tieProbability`/`lossProbability`：浮点，0–1，三者之和 ≈ 1。
- `expectedValueBb`：单位为大盲注 (Big Blind) 的期望收益，浮点，两位小数。
- `percentile`：0–1，保留两位小数，基于真实胜率分布计算（详见 §5.3）。
- `recommendation`：`fold` / `call` / `raise`。
- `confidence`：0–1，代表 solver 对策略的信心（来自迭代数/误差估计，若求解器无该信息则以胜率标准差估算）。
- `tips`：面向用户的自然语言建议。
- `solverLatencyMs`：实际调用耗时；回退场景返回 `0` 并在 `fallback` 中说明。
- `iterations`：求解器迭代次数/样本量；若不可用填 `null`。
- `fallback`：`null` 或对象 `{ "reason": "timeout" | "solver_error" | "mode=heuristic" }`。

### 3.3 错误响应
| 场景 | HTTP | payload 示例 |
| --- | --- | --- |
| 缺少 `cards` | 422 | `{ "error": "missing_cards" }` |
| 非法/重复牌 | 400 | `{ "error": "invalid_cards", "detail": "duplicate or malformed cards" }` |
| `players` 越界或非整数 | 400 | `{ "error": "invalid_players" }` |
| `mode` / `timeoutMs` 非法 | 400 | `{ "error": "invalid_query" }` |
| 求解器超时且回退失败 | 504 | `{ "error": "solver_timeout", "trace_id": "..." }` |
| 求解器返回 5xx | 502 | `{ "error": "solver_unavailable", "trace_id": "..." }` |
| 未捕获异常 | 500 | `{ "error": "internal_error", "trace_id": "..." }` |

## 4. 输入校验
1. `cards`：同 MVP 版本，标准化为大写 rank + 小写 suit，并检查重复牌。
2. `players`：缺省用 2，合法范围 `[2,10]`。
3. `mode`：若提供只能是 `solver` 或 `heuristic`。
4. `timeoutMs`：若提供，解析为整数并限制在 `[100,2000]`；<600 仍允许但记录 WARNING。
5. 非法参数直接返回 4xx；不得触发求解器调用。

## 5. 真实求解器集成
### 5.1 求解器接口
- **调用方式**：HTTP POST `SOLVER_BASE_URL + /v1/preflop/evaluate`。
- **鉴权**：若设置 `SOLVER_API_KEY`，服务需在请求头 `SOLVER_API_KEY_HEADER`（默认 `Authorization`）中发送 `SOLVER_API_KEY_SCHEME` + 空格 + token；当 `SOLVER_API_KEY_SCHEME` 为空字符串时直接发送原始 token。
- **默认行为**：若未配置 `SOLVER_BASE_URL`，服务回退至 `http://solver.mock` 并始终使用 Chen fallback（方便开发/预览环境）。
- **请求**
```json
{
  "ranks": ["A", "A"],
  "suits": ["s", "d"],
  "players": 6,
  "max_time_ms": 800
}
```
- **成功响应**
```json
{
  "win_prob": 0.8621,
  "tie_prob": 0.0105,
  "loss_prob": 0.1274,
  "ev_bb": 2.446,
  "recommendation": "raise",
  "confidence": 0.91,
  "iterations": 500000,
  "solver_version": "solver-core-2025.09.1"
}
```
- **错误响应**
  - 408：超时 → 业务判定为 `timeout`。
  - 422：输入非法 → 直接映射到 502（出现代表 server 侧 bug，需监控）。
  - 5xx：视为 `solver_error`。

求解器基地址通过环境变量 `SOLVER_BASE_URL` 配置；缺省或解析失败时服务启动需报错并退出。

### 5.2 调用策略
- 使用 `async` HTTP 客户端，超时时间 `timeoutMs + 100ms`。
- 若 `mode=heuristic`，跳过求解器调用，直接 Chen 公式计算，返回 `method="chen:v1"`。
- 若求解器返回错误或超时：
  1. 记录 ERROR（包含 trace_id、cards、players、timeoutMs、status_code）。
  2. 运行 Chen 公式作为回退，`method="solver:v1+fallback"`，`fallback.reason` 记录原因。
  3. 若回退也失败（理论不应发生），返回 500/504。

### 5.3 分位与提示映射
- `percentile` = `winProbability`，按玩家数进行下调：`max(0.05, winProb - 0.03*(players-2))`，保留两位。
- `recommendation` 按求解器原始建议；若缺失，使用以下规则：
  - `winProbability >= 0.75` → `raise`
  - `0.55 <= winProbability < 0.75` → `call`
  - 否则 → `fold`
- `tips` 取决于 `recommendation` 与 `percentile`：
  - `raise` & percentile ≥ 0.85 → “Premium pair, play aggressively”。
  - `raise` & percentile < 0.85 → “Strong value hand, apply pressure”。
  - `call` → “Playable hand, proceed with pot control”。
  - `fold` → “Low equity hand, fold preflop”。
- 回退模式下沿用 Chen 公式旧映射，但需在响应中说明 `fallback.reason`。

## 6. 日志与可观测性
- 启动日志：`service=texas-preflop method=solver version=<git sha> solver_base_url=<...>`。
- 请求日志 (INFO)：`trace_id cards players method percentile solver_latency_ms fallback_reason`。
- 错误日志：
  - 求解器超时 → WARN。
  - 求解器 5xx → ERROR。
  - 业务校验失败 → INFO/WARN（含 `error_code`）。
- 指标：
  - Prometheus counter `preflop_requests_total` (labels: method, fallback_reason)。
  - Histogram `preflop_solver_latency_ms`。
  - Counter `preflop_solver_failures_total` (labels: reason)。

## 7. 非功能需求
- **可用性**：回退路径必须可用；求解器不可用时成功率 ≥ 99% 通过 Chen 公式响应。
- **性能**：
  - 平均响应时间 < `timeoutMs + 50ms`。
  - 并发 50 req/s 不降级。
- **可配置性**：`SOLVER_BASE_URL`、`DEFAULT_TIMEOUT_MS`、`CHEN_FALLBACK_ENABLED` 需支持环境变量覆盖；`SOLVER_BASE_URL` 缺省时默认指向 `http://solver.mock`。
- **安全**：若存在 `SOLVER_API_KEY`，启动时需验证配置并确保不会在日志中打印明文 token。
- **恢复**：求解器恢复后自动切换至正常模式，不需人工操作。

## 8. 开发任务拆解
1. **配置管理**：加载 `SOLVER_BASE_URL`、默认超时、是否启用 fallback 的环境变量；缺失时终止启动。
2. **客户端封装**：实现 `SolverClient`（HTTP 调用、超时、错误映射、重试=0）。
3. **服务层**：
   - 参数校验（cards, players, mode, timeoutMs）。
   - 调用求解器 → 统一转换为响应模型。
   - Chen fallback（复用现有实现，迁移为独立模块 `heuristics.py`）。
4. **模型定义**：成功/失败响应 Pydantic 模型，保持向后兼容（旧字段保留并说明）。
5. **日志与指标**：接入标准 logging + 可插拔 metrics（可先 stub）。
6. **测试**：详见下一节。
7. **文档**：更新 README、runbook、错误码列表。

## 9. 测试与验收
1. **单元**
   - cards/players/mode/timeout 校验。
   - SolverClient 正常/超时/错误解析。
   - Chen fallback 函数正确性（沿用旧测试）。
2. **集成（mock solver）**
   - 正常返回：断言响应 `method=solver:v1`, `winProbability` 与 mock 一致。
   - 超时 → fallback：`method=solver:v1+fallback`, `fallback.reason="timeout"`, solverLatencyMs=0。
   - `mode=heuristic`：跳过 solver，`method=chen:v1`。
3. **验收**
   - `cards=As,Ad&players=2` → `winProbability >= 0.80`，`recommendation=raise`。
   - `cards=7h,2c&players=2` → `winProbability <= 0.30`，`recommendation=fold`。
   - `cards=As,Ad&players=11` → 400 (`invalid_players`)。
   - `timeoutMs=50` → WARN + fallback。
   - 求解器返回 500 → fallback + WARN。
   - 缺少 `cards` → 422 (`missing_cards`)。

## 10. 未来扩展
- 扩展到翻牌/转牌/河牌（board 信息）→ 需要 solver 支持更多维度。
- 增加多语言提示文本。
- 增加用户鉴权 / 速率限制。
- 根据 solver 返回的策略拓展多动作建议（例如混合概率）。

> 本规格是落地真实求解器集成的权威指引。任何新增字段或行为必须同步更新本文件，并在 PR 中与产品/研发负责人评审确认。
