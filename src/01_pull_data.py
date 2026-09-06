"""
01_pull_data.py — download the price panel and record its provenance.

Run:  python src/01_pull_data.py

Writes:
  data/prices.parquet   fast binary copy
  data/prices.csv       human-readable archival copy
  data/manifest.txt     SHA256, shape, date range, package versions

WHY THE MANIFEST: yfinance reads live Yahoo data, which is revised over time
and extends every day. A rerun in 2027 will NOT produce an identical file. The
manifest lets a future run detect that the data changed, rather than silently
producing different numbers. To reproduce the exact 2026 results, use the
archived CSV rather than re-downloading.
"""

import hashlib
import sys

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import (ALL_TICKERS, DATA, DOWNLOAD_END, DOWNLOAD_START,
                    PANEL_START, UNIVERSE)


def download(tickers, start, end, tries=3):
    """Download adjusted closes, retrying tickers that come back empty.

    yfinance uses a local SQLite cache that can throw
    'database is locked' under parallel downloads, which produces a column of
    NaNs rather than an error. This silently corrupts the panel, so any empty
    column is re-fetched one ticker at a time.
    """
    raw = yf.download(tickers, start=start, end=end, auto_adjust=True,
                      progress=False, group_by="column")
    px = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
    px = px.dropna(how="all")

    for attempt in range(tries):
        empty = [t for t in tickers
                 if t not in px.columns or px[t].isna().all()]
        if not empty:
            break
        print(f"  retry {attempt + 1}: refetching {empty}")
        for t in empty:
            one = yf.download(t, start=start, end=end, auto_adjust=True,
                              progress=False)
            s = one["Close"]
            if isinstance(s, pd.DataFrame):
                s = s.iloc[:, 0]
            px[t] = s.reindex(px.index)

    still_empty = [t for t in tickers
                   if t not in px.columns or px[t].isna().all()]
    if still_empty:
        raise RuntimeError(f"No data for: {still_empty}")
    return px[[t for t in tickers if t in px.columns]]


def main():
    print(f"Downloading {len(ALL_TICKERS)} tickers "
          f"{DOWNLOAD_START} -> {DOWNLOAD_END}")
    px = download(ALL_TICKERS, DOWNLOAD_START, DOWNLOAD_END)

    px.to_parquet(DATA / "prices.parquet")
    px.to_csv(DATA / "prices.csv")

    digest = hashlib.sha256(
        (DATA / "prices.csv").read_bytes()).hexdigest()

    inception = pd.Series(
        {t: px[t].first_valid_index() for t in px.columns}).sort_values()
    universe_start = max(inception[t] for t in UNIVERSE)

    lines = [
        "sector-momentum-study data manifest",
        f"generated            : {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC",
        f"download window      : {DOWNLOAD_START} -> {DOWNLOAD_END} (end exclusive)",
        f"shape                : {px.shape[0]} rows x {px.shape[1]} cols",
        f"date range           : {px.index.min():%Y-%m-%d} -> {px.index.max():%Y-%m-%d}",
        f"sha256(prices.csv)   : {digest}",
        f"universe complete from: {universe_start:%Y-%m-%d}",
        f"PANEL_START in common : {PANEL_START}",
        "",
        "package versions",
        f"  python  {sys.version.split()[0]}",
        f"  pandas  {pd.__version__}",
        f"  yfinance {yf.__version__}",
        "",
        "inception dates",
    ] + [f"  {t:5s} {d:%Y-%m-%d}" for t, d in inception.items()]

    (DATA / "manifest.txt").write_text("\n".join(lines) + "\n")

    print("\n".join(lines))
    print(f"\nWrote {DATA/'prices.parquet'}, prices.csv, manifest.txt")

    if str(universe_start.date()) != PANEL_START:
        print(f"\nWARNING: universe completeness date {universe_start.date()} "
              f"differs from PANEL_START {PANEL_START} in common.py. "
              f"Yahoo history changed; results will not match the 2026 run.")


if __name__ == "__main__":
    main()
