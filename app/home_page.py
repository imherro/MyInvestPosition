from __future__ import annotations

from html import escape
from typing import Any


def _pct(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value):.2f}%"


def _nav(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value):.4f}"


def _pp(value: Any) -> str:
    if value is None:
        return "-"
    number = float(value)
    sign = "+" if number > 0 else ""
    return f"{sign}{number:.2f} pp"


def _safe(value: Any) -> str:
    return escape("" if value is None else str(value), quote=True)


def _bar_width(value: Any) -> str:
    try:
        number = max(0, min(100, float(value)))
    except (TypeError, ValueError):
        number = 0
    return f"{number:.2f}%"


def _recommendation_items(items: list[str]) -> str:
    return "\n".join(f"<li>{_safe(item)}</li>" for item in items)


def _card_items(cards: list[dict[str, Any]]) -> str:
    rows = []
    for card in cards:
        value = card.get("value_pct")
        rows.append(
            f"""
            <article class="metric">
              <div class="metric-label">{_safe(card.get("label"))}</div>
              <div class="metric-value">{_pct(value)}</div>
              <div class="bar" aria-hidden="true"><span style="width:{_bar_width(value)}"></span></div>
            </article>
            """
        )
    return "\n".join(rows)


def _comparison_rows(comparison: dict[str, dict[str, Any]]) -> str:
    labels = {
        "risk": "风险仓",
        "defensive": "防御/现金仓",
        "core_proxy": "核心宽基/质量代理",
        "shadow_exact": "影子精确主线",
    }
    rows = []
    for key, label in labels.items():
        item = comparison.get(key, {})
        rows.append(
            f"""
            <tr>
              <th>{_safe(label)}</th>
              <td>{_pct(item.get("shadow_pct"))}</td>
              <td>{_pct(item.get("real_pct"))}</td>
              <td class="gap">{_pp(item.get("gap_pp"))}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def _allocation_rows(items: list[dict[str, Any]]) -> str:
    rows = []
    for item in items:
        rows.append(
            f"""
            <tr>
              <th>{_safe(item.get("code"))}</th>
              <td>{_safe(item.get("name"))}</td>
              <td>{_safe(item.get("sleeve"))}</td>
              <td>{_pct(item.get("target_weight_pct"))}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def _position_rows(items: list[dict[str, Any]]) -> str:
    rows = []
    for item in items:
        rows.append(
            f"""
            <tr>
              <th>{_safe(item.get("code"))}</th>
              <td>{_safe(item.get("name"))}</td>
              <td>{_pct(item.get("weight_pct"))}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def _bucket_rows(items: list[dict[str, Any]]) -> str:
    rows = []
    for item in items:
        rows.append(
            f"""
            <tr>
              <th>{_safe(item.get("bucket"))}</th>
              <td>{_pct(item.get("weight_pct"))}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def render_home_page(payload: dict[str, Any]) -> str:
    page = payload.get("page", {})
    hero = payload.get("hero", {})
    top_positions = payload.get("real_top_positions", {})
    title = _safe(page.get("title", "MyInvestPosition"))
    subtitle = _safe(page.get("subtitle", "影子账户与 QMT 实盘净值对照"))

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #17202a;
      --muted: #667085;
      --border: #d9dee7;
      --risk: #b42318;
      --ok: #067647;
      --accent: #155eef;
      --bar: #d9e6ff;
      --bar-fill: #2e5aac;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      letter-spacing: 0;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px 20px 44px;
    }}
    header {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 16px;
      align-items: end;
      padding-bottom: 18px;
      border-bottom: 1px solid var(--border);
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: 30px;
      line-height: 1.18;
      font-weight: 700;
    }}
    .subtitle, .meta, .label {{
      color: var(--muted);
    }}
    .meta {{
      text-align: right;
      font-size: 13px;
      line-height: 1.65;
      white-space: nowrap;
    }}
    .signal {{
      margin: 22px 0;
      padding: 18px 20px;
      border: 1px solid #f0c6c2;
      background: #fff7f6;
      border-radius: 8px;
    }}
    .signal strong {{
      display: block;
      color: var(--risk);
      font-size: 18px;
      margin-bottom: 6px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }}
    .metric, section {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
    }}
    .metric {{
      padding: 15px;
      min-height: 116px;
    }}
    .metric-label {{
      color: var(--muted);
      font-size: 13px;
    }}
    .metric-value {{
      font-size: 28px;
      line-height: 1.35;
      font-weight: 700;
      margin: 6px 0 10px;
    }}
    .bar {{
      height: 8px;
      background: var(--bar);
      border-radius: 999px;
      overflow: hidden;
    }}
    .bar span {{
      display: block;
      height: 100%;
      background: var(--bar-fill);
    }}
    .section-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(340px, .82fr);
      gap: 16px;
      margin-top: 16px;
    }}
    section {{
      padding: 16px;
      overflow: hidden;
    }}
    h2 {{
      margin: 0 0 12px;
      font-size: 17px;
      line-height: 1.3;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      padding: 10px 8px;
      border-bottom: 1px solid #edf0f4;
      text-align: right;
      vertical-align: top;
    }}
    th:first-child, td:first-child, td:nth-child(2) {{
      text-align: left;
    }}
    tbody tr:last-child th, tbody tr:last-child td {{
      border-bottom: none;
    }}
    .gap {{
      font-weight: 700;
      color: var(--risk);
    }}
    ol {{
      margin: 0;
      padding-left: 22px;
    }}
    li {{
      margin: 0 0 10px;
      line-height: 1.58;
    }}
    .navs {{
      display: flex;
      gap: 14px;
      margin-top: 12px;
      color: var(--muted);
      font-size: 14px;
      flex-wrap: wrap;
    }}
    .navs strong {{
      color: var(--text);
    }}
    @media (max-width: 900px) {{
      header, .section-grid {{
        grid-template-columns: 1fr;
      }}
      .meta {{
        text-align: left;
        white-space: normal;
      }}
      .grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}
    @media (max-width: 560px) {{
      main {{
        padding: 20px 12px 34px;
      }}
      h1 {{
        font-size: 24px;
      }}
      .grid {{
        grid-template-columns: 1fr;
      }}
      th, td {{
        padding: 9px 5px;
        font-size: 13px;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>{title}</h1>
        <div class="subtitle">{subtitle}</div>
        <div class="navs">
          <span>影子净值 <strong>{_nav(hero.get("shadow_nav"))}</strong></span>
          <span>实盘净值指数 <strong>{_nav(hero.get("real_nav_index"))}</strong></span>
          <span>风险差异 <strong>{_pp(hero.get("risk_gap_pp"))}</strong></span>
        </div>
      </div>
      <div class="meta">
        <div>生成时间：{_safe(page.get("generated_at"))}</div>
        <div>基准日期：{_safe(page.get("basis_date"))}</div>
      </div>
    </header>

    <div class="signal">
      <strong>{_safe(hero.get("market_regime"))}</strong>
      <div>{_safe(page.get("primary_signal"))}</div>
    </div>

    <div class="grid">
      {_card_items(payload.get("cards", []))}
    </div>

    <div class="section-grid">
      <section>
        <h2>仓位对照</h2>
        <table>
          <thead>
            <tr><th>结构</th><th>影子</th><th>实盘</th><th>差异</th></tr>
          </thead>
          <tbody>
            {_comparison_rows(payload.get("comparison", {}))}
          </tbody>
        </table>
      </section>
      <section>
        <h2>操作建议</h2>
        <ol>
          {_recommendation_items(payload.get("recommendations", []))}
        </ol>
      </section>
    </div>

    <div class="section-grid">
      <section>
        <h2>影子账户目标</h2>
        <table>
          <thead>
            <tr><th>标的</th><th>名称</th><th>袖套</th><th>目标</th></tr>
          </thead>
          <tbody>
            {_allocation_rows(payload.get("shadow_allocations", []))}
          </tbody>
        </table>
      </section>
      <section>
        <h2>实盘前十大持仓</h2>
        <table>
          <thead>
            <tr><th>标的</th><th>名称</th><th>比例</th></tr>
          </thead>
          <tbody>
            {_position_rows(top_positions.get("items", []))}
          </tbody>
        </table>
      </section>
    </div>

    <section style="margin-top:16px">
      <h2>优先腾挪来源</h2>
      <table>
        <thead>
          <tr><th>分组</th><th>当前比例</th></tr>
        </thead>
        <tbody>
          {_bucket_rows(payload.get("reduction_buckets", []))}
        </tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""
