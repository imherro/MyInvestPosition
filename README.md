# MyInvestPosition

只读持仓对照工作区：拉取影子账户最新组合，读取本机 QMT 实盘持仓，输出净值指数、仓位差异和比例化操作建议。

## 系统逻辑

本项目只做“影子账户目标仓位”和“QMT 实盘当前仓位”的只读核对，不做自动交易。

整体流程如下：

1. 上游影子账户系统先生成最新组合，公开接口为 `https://shadow.okbbc.com/api/latest`。
2. 本项目运行 `scripts/position_compare.py`，只读拉取影子账户接口，并只读连接本机 QMT。
3. 脚本把 QMT 原始资产、持仓数量、市值等敏感信息写入 `data/private/`，该目录不提交。
4. `core/decision_engine.py` 把偏差规则统一转换为 `DecisionAction`，再合并为 `DecisionSet`。
5. 脚本把可公开审计的比例化摘要和结构化决策写入 `data/public/latest_comparison.json`。
6. 脚本同时生成 `reports/latest_position_compare.md` 和日期归档报告。
7. 本地只读服务读取公开摘要，提供 `/api/index` 和首页 `/`。

数据链路是单向的：

```text
影子账户 latest API + QMT 只读查询
  -> scripts/position_compare.py
  -> data/private/ 原始私有快照
  -> core/decision_engine.py 结构化决策
  -> data/public/latest_comparison.json 公开比例摘要和 actions
  -> reports/*.md / app.server 只读页面
```

## 决策中间层

本项目的建议必须先经过统一决策中间层，再渲染为报告或页面文字。

- `core/decision_schema.py` 定义 `DecisionAction` 和 `DecisionSet`。
- `DecisionAction` 字段包括 `symbol`、`action`、`target_delta`、`priority`、`confidence`、`source`、`risk_level`、`reason`。
- `DecisionSet` 字段包括 `timestamp`、`account_id` 和 `actions`，其中 `account_id` 只允许公开脱敏值 `masked`。
- `core/trade_constraints.py` 定义 `TradeConstraint`，包括 `min_trade_unit`、`max_position`、`liquidity_score`、`tradable`、`reason`。
- `TradeConstraint` 同时包含 `timestamp` 和 `valid_until`，过期约束会在评分时降低流动性因子。
- `core/market_state.py` 根据影子账户的市场状态生成 `MarketState`，包括 `volatility`、`liquidity_regime`、`trend_regime`、`risk_sentiment`、`timestamp`。
- `core/adaptive_constraints.py` 根据市场状态动态调整交易约束：波动升高降低最高仓位，弱势状态降低风险资产约束，低流动性状态降低可交易评分。
- `core/normalized_scoring.py` 对每条 `DecisionAction` 做归一化加权评分，不再使用纯乘法模型。
- `core/decision_engine.py` 负责把不同规则输出的 action 送入评分系统，按最终 `score` 排序并取 Top N。
- `core/decision_logger.py` 记录 action、评分拆解、market state 快照和 constraint 快照，用于未来回放和漂移分析。
- `core/drift_detector.py` 计算 shadow vs real 的风险、权重、结构和防御/流动性漂移。
- `core/action_feedback.py` 定义 `ActionOutcome`，用于把 action 的预期分数和未来实际结果对齐。
- `core/score_calibration.py` 根据已实现结果校准 confidence 权重；没有真实结果时保持中性，不伪造调整。
- `core/signal_registry.py` 把规则来源映射到 `shadow_gap`、`risk_engine`、`market_alignment`、`defensive_filter` 等独立 signal。
- `core/signal_ledger.py` 记录 signal source、action、realized return 和 drift contribution。
- `core/signal_isolation.py` 按 signal source 隔离 expected score、realized return 和 drift contribution，避免 cross-contamination。
- `core/independent_calibrator.py` 对每个 signal 独立校准 confidence weight，不再使用单一全局 confidence 权重。
- `core/decision_adjustment.py` 汇总 `decision -> shadow_simulation -> outcome -> calibration` 的调整回路。
- 同一 `symbol` 的多条 action 不再直接抵消；不同来源的 `BUY`、`SELL`、`REBALANCE` 会各自保留评分和解释。
- 报告和首页使用评分后的 action 渲染自然语言，不在展示层做硬优先级覆盖。

公开 API 会同时提供：

```json
{
  "timestamp": "2026-06-22T23:23:44+08:00",
  "actions": [
    {
      "symbol": "PORTFOLIO",
      "action": "REDUCE_RISK",
      "target_delta": -1.8439,
      "priority": 0.7384,
      "confidence": 0.88,
      "source": "risk_budget_rule",
      "risk_level": "low",
      "reason": "实盘风险仓 36.84% 高于影子风险预算 35.00%",
      "score": 0.874425,
      "liquidity": 0.9,
      "tradable": true,
      "score_breakdown": {
        "priority_norm": 0.7384,
        "confidence_norm": 0.954349,
        "liquidity_norm": 0.9,
        "tradability_factor": 1.0,
        "risk_adjustment_norm": 1.0,
        "market_state_factor": 1.00275,
        "weight_priority": 0.35,
        "weight_confidence": 0.25,
        "weight_liquidity": 0.25,
        "weight_risk_adjustment": 0.15
      },
      "constraint_reason": "组合层或袖套层动作，不绑定单一证券交易单位。 波动偏高，下调单标的最高仓位。 偏防守/弱势状态，下调风险资产约束。"
    }
  ]
}
```

报告和首页里的自然语言建议只负责展示 `DecisionAction`，不再直接作为规则输出。

