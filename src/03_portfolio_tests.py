"""
03_portfolio_tests.py — Tests 2 to 5, the portfolio-level evaluation.

Run:  python src/03_portfolio_tests.py

A good IC does not imply a good long-only portfolio: IC scores the whole
cross-section, but you only ever hold the top N. These tests measure what the
portfolio actually did.

  Test 2  Top-3 vs equal-weight vs SPY; top-3 composition by year
  Test 3  Risk-adjusted, 200-SMA gate, sensitivity to N
  Test 4  SPY and BIL added as ranking candidates, realistic costs
  Test 5  QQQ added as a ranking candidate, realistic costs

PRE-REGISTERED PASS RULES (fixed before Test 3 was run):
  1. Ret/Vol must beat the benchmark's, net of costs
  2. ex-best5 CAGR must not fall by more than half
  3. Results must plateau across n_top = 2..5, not spike at one value

Writes: results/03_test2.txt .. results/06_test5.csv
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (BENCH, CASH, COST_BPS, GROWTH, RESULTS, UNIVERSE, WARMUP,
                    aligned, bench_returns, blend_signal, build_curve,
                    build_signals, forward_returns, load_prices,
                    rebalance_dates, split_train, stats)

H = 10   # headline rebalance horizon, trading days


def test2(u, signals, train, sig_start):
    """Top-3 vs equal-weight vs SPY, plus composition and turnover."""
    print("\n=== TEST 2: BENCHMARKS AND COMPOSITION (train only) ===")

    def diagnose(sig, horizon, n_top=3, min_assets=10):
        fwd = forward_returns(u, horizon)
        spy = forward_returns(train[[BENCH]], horizon)[BENCH]
        rows, prev = [], set()
        for d in rebalance_dates(sig, sig_start, horizon):
            both = aligned(sig, fwd, d)
            if len(both) < min_assets:
                continue
            order = both["sig"].sort_values(ascending=False).index
            top = list(order[:n_top])
            rows.append({"date": d, "top": top,
                         "top_ret": both.loc[top, "fwd"].mean(),
                         "ew_ret": both["fwd"].mean(),
                         "spy_ret": spy.loc[d],
                         "changed": len(set(top) - prev)})
            prev = set(top)
        return pd.DataFrame(rows).set_index("date")

    def summarise(name, horizon):
        d = diagnose(signals[name], horizon)
        yrs = len(d) * horizon / 252
        cagr = lambda s: 100 * ((1 + s).prod() ** (1 / yrs) - 1)
        print(f"\n  {name}, {horizon}-day | {len(d)} periods, {yrs:.1f} yrs")
        print(f"    top3 CAGR : {cagr(d.top_ret):6.2f}%")
        print(f"    equal-wt  : {cagr(d.ew_ret):6.2f}%")
        print(f"    SPY       : {cagr(d.spy_ret):6.2f}%")
        print(f"    top3 > equal-wt: {100*(d.top_ret>d.ew_ret).mean():.1f}% of periods")
        print(f"    top3 > SPY     : {100*(d.top_ret>d.spy_ret).mean():.1f}% of periods")
        print(f"    names changed/rebalance: {d.changed.mean():.2f} of 3")
        return d

    d = summarise("blend", H)
    summarise("mom120", H)
    summarise("mom120", 21)

    comp = (d.explode("top").assign(year=lambda x: x.index.year)
            .groupby(["year", "top"]).size().unstack(fill_value=0))
    print("\n  Top-3 composition by year (blend, 10-day):")
    print(comp.to_string())
    comp.to_csv(RESULTS / "03_composition.csv")
    return d


def test3(u, signals, train, sig_start):
    """Risk-adjusted comparison, the 200-SMA gate, and n_top sensitivity."""
    print("\n=== TEST 3: RISK-ADJUSTED + GATE + SENSITIVITY (train only) ===")
    out = []
    for name in ["blend", "mom120"]:
        for gate in [False, True]:
            c = build_curve(signals[name], u, sig_start, H, 3, gate,
                            costs=False, cash_prices=train[CASH])
            stats(c.ret, H, f"{name} top3 gate={gate}", out)

    idx = build_curve(signals["blend"], u, sig_start, H, 3, False,
                      cash_prices=train[CASH]).index
    stats(bench_returns(train, BENCH, H, idx), H, "SPY buy & hold", out)
    ew = forward_returns(u, H).mean(axis=1).loc[idx]
    stats(ew, H, "equal-weight 15", out)

    print("\n  n_top sensitivity (blend, no gate, no costs):")
    for k in [1, 2, 3, 4, 5]:
        stats(build_curve(signals["blend"], u, sig_start, H, k, False,
                          cash_prices=train[CASH]).ret, H, f"top{k}", out)

    g = build_curve(signals["blend"], u, sig_start, H, 3, True,
                    cash_prices=train[CASH])
    print(f"\n  gate: avg names held {g.held.mean():.2f} of 3")
    pd.DataFrame(out).to_csv(RESULTS / "04_test3.csv", index=False)


def candidate_test(train, sig_start, extra, label, outfile):
    """Tests 4 and 5: add `extra` and CASH to the ranking candidates.

    Motivation: in Tests 1-3 the strategy was forced to hold three
    concentrated thematic bets at all times and could never simply hold the
    index. Adding an index as a candidate lets it decline to be concentrated.
    """
    print(f"\n=== {label} (train only) ===")
    cands = UNIVERSE + [extra, CASH]
    c_px = train[cands]
    sig = blend_signal(c_px)
    out = []

    for gate in [False, True]:
        for cost in [False, True]:
            c = build_curve(sig, c_px, sig_start, H, 3, gate, cost,
                            min_assets=12)
            stats(c.ret, H, f"top3 gate={str(gate):5s} costs={cost}", out)

    d = build_curve(sig, c_px, sig_start, H, 3, True, True, min_assets=12)
    stats(bench_returns(train, extra, H, d.index), H,
          f"{extra} buy & hold", out)
    if extra != BENCH:
        stats(bench_returns(train, BENCH, H, d.index), H,
              f"{BENCH} buy & hold", out)

    print("\n  n_top sensitivity (gate=True, costs=True):")
    for k in [2, 3, 4, 5]:
        stats(build_curve(sig, c_px, sig_start, H, k, True, True,
                          min_assets=12).ret, H, f"top{k}", out)

    picked = d["names"].apply(lambda ns: extra in ns).mean()
    in_cash = d["names"].apply(lambda ns: CASH in ns).mean()
    print(f"\n  {extra} in top3: {100*picked:.1f}%   "
          f"{CASH} in top3: {100*in_cash:.1f}%")
    print(f"  names changed/rebalance: {d.changed.mean():.2f} of 3")
    print(f"  (selection rate under ~5% means the strategy structurally "
          f"cannot hold the index)")
    pd.DataFrame(out).to_csv(RESULTS / outfile, index=False)


def main():
    px = load_prices()
    train = split_train(px)
    u = train[UNIVERSE]
    sig_start = u.index[WARMUP]
    signals = build_signals(u)

    print(f"train {train.index.min():%Y-%m-%d} -> {train.index.max():%Y-%m-%d}"
          f" | signals from {sig_start:%Y-%m-%d} | costs {COST_BPS}bp/side")

    test2(u, signals, train, sig_start)
    test3(u, signals, train, sig_start)
    candidate_test(train, sig_start, BENCH,
                   "TEST 4: SPY + BIL AS CANDIDATES", "05_test4.csv")
    candidate_test(train, sig_start, GROWTH,
                   "TEST 5: QQQ + BIL AS CANDIDATES", "06_test5.csv")

    print("\n" + "=" * 70)
    print("The test period (2019-01-01 onward) was never loaded by any script")
    print("in this repo. It remains an unspent holdout.")
    print("=" * 70)


if __name__ == "__main__":
    main()
