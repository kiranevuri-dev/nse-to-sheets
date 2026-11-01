from datetime import date
import io
import json
import os
import zipfile
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import requests

# 1. Google Sheets Setup (GitHub Secret నుండి క్రెడెన్షియల్స్ తీసుకోవడం)
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
import gspread

client = gspread.authorize(creds)

# మీ Google Sheet పేరు ఇక్కడ ఇవ్వండి (మీ గూగుల్ షీట్ పేరుతో మార్చుకోండి)
sheet = client.open("Zerodha_Futures_Data").sheet1

# 2. NSE Bhavcopy Download Setup
TODAY = date.today()
URL = "https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{d}_F_0000.csv.zip"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"}

s = requests.Session()
s.headers.update(HEADERS)
s.get("https://www.nseindia.com", timeout=15)

try:
  r = s.get(URL.format(d=TODAY.strftime("%Y%m%d")), timeout=30)
  if r.status_code == 200:
    z = zipfile.ZipFile(io.BytesIO(r.content))
    df = pd.read_csv(z.open(z.namelist()[0]))

    # Nifty & BankNifty Index Futures ఫిల్టర్ చేయడం
    SYMBOLS = ["NIFTY", "BANKNIFTY"]
    df = df[(df["FinInstrmTp"] == "IDF") & (df["TckrSymb"].isin(SYMBOLS))]

    # కరెంట్ మంత్ (Nearest Expiry) డేటాను ఎంచుకోవడం
    df["XpryDt"] = pd.to_datetime(df["XpryDt"])
    df = df.sort_values("XpryDt")
    nearest_expiry = df["XpryDt"].min()
    df = df[df["XpryDt"] == nearest_expiry]

    cols = [
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

    # గూగుల్ షీట్‌లోకి డేటాను అపెండ్ చేయడం
    for _, row in df[cols].iterrows():
      row_list = [str(val) for val in row.values]
      sheet.append_row(row_list)

    print("Data successfully updated to Google Sheet!")
  else:
    print("Market might be closed today (Holiday/Weekend). Status:", r.status_code)
except Exception as e:
  print("Error fetching data:", e)
