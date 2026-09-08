from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge yfinance shard CSV files")
    parser.add_argument("--shards-dir", default="shards")
    parser.add_argument("--latest-dir", default="data/latest")
    parser.add_argument("--expected-count", type=int, default=0)
    parser.add_argument("--max-error-rate", type=float, default=0.25)
    args = parser.parse_args()

    shard_dir = Path(args.shards_dir)
    files = sorted(shard_dir.glob("shard_*.csv"))
    if not files:
        raise RuntimeError(f"No shard CSV files found under {shard_dir}")

    frames = [pd.read_csv(path, dtype={"証券コード": "string"}) for path in files]
    df = pd.concat(frames, ignore_index=True)

    if "証券コード" in df.columns:
        df["証券コード"] = df["証券コード"].astype("string").str.replace(r"\.0$", "", regex=True)
        df = df.drop_duplicates(subset=["証券コード"], keep="last")
        df = df.sort_values("証券コード", kind="stable")

    total = len(df)
    errors = int((df.get("企業名") == "エラー").sum()) if "企業名" in df.columns else total
    error_rate = errors / total if total else 1.0

    if args.expected_count and total != args.expected_count:
        raise RuntimeError(f"Merged row count mismatch: got {total}, expected {args.expected_count}")
    if error_rate > args.max_error_rate:
        raise RuntimeError(
            f"Yahoo/yfinance error rate too high: {errors}/{total} = {error_rate:.1%} "
            f"> allowed {args.max_error_rate:.1%}"
        )

    latest_dir = Path(args.latest_dir)
    latest_dir.mkdir(parents=True, exist_ok=True)
    csv_path = latest_dir / "yy_market_data_latest.csv"
    meta_path = latest_dir / "yy_market_data_latest.meta.json"

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    success = total - errors
    metrics = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "row_count": total,
        "success_count": success,
        "error_count": errors,
        "error_rate": error_rate,
        "shard_file_count": len(files),
        "roic_available": int(df["ROIC(%)"].notna().sum()) if "ROIC(%)" in df.columns else 0,
        "operating_margin_available": int(df["最新年度営業利益率(%)"].notna().sum()) if "最新年度営業利益率(%)" in df.columns else 0,
        "fcf_yield_available": int(df["3年間平均真FCF利回り(%)"].notna().sum()) if "3年間平均真FCF利回り(%)" in df.columns else 0,
    }
    meta_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"Latest CSV: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
