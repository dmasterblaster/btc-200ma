# scripts/fetch_200dma.py
import io
import json
import os

import pandas as pd
import requests

METRIC = "200wma-heatmap"
URL = f"https://api.bitcoinmagazinepro.com/metrics/{METRIC}"

# ROOT data path (this is the key fix)
OUT_PATH = "data/200dma.json"


def pick_col(df: pd.DataFrame, candidates):
    cols = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in cols:
            return cols[c.lower()]
    raise ValueError(f"Missing column, found: {df.columns}")


def coerce_csv(raw: str) -> str:
    s = raw.strip()
    if s.startswith('"') and s.endswith('"'):
        s = json.loads(s)
    if s.startswith(","):
        s = s[1:]
    return s


def main():
    api_key = os.environ["BMP_API_KEY"]

    resp = requests.get(
        URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "*/*",
        },
        timeout=30,
    )
    resp.raise_for_status()

    csv_text = coerce_csv(resp.text)
    df = pd.read_csv(io.StringIO(csv_text))

    date_col = pick_col(df, ["date", "time", "timestamp"])
    price_col = pick_col(df, ["price"])

    df = df[[date_col, price_col]].rename(
        columns={date_col: "date", price_col: "price"}
    )

    df["date"] = pd.to_datetime(df["date"])
    df["price"] = pd.to_numeric(df["price"])
    df = df.sort_values("date")

    df["dma200"] = df["price"].rolling(200).mean()
    df = df.dropna()

    rows = [
        {"date": d.strftime("%Y-%m-%d"), "price": float(p), "dma200": float(m)}
        for d, p, m in zip(df["date"], df["price"], df["dma200"])
    ]

    os.makedirs("data", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(rows, f)

    print(f"Wrote {OUT_PATH} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
