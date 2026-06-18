from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PATHS = [ROOT / "reports", ROOT / "data/public"]
FORBIDDEN_PATTERNS = {
    "account_id": re.compile(r"\baccount_id\b", re.IGNORECASE),
    "total_asset": re.compile(r"\btotal_asset\b", re.IGNORECASE),
    "market_value": re.compile(r"\bmarket_value\b", re.IGNORECASE),
    "position_volume": re.compile(r"\b(can_use_)?volume\b", re.IGNORECASE),
    "masked_account_digits": re.compile(r"\d{2}\*+\d{2}"),
}


def iter_files() -> list[Path]:
    files: list[Path] = []
    for path in PUBLIC_PATHS:
        if not path.exists():
            continue
        if path.is_file():
            files.append(path)
        else:
            files.extend(p for p in path.rglob("*") if p.is_file())
    return files


def main() -> int:
    failures: list[str] = []
    for path in iter_files():
        if path.name == "check_public_privacy.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in FORBIDDEN_PATTERNS.items():
            if pattern.search(text):
                failures.append(f"{path.relative_to(ROOT)} contains {label}")
    if failures:
        print("\n".join(failures))
        return 1
    print("public privacy scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
