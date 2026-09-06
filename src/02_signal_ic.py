"""
02_signal_ic.py — data quality checks and Test 1 (information coefficient).

Run:  python src/02_signal_ic.py

Answers one question: does ranking these ETFs by trailing return say anything
about their forward return? If the answer is no, nothing downstream matters.

The Information Coefficient is the Spearman rank correlation between the
signal and the forward return, computed across the 15 assets on each
rebalance date. Spearman is computed as a Pearson correlation of ranks so
that scipy is not required.

Writes: results/01_quality.txt, results/02_ic_table.csv
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (BENCH, CASH, HORIZONS, LOOKBACKS, RESULTS, UNIVERSE,
                    WARMUP, aligned, build_signals, forward_returns,
                    load_prices, rebalance_dates, split_train)


def quality_report(px):
    """Structural checks on the panel. Catches silent data corruption."""
    out = []

    def say(s):
        print(s)
        out.append(s)

    say(f"rows: {len(px)}   cols: {px.shape[1]}")
    say(f"range: {px.index.min():%Y-%m-%d} -> {px.index.max():%Y-%m-%d}")
    say(f"duplicate dates: {int(px.index.duplicated().sum())}")
    say(f"index sorted: {px.index.is_monotonic_increasing}")

    nans = px.isna().sum()
    say("columns with NaNs: " +
        ("none" if not (nans > 0).any() else str(nans[nans > 0].to_dict())))
    say(f"non-positive prices: {int((px <= 0).sum().sum())}")

    rets = px / px.shift(1) - 1
    big = rets.abs() > 0.25
    say(f"daily moves >25%: {int(big.to_numpy().sum())}")
    if big.to_numpy().any():
        hits = rets.where(big).dropna(how="all").dropna(axis=1, how="all")
        say(hits.round(3).to_string())
    say("")
    say("NOTE: a >25% move is flagged for eyeballing, not auto-rejected. "
        "March 2020 legitimately produced some.")
    return out


def evaluate(sig, prices, sig_start, horizon, n_top=3, min_assets=10):
    """IC and top/bottom-N forward returns for one signal at one horizon."""
    fwd = forward_returns(prices, horizon)
    ics, tops, bots = [], [], []
    for d in rebalance_dates(sig, sig_start, horizon):
        both = aligned(sig, fwd, d)
        if len(both) < min_assets:
            continue
        # Spearman == Pearson on ranks; avoids a scipy dependency
        ics.append(both["sig"].rank().corr(both["fwd"].rank()))
        order = both["sig"].sort_values(ascending=False).index
        tops.append(both.loc[order[:n_top], "fwd"].mean())
        bots.append(both.loc[order[-n_top:], "fwd"].mean())

    ics = pd.Series(ics).dropna()
    n, sd = len(ics), ics.std()
    ir = ics.mean() / sd if sd and sd > 0 else np.nan
    ann = 252 / horizon
    return {
        "n": n,
        "mean_IC": round(ics.mean(), 4),
        "IC_IR": round(ir, 3),
        "t_stat": round(ir * np.sqrt(n), 2) if n > 1 else np.nan,
        "IC_pos_%": round(100 * (ics > 0).mean(), 1),
        "top3_%pa": round(100 * np.mean(tops) * ann, 2),
        "bot3_%pa": round(100 * np.mean(bots) * ann, 2),
        "spread_%pa": round(100 * (np.mean(tops) - np.mean(bots)) * ann, 2),
    }


def main():
    px = load_prices()

    print("=== DATA QUALITY ===")
    lines = quality_report(px)
    (RESULTS / "01_quality.txt").write_text("\n".join(lines) + "\n")

    train = split_train(px)
    u = train[UNIVERSE]
    sig_start = u.index[WARMUP]

    print(f"\ntrain: {train.index.min():%Y-%m-%d} -> "
          f"{train.index.max():%Y-%m-%d}")
    print(f"signals from: {sig_start:%Y-%m-%d}   rows: {len(train)}")
    print(f"excluded from ranking: {BENCH}, {CASH} (benchmarks, Test 1-3)")

    signals = build_signals(u)

    rows = [{"signal": name, "horizon_d": h,
             **evaluate(sig, u, sig_start, h)}
            for name, sig in signals.items() for h in HORIZONS]
    table = pd.DataFrame(rows).set_index(["signal", "horizon_d"])

    print("\n=== TEST 1: INFORMATION COEFFICIENT (train only) ===")
    print(table.to_string())
    table.to_csv(RESULTS / "02_ic_table.csv")

    print("\nHOW TO READ THIS")
    print("  A t-stat near 1.0-1.2 is the noise floor: random data produced")
    print("  that in testing. Look for consistent sign across the whole grid,")
    print("  not one strong cell. Horizons are NOT independent evidence -")
    print("  they are the same period sampled at different frequencies.")


if __name__ == "__main__":
    main()
