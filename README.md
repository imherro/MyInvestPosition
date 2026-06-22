# MyInvestPosition

只读持仓对照工作区：拉取影子账户最新组合，读取本机 QMT 实盘持仓，输出净值指数、仓位差异和比例化操作建议。

## 系统逻辑

本项目只做“影子账户目标仓位”和“QMT 实盘当前仓位”的只读核对，不做自动交易。

整体流程如下：

1. 上游影子账户系统先生成最新组合，公开接口为 `https://shadow.okbbc.com/api/latest`。
2. 本项目运行 `scripts/position_compare.py`，只读拉取影子账户接口，并只读连接本机 QMT。
3. 脚本把 QMT 原始资产、持仓数量、市值等敏感信息写入 `data/private/`，该目录不提交。
4. 脚本把可公开审计的比例化摘要写入 `data/public/latest_comparison.json`。
5. 脚本同时生成 `reports/latest_position_compare.md` 和日期归档报告。
6. 本地只读服务读取公开摘要，提供 `/api/index` 和首页 `/`。

数据链路是单向的：

```text
影子账户 latest API + QMT 只读查询
  -> scripts/position_compare.py
  -> data/private/ 原始私有快照
  -> data/public/latest_comparison.json 公开比例摘要
  -> reports/*.md / app.server 只读页面
```

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
- `GET /api/index`：首页同源 JSON 数据，字段包括 `hero`、`cards`、`sleeve_deviations`、`comparison`、`recommendations`、`shadow_allocations`、`real_top_positions`。
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
- 检查报告和首页建议是否来自比例偏差，而不是来自原始金额或持仓数量。
