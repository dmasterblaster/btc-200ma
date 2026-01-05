# scripts/fetch_200wma.py
import io
import json
import os

import pandas as pd
import requests


METRIC = "200wma-heatmap"
URL = f"https://api.bitcoinmagazinepro.com/metrics/{METRIC}"
OUT_PATH = "docs/data/200wma.json"  # adjust if your Pages root differs


def pick_col(df: pd.DataFrame, candidates: list[str]) -> str:
    cols_map = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidates:
        key = cand.strip().lower()
        if key in cols_map:
            return cols_map[key]
    raise KeyError(f"Missing column. Tried {candidates}. Found {list(df.columns)}")


def main() -> None:
    api_key = os.environ.get("BMP_API_KEY")
    if not api_key:
        raise RuntimeError("Missing BMP_API_KEY env var")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "*/*",
        "User-Agent": "Mozilla/5.0 (compatible; btc-200ma/1.0)",
    }

    resp = requests.get(URL, headers=headers, timeout=45)
    print("BMP API status code:", resp.status_code)
    print("Content-Type:", resp.headers.get("Content-Type"))
    print("First 160 chars:", resp.text[:160].replace("\n", "\\n"))
    resp.raise_for_status()

    raw = resp.text.strip()

    # IMPORTANT: This endpoint often returns CSV text even when Content-Type says application/json.
    # So we always try CSV first, then fall back to JSON only if CSV parsing fails.
    df = None
    try:
        df = pd.read_csv(io.StringIO(raw))
    except Exception:
        # Fall back to JSON
        try:
            j = resp.json()
            # Sometimes the JSON is literally a string that contains CSV
            if isinstance(j, str):
                df = pd.read_csv(io.StringIO(j))
            elif isinstance(j, dict) and "data" in j:
                df = pd.DataFrame(j["data"])
            else:
                df = pd.DataFrame(j)
        except Exception as e:
            raise RuntimeError("Could not parse response as CSV or JSON") from e

    # Column names from your screenshot look like:
    # Date, Price, 200week_avg, 200wma_monthly_increase
    date_col = pick_col(df, ["Date", "date", "Time", "time", "Timestamp", "timestamp"])
    price_col = pick_col(df, ["Price", "price"])
    ma_col = pick_col(df, ["200week_avg", "200WMA", "200wma", "MA200W", "ma200w"])

    out = df[[date_col, price_col, ma_col]].copy()
    out.columns = ["date", "price", "ma200w"]

    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"]).sort_values("date")

    out["price"] = pd.to_numeric(out["price"], errors="coerce")
    out["ma200w"] = pd.to_numeric(out["ma200w"], errors="coerce")
    out = out.dropna(subset=["price", "ma200w"])

    rows = [
        {"date": d.strftime("%Y-%m-%d"), "price": float(p), "ma200w": float(m)}
        for d, p, m in zip(out["date"], out["price"], out["ma200w"])
    ]

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)

    print(f"Wrote {OUT_PATH} rows={len(rows)}")


if __name__ == "__main__":
    main()
