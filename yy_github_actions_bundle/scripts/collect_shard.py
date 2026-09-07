from __future__ import annotations

import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fcf5y_roic_core import analyze_japanese_stocks, read_stock_codes  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect one shard of TSE yfinance data")
    parser.add_argument("--input", default="input.lst")
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if args.shard_count <= 0:
        raise ValueError("--shard-count must be > 0")
    if not 0 <= args.shard_index < args.shard_count:
        raise ValueError("--shard-index must satisfy 0 <= index < count")

    codes = read_stock_codes(args.input)
    if not codes:
        print("No stock codes loaded", file=sys.stderr)
        return 2

    shard_codes = [code for i, code in enumerate(codes) if i % args.shard_count == args.shard_index]
    print(
        f"UTC={datetime.now(timezone.utc).isoformat()} "
        f"shard={args.shard_index}/{args.shard_count} codes={len(shard_codes)}"
    )

    df = analyze_japanese_stocks(shard_codes)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8-sig")

    errors = int((df.get("企業名") == "エラー").sum()) if "企業名" in df.columns else len(df)
    print(f"Saved {len(df)} rows to {out}; errors={errors}")

    # A shard is considered runnable even if individual Yahoo requests fail.
    # The merge step will enforce whole-run health thresholds.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
