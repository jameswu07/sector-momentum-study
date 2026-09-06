# Sector momentum on US ETFs — a strategy that didn't work

I tried to turn my own trading history into a systematic strategy. It did not beat
just buying an index fund on average. 

Run 5 September 2026 · Python 3.13.15 · Melbourne

---

## The short version

Take 15 liquid US sector and thematic ETFs. Rank them by how much they've gone up
recently, hold the top 3, rebalance every 10 trading days. Does that beat buying
SPY and doing nothing?

No. 

I ran five tests on 2011–2018 data. Nothing beat buy-and-hold once you adjust
for risk, and everything depended far more on a few lucky periods than the
benchmark did.

The interesting part is *why*: Ranking on raw past return quietly selects for
volatility — an index is the average of its sectors, so it almost never has a
top-3 trailing return against them. That means the strategy structurally can't
hold one, and is always concentrated in whatever is jumping around the most.

(I never tested 2019–2026 data)

---

## What's in here

```
README.md                      this — method and results
LAB_NOTEBOOK.md                everything I did, in order, including dead ends
FUTURE_multi_asset_trend.md    notes on a different idea I might try later
requirements.txt               package versions
src/common.py                  universe, dates, signals, metrics — all settings live here
src/01_pull_data.py            downloads data, writes a manifest
src/02_signal_ic.py            data checks + Test 1
src/03_portfolio_tests.py      Tests 2-5
results/                       output from the 5 Sep 2026 run
```

## 1. Inspiration

I pulled my own brokerage records — 522 trade confirmations on CommSec, July 2018 to March
2025, all discretionary.

Two things jumped out.

**88% of everything I made came from one quarter.** June to August 2019, and 85%
of that was ASX gold and silver miners during the period AUD gold hit record
highs. The remaining four and a half years produced about 7% of total profit
across 133 trades, at a profit factor of 1.05. 

**That 2019 quarter was sector momentum, just done by hand and without any
discipline.** All trades in one sector, a real macro trend under it, 7–9 day holds, capital
recycled about ten times.

So the question was: was that repeatable, or was it luck? If it's a real effect I
should be able to write it as rules, run it on a computer, and strip out the
behavioural stuff the records also showed: winners held 34 days against losers
held 108, position size roughly 4x-ing while my win rate fell from 55% to 25%.

The records also showed five trades produced more than the other 128 combined
lost. That's where the `ex-best5` test below comes from.

## 2. Universe

| Group | Tickers |
|---|---|
| SPDR sectors (9) | XLE XLK XLF XLV XLI XLB XLY XLP XLU |
| Thematics (6) | GDX SIL URA LIT COPX SMH |
| Benchmarks / cash | SPY, QQQ, BIL |

The thematics map onto what I was actually trading: gold and silver miners in
2019, then lithium, uranium, copper and semis in 2021–2024.

**Recency bias.** I picked this list in 2026, already
knowing uranium and lithium had big runs. That's hindsight and it makes every
result below look better than it should. A train/test split doesn't fix it. Worth
noting the strategy failed anyway, with that advantage baked in.

## 3. Data

Daily adjusted closes from Yahoo via `yfinance`, adjusted for splits and dividends.
(If you use unadjusted prices, momentum sees a fake crash on every ex-div 
date)

Pulled 2004-01-01 to 2026-09-05, then clipped.

**Inception dates decide where the backtest can honestly start.** If you begin
before every ETF exists, the universe silently changes composition partway
through and the early years aren't comparable to the later ones.

| Ticker | First bar |
|---|---|
| XLE XLK XLF XLV XLI XLB XLY XLP XLU SMH SPY QQQ | 2004-01-02 or earlier |
| GDX | 2006-05-22 |
| BIL | 2007-05-30 |
| SIL, COPX | 2010-04-20 |
| LIT | 2010-07-23 |
| **URA — the binding one** | **2010-11-05** |

(That gives 3,981 rows from 2010-11-05 to 2026-09-04)

> The original session pulled 17 tickers and fetched QQQ separately when I added
> Test 5. `01_pull_data.py` grabs all 18 at once, so a fresh run shows 18 columns.
> Only the 15-name universe is ever ranked in Tests 1–3.

### Split

| | Period | |
|---|---|---|
| Warm-up | 2010-11-05 → 2011-08-22 | 200 bars for the 200-day SMA |
| **Train** | 2011-08-23 → 2018-12-31 | everything was built on this |
| **Test** | 2019-01-01 → 2026-09-04 | **never loaded** |

