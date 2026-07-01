"""
verify_usgs_site.py — sanity check USGS station metadata + data availability.

Run:
    python scripts/verify_usgs_site.py
"""

from datetime import datetime
import requests
import pandas as pd

USGS_ID = "09481500"
START = "1900-01-01"
END = datetime.today().strftime("%Y-%m-%d")


def fetch_usgs_metadata(site_id: str):
    url = "https://waterservices.usgs.gov/nwis/site/"
    params = {
        "format": "rdb",
        "sites": site_id,
        "siteOutput": "expanded"
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.text


def fetch_usgs_daily(site_id: str):
    url = "https://waterservices.usgs.gov/nwis/dv/"
    params = {
        "format": "json",
        "sites": site_id,
        "startDT": START,
        "endDT": END,
        "parameterCd": "00060",  # discharge
        "statCd": "00003"        # mean daily
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    print(f"\n🔎 Checking USGS site {USGS_ID}\n")

    # --- Metadata ---
    meta = fetch_usgs_metadata(USGS_ID)
    print("📄 Metadata snippet:")
    print(meta.splitlines()[0:15])

    # --- Data ---
    data = fetch_usgs_daily(USGS_ID)

    try:
        values = data["value"]["timeSeries"][0]["values"][0]["value"]
    except Exception:
        raise RuntimeError("No discharge time series returned — site may not have daily data.")

    df = pd.DataFrame(values)
    df["date"] = pd.to_datetime(df["dateTime"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    print("\n📊 Data summary:")
    print("rows:", len(df))
    print("date range:", df["date"].min().date(), "→", df["date"].max().date())
    print("missing %:", round(100 * df["value"].isna().mean(), 2))
    print("mean flow:", round(df["value"].mean(), 3))

    print("\n✔ Done")


if __name__ == "__main__":
    main()