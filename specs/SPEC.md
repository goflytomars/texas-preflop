# Preflop Web/HTTP MVP Evaluation Spec

## 背景
Preflop 服务为德州扑克手牌提供实时评估结果。当前 MVP 已具备核心 API 与部署管道，本周目标是在生产环境完成验证并准备上线交接。

## 目标
- 在 5 个工作日内确认服务满足性能、稳定性、可观测性与运维交接要求。
- 输出评估报告与运行手册，确保上线后 on-call 团队可独立维护。
- 识别并缓解高风险缺陷或缺口，为正式发布做准备。

## 约束
- 不引入超出 MVP 范围的新功能。
- 仅允许修复影响上线评估的缺陷或配置项。
- 依赖的基础设施（Kubernetes 集群、监控栈、求解器服务）假定已可用。

## API
| Endpoint | Method | 描述 | 请求 | 响应 | 验证 & 错误处理 |
| --- | --- | --- | --- | --- | --- |
| `/api/v1/preflop/evaluate` | POST | 计算指定起手牌在给定位置/筹码深度下的建议动作与 EV | `{"hand": "AsKh", "position": "CO", "stackDepth": 100, "metadata": {...}}` | `{"recommendation": "raise", "confidence": 0.84, "ev": 1.25, "latencyMs": 120}` | 缺字段→400；非法组合→422；依赖失败→503（含 `retryAfter`）；所有请求附带 `requestId` 返回 |
| `/api/v1/health` | GET | 轻量健康检查供 LB 与 runbook 使用 | None | `{"status": "ok", "timestamp": "ISO-8601"}` | 当依赖降级时返回 503 并在 body 中说明关键检查失败 |
| `/api/v1/metrics` | GET | （受保护）返回聚合指标供运维复核 | `?window=15m` | `{"rps": 42, "p95LatencyMs": 210, "errorRate": 0.4, ...}` | 鉴权失败→401；内部异常→500 并记录 `correlationId` |

### API 其他要求
- P95 延迟 ≤ 250 ms（50 RPS 常态，100 RPS 突发）。
- 请求体 ≤ 32 KB，服务器对重复 payload 在 5 分钟内应视为幂等。
- 所有响应返回 `traceId` 以便链路追踪；日志需脱敏用户输入。

## 架构与依赖
- 运行于现有 Kubernetes 集群，使用 HPA 以 CPU(70%) 与自定义延迟指标自动扩缩。
- 求解器服务通过 gRPC 调用，需配置重试与熔断策略；缓存层可选（Redis）用于热点手牌。
- 监控：Prometheus + Grafana（仪表板 ID `preflop-launch`），告警通过 PagerDuty 触发。
- CI/CD：GitHub Actions 构建 → Artifact Registry → Argo Rollouts 蓝绿发布。

## 验收
1. **冒烟测试**：生产环境执行 `/health` 与三组 `/evaluate` 用例，均返回 2xx 且延迟 < 200 ms。
2. **性能测试**：在 1.5× 峰值负载下运行 30 分钟，错误率 <1%，P95 延迟 ≤ 250 ms。
3. **回滚演练**：触发一次受控失败并完成自动回滚，验证告警、通知与恢复流程。
4. **监控交接**：告警策略与仪表板由 on-call 审核通过，演练一次值班交接。
5. **安全合规**：依赖扫描无高危漏洞，Secrets 轮换计划签署确认。

## 交付物
- 更新后的 `docs/PLAN.md`、运行手册、性能报告与缺陷清单。
- Grafana 仪表板链接、PagerDuty 轮值计划、回滚剧本文档。
- 回顾会议安排与会议记录模板。

## 未决问题
- `/metrics` 是否需延伸至 BI 团队，若是需确认数据脱敏要求。
- 求解器服务是否具备多活部署以避免单点故障？
- 峰值负载期间是否需要预热缓存或长连接优化？
