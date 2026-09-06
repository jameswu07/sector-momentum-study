"""
common.py — shared constants and helpers for the sector-momentum study.

Every script imports from here so that the universe definition, the
train/test boundary and the statistics functions are defined exactly once.
Changing anything in this file changes every result downstream.
"""

from pathlib import Path
import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"
DATA.mkdir(exist_ok=True)
RESULTS.mkdir(exist_ok=True)

# --------------------------------------------------------------------------
# Universe
#
# 9 SPDR sector ETFs + 6 thematic ETFs. SPY, QQQ and BIL are NOT part of the
# tradeable universe by default; they enter as benchmarks, and in Tests 4 and 5
# as additional ranking candidates.
#
# HONEST NOTE ON SELECTION BIAS: this list was chosen in 2026 with knowledge
# of which themes performed well (lithium, uranium, gold). That bias inflates
# every backtest result below and is not removed by the train/test split.
# --------------------------------------------------------------------------
UNIVERSE = [
    "XLE", "XLK", "XLF", "XLV", "XLI", "XLB", "XLY", "XLP", "XLU",   # sectors
    "GDX", "SIL", "URA", "LIT", "COPX", "SMH",                        # thematics
]
BENCH = "SPY"      # primary benchmark
GROWTH = "QQQ"     # secondary benchmark / Test 5 candidate
CASH = "BIL"       # 1-3 month T-bill ETF, used as the cash leg

ALL_TICKERS = UNIVERSE + [BENCH, GROWTH, CASH]

# --------------------------------------------------------------------------
# Study parameters — fixed before results were seen
# --------------------------------------------------------------------------
DOWNLOAD_START = "2004-01-01"   # pull everything, then clip
DOWNLOAD_END = "2026-09-05"     # exclusive; last bar is 2026-09-04
PANEL_START = "2010-11-05"      # first date on which ALL 15 universe ETFs exist
TRAIN_END = pd.Timestamp("2018-12-31")

LOOKBACKS = [20, 60, 120]       # momentum lookbacks, trading days
HORIZONS = [5, 10, 21]          # forward return / rebalance horizons
WARMUP = 200                    # bars reserved so the 200-day SMA is defined
COST_BPS = 8                    # per side of traded notional: IBKR min
                                # commission on a ~US$1,100 position (~3.2bp)
                                # plus roughly half the ETF spread


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------
def load_prices(clip=True):
    """Load the saved adjusted-close panel.

    Prefers Parquet; falls back to CSV so the archive stays readable even if
    the Parquet engine is unavailable.
    """
    pq, csv = DATA / "prices.parquet", DATA / "prices.csv"
    if pq.exists():
        px = pd.read_parquet(pq)
    elif csv.exists():
        px = pd.read_csv(csv, index_col=0, parse_dates=True)
    else:
        raise FileNotFoundError(
            "No price file found. Run src/01_pull_data.py first."
        )
    px.index = pd.to_datetime(px.index)
    px = px.sort_index()
    return px.loc[PANEL_START:] if clip else px


def split_train(px):
    """Return the training slice. The test period is never returned here."""
    return px.loc[:TRAIN_END]


# --------------------------------------------------------------------------
# Signals
# --------------------------------------------------------------------------
def momentum(frame, lookback):
    """Total return over `lookback` trading days."""
    return frame / frame.shift(lookback) - 1


def blend_signal(frame, lookbacks=LOOKBACKS):
    """Average of the cross-sectional ranks of each lookback's momentum.

    Rank-averaging rather than return-averaging so that the three lookbacks
    contribute equally regardless of their different return scales.
    """
    ranks = [momentum(frame, L).rank(axis=1) for L in lookbacks]
    return sum(ranks) / len(ranks)


def build_signals(frame, lookbacks=LOOKBACKS):
    """Dict of every signal tested: each raw lookback, plus the blend."""
    sigs = {f"mom{L}": momentum(frame, L) for L in lookbacks}
    sigs["blend"] = blend_signal(frame, lookbacks)
    return sigs


# --------------------------------------------------------------------------
# Evaluation helpers
# --------------------------------------------------------------------------
def aligned(sig, fwd, date):
    """Signal and forward return for one date, aligned and NaN-dropped."""
    both = pd.concat([sig.loc[date], fwd.loc[date]], axis=1)
    both.columns = ["sig", "fwd"]
    return both.dropna()


def forward_returns(frame, horizon):
    """Simple return over the next `horizon` trading days.

    Computed AFTER the training slice is taken, so the final `horizon` bars
    become NaN rather than peeking into the test period.
    """
    return frame.shift(-horizon) / frame - 1


