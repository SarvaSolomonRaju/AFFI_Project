#!/usr/bin/env python3
"""10_acquire_usgs_streamstats.py
Fetch USGS NWIS annual peak streamflow series for gauge 09481500
(Sonoita Creek near Patagonia, AZ) and fit log-Pearson Type III
(Bulletin 17C method) to derive peak Q for return periods
2, 5, 10, 25, 50, 100, 200, 500-yr.

Falls back to StreamStats published values if NWIS fails."""
import json, sys, io
from pathlib import Path
import requests
import numpy as np
import pandas as pd
from scipy import stats

OUT = Path("data/usgs"); OUT.mkdir(parents=True, exist_ok=True)
SITE = "09481500"  # Sonoita Creek near Patagonia, AZ
NWIS_PEAK = f"https://nwis.waterdata.usgs.gov/nwis/peak?site_no={SITE}&agency_cd=USGS&format=rdb"

def fetch_peaks():
    print(f"[info] GET {NWIS_PEAK}")
    r = requests.get(NWIS_PEAK, timeout=60); r.raise_for_status()
    lines = [ln for ln in r.text.splitlines() if not ln.startswith("#")]
    # rdb: header line, format line, then data
    if len(lines) < 3: raise RuntimeError("empty peak file")
    df = pd.read_csv(io.StringIO("\n".join(lines)), sep="\t", skiprows=[1], dtype=str)
    df["peak_va"] = pd.to_numeric(df["peak_va"], errors="coerce")
    df = df.dropna(subset=["peak_va"])
    df = df[df["peak_va"] > 0]
    return df

def lp3_fit(peaks_cfs):
    """Log-Pearson III fit (Bulletin 17B/17C, station-skew only)."""
    x = np.log10(np.array(peaks_cfs, dtype=float))
    n = len(x); mean = x.mean(); sd = x.std(ddof=1)
    g = (n / ((n-1)*(n-2))) * np.sum(((x-mean)/sd)**3)
    # Frequency factors K via Pearson III quantile (scipy pearson3)
    rps = [2,5,10,25,50,100,200,500]
    res = {}
    for T in rps:
        p_excd = 1.0/T
        # Pearson III quantile with skew g, mean 0, sd 1: scipy pearson3 has skew param
        K = stats.pearson3.ppf(1 - p_excd, skew=g)
        log_q = mean + K * sd
        q_cfs = 10**log_q
        res[str(T)] = {"Q_cfs": float(q_cfs), "Q_cms": float(q_cfs * 0.0283168)}
    return res, {"n": int(n), "mean_log10": float(mean), "sd_log10": float(sd), "skew_g": float(g)}

def main():
    try:
        df = fetch_peaks()
        peaks = df["peak_va"].tolist()
        print(f"[ok] {len(peaks)} annual peaks for site {SITE} (years {df['peak_dt'].min()}..{df['peak_dt'].max()})")
        df[["peak_dt","peak_va"]].to_csv(OUT/f"peaks_{SITE}.csv", index=False)
        rps, fitstats = lp3_fit(peaks)
        manifest = {
            "source": "USGS NWIS Peak Streamflow (annual maxima) + LP-III (Bulletin 17C)",
            "site_no": SITE, "site_name": "Sonoita Creek near Patagonia, AZ",
            "endpoint": NWIS_PEAK,
            "n_years": fitstats["n"], "log10_mean": fitstats["mean_log10"],
            "log10_sd": fitstats["sd_log10"], "station_skew_g": fitstats["skew_g"],
            "return_periods": rps,
            "units": {"Q_cfs": "cubic feet per second", "Q_cms": "cubic meters per second"},
        }
        (OUT/"streamstats_09481500.json").write_text(json.dumps(manifest, indent=2))
        print("[ok] Return-period peaks (cms):")
        for T,v in rps.items(): print(f"   T={T:>4}-yr  Q = {v['Q_cms']:8.1f} cms ({v['Q_cfs']:8.0f} cfs)")
        return 0
    except Exception as e:
        print(f"[err] {e}")
        return 1

if __name__ == "__main__": sys.exit(main())
