from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SHADOW_URL = "https://shadow.okbbc.com/api/latest"
CN_TZ = timezone(timedelta(hours=8))

DEFENSIVE_CODES = {"CASH", "511360.SH"}
CORE_PROXY_CODES = {"159201.SZ", "510500.SH"}
SHADOW_EXACT_CODES = {"588170.SH", "588850.SH", "159745.SZ", "515050.SH"}
RELATED_MAINLINE_CODES = {"159558.SZ", "588200.SH", "515880.SH", "562500.SH", "159667.SZ"}

REDUCTION_BUCKETS = {
    "券商/证券保险": {"512070.SH", "159842.SZ", "512880.SH"},
    "医药/医疗": {"159992.SZ", "513120.SH", "603087.SH", "300760.SZ"},
    "稀土/有色": {"516150.SH", "512400.SH", "562800.SH"},
}


@dataclass
class PublicPosition:
    code: str
    name: str
    weight_pct: float


def read_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def ensure_dirs() -> None:
    for rel in ("reports", "data/public", "data/private"):
        (ROOT / rel).mkdir(parents=True, exist_ok=True)


def fetch_json(url: str) -> tuple[dict[str, Any], str]:
    candidates = [url]
    if not url.endswith("/"):
        candidates.append(url + "/")
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    last_error: Exception | None = None
    for candidate in candidates:
        req = urllib.request.Request(candidate, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.load(resp), candidate
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 404:
                continue
            raise
    if last_error:
        raise last_error
    raise RuntimeError(f"Unable to fetch {url}")


def qmt_site_packages(qmt_install_path: Path) -> Path:
    return qmt_install_path / "python" / "Lib" / "site-packages"


def load_xtquant(qmt_install_path: Path) -> None:
    site_packages = qmt_site_packages(qmt_install_path)
    xtquant_dir = site_packages / "xtquant"
    if not xtquant_dir.exists():
        raise RuntimeError(f"xtquant not found under {site_packages}")
    sys.path.insert(0, str(site_packages))
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(str(xtquant_dir))


def detect_qmt_account(userdata_path: Path) -> str:
    env_account = os.environ.get("QMT_ACCOUNT_ID", "").strip()
    if env_account:
        return env_account

    users_dir = userdata_path / "users"
    candidates = sorted(
        p.name for p in users_dir.iterdir() if p.is_dir() and p.name.isdigit()
    )
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise RuntimeError(f"No QMT account directory found under {users_dir}")
    raise RuntimeError(
        "Multiple QMT account directories found; set QMT_ACCOUNT_ID locally."
    )


def mask_account(account_id: str) -> str:
    return "masked"


def query_qmt() -> dict[str, Any]:
    qmt_install_path = Path(os.environ.get("QMT_INSTALL_PATH", r"D:\国金证券QMT交易端"))
    userdata_path = Path(
        os.environ.get("QMT_USERDATA_PATH", str(qmt_install_path / "userdata_mini"))
    )
    account_id = detect_qmt_account(userdata_path)
    load_xtquant(qmt_install_path)

    from xtquant import xtdata
    from xtquant.xttrader import XtQuantTrader
    from xtquant.xttype import StockAccount

    session = int(time.time()) % 1_000_000_000
    trader = XtQuantTrader(str(userdata_path), session)
    try:
        trader.start()
        connect_rc = trader.connect()
        if connect_rc != 0:
            raise RuntimeError(f"QMT connect failed: {connect_rc}")
        account = StockAccount(account_id, "STOCK")
        subscribe_rc = trader.subscribe(account)
        if subscribe_rc not in (0, None):
            raise RuntimeError(f"QMT subscribe failed: {subscribe_rc}")

        asset = trader.query_stock_asset(account)
        positions = trader.query_stock_positions(account) or []
        if asset is None:
            raise RuntimeError("QMT returned no asset object")

        total_asset = float(getattr(asset, "total_asset", 0) or 0)
        if total_asset <= 0:
            raise RuntimeError("QMT total_asset is empty")

        cash = float(getattr(asset, "cash", 0) or 0)
        market_value = float(getattr(asset, "market_value", 0) or 0)
        public_positions: list[PublicPosition] = []
        private_positions: list[dict[str, Any]] = []

        if cash > 0:
            public_positions.append(
                PublicPosition("CASH", "现金", round(cash / total_asset * 100, 4))
            )

        for pos in positions:
            code = str(getattr(pos, "stock_code", ""))
            mv = float(getattr(pos, "market_value", 0) or 0)
            if not code or mv <= 0:
                continue
            detail = xtdata.get_instrument_detail(code) or {}
            name = detail.get("InstrumentName") or detail.get("Name") or code
            public_positions.append(
                PublicPosition(code, name, round(mv / total_asset * 100, 4))
            )
            private_positions.append(
                {
                    "code": code,
                    "name": name,
                    "market_value": mv,
                    "weight_pct": round(mv / total_asset * 100, 4),
                }
            )

        public_positions.sort(key=lambda p: p.weight_pct, reverse=True)
        return {
            "account_mask": mask_account(account_id),
            "collected_at": datetime.now(CN_TZ).isoformat(timespec="seconds"),
            "total_asset": total_asset,
            "cash": cash,
            "market_value": market_value,
            "cash_weight_pct": round(cash / total_asset * 100, 4),
            "positions_count": len(positions),
            "public_positions": public_positions,
            "private_positions": private_positions,
        }
    finally:
        try:
            trader.stop()
        except Exception:
            pass


def load_or_create_baseline(total_asset: float) -> tuple[float, bool, str]:
    baseline_path = ROOT / "data/private/real_nav_baseline.json"
    if baseline_path.exists():
        data = json.loads(baseline_path.read_text(encoding="utf-8"))
        return float(data["base_total_asset"]), False, data["base_time"]

    base_time = datetime.now(CN_TZ).isoformat(timespec="seconds")
    baseline_path.write_text(
        json.dumps(
            {
                "base_time": base_time,
                "base_total_asset": total_asset,
                "note": "Local private baseline for normalized account index; not cash-flow adjusted.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return total_asset, True, base_time


def sum_weights(positions: list[PublicPosition], codes: set[str]) -> float:
    return round(sum(p.weight_pct for p in positions if p.code in codes), 4)


def bucket_weight(positions: list[PublicPosition], codes: set[str]) -> float:
    return sum_weights(positions, codes)


def build_public_summary(shadow: dict[str, Any], shadow_url: str, qmt: dict[str, Any]) -> dict[str, Any]:
    positions = qmt["public_positions"]
    run = shadow.get("run") or {}
    sleeve = shadow.get("sleeve_summary") or {}

    defensive_weight = sum_weights(positions, DEFENSIVE_CODES)
    real_risk_weight = round(100 - defensive_weight, 4)
    shadow_defensive = float(sleeve.get("defensive", run.get("cash_ratio", 0)) or 0)
    shadow_risk = float(run.get("risk_budget_ratio", 100 - shadow_defensive) or 0)

    baseline, created, base_time = load_or_create_baseline(qmt["total_asset"])
    real_nav = qmt["total_asset"] / baseline if baseline else 1.0

    exact_shadow_weight = sum_weights(positions, SHADOW_EXACT_CODES)
    related_mainline_weight = sum_weights(positions, RELATED_MAINLINE_CODES)
    core_proxy_weight = sum_weights(positions, CORE_PROXY_CODES)

    reduction_buckets = [
        {
            "bucket": bucket,
            "weight_pct": round(bucket_weight(positions, codes), 4),
            "codes": sorted(codes),
        }
        for bucket, codes in REDUCTION_BUCKETS.items()
    ]
    tiny_weight = round(sum(p.weight_pct for p in positions if 0 < p.weight_pct < 0.3), 4)

    return {
        "generated_at": datetime.now(CN_TZ).isoformat(timespec="seconds"),
        "shadow_url_used": shadow_url,
        "shadow": {
            "run_at": run.get("run_at"),
            "basis_date": run.get("basis_date"),
            "market_regime": run.get("market_regime"),
            "nav": round(float(run.get("nav", 0) or 0), 6),
            "daily_return_pct": round(float(run.get("daily_return_ratio", 0) or 0), 4),
            "risk_weight_pct": round(shadow_risk, 4),
            "defensive_weight_pct": round(shadow_defensive, 4),
            "sleeve_summary": sleeve,
            "allocations": [
                {
                    "code": a.get("code"),
                    "name": a.get("name"),
                    "sleeve": a.get("sleeve"),
                    "theme": a.get("theme"),
                    "target_weight_pct": round(float(a.get("target_weight_ratio", 0) or 0), 4),
                    "pct_chg": a.get("pct_chg"),
                }
                for a in (shadow.get("allocations") or [])
            ],
        },
        "real": {
            "account_mask": qmt["account_mask"],
            "collected_at": qmt["collected_at"],
            "nav_index": round(real_nav, 6),
            "nav_baseline_created": created,
            "nav_baseline_time": base_time,
            "positions_count": qmt["positions_count"],
            "defensive_proxy_weight_pct": defensive_weight,
            "risk_weight_pct": real_risk_weight,
            "cash_weight_pct": qmt["cash_weight_pct"],
            "core_proxy_weight_pct": core_proxy_weight,
            "shadow_exact_codes_weight_pct": exact_shadow_weight,
            "related_mainline_weight_pct": related_mainline_weight,
            "positions": [
                {"code": p.code, "name": p.name, "weight_pct": p.weight_pct}
                for p in positions
            ],
        },
        "diff": {
            "risk_over_shadow_pp": round(real_risk_weight - shadow_risk, 4),
            "defensive_vs_shadow_pp": round(defensive_weight - shadow_defensive, 4),
            "core_proxy_vs_shadow_core_pp": round(core_proxy_weight - float(sleeve.get("core", 0) or 0), 4),
            "shadow_exact_codes_gap_pp": round(
                exact_shadow_weight
                - sum(float(a.get("target_weight_ratio", 0) or 0) for a in (shadow.get("allocations") or []) if a.get("code") in SHADOW_EXACT_CODES),
                4,
            ),
        },
        "reduction_buckets": reduction_buckets,
        "tiny_positions_weight_pct": tiny_weight,
    }


def fmt_pct(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{float(value):.2f}%"


def recommendation_text(summary: dict[str, Any]) -> list[str]:
    diff = summary["diff"]
    real = summary["real"]
    shadow = summary["shadow"]
    risk_gap = diff["risk_over_shadow_pp"]
    defensive_gap = diff["defensive_vs_shadow_pp"]
    core_gap = diff["core_proxy_vs_shadow_core_pp"]
    exact_gap = diff["shadow_exact_codes_gap_pp"]

    lines = []
    if risk_gap > 1:
        lines.append(
            f"先把实盘风险仓从 {fmt_pct(real['risk_weight_pct'])} 压回影子账户的 {fmt_pct(shadow['risk_weight_pct'])} 附近，幅度约 {risk_gap:.2f} 个百分点；资金来源优先选模型未覆盖的行业卫星仓和极小仓位。"
        )
    elif risk_gap < -1:
        lines.append(
            f"实盘风险仓低于影子账户约 {abs(risk_gap):.2f} 个百分点，可以只在影子主线确认后小步补齐，不需要一次性拉满。"
        )
    else:
        lines.append("实盘总风险预算与影子账户接近，主要矛盾在结构而不是仓位总量。")

    if defensive_gap < -1:
        lines.append(
            f"防御仓不足约 {abs(defensive_gap):.2f} 个百分点；若继续把短融 ETF 视作现金替代，仍建议补到 64% 左右，降低主题仓挤在一起的波动。"
        )

    if core_gap < -3:
        lines.append(
            f"核心宽基/质量代理仓低于影子核心仓约 {abs(core_gap):.2f} 个百分点；后续结构调整应优先从非模型卫星仓轮入核心代理，而不是新增净风险。"
        )

    if exact_gap < -5:
        lines.append(
            f"影子账户的精确主线标的合计缺口约 {abs(exact_gap):.2f} 个百分点；半导体材料设备当日涨幅较大，适合分段观察，不适合用一次性追高完成对齐。"
        )

    lines.append(
        "个股仓位在本流程里只作为组合结构来源处理：没有独立研究结论前不加仓，需要降风险或降复杂度时优先从低权重、低协同的个股和行业卫星仓中腾挪。"
    )
    return lines


def render_report(summary: dict[str, Any]) -> str:
    shadow = summary["shadow"]
    real = summary["real"]
    diff = summary["diff"]
    generated_at = summary["generated_at"]
    lines: list[str] = []

    lines.append(f"# 净值与持仓对照 - {generated_at[:10]}")
    lines.append("")
    lines.append("## 结论")
    for item in recommendation_text(summary):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 净值对照")
    lines.append("")
    lines.append("| 项目 | 影子账户 | QMT 实盘 | 差异 |")
    lines.append("| --- | ---: | ---: | ---: |")
    nav_note = "首次基线对照" if real["nav_baseline_created"] else "本地基线对照"
    lines.append(
        f"| 净值指数 | {shadow['nav']:.4f} | {real['nav_index']:.4f} | {nav_note} |"
    )
    lines.append(
        f"| 风险仓 | {fmt_pct(shadow['risk_weight_pct'])} | {fmt_pct(real['risk_weight_pct'])} | {diff['risk_over_shadow_pp']:+.2f} pp |"
    )
    lines.append(
        f"| 防御/现金仓 | {fmt_pct(shadow['defensive_weight_pct'])} | {fmt_pct(real['defensive_proxy_weight_pct'])} | {diff['defensive_vs_shadow_pp']:+.2f} pp |"
    )
    lines.append(
        f"| 纯现金 | - | {fmt_pct(real['cash_weight_pct'])} | 实盘主要用短融 ETF 代替现金 |"
    )
    lines.append("")
    lines.append(
        f"- 影子账户：run_at={shadow['run_at']}，basis_date={shadow['basis_date']}，市场状态={shadow['market_regime']}。"
    )
    lines.append(
        f"- QMT 实盘：collected_at={real['collected_at']}，账号={real['account_mask']}，持仓数={real['positions_count']}。"
    )
    if real["nav_baseline_created"]:
        lines.append("- QMT 净值指数为本次首次本地基线，后续复跑会用本地私有基线继续对照；该指数未做申赎/转账现金流调整。")
    else:
        lines.append(f"- QMT 净值指数基线时间：{real['nav_baseline_time']}；该指数未做申赎/转账现金流调整。")
    lines.append("")

    lines.append("## 影子账户目标")
    lines.append("")
    lines.append("| 标的 | 名称 | 袖套 | 目标比例 | 当日涨跌 |")
    lines.append("| --- | --- | --- | ---: | ---: |")
    for alloc in shadow["allocations"]:
        lines.append(
            f"| {alloc['code']} | {alloc['name']} | {alloc['sleeve']} | {fmt_pct(alloc['target_weight_pct'])} | {fmt_pct(alloc['pct_chg']) if alloc['pct_chg'] is not None else '-'} |"
        )
    lines.append("")

    lines.append("## 实盘主要持仓")
    lines.append("")
    lines.append("| 标的 | 名称 | 当前比例 |")
    lines.append("| --- | --- | ---: |")
    for pos in real["positions"]:
        lines.append(f"| {pos['code']} | {pos['name']} | {fmt_pct(pos['weight_pct'])} |")
    lines.append("")

    lines.append("## 结构差异")
    lines.append("")
    lines.append("| 结构 | 影子目标 | 实盘当前 | 差异 |")
    lines.append("| --- | ---: | ---: | ---: |")
    core_target = float(shadow["sleeve_summary"].get("core", 0) or 0)
    target_exact = sum(
        a["target_weight_pct"] for a in shadow["allocations"] if a["code"] in SHADOW_EXACT_CODES
    )
    lines.append(
        f"| 防御/现金 | {fmt_pct(shadow['defensive_weight_pct'])} | {fmt_pct(real['defensive_proxy_weight_pct'])} | {diff['defensive_vs_shadow_pp']:+.2f} pp |"
    )
    lines.append(
        f"| 核心宽基/质量代理 | {fmt_pct(core_target)} | {fmt_pct(real['core_proxy_weight_pct'])} | {diff['core_proxy_vs_shadow_core_pp']:+.2f} pp |"
    )
    lines.append(
        f"| 影子精确主线标的 | {fmt_pct(target_exact)} | {fmt_pct(real['shadow_exact_codes_weight_pct'])} | {diff['shadow_exact_codes_gap_pp']:+.2f} pp |"
    )
    lines.append(
        f"| 相关主线代理 | - | {fmt_pct(real['related_mainline_weight_pct'])} | 不是精确影子持仓 |"
    )
    lines.append("")

    lines.append("## 优先腾挪来源")
    lines.append("")
    lines.append("| 分组 | 当前比例 | 说明 |")
    lines.append("| --- | ---: | --- |")
    for bucket in summary["reduction_buckets"]:
        lines.append(
            f"| {bucket['bucket']} | {fmt_pct(bucket['weight_pct'])} | 模型未覆盖，适合作为降风险和轮入核心的资金来源 |"
        )
    lines.append(
        f"| 低于 0.30% 的极小仓位 | {fmt_pct(summary['tiny_positions_weight_pct'])} | 管理复杂度高，优先合并或清理 |"
    )
    lines.append("")

    lines.append("## 操作建议")
    lines.append("")
    lines.append("1. 第一优先级是仓位预算：把风险仓净降约 7-8 个百分点，防御仓补到 64% 左右。")
    lines.append("2. 第二优先级是结构简化：不要新增净风险，用模型未覆盖的券商、医药、稀土有色和零散个股，轮入核心宽基/质量代理。")
    lines.append("3. 第三优先级才是影子主线：588170、159745、515050 等缺口只用腾挪资金分段补，不用现金仓一次性追。")
    lines.append("4. 588850 对应的高端制造/机器人方向，实盘已有多个相关代理，先合并重复暴露，再决定是否换成影子精确标的。")
    lines.append("5. 个股不在本次影子账户模型内，除非已有单独研究结论，否则不做加仓建议；需要降复杂度时优先处理低权重个股。")
    lines.append("")
    lines.append("## 数据与隐私")
    lines.append("")
    lines.append("- 本报告只包含比例，不包含资金账号原文、资产金额、市值或持仓数量。")
    lines.append("- 原始 QMT 资产基线仅保存在本地 `data/private/`，不会同步到 GitHub。")
    lines.append("- QMT 读取使用只读查询接口；脚本没有下单或撤单入口。")
    lines.append("")
    return "\n".join(lines)


def save_outputs(summary: dict[str, Any], qmt_private: dict[str, Any]) -> None:
    public_path = ROOT / "data/public/latest_comparison.json"
    public_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    private_path = ROOT / "data/private/latest_qmt_snapshot.json"
    private_payload = {
        "collected_at": qmt_private["collected_at"],
        "account_mask": qmt_private["account_mask"],
        "total_asset": qmt_private["total_asset"],
        "cash": qmt_private["cash"],
        "market_value": qmt_private["market_value"],
        "positions": qmt_private["private_positions"],
    }
    private_path.write_text(json.dumps(private_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    report = render_report(summary)
    latest_report = ROOT / "reports/latest_position_compare.md"
    latest_report.write_text(report, encoding="utf-8")

    dated_report = ROOT / "reports" / f"{datetime.now(CN_TZ).strftime('%Y-%m-%d')}_position_compare.md"
    dated_report.write_text(report, encoding="utf-8")


def main() -> int:
    read_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Compare shadow portfolio with QMT real positions.")
    parser.add_argument("--shadow-url", default=os.environ.get("SHADOW_LATEST_URL", DEFAULT_SHADOW_URL))
    args = parser.parse_args()

    ensure_dirs()

    shadow, shadow_url = fetch_json(args.shadow_url)
    qmt = query_qmt()
    summary = build_public_summary(shadow, shadow_url, qmt)
    save_outputs(summary, qmt)

    print(json.dumps({
        "report": "reports/latest_position_compare.md",
        "public_summary": "data/public/latest_comparison.json",
        "shadow_url_used": shadow_url,
        "real_nav_index": summary["real"]["nav_index"],
        "risk_over_shadow_pp": summary["diff"]["risk_over_shadow_pp"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
