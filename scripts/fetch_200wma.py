import io
import json
import os
from datetime import datetime, timezone

import pandas as pd
import requests


METRIC = "200wma-heatmap"
URL = f"https://api.bitcoinmagazinepro.com/metrics/{METRIC}"  # no /v1 per BM Pro docs
OUT_PATH = "docs/data/200wma.json"


def pick_col(df: pd.DataFrame, candidates: list[str]) -> str:
    cols_lower = {c.lower(): c for c in df.columns}
    for name in candidates:
        if name.lower() in cols_lower:
            return cols_lower[name.lower()]
    raise KeyError(f"Could not find any of these columns: {candidates}. Found: {list(df.columns)}")


def main() -> None:
    api_key = os.environ.get("BMP_API_KEY")
    if not api_key:
        raise RuntimeError("Missing env var BMP_API_KEY")

    headers = {
        "Authorization": f"Bearer {api_key}",  # docs recommend header auth
        "Accept": "text/csv,application/json;q=0.9,*/*;q=0.8",
    }

    resp = requests.get(URL, headers=headers, timeout=45)
    print("BMP API status code:", resp.status_code)
    print("Content-Type:", resp.headers.get("Content-Type"))
    resp.raise_for_status()

    text = resp.text.strip()

    # Most BMP metrics return CSV even if some examples mention JSON.
    # Try CSV first, fall back to JSON if needed.
    df = None
    try:
        df = pd.read_csv(io.StringIO(text))
    except Exception:
        try:
            j = resp.json()
            # If they ever return JSON, try to normalize it
            df = pd.DataFrame(j)
        except Exception as e:
            raise RuntimeError("Could not parse response as CSV or JSON") from e

    # Normalize date column
    date_col = None
    for c in df.columns:
        if str(c).lower() in ["date", "time", "timestamp"]:
            date_col = c
            break
    if date_col is None:
        # Some responses may have an unnamed first column used as index
        if df.columns[0] == "" or str(df.columns[0]).startswith("Unnamed"):
            date_col = df.columns[0]
        else:
            raise KeyError(f"Could not find a Date-like column. Columns: {list(df.columns)}")

    price_col = pick_col(df, ["Price", "price", "BTC Price", "btc_price"])
    ma_col = pick_col(df, ["200WMA", "200wma", "200 Week Moving Average", "200_week_ma", "MA200W"])

    out_df = df[[date_col, price_col, ma_col]].copy()
    out_df.columns = ["Date", "Price", "MA200W"]

    # Clean and sort
    out_df["Date"] = pd.to_datetime(out_df["Date"], errors="coerce", utc=True)
    out_df = out_df.dropna(subset=["Date"])
    out_df = out_df.sort_values("Date")

    # Cast numeric
    out_df["Price"] = pd.to_numeric(out_df["Price"], errors="coerce")
    out_df["MA200W"] = pd.to_numeric(out_df["MA200W"], errors="coerce")

    out_df = out_df.dropna(subset=["Price", "MA200W"])

    payload = {
        "meta": {
            "source": "bitcoinmagazinepro",
            "metric": METRIC,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "rows": int(len(out_df)),
        },
        "data": [
            {
                "Date": d.strftime("%Y-%m-%d"),
                "Price": float(p),
                "MA200W": float(m),
            }
            for d, p, m in zip(out_df["Date"], out_df["Price"], out_df["MA200W"])
        ],
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    print(f"Wrote {OUT_PATH} with {payload['meta']['rows']} rows")


if __name__ == "__main__":
    main()