Forward returns get computed *after* the training slice is cut, so the last few
periods go NaN instead of reaching into the test window.

## 4. How it works

**Signals.** Momentum over 20, 60 and 120 trading days, plus `blend` — the average
of the three cross-sectional ranks. I averaged ranks rather than returns so the
three lookbacks count equally instead of the longest one dominating.

**Portfolio.** Long only. Rank, optionally drop anything below its own 200-day SMA
(cash is exempt), hold the top N equally weighted, park any unfilled slot in BIL.
Hold for one full horizon, no stops in between.

**Costs.** 8bp per side of whatever gets traded. That's IBKR's US$0.35 minimum on a
~US$1,100 position, about 3.2bp, plus roughly half the ETF spread. At the turnover
this thing runs, it works out to about 1.6% a year.

**What I'm measuring.**

- **IC** — rank correlation between the signal and the forward return across the
  universe at each rebalance. Sampled non-overlapping so the observations are
  independent. Done as Pearson-on-ranks so it doesn't need scipy.
- **Ret/Vol** — CAGR over annualised vol. Close to a Sharpe ratio, since rates
  were near zero for most of 2011–2018, but it isn't risk-free adjusted.
- **ex-best5** — CAGR recalculated with the five best periods deleted. This is the
  outlier test, taken straight from what my own records did.

### Rules:

Written down before Test 3, and I didn't move them afterwards:

1. **Ret/Vol has to beat the benchmark**, after costs.
2. **ex-best5 can't fall by more than half.**
3. **It has to hold up across n_top = 2…5**, not spike at one value.

---

## 5. Results

All training data. Raw output is in `results/`.

### Test 1 — does the ranking predict anything?

| Signal | Horizon | n | mean IC | t-stat | IC>0 | spread %pa |
|---|---|---|---|---|---|---|
| mom20 | 5 / 10 / 21 | 370 / 185 / 88 | .034 / .034 / .030 | 1.53 / 1.11 / 0.66 | 54.1 / 53.5 / 51.1 | 3.6 / 1.8 / 3.7 |
| mom60 | 5 / 10 / 21 | 370 / 185 / 88 | .018 / .038 / −.006 | 0.81 / 1.27 / −0.15 | 47.6 / 54.6 / 46.6 | 0.2 / 0.7 / −1.6 |
| **mom120** | 5 / 10 / 21 | 370 / 185 / 88 | **.065 / .072 / .064** | **2.89 / 2.28 / 1.42** | 54.1 / 59.5 / 58.0 | 8.3 / 6.5 / 8.8 |
| blend | 5 / 10 / 21 | 370 / 185 / 88 | .047 / .069 / .036 | 2.18 / 2.34 / 0.84 | 53.2 / 59.5 / 53.4 | 8.6 / 7.9 / 6.1 |

11 of 12 cells positive, and mom120 sits at basically the same level across all
three horizons rather than spiking at one. **Looked promising. It was misleading.**

Three caveats I wrote down at the time: the horizons are the same 7.4 years
sampled at different speeds, not three separate pieces of evidence; `blend`
contains `mom120`; and I'd already measured the noise floor at t ≈ 1.0–1.2 by
running the whole thing on randomly generated prices first.

### Test 2 — but does the actual portfolio make money?

| Signal | top-3 CAGR | equal-weight | SPY | turnover |
|---|---|---|---|---|
| blend, 10d | 14.39% | 5.62% | 13.29% | 1.12 of 3 |
| mom120, 10d | 6.57% | 5.62% | 13.29% | 0.72 of 3 |
| mom120, 21d | 6.41% | 5.51% | 13.19% | 1.12 of 3 |

**Here's the thing that should have worried me more than it did.** mom120 and
blend have basically identical ICs (.072 vs .069, t = 2.28 vs 2.34) but their
portfolios returned 6.57% and 14.39%. An 8-point gap between two near-identical
signals over the same 185 periods means the difference lives in a handful of
periods, not in skill. IC scores the whole cross-section; I only ever hold three
names.

The composition was genuine rotation though, not a disguised tech bet — 2013
consumer and industrials, 2014 semis, 2016 GDX/SIL/COPX, 2017 LIT/SMH. It found
the 2016 miner rally and the 2017 lithium run on its own.

### Test 3 — add risk

