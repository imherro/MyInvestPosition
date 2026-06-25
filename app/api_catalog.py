from __future__ import annotations

from html import escape
from typing import Any


SYSTEM_NAME = "MyInvestPosition"
SYSTEM_VERSION = "0.2.0"
SYSTEM_DESCRIPTION = "影子账户目标仓位与 QMT 实盘当前仓位的只读核对系统。"


def _endpoint(
    method: str,
    path: str,
    purpose: str,
    response: str,
    parameters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "method": method,
        "path": path,
        "purpose": purpose,
        "parameters": parameters or [],
        "response": response,
        "read_only": True,
    }


GROUPS: list[dict[str, Any]] = [
    {
        "id": "documentation",
        "name": "文档入口",
        "description": "接口目录、HTML 文档和 OpenAPI 机器可读描述。",
        "endpoints": [
            _endpoint("GET", "/api", "返回当前系统所有公开接口目录。", "JSON 接口目录，不触发数据计算。"),
            _endpoint("GET", "/docs", "返回轻量 HTML 接口说明页。", "HTML 文档页。"),
            _endpoint("GET", "/redoc", "返回面向 OpenAPI 的说明页。", "HTML 文档页。"),
            _endpoint("GET", "/openapi.json", "返回 OpenAPI 3.1 JSON。", "OpenAPI JSON。"),
        ],
    },
    {
        "id": "current_data",
        "name": "当前数据",
        "description": "当前公开持仓对照数据，只读取公开摘要文件。",
        "endpoints": [
            _endpoint(
                "GET",
                "/api/index",
                "返回首页同源 JSON 数据。",
                "当前净值对照、仓位偏差、操作建议、决策集、市场状态、交易约束和隐私标记。",
            ),
        ],
    },
    {
        "id": "historical_data",
        "name": "历史数据",
        "description": "当前系统暂无公开历史数据 API；历史报告仅以仓库文件形式保存。",
        "endpoints": [],
    },
    {
        "id": "analysis_results",
        "name": "分析结果",
        "description": "面向人工查看的只读 Web 页面。",
        "endpoints": [
            _endpoint("GET", "/", "返回 MyInvestPosition 首页。", "HTML 页面，展示净值对照、仓位偏差和建议。"),
            _endpoint("GET", "/index.html", "返回 MyInvestPosition 首页别名。", "HTML 页面，同 /。"),
        ],
    },
    {
        "id": "system_status",
        "name": "系统状态",
        "description": "只读健康检查。",
        "endpoints": [
            _endpoint("GET", "/health", "返回服务健康状态。", 'JSON：{"ok": true}。'),
        ],
    },
]

RECOMMENDED_ENTRYPOINTS = [
    {"label": "接口目录", "path": "/api", "reason": "查看全部公开接口和安全边界。"},
    {"label": "当前数据", "path": "/api/index", "reason": "程序读取当前净值对照和仓位偏差。"},
    {"label": "Web 首页", "path": "/", "reason": "人工查看净值对照、建议和接口摘要。"},
]

SAFETY_BOUNDARIES = [
    "/api 只返回说明，不触发重计算、写入、交易或同步。",
    "公开接口均为 GET 只读接口。",
    "公开接口不提供下单、撤单、交易写入或 QMT 写入入口。",
    "账号、资产金额、股数、市值等原始私有数据只保存在 data/private/，不会通过公开接口返回。",
    "/api/index 和首页只读取 data/public/latest_comparison.json。",
]


def build_api_catalog(base_url: str = "") -> dict[str, Any]:
    normalized_base_url = base_url.rstrip("/")
    total_endpoints = sum(len(group["endpoints"]) for group in GROUPS)
    return {
        "system": {
            "name": SYSTEM_NAME,
            "version": SYSTEM_VERSION,
            "description": SYSTEM_DESCRIPTION,
        },
        "base_url": normalized_base_url,
        "docs": {
            "api": "/api",
            "docs": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json",
        },
        "recommended_entrypoints": RECOMMENDED_ENTRYPOINTS,
        "safety": {
            "read_only": True,
            "no_recompute": True,
            "no_writes": True,
            "no_trading": True,
            "boundaries": SAFETY_BOUNDARIES,
        },
        "groups": GROUPS,
        "total_endpoints": total_endpoints,
    }


