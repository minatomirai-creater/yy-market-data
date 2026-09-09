from __future__ import annotations

import io
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

JPX_LIST_PAGE = "https://www.jpx.co.jp/markets/statistics-equities/misc/01.html"
OUTPUT_PATH = Path("input.lst")
DETAIL_OUTPUT_PATH = Path("data/universe/jpx_universe_latest.csv")
MIN_COUNT = 3000
MAX_COUNT = 5000
MAX_DELTA_RATE = 0.05
MARKET_KEYWORDS = ("プライム", "スタンダード", "グロース")
EXCLUDE_KEYWORDS = (
    "ETF", "ETN", "REIT", "リート", "投資法人", "インフラ",
    "PRO Market", "外国株", "優先株", "出資証券",
)


def _headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120 Safari/537.36"
        )
    }


def fetch_text(url: str) -> str:
    r = requests.get(url, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.text


def fetch_bytes(url: str) -> bytes:
    r = requests.get(url, headers=_headers(), timeout=60)
    r.raise_for_status()
    return r.content


def find_latest_excel_url() -> str:
    """JPX『東証上場銘柄一覧』ページから最新のExcelリンクを検出する。"""
    soup = BeautifulSoup(fetch_text(JPX_LIST_PAGE), "html.parser")
    candidates: list[tuple[int, str]] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(" ", strip=True)
        lower = href.lower()
        if not lower.endswith((".xls", ".xlsx")):
            continue
        combined = f"{text} {href}"
        score = 0
        if "上場銘柄" in combined:
            score += 10
        if "data" in lower:
            score += 1
        candidates.append((score, urljoin(JPX_LIST_PAGE, href)))
    if not candidates:
        raise RuntimeError("JPXページからExcelリンクを検出できませんでした。")
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidates[0][1]


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).replace("\n", "").replace("\r", "").strip() for c in out.columns]
    return out


def detect_column(columns, keywords, required=True):
    for col in columns:
        s = str(col)
        if all(k in s for k in keywords):
            return col
    if required:
        raise RuntimeError(f"列を検出できません: keywords={keywords}, columns={list(columns)}")
    return None


def normalize_code(value) -> str | None:
    if pd.isna(value):
        return None
    s = str(value).strip().upper()
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    if not re.fullmatch(r"[0-9A-Z]{4}", s):
        return None
    return s


def is_target_market(value) -> bool:
    if pd.isna(value):
        return False
    s = str(value)
    return any(k in s for k in MARKET_KEYWORDS) and not any(k in s for k in EXCLUDE_KEYWORDS)


def read_previous_codes(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip().upper() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_delta(previous: list[str], current: list[str]) -> None:
    if not previous:
        print("Previous universe not found; delta gate skipped.")
        return
    prev_n = len(previous)
    cur_n = len(current)
    delta_rate = abs(cur_n - prev_n) / prev_n if prev_n else 0.0
    print(f"Previous universe count: {prev_n}")
    print(f"Current universe count : {cur_n}")
    print(f"Universe delta rate    : {delta_rate:.2%}")
    if delta_rate > MAX_DELTA_RATE:
        raise RuntimeError(
            "Previous Universe Delta Gate failed: "
            f"previous={prev_n}, current={cur_n}, delta={delta_rate:.2%} > {MAX_DELTA_RATE:.0%}"
        )


def main() -> None:
    print("JPX universe refresh start")
    previous_codes = read_previous_codes(OUTPUT_PATH)
    excel_url = find_latest_excel_url()
    print(f"JPX Excel URL: {excel_url}")

    df = pd.read_excel(io.BytesIO(fetch_bytes(excel_url)), dtype=str)
    df = normalize_columns(df)

    print("JPX columns:")
    for c in df.columns:
        print(f"  - {c}")

    code_col = detect_column(df.columns, ["コード"])
    market_col = detect_column(df.columns, ["市場"])
    name_col = detect_column(df.columns, ["銘柄名"], required=False)
    if name_col is None:
        name_col = detect_column(df.columns, ["会社名"], required=False)

    print(f"Code column   : {code_col}")
    print(f"Market column : {market_col}")

    work = df.copy()
    work["__code"] = work[code_col].map(normalize_code)
    work["__market"] = work[market_col].astype(str)
    work = work[work["__market"].map(is_target_market)]
    work = work[work["__code"].notna()]
    work = work.drop_duplicates(subset=["__code"], keep="first").sort_values("__code")

    codes = work["__code"].tolist()
    if len(codes) < MIN_COUNT:
        raise RuntimeError(f"対象銘柄数が異常に少ないです: {len(codes)}")
    if len(codes) > MAX_COUNT:
        raise RuntimeError(f"対象銘柄数が異常に多いです: {len(codes)}")

    validate_delta(previous_codes, codes)
    OUTPUT_PATH.write_text("\n".join(codes) + "\n", encoding="utf-8")

    DETAIL_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output_cols = [code_col, market_col]
    if name_col is not None:
        output_cols.insert(1, name_col)
    detail = work[output_cols + ["__code"]].copy()
    detail.to_csv(DETAIL_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print("=== JPX Universe Summary ===")
    print(f"Total target issues: {len(codes)}")
    print(f"First 10: {codes[:10]}")
    print(f"Last 10 : {codes[-10:]}")
    print(f"Saved: {OUTPUT_PATH}")
    print(f"Saved: {DETAIL_OUTPUT_PATH}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"JPX universe refresh failed: {e}", file=sys.stderr)
        raise
