# Texas Preflop — Product Brief

## 概要
Texas Preflop 是一个 **德州扑克起手牌评估 API 服务**。  
目标是在 MVP 阶段提供一个 HTTP 接口，输入两张起手牌与参与人数，输出该牌的近似强度分数、分位（percentile）、以及玩法建议。

## 用户场景
- **休闲玩家**：快速查询某手牌在不同对局人数下的相对强度。  
- **开发者/集成方**：在工具、Bot、训练软件中嵌入接口，作为判断依据。  

## 功能范围 (In Scope)
- 提供一个 GET `/preflop` API。
- 输入参数：
  - `cards`：两张牌，格式如 `"As,Ad"`（A/K/Q/J/T/9…2 + s/h/d/c 表示花色）。
  - `players`：整数，范围 2–10，默认 2。
- 输出 JSON，包括：
  - `cards`：输入的牌。
  - `players`：参与人数。
  - `score`：基于 Chen 公式的分数。
  - `percentile`：粗分位（映射到 0–1）。
  - `method`：固定返回 `"chen"`，标明当前近似算法。
  - `tips`：基于分数的简短策略建议（如“Premium pair, play aggressively”）。

## 非功能范围 (Out of Scope v1)
- 精确胜率计算（基于完全枚举或蒙特卡洛）。
- 用户系统、鉴权、数据库存储。
- 前端界面。

## 算法说明
- 使用 **Chen 公式** 作为 v1 的近似算法。
- Chen 公式规则简述：
  - 高牌基准分：A=10，K=8，Q=7，J=6，T=5，其他牌=rank/2 四舍五入。
  - 对子：分数 = 基准分 × 2，最少为 5。
  - 同花：+2。
  - 连张修正：差 0 → +1，差 1 → –1，差 2 → –2，差 ≥3 → –4。
  - 小连张奖励：若最高牌 ≤6 且是连张 → +1。
- 将分数映射到分位：  
  - ≥20 → 0.99，≥16 → 0.95，≥13 → 0.90，≥10 → 0.80，≥8 → 0.70，≥6 → 0.55，≥4 → 0.40，其他 → 0.25。  
  - 多人局下调：每多 1 人分位 –0.04，下限 0.05。

## 错误处理
- 400：非法牌面或重复牌 (`invalid_cards`)。
- 400：players 参数越界 (`invalid_players`)。
- 422：缺少参数 (`missing_cards`)。

## 非功能性需求 (NFR)
- **可靠性**：输入错误时返回结构化 JSON 错误，状态码 4xx/5xx。  
- **可观测性**：启动时打印版本与方法；日志包含请求和错误原因。  
- **性能目标**：单机启动后 <1s 可用；单次查询 O(1) 时间。  

## 验收标准示例
1. Given `cards=As,Ad` & `players=2` → 返回 score ≥16, percentile ≥0.9。  
2. Given `cards=7h,2c` → 返回 percentile ≤0.55。  
3. Given `cards=As,As` → 返回 400 + `invalid_cards`。  
4. Given `players=11` → 返回 400 + `invalid_players`。  
5. Given 缺少 `cards` → 返回 422 + `missing_cards`。

## 未来扩展
- v2 引入真实胜率计算（蒙特卡洛/全枚举）。
- 增加多语言提示文案。
- 增加用户 API key 鉴权。