def build_openapi_document(base_url: str = "") -> dict[str, Any]:
    catalog = build_api_catalog(base_url)
    paths: dict[str, Any] = {}
    for group in catalog["groups"]:
        for endpoint in group["endpoints"]:
            method = endpoint["method"].lower()
            paths.setdefault(endpoint["path"], {})[method] = {
                "tags": [group["name"]],
                "summary": endpoint["purpose"],
                "description": endpoint["response"],
                "parameters": endpoint["parameters"],
                "responses": {
                    "200": {
                        "description": endpoint["response"],
                    }
                },
                "x-read-only": endpoint["read_only"],
            }
    servers = [{"url": catalog["base_url"]}] if catalog["base_url"] else []
    return {
        "openapi": "3.1.0",
        "info": {
            "title": catalog["system"]["name"],
            "version": catalog["system"]["version"],
            "description": catalog["system"]["description"],
        },
        "servers": servers,
        "paths": paths,
    }


def render_api_docs(catalog: dict[str, Any], title: str = "MyInvestPosition API") -> str:
    group_blocks = []
    for group in catalog["groups"]:
        endpoint_rows = []
        for endpoint in group["endpoints"]:
            endpoint_rows.append(
                f"""
                <tr>
                  <td>{escape(endpoint["method"])}</td>
                  <td><code>{escape(endpoint["path"])}</code></td>
                  <td>{escape(endpoint["purpose"])}</td>
                  <td>{escape(endpoint["response"])}</td>
                  <td>{"是" if endpoint["read_only"] else "否"}</td>
                </tr>
                """
            )
        endpoint_table = (
            "<p class=\"empty\">暂无公开接口。</p>"
            if not endpoint_rows
            else f"""
            <table>
              <thead><tr><th>方法</th><th>路径</th><th>用途</th><th>返回</th><th>只读</th></tr></thead>
              <tbody>{''.join(endpoint_rows)}</tbody>
            </table>
            """
        )
        group_blocks.append(
            f"""
            <section>
              <h2>{escape(group["name"])}</h2>
              <p>{escape(group["description"])}</p>
              {endpoint_table}
            </section>
            """
        )

    safety_items = "".join(f"<li>{escape(item)}</li>" for item in catalog["safety"]["boundaries"])
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)}</title>
  <style>
    body {{ margin: 0; background: #f6f7f9; color: #17202a; font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif; }}
    main {{ width: min(1180px, calc(100% - 32px)); margin: 0 auto; padding: 28px 0 42px; }}
    h1 {{ margin: 0 0 8px; font-size: 30px; }}
    h2 {{ margin: 0 0 8px; font-size: 18px; }}
    p {{ color: #667085; line-height: 1.6; }}
    section {{ margin-top: 16px; padding: 16px; border: 1px solid #d9dee7; border-radius: 8px; background: #fff; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 9px 8px; border-bottom: 1px solid #edf0f4; text-align: left; vertical-align: top; }}
    code {{ color: #155eef; }}
    .links {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 16px 0; }}
    .links a {{ color: #155eef; text-decoration: none; }}
    .empty {{ margin: 0; color: #98a2b3; }}
  </style>
</head>
<body>
  <main>
    <h1>{escape(catalog["system"]["name"])} API</h1>
    <p>{escape(catalog["system"]["description"])} 版本：{escape(catalog["system"]["version"])}。公开接口总数：{catalog["total_endpoints"]}。</p>
    <div class="links">
      <a href="/api">/api</a>
      <a href="/openapi.json">/openapi.json</a>
      <a href="/">返回首页</a>
    </div>
    <section>
      <h2>安全边界</h2>
      <ul>{safety_items}</ul>
    </section>
    {''.join(group_blocks)}
  </main>
</body>
</html>
"""
