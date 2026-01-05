# scripts/fetch_200wma.py
import io
import json
import os

import pandas as pd
import requests

METRIC = "200wma-heatmap"
URL = f"https://api.bitcoinmagazinepro.com/metrics/{METRIC}"
OUT_PATH = "docs/data/200wma.json"


def pick_col(df: pd.DataFrame, candidates: list[str]) -> str:
    cols_map = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidates:
        key = cand.strip().lower()
        if key in cols_map:
            return cols_map[key]
    raise KeyError(f"Missing column. Tried {candidates}. Found {list(df.columns)}")


def coerce_to_csv_text(raw: str) -> str:
    s = raw.strip()

    # If response is a JSON string that contains CSV, unescape it
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        try:
            s = json.loads(s)
        except Exception:
            s = s[1:-1]

    s = s.lstrip()
    if s.startswith(","):
        s = s[1:]
    if s.startswith('",'):
        s = s[2:]

    return s


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
    preview = resp.text[:160].replace("\n", "\\n")
    print("First 160 chars:", preview)
    resp.raise_for_status()

    csv_text = coerce_to_csv_text(resp.text)
    df = pd.read_csv(io.StringIO(csv_text))

    date_col = pick_col(df, ["Date", "date", "Time", "time", "Timestamp", "timestamp"])
    price_col = pick_col(df, ["Price", "price"])

    out = df[[date_col, price_col]].copy()
    out.columns = ["date", "price"]

    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["price"] = pd.to_numeric(out["price"], errors="coerce")
    out = out.dropna(subset=["date", "price"]).sort_values("date")

    # If there are multiple rows per day, keep the last one
    out["day"] = out["date"].dt.strftime("%Y-%m-%d")
    out = out.groupby("day", as_index=False).agg(date=("date", "max"), price=("price", "last"))
    out = out.sort_values("date")

    # 200-day simple moving average on the available daily series
    out["ma200d"] = out["price"].rolling(window=200, min_periods=200).mean()

    # Keep only rows where the 200d MA exists (after 200 data points)
    out = out.dropna(subset=["ma200d"])

    rows = [
        {"date": d.strftime("%Y-%m-%d"), "price": float(p), "ma200d": float(m)}
        for d, p, m in zip(out["date"], out["price"], out["ma200d"])
    ]

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f)

    print(f"Wrote {OUT_PATH} rows={len(rows)}")


if __name__ == "__main__":
    main()