| Variant | CAGR | vol | Ret/Vol | maxDD | ex-best5 |
|---|---|---|---|---|---|
| blend top3, no gate | 14.39% | 15.9% | 0.91 | −18.7% | 7.29% |
| blend top3, gate | 14.89% | 15.6% | 0.96 | −15.4% | 7.77% |
| mom120 top3, gate | 7.81% | 17.7% | 0.44 | −20.0% | 0.28% |
| **SPY** | **13.29%** | **11.2%** | **1.19** | **−13.8%** | **9.34%** |
| equal-weight 15 | 5.62% | 14.7% | 0.38 | −23.8% | 0.32% |

n_top sensitivity: top1 0.24, top2 0.90, top3 0.91, top4 0.79, top5 0.83.

**Fails all three rules.** SPY wins on Ret/Vol, wins on drawdown, and leans less on
outliers.

The single highest-ranked pick returned 5.25% at 22% vol with a *negative* ex-best5. If the signal were real, its
strongest expression should be its best result.

The 200-SMA gate did help, and it helped drawdown (−18.7% → −15.4%) more than
return, which is what the literature on trend filters says should happen.

### Test 4 — let it hold the index

| Variant | CAGR | vol | Ret/Vol | maxDD | ex-best5 |
|---|---|---|---|---|---|
| top3, gate, costs | 13.58% | 15.2% | 0.89 | −12.4% | 6.57% |
| SPY | 13.29% | 11.2% | 1.19 | −13.8% | 9.34% |

I thought the problem might be that the strategy is forced to hold three
concentrated bets and can never just own the market. So I let SPY and BIL compete
in the ranking.

**SPY got picked 0.5% of the time.** The fix never engaged, and that turned out
to be the actual diagnosis.

### Test 5 — try QQQ instead

| Variant | CAGR | vol | Ret/Vol | maxDD | ex-best5 |
|---|---|---|---|---|---|
| top3, gate, costs | 14.23% | 15.4% | 0.93 | −12.3% | 7.17% |
| **QQQ** | **17.21%** | **13.8%** | **1.25** | −16.8% | **12.64%** |
| SPY | 13.29% | 11.2% | 1.19 | −13.8% | 9.34% |

QQQ is more volatile and tech concentrated, so it gets picked more often. **32.4% of the time.** The
structural objection is answered, and it still lost to just holding QQQ on
return, volatility and outlier dependence, all three at once. n_top flattens out
at 0.93 / 0.92 / 0.92, below the benchmark.

---

## 6. Why it failed

A third of the time the strategy chose the index, and in those periods it earned
the index return. The other two-thirds it swapped in thematic ETFs, and that
swapping dragged 17.21% down to 14.23% while increasing vol from 13.8% up to 15.4%.

**So on average, every time the ranking preferred something over the index, it
destroyed value.** 

Three reasons underneath it:

1. **The rank selects for volatility.** An index is the average of its parts, so it
   almost never posts a top-3 trailing return against them. Ranking on raw return
   is therefore a volatility filter, and the strategy is concentrated by
   construction. I considered vol-scaling the rank and rejected it. (That would
   have excluded exactly the high-vol breakouts (2016 miners, 2017 lithium) the
   thing exists to catch)
2. **Not enough independent bets.** Information ratio scales roughly as IC ×
   √(independent bets). Nine of my fifteen are slices of the same index,
   correlated 0.8–0.9 with each other and with SPY. Realistically that's about
   five bets, not fifteen, so adding more US sector ETFs would do nothing.
3. **Too dependent on outliers.** ex-best5 halved the strategy's CAGR while only
   cutting the benchmark's by 27–30%. Half the return comes from 5 of 185 periods, which is the same shape as my own records, where 5 of 133 trades produced
   all the profit.

**Using leverage and options don't rescue this.** Leverage multiplies return and vol
together, so Ret/Vol stays roughly where it is and then you subtract decay and
financing. There's no excess Sharpe here to lever in the first place. Options
would add 3–10% spreads to something already losing to a free alternative.

## 7. Running it

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows PowerShell
pip install -r requirements.txt

python src\01_pull_data.py          # downloads data, writes data/manifest.txt
python src\02_signal_ic.py          # data checks + Test 1
python src\03_portfolio_tests.py    # Tests 2-5
```

macOS or Linux: `source .venv/bin/activate` and forward slashes.

---

*Not investment advice*