## 核对口径

所有公开输出都使用比例口径，不输出资金账号、总资产、持仓股数、持仓市值、盈亏金额或委托信息。

- 影子净值：直接使用影子账户接口返回的 `nav`。
- 实盘净值指数：使用本地私有基线文件计算 `当前总资产 / 基线总资产`，只公开指数，不公开金额。
- 影子风险仓：使用影子账户接口的 `risk_budget_ratio`。
- 实盘风险仓：按 `100% - 防御/现金仓比例` 计算。
- 防御/现金仓：固定包含 `CASH`、`511360.SH`，并动态加入影子账户当前标记为 `defensive` 的标的，例如 `511880.SH`。
- 核心仓：动态加入影子账户当前标记为 `core` 的标的，同时把 `159201.SZ`、`510500.SH` 作为实盘核心/质量代理口径。
- 精确主线/主题仓：只使用影子账户当前标记为 `mainline` 或 `thematic` 的精确代码。
- 相关主线代理仓：`159558.SZ`、`588200.SH`、`515880.SH`、`562500.SH`、`159667.SZ` 等只做参考展示。如果其中某个代码已经是影子账户精确主线标的，就从相关代理里移除，避免重复计算。
- 非模型卫星仓：未映射到影子账户袖套的行业、个股和零散仓位，用来识别主要腾挪来源。

## 建议生成逻辑

操作建议不是交易指令，只是基于仓位偏差生成的只读提示：

- 如果实盘风险仓高于影子账户，第一优先级是降低风险仓到影子预算附近。
- 如果防御/现金仓低于影子账户，提示先补防御仓，再考虑主线对齐。
- 如果核心仓低于影子核心目标，提示从非模型卫星仓轮入核心代理，而不是新增净风险。
- 如果精确主线/主题仓低于影子目标，提示只用腾挪资金分段对齐。
- 个股不在影子账户模型内，没有单独研究结论前不生成加仓建议。

## 页面和接口

`app.server` 是本地只读服务，默认端口使用 `8018`。

- `GET /`：HTML 首页，展示净值对照、仓位偏差、影子目标、实盘主要持仓和建议。
- `GET /api/index`：首页同源 JSON 数据，字段包括 `timestamp`、`actions`、`decision_set`、`market_state`、`trade_constraints`、`decision_log`、`decision_adjustment`、`hero`、`cards`、`sleeve_deviations`、`comparison`、`recommendations`、`shadow_allocations`、`real_top_positions`。
- `GET /health`：健康检查。

`/api/index` 和 `/` 只读取 `data/public/latest_comparison.json`，不会读取 `data/private/`，也不会连接 QMT。

## 边界

- 只读：脚本只调用 QMT 查询接口，不包含报单、撤单或交易写入入口。
- 隐私：账号、资产金额、股数、市值等原始数据只写入 `data/private/`，该目录被 Git 忽略。
- 对外：提交到 GitHub 的报告只保留比例、净值指数、仓位差异和建议。

## 运行

```powershell
py -3.11 scripts\position_compare.py
```

默认会自动：

1. 访问 `https://shadow.okbbc.com/api/latest`，如遇无斜杠 404，会重试 `https://shadow.okbbc.com/api/latest/`。
2. 从 `D:\国金证券QMT交易端\userdata_mini` 只读连接 QMT。
3. 在 `reports/latest_position_compare.md` 写入本次对照报告。
4. 在 `data/public/latest_comparison.json` 写入可公开同步的比例化摘要。

## 启动只读服务

```powershell
py -3.11 -m app.server --host 127.0.0.1 --port 8018
```

如端口被占用，替换 `--port` 后重新启动即可。

如 QMT 安装路径或账号不同，在本地 `.env` 或当前 PowerShell 会话里设置：

```powershell
$env:QMT_INSTALL_PATH='D:\国金证券QMT交易端'
$env:QMT_USERDATA_PATH='D:\国金证券QMT交易端\userdata_mini'
$env:QMT_ACCOUNT_ID='你的资金账号'
```

## 审计重点

- 检查 `scripts/position_compare.py` 是否始终只读调用 QMT，并且原始私有数据只写入 `data/private/`。
- 检查 `scripts/check_public_privacy.py` 是否覆盖公开文件中的金额、股数、账号等敏感字段。
- 检查 `app/index_api.py` 是否只消费 `data/public/latest_comparison.json`，没有读取私有目录。
- 检查仓位分类是否按影子账户当前 `sleeve` 动态识别，而不是写死过期标的。
- 检查 `core/market_state.py`、`core/adaptive_constraints.py`、`core/normalized_scoring.py` 是否进入决策链。
- 检查 `core/trade_constraints.py` 是否带时序字段，并且 stale constraint 会被降权。
- 检查 `core/decision_logger.py` 是否记录 action、score breakdown、market_state 和 constraint snapshot。
- 检查 `core/drift_detector.py` 是否能计算 shadow vs real drift。
- 检查 `core/action_feedback.py` 和 `core/score_calibration.py` 是否支持用真实 outcome 校准 score。
- 检查 `core/signal_registry.py`、`core/signal_ledger.py`、`core/signal_isolation.py`、`core/independent_calibrator.py` 是否实现 per-signal 学习，避免 global confidence collapse。
- 检查 `core/decision_adjustment.py` 是否把 decision_log 转成可回放的反馈调整结构。
- 检查 `core/decision_engine.py` 是否只输出评分后的 `DecisionAction`，以及同标的多信号是否没有被直接抵消。
- 检查报告和首页建议是否来自 `DecisionAction`，而不是直接拼接动作字符串。
