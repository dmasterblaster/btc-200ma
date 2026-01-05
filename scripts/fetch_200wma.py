import io
import json
import os
import pandas as pd
import requests

METRIC = "200wma-heatmap"
URL = f"https://api.bitcoinmagazinepro.com/metrics/{METRIC}"
OUT_PATH = "docs/data/200wma.json"


def main():
    api_key = os.environ["BMP_API_KEY"]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "*/*",
        "User-Agent": "btc-200wma-script",
    }

    resp = requests.get(URL, headers=headers, timeout=30)
    print("Status:", resp.status_code)
    resp.raise_for_status()

    raw = resp.text.strip()

    # Endpoint returns a JSON string that contains CSV
    if raw.startswith('"') and raw.endswith('"'):
        raw = json.loads(raw)

    # Remove leading comma if present
    if raw.startswith(","):
        raw = raw[1:]

    df = pd.read_csv(io.StringIO(raw))

    # Expected columns from BMP
    df = df.rename(columns={
        "Date": "date",
        "Price": "price",
        "200week_avg": "ma200w"
    })

    df = df[["date", "price", "ma200w"]].dropna()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    rows = [
        {
            "date": d.strftime("%Y-%m-%d"),
            "price": float(p),
            "ma200w": float(m),
        }
        for d, p, m in zip(df["date"], df["price"], df["ma200w"])
    ]

    os.makedirs("docs/data", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(rows, f)

    print(f"Wrote {OUT_PATH} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
