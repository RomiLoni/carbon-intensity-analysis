import argparse
import os
from datetime import datetime, timedelta, timezone
import json
import time

import requests
import pandas as pd

BASE_URL = "https://api.carbonintensity.org.uk/intensity/{start}/{end}"

def iso_date(d):
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%dT%H:%MZ")
    return f"{d}T00:00Z"

def fetch_range(start_utc: datetime, end_utc: datetime, pause=0.9) -> pd.DataFrame:
    frames = []
    cursor = start_utc
    while cursor < end_utc:
        chunk_end = min(cursor + timedelta(days=30), end_utc)
        url = BASE_URL.format(start=iso_date(cursor), end=iso_date(chunk_end))
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        data = payload.get("data", [])
        if data:
            df = pd.json_normalize(data)
            frames.append(df)
        time.sleep(pause)
        cursor = chunk_end
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    return out

def tidy(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    cols = {
        "from": "from_utc",
        "to": "to_utc",
        "intensity.forecast": "forecast_gco2_per_kwh",
        "intensity.actual": "actual_gco2_per_kwh",
        "intensity.index": "index_label",
    }
    df = df.rename(columns=cols)
    for c in ["from_utc", "to_utc"]:
        df[c] = pd.to_datetime(df[c], utc=True, errors="coerce")
    df = df.sort_values("from_utc").reset_index(drop=True)
    return df

def main():
    parser = argparse.ArgumentParser(description="Fetch UK carbon intensity data and save CSV.")
    parser.add_argument("--start", type=str, help="Start date (UTC) in YYYY-MM-DD", default=None)
    parser.add_argument("--end", type=str, help="End date (UTC) in YYYY-MM-DD", default=None)
    parser.add_argument("--days", type=int, help="Fetch last N days (overrides start/end)", default=None)
    args = parser.parse_args()

    if args.days is not None:
        end_utc = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        start_utc = end_utc - timedelta(days=args.days)
    else:
        if not args.start or not args.end:
            raise SystemExit("Provide --days OR both --start and --end (YYYY-MM-DD).")
        start_utc = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_utc = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    print(f"Fetching UK carbon intensity from {start_utc} to {end_utc} (UTC) ...")
    df_raw = fetch_range(start_utc, end_utc)
    df = tidy(df_raw)

    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = f"data/raw/uk_ci_raw_{stamp}.json"
    csv_path = f"data/processed/uk_ci_processed_{stamp}.csv"

    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(df_raw.to_dict(orient="records"), f, ensure_ascii=False)

    df.to_csv(csv_path, index=False)

    print(f"Saved raw JSON: {raw_path}")
    print(f"Saved processed CSV: {csv_path}")
    print("Done.")

if __name__ == "__main__":
    main()