# MyInvestPosition

只读持仓对照工作区：拉取影子账户最新组合，读取本机 QMT 实盘持仓，输出净值指数、仓位差异和比例化操作建议。

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

## 只读 API

```powershell
py -3.11 -m app.server --host 127.0.0.1 --port 8018
```

- `GET /api/index`：返回主页主要内容，包括净值对照、仓位差异、影子目标、实盘前十大持仓和操作建议。
- `GET /`：返回可直接浏览的首页。
- `GET /health`：健康检查。

`/api/index` 只读取 `data/public/latest_comparison.json`，不会读取 `data/private/`，也不会连接 QMT。
首页 `/` 和 `/api/index` 使用同一份公开摘要数据。
如端口被占用，替换 `--port` 后重新启动即可。

如 QMT 安装路径或账号不同，在本地 `.env` 或当前 PowerShell 会话里设置：

```powershell
$env:QMT_INSTALL_PATH='D:\国金证券QMT交易端'
$env:QMT_USERDATA_PATH='D:\国金证券QMT交易端\userdata_mini'
$env:QMT_ACCOUNT_ID='你的资金账号'
```
