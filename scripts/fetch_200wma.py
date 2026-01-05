import io
import json
import os

import pandas as pd
import requests


METRIC = "200wma-heatmap"
URL = f"https://api.bitcoinmagazinepro.com/metrics/{METRIC}"
OUT_PATH = "docs/data/200wma.json"  # change if your Pages root is different


def pick_col(df: pd.DataFrame, candidates: list[str]) -> str:
    # case-insensitive column picker
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
        "Accept": "text/csv",
    }

    resp = requests.get(URL, headers=headers, timeout=45)
    print("BMP API status code:", resp.status_code)
    resp.raise_for_status()

    # Parse CSV
    df = pd.read_csv(io.StringIO(resp.text))

    # Find columns (BMP sometimes varies naming slightly)
    date_col = pick_col(df, ["Date", "date", "Time", "time", "Timestamp", "timestamp"])
    price_col = pick_col(df, ["Price", "price"])
    ma_col = pick_col(df, ["200WMA", "200wma", "MA200W", "ma200w", "200 Week Moving Average"])

    out = df[[date_col, price_col, ma_col]].copy()
    out.columns = ["date", "price", "ma200w"]

    # Normalize
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"])
    out = out.sort_values("date")

    out["price"] = pd.to_numeric(out["price"], errors="coerce")
    out["ma200w"] = pd.to_numeric(out["ma200w"], errors="coerce")
    out = out.dropna(subset=["price", "ma200w"])

    # Convert to the exact JSON format your HTML expects
    rows = [
        {
            "date": d.strftime("%Y-%m-%d"),
            "price": float(p),
            "ma200w": float(m),
        }
        for d, p, m in zip(out["date"], out["price"], out["ma200w"])
    ]

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)

    print(f"Wrote {OUT_PATH} rows={len(rows)}")


if __name__ == "__main__":
    main()