def rebalance_dates(sig, sig_start, horizon):
    """Non-overlapping rebalance dates, so IC observations are independent."""
    return sig.loc[sig_start:].index[::horizon]


def stats(r, horizon, label, out=None):
    """Print and return the standard risk/return summary for a return series.

    Ret/Vol is CAGR divided by annualised volatility. It is close to a Sharpe
    ratio because the risk-free rate was near zero for most of 2011-2018, but
    it is NOT risk-free adjusted.

    ex-best5 recomputes the CAGR with the five best periods removed. It is the
    outlier-dependence test: a strategy whose return collapses when a handful
    of periods are dropped is not reliably repeatable.
    """
    n = len(r)
    yrs = n * horizon / 252
    cagr = (1 + r).prod() ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(252 / horizon)
    eq = (1 + r).cumprod()
    dd = (eq / eq.cummax() - 1).min()
    ex = r.drop(r.nlargest(5).index)
    cagr_x = (1 + ex).prod() ** (1 / (len(ex) * horizon / 252)) - 1
    row = {
        "label": label, "CAGR%": 100 * cagr, "vol%": 100 * vol,
        "Ret/Vol": cagr / vol if vol > 0 else np.nan,
        "maxDD%": 100 * dd, "ex_best5_CAGR%": 100 * cagr_x, "n_periods": n,
    }
    print(f"  {label:28s} CAGR {row['CAGR%']:6.2f}%  vol {row['vol%']:5.1f}%  "
          f"Ret/Vol {row['Ret/Vol']:5.2f}  maxDD {row['maxDD%']:6.1f}%  "
          f"ex-best5 {row['ex_best5_CAGR%']:6.2f}%")
    if out is not None:
        out.append(row)
    return row


def build_curve(sig, prices, sig_start, horizon, n_top=3, use_gate=False,
                costs=False, min_assets=10, cash_ticker=CASH, cash_prices=None):
    """Run the long-only top-N rotation and return its per-period returns.

    Rules, in order:
      1. At each rebalance date, rank all candidates by `sig`.
      2. If `use_gate`, drop any candidate trading below its own 200-day SMA.
         The cash ticker is exempt from the gate.
      3. Hold the top `n_top` survivors, equally weighted.
      4. If fewer than `n_top` survive, the remaining weight sits in cash.
         If NOTHING survives the gate, the whole portfolio sits in cash.
      5. If `costs`, subtract COST_BPS per side on the notional actually traded.

    The cash return is taken from `prices[cash_ticker]` when the cash ticker is
    part of the candidate frame (Tests 4-5). When it is not (Tests 1-3 rank the
    15-name universe only), pass the cash price series as `cash_prices`.

    Positions are held for exactly `horizon` days; there are no intra-period
    stops in this version.
    """
    fwd = forward_returns(prices, horizon)
    sma = prices.rolling(200).mean()

    if cash_ticker in prices.columns:
        cash_fwd = fwd[cash_ticker]
    elif cash_prices is not None:
        cash_fwd = forward_returns(cash_prices.to_frame(cash_ticker),
                                   horizon)[cash_ticker]
    else:
        cash_fwd = None

    rows, prev = [], set()
    for d in rebalance_dates(sig, sig_start, horizon):
        both = aligned(sig, fwd, d)
        if len(both) < min_assets:
            continue

        c = 0.0
        if cash_fwd is not None:
            v = cash_fwd.get(d, np.nan)
            c = 0.0 if pd.isna(v) else float(v)

        cand = both
        if use_gate:
            above = prices.loc[d] > sma.loc[d]
            keep = [t for t in both.index
                    if t == cash_ticker or above.get(t, False)]
            cand = both.loc[keep]          # may legitimately be empty

        order = list(cand["sig"].sort_values(ascending=False).index[:n_top])
        held = len(order)
        r = (cand.loc[order, "fwd"].sum() + (n_top - held) * c) / n_top

        changed = len(set(order) - prev)
        if costs:
            r -= 2 * (changed / n_top) * COST_BPS / 10000
        rows.append({"date": d, "ret": r, "held": held, "changed": changed,
                     "names": order})
        prev = set(order)
    return pd.DataFrame(rows).set_index("date")


def bench_returns(px, ticker, horizon, index):
    """Buy-and-hold benchmark returns sampled on the same rebalance dates."""
    return (px[ticker].shift(-horizon) / px[ticker] - 1).loc[index]
