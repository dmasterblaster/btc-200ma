# scripts/fetch_200wma.py
import io
import json
import os

import pandas as pd
import requests


METRIC = "200wma-heatmap"
URL = f"https://api.bitcoinmagazinepro.com/metrics/{METRIC}"
OUT_PATH = "docs/data/200wma.json"  # adjust if your Pages root is different


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

    # Do the same thing as the endpoints that worked:
    # 1) Authorization bearer
    # 2) Do NOT force CSV-only Accept
    # 3) Include a normal User-Agent
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

    ct = (resp.headers.get("Content-Type") or "").lower()

    # Parse response depending on what the endpoint returns
    if "application/json" in ct:
        j = resp.json()
        # could be list of dicts, or dict with a data field
        if isinstance(j, dict) and "data" in j:
            df = pd.DataFrame(j["data"])
        else:
            df = pd.DataFrame(j)
    else:
        # treat as CSV/plain text
        df = pd.read_csv(io.StringIO(resp.text))

    # Identify columns
    date_col = pick_col(df, ["Date", "date", "Time", "time", "Timestamp", "timestamp"])
    price_col = pick_col(df, ["Price", "price"])
    ma_col = pick_col(df, ["200WMA", "200wma", "MA200W", "ma200w", "200_week_ma", "200 Week Moving Average"])

    out = df[[date_col, price_col, ma_col]].copy()
    out.columns = ["date", "price", "ma200w"]

    # Normalize
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"])
    out = out.sort_values("date")

    out["price"] = pd.to_numeric(out["price"], errors="coerce")
    out["ma200w"] = pd.to_numeric(out["ma200w"], errors="coerce")
    out = out.dropna(subset=["price", "ma200w"])

    # Write JSON in the exact format your HTML expects (top-level array)
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
