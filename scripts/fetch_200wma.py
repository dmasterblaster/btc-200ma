import os
import io
import json
import requests
import pandas as pd


API_URL = "https://api.bitcoinmagazinepro.com/v1/metrics/200wma-heatmap"
OUT_PATH = "data/200wma.json"


def pick_column(columns, candidates):
    """
    Return the first column name that matches any candidate (case-insensitive).
    """
    lower_map = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    return None


def main():
    api_key = os.environ.get("BMP_API_KEY")
    if not api_key:
        raise RuntimeError("Missing BMP_API_KEY environment variable (set GitHub secret BMP_API_KEY).")

    headers = {
        "X-Api-Key": api_key,
        "Accept": "text/csv",
    }

    resp = requests.get(API_URL, headers=headers, timeout=60)
    print("BMP API status code:", resp.status_code)
    resp.raise_for_status()

    text = resp.text
    if not text or len(text.strip()) < 10:
        raise RuntimeError("Empty response body from BMP API.")

    # Read CSV
    df = pd.read_csv(io.StringIO(text))

    if df is None or df.empty:
        raise RuntimeError(f"Parsed empty DataFrame from CSV. Columns: {list(df.columns)}")

    # Try to detect columns
    cols = list(df.columns)

    date_col = pick_column(cols, ["Date", "date", "time", "timestamp"])
    price_col = pick_column(cols, ["Price", "price", "btc_price", "BTC Price", "BTC_Price"])
    ma_col = pick_column(cols, [
        "200WMA", "200wma", "200_WMA", "200_wma",
        "200 Week Moving Average", "200 Week MA", "200 Week Moving Average Price",
        "two_hundred_week_moving_average", "Two Hundred Week Moving Average",
        "MA_200W", "ma_200w"
    ])

    # If price column is missing, sometimes first numeric after Date is price
    if date_col is None:
        raise RuntimeError(f"Could not find a date column. CSV columns: {cols}")

    # Normalize date to string YYYY-MM-DD
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.dropna(subset=[date_col])

    # Try fallback heuristics if columns not found
    numeric_cols = [c for c in cols if c != date_col]

    # If still missing price_col, guess from common name patterns
    if price_col is None:
        # pick first column that contains "price" but is not realized price etc
        for c in cols:
            lc = c.lower()
            if "price" in lc and "real" not in lc and "realized" not in lc:
                price_col = c
                break

    # If still missing, fallback to first numeric column
    if price_col is None and numeric_cols:
        price_col = numeric_cols[0]

    # If ma_col missing, try to find a column containing "200" and "wma" or "week"
    if ma_col is None:
        for c in cols:
            lc = c.lower()
            if "200" in lc and ("wma" in lc or "week" in lc) and "heat" not in lc:
                ma_col = c
                break

    if ma_col is None:
        raise RuntimeError(f"Could not find a 200WMA column. CSV columns: {cols}")

    # Convert to numeric
    df[price_col] = pd.to_numeric(df[price_col], errors="coerce")
    df[ma_col] = pd.to_numeric(df[ma_col], errors="coerce")

    df = df.dropna(subset=[price_col, ma_col])
    df = df.sort_values(by=date_col)

    out = []
    for _, row in df.iterrows():
        out.append({
            "date": row[date_col],
            "price": float(row[price_col]),
            "ma200w": float(row[ma_col]),
        })

    os.makedirs("data", exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(out)} rows to {OUT_PATH}")


if __name__ == "__main__":
    main()
