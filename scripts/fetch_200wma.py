# scripts/fetch_200wma.py
import io
import json
import os

import pandas as pd
import requests


METRIC = "200wma-heatmap"
URL = f"https://api.bitcoinmagazinepro.com/metrics/{METRIC}"
OUT_PATH = "docs/data/200wma.json"  # adjust if needed


def pick_col(df: pd.DataFrame, candidates: list[str]) -> str:
    cols_map = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidates:
        key = cand.strip().lower()
        if key in cols_map:
            return cols_map[key]
    raise KeyError(f"Missing column. Tried {candidates}. Found {list(df.columns)}")


def coerce_to_csv_text(raw: str) -> str:
    s = raw.strip()

    # Case 1: The entire response is a JSON string that contains CSV (starts with a quote)
    # Example: ",Date,Price...\n0,2010-..."
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        try:
            s = json.loads(s)  # unescape \n, \\, etc.
        except Exception:
            # If it's quoted but not valid JSON, just strip the outer quotes
            s = s[1:-1]

    # Sometimes the CSV starts with an empty first header due to a leading comma or '",'
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

    # Parse CSV
    df = pd.read_csv(io.StringIO(csv_text))

    # Expected columns: Date, Price, 200week_avg (names can vary slightly)
    date_col = pick_col(df, ["Date", "date", "Time", "time", "Timestamp", "timestamp"])
    price_col = pick_col(df, ["Price", "price"])
    ma_col = pick_col(df, ["200week_avg", "200weekavg", "200wma", "200WMA", "ma200w", "200_week_avg"])

    out = df[[date_col, price_col, ma_col]].copy()
    out.columns = ["date", "price", "ma200w"]

    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["price"] = pd.to_numeric(out["price"], errors="coerce")
    out["ma200w"] = pd.to_numeric(out["ma200w"], errors="coerce")

    out = out.dropna(subset=["date", "price", "ma200w"]).sort_values("date")

    rows = [
        {"date": d.strftime("%Y-%m-%d"), "price": float(p), "ma200w": float(m)}
        for d, p, m in zip(out["date"], out["price"], out["ma200w"])
    ]

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f)

    print(f"Wrote {OUT_PATH} rows={len(rows)}")


if __name__ == "__main__":
    main()
