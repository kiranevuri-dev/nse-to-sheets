[github_readme.md](https://github.com/user-attachments/files/35420714/github_readme.md)
# NSE & BSE Index Futures Bhavcopy Tracker

An automated Python pipeline that downloads daily End-of-Day (EOD) **UDiFF Bhavcopy** reports from both **NSE** and **BSE**, extracts front-month futures data for **NIFTY**, **BANKNIFTY**, and **SENSEX**, and logs the results into a Google Sheet in descending chronological order.

---

## Features

- **Multi-Exchange UDiFF Support:** Fetches `.csv.zip` archives from NSE (`NIFTY`, `BANKNIFTY`) and uncompressed `.CSV` files from BSE (`SENSEX`).
- **Front-Month Contract Filtering:** Automatically selects the nearest expiry (`IDF`) independently for each index symbol.
- **IST Timezone & Holiday Safe:** Explicitly uses `Asia/Kolkata` (IST) to prevent UTC date mismatches on cloud servers and exits cleanly on weekends or exchange holidays (`404`).
- **Automated Google Sheet Formatting:**
  - Creates, bolds, and freezes the header row (`A1:J1`) on first run without overwriting existing records.
  - Appends values using `USER_ENTERED` so prices, open interest, and volumes remain numeric for formulas and charts.
  - Deduplicates entries by `(Trade Date, Symbol)` to ensure idempotent re-runs.
  - Sorts the entire table (`A2:J`) in **descending order by Trade Date** so the latest trading session always appears at the top.

---

## Google Sheet Schema

The script writes to a spreadsheet named **`Index_Futures_Data`** (first worksheet) with the following columns:

| Column | Header | UDiFF Field | Description |
| :--- | :--- | :--- | :--- |
| **A** | `Trade Date` | `TradDt` | Trading date (`YYYY-MM-DD`) |
| **B** | `Symbol` | `TckrSymb` | Index ticker (`NIFTY`, `BANKNIFTY`, `SENSEX`) |
| **C** | `Expiry Date` | `XpryDt` | Nearest futures contract expiry (`YYYY-MM-DD`) |
| **D** | `Open` | `OpnPric` | Opening futures price |
| **E** | `High` | `HghPric` | Intraday high price |
| **F** | `Low` | `LwPric` | Intraday low price |
| **G** | `Close` | `ClsPric` | Closing futures price |
| **H** | `Settlement Price` | `SttlmPric` | Daily EOD settlement price |
| **I** | `Open Interest` | `OpnIntrst` | End-of-day open interest |
| **J** | `Volume` | `TtlTradgVol` | Total contracts traded |

---

## Prerequisites & Setup

### 1. Google Cloud & Service Account Setup
1. Open the [Google Cloud Console](https://console.cloud.google.com/) and create or select a project.
2. Enable both the **Google Sheets API** and **Google Drive API**.
3. Navigate to **IAM & Admin → Service Accounts**, create a new service account, and generate a **JSON key**.
4. Create a Google Sheet titled **`Zerodha_Futures_Data`**.
5. Click **Share** on the Google Sheet and grant **Editor** access to the `client_email` address found inside your downloaded JSON key file.

### 2. Local Installation
Clone this repository and install the required dependencies:

```bash
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>
pip install gspread pandas requests
```

### 3. Configure Environment Variables
Set the entire contents of your Google Service Account JSON file as the `GOOGLE_CREDS` environment variable:

**Linux / macOS:**
```bash
export GOOGLE_CREDS='{"type": "service_account", "project_id": "...", ...}'
python main.py
```

**Windows (PowerShell):**
```powershell
$env:GOOGLE_CREDS = Get-Content -Raw -Path "path\to\service-account.json"
python main.py
```

---

## Automating Daily Runs with GitHub Actions

NSE and BSE typically publish EOD derivatives Bhavcopy files between **6:00 PM and 7:30 PM IST**. You can run this script automatically every weekday using GitHub Actions:

1. In your GitHub repository, go to **Settings → Secrets and variables → Actions**.
2. Click **New repository secret**, name it `GOOGLE_CREDS`, and paste the full JSON content of your service account key.
3. Add `.github/workflows/daily_bhavcopy.yml` to your repository:

```yaml
name: Daily NSE & BSE Futures Bhavcopy

on:
  schedule:
    # Runs at 14:00 UTC (7:30 PM IST) Monday through Friday
    - cron: "0 14 * * 1-5"
  workflow_dispatch:

jobs:
  fetch-bhavcopy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install gspread pandas requests

      - name: Run Bhavcopy script
        env:
          GOOGLE_CREDS: ${{ secrets.GOOGLE_CREDS }}
        run: python main.py
```

---

## Repository Structure

```text
├── .github/
│   └── workflows/
│       └── daily_bhavcopy.yml   # Scheduled GitHub Actions workflow
├── main.py                      # Main NSE + BSE Bhavcopy fetcher & Sheet updater
├── requirements.txt             # Python dependencies (gspread, pandas, requests)
└── README.md                    # Project documentation
```

---

## Disclaimer

This project fetches publicly available end-of-day market reports from NSE India and BSE India for personal data logging and analysis. Ensure your usage complies with the respective exchanges' terms of service.
