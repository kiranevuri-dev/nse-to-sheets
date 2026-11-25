from datetime import datetime
import io
import json
import os
import sys
import zipfile
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
import requests

# 1. Google Sheets Setup
creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
client = gspread.service_account_from_dict(creds_dict)
sheet = client.open("Zerodha_Futures_Data").sheet1

# 2. Date & Weekend Check (Explicit IST)
IST = ZoneInfo("Asia/Kolkata")
TODAY = datetime.now(IST).date()
DATE_STR = TODAY.strftime("%Y%m%d")

if TODAY.weekday() >= 5:
    print("Today is a weekend (Holiday). Market is closed. Exiting safely.")
    sys.exit(0)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

COLS = [
    "TradDt",
    "TckrSymb",
    "XpryDt",
    "OpnPric",
    "HghPric",
    "LwPric",
    "ClsPric",
    "SttlmPric",
    "OpnIntrst",
    "TtlTradgVol",
]


def parse_udiff_futures(raw_bytes: bytes, symbols: list[str]) -> pd.DataFrame:
    """Reads either a zipped or plain UDiFF CSV and extracts front-month IDF rows."""
    if raw_bytes[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
            csv_name = next(name for name in z.namelist() if name.lower().endswith(".csv"))
            with z.open(csv_name) as f:
                df = pd.read_csv(f)
    else:
        df = pd.read_csv(io.BytesIO(raw_bytes))

    # Strip any extra whitespace in headers or string identifiers
    df.columns = df.columns.str.strip()
    df["FinInstrmTp"] = df["FinInstrmTp"].astype(str).str.strip()
    df["TckrSymb"] = df["TckrSymb"].astype(str).str.strip()

    df = df[(df["FinInstrmTp"] == "IDF") & (df["TckrSymb"].isin(symbols))].copy()
    if df.empty:
        return df

    # Keep the nearest expiry independently for each symbol
    df["XpryDt"] = pd.to_datetime(df["XpryDt"])
    nearest_per_symbol = df.groupby("TckrSymb")["XpryDt"].transform("min")
    df = df[df["XpryDt"] == nearest_per_symbol].sort_values("TckrSymb")

    df["XpryDt"] = df["XpryDt"].dt.strftime("%Y-%m-%d")
    df["TradDt"] = pd.to_datetime(df["TradDt"]).dt.strftime("%Y-%m-%d")
    return df[COLS]


def fetch_nse_futures(date_str: str) -> pd.DataFrame:
    url = f"https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{date_str}_F_0000.csv.zip"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/all-reports-derivatives",
    }
    session = requests.Session()
    session.headers.update(headers)
    session.get("https://www.nseindia.com", timeout=15)

    r = session.get(url, timeout=30)
    if r.status_code == 404:
        print(f"NSE Bhavcopy not available yet for {TODAY}.")
        return pd.DataFrame(columns=COLS)
    r.raise_for_status()
    return parse_udiff_futures(r.content, ["NIFTY", "BANKNIFTY"])


def fetch_bse_futures(date_str: str) -> pd.DataFrame:
    url = f"https://www.bseindia.com/download/BhavCopy/Derivative/BhavCopy_BSE_FO_0_0_0_{date_str}_F_0000.CSV"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/csv,application/octet-stream,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.bseindia.com/",
    }
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code == 404:
        print(f"BSE Bhavcopy not available yet for {TODAY}.")
        return pd.DataFrame(columns=COLS)
    r.raise_for_status()
    return parse_udiff_futures(r.content, ["SENSEX"])


try:
    frames = []
    for label, fetcher in [("NSE", fetch_nse_futures), ("BSE", fetch_bse_futures)]:
        try:
            data = fetcher(DATE_STR)
            if not data.empty:
                frames.append(data)
        except Exception as exchange_err:
            print(f"Warning: {label} fetch failed -> {exchange_err}")

    if not frames:
        print("No market data retrieved from NSE or BSE today.")
        sys.exit(0)

    combined_df = pd.concat(frames, ignore_index=True)

    # Deduplicate against existing (TradDt, TckrSymb) entries in Google Sheets
    existing_rows = sheet.get_all_values()
    existing_keys = {(row[0], row[1]) for row in existing_rows[1:] if len(row) >= 2}

    rows_to_add = [
        [val.item() if hasattr(val, "item") else val for val in row]
        for row in combined_df.itertuples(index=False, name=None)
        if (row[0], row[1]) not in existing_keys
    ]

    if rows_to_add:
        sheet.append_rows(rows_to_add, value_input_option="USER_ENTERED")
        added_symbols = [r[1] for r in rows_to_add]
        print(f"Added {len(rows_to_add)} row(s) ({', '.join(added_symbols)}) to Google Sheet!")
    else:
        print("All fetched symbols for today are already present in the sheet.")

except Exception as e:
    print("Fatal error updating Google Sheet:", e)
    sys.exit(1)
