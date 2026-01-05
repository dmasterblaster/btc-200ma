import os
import json
import requests
import pandas as pd
from io import StringIO
from pathlib import Path

API_URL = "https://api.bitcoinmagazinepro.com/v1/metrics/200wma-heatmap"

def main():
    api_key = os.environ.get("BMP_API_KEY")
    if not api_key:
        raise RuntimeError("BMP_API_KEY env var missing")

    headers = {
        "X-API-KEY": api_key,
        "Accept": "text/csv",  # IMPORTANT, prevents 406 for many BMP endpoints
    }

    resp = requests.get(API_URL, headers=headers, timeout=60)
    print("BMP API status code:", resp.status_code)
    print("Content-Type:", resp.headers.get("Content-Type", ""))
    print("First 200 chars of response:\n", resp.text[:200])

    resp.raise_for_status()

    # Parse CSV
    df = pd.read_csv(StringIO(resp.text))

    # Some BMP CSVs have an unnamed first column
    if df.columns[0].startswith("Unnamed"):
        df = df.drop(columns=[df.columns[0]])

    # Show columns to confirm what we got
    print("Columns:", list(df.columns))

    # You will need to map these based on actual columns returned
    # Common patterns might be: Date, Price, 200WMA (or similar)
    # For now, try to infer:
    date_col = "Date" if "Date" in df.columns else df.columns[0]

    # Try common price column names
    price_col = None
    for c in ["Price", "price", "BTC Price", "btc_price"]:
        if c in df.columns:
            price_col = c
            break

    # Try common 200wma column names
    ma_col = None
    for c in ["200WMA", "200wma", "wma_200", "200 Week Moving Average", "200_week_ma"]:
        if c in df.columns:
            ma_col = c
            break

    if price_col is None or ma_col is None:
        raise RuntimeError(
            "Could not find expected columns for price and 200WMA. "
            f"Got columns: {list(df.columns)}"
        )

    df = df[[date_col, price_col, ma_col]].copy()
    df.columns = ["date", "price", "ma200w"]

    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["ma200w"] = pd.to_numeric(df["ma200w"], errors="coerce")
    df = df.dropna()

    out = df.to_dict(orient="records")
    Path("data").mkdir(parents=True, exist_ok=True)

    with open("data/200wma.json", "w") as f:
        json.dump(out, f)

    print(f"Wrote {len(out)} rows to data/200wma.json")

if __name__ == "__main__":
    main()
