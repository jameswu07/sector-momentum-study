# Multi-Asset Trend Following — Design Note

Written 5 September 2026, immediately after abandoning the sector-momentum
study. This is a **design note and honest assessment**, not a plan to
implement. Nothing here has been tested.

---

## 1. What it actually is

**Time-series momentum.** For each asset independently, ask one question: is
its own recent return positive? If yes, hold it long. If no, hold cash (or,
with futures, go short).

That is the entire signal. What makes it a strategy rather than a coin flip is
doing it across 15–40 assets from genuinely different classes — equity indices,
government bonds, gold, commodities, currencies — and sizing each by its own
volatility so no single position dominates.

### How it differs from what was just tested, and why that matters

The sector-momentum study failed for a specific reason: ranking assets against
each other on raw trailing return systematically selects for volatility,
because a diversified index almost never posts a top-3 return against
individual sectors. The strategy was permanently concentrated by construction.

Time-series momentum has no ranking step at all.

| | Cross-sectional (failed) | Time-series (this) |
|---|---|---|
| Question asked | Which assets are best *relative to each other*? | Is *this* asset trending, judged against itself? |
| Decisions | One ranking across the universe | N independent binary decisions |
| Concentration | Forced — always holds exactly N | Emergent — can hold 15, or 2, or none |
| Volatility bias | Structural, unavoidable | Absent |
| Behaviour in a broad selloff | Rotates into whatever fell least | Exits everything, sits in cash |

That last row is the real prize. The failed strategy could never be defensive
because something always ranks top-3, even in a crash. A time-series system
holds nothing when nothing is trending. This is why trend followers
historically post their best years in bad equity years — 2008 and 2022 being
the standard examples.

## 2. Why breadth is the whole point

Information ratio scales roughly as **IC × √(number of independent bets)**.

The failed study nominally had 15 assets. But nine were slices of the S&P 500,
correlated 0.8–0.9 with each other and with the index, and the six thematics
were themselves correlated through the commodity cycle. Effective independent
bets: maybe four or five. Adding more US equity sectors would have added
literally nothing to that count.

Bonds, gold, currencies and commodities are correlated with equities at
roughly 0.0–0.3 and with each other at similar levels. Twenty such assets give
perhaps twelve to fifteen independent bets. **That is a two-to-three-times
improvement in information ratio from diversification alone, holding signal
quality constant.**

Diversification is the edge here. The trend signal itself is weak and widely
known. What produces a respectable Sharpe is many weak, uncorrelated bets
running simultaneously.

## 3. The evidence, and the honest counter-evidence

### For

- **Moskowitz, Ooi & Pedersen (2012), "Time Series Momentum",** *Journal of
  Financial Economics.* Documents the effect across 58 futures markets over
  25 years, consistent across asset classes.
- **Hurst, Ooi & Pedersen (2017), "A Century of Evidence on Trend-Following
  Investing",** *Journal of Portfolio Management.* Extends the test back to
  1880. Positive in every decade examined, which is unusual for any anomaly.
- **Lempérière et al. (2014), "Two Centuries of Trend Following"** (Capital
  Fund Management). Independent replication over a similar span.
- Plausible mechanisms exist rather than pure data-mining: under-reaction to
  news, herding, and the fact that risk-management flows are mechanically
  trend-amplifying (hedgers and levered funds sell into declines).

### Against — read this part twice

- **The 2010s were poor.** Managed-futures indices broadly delivered weak
  returns from roughly 2010 to 2019. A century of evidence does not help you
  through a ten-year drawdown, and ten years is longer than most people's
  patience.
- **It is crowded.** This is the single most institutionalised systematic
  strategy in existence, with hundreds of billions deployed. Whatever edge
  remains is thin and shared.
- **The published results are futures-based.** Futures give leverage,
  shorting, tight spreads and low financing costs. The ETF version available
  to a retail account is long-only, unlevered and more expensive. Expect a
  material haircut to published numbers, not a small one.
- **Long stretches of nothing.** Trend systems typically win on 35–45% of
  trades and make money via a few large winners. That distribution is
  psychologically brutal, and it is the same outlier-dependence structure that
  was treated as a failure signal in the sector study. The difference is that
  here it is a documented property of the strategy rather than an artefact —
  but the lived experience is identical, and worth being honest about.

## 4. Would it work at A$5,000?

Marginal, and this deserves an answer before any code is written.

Twenty assets at A$5,000 is A$250 each, roughly US$165. IBKR's minimum
commission is US$0.35 per order, which on a US$165 position is **0.21% per
side**. A monthly trend system turning over 200–300% a year would pay perhaps
**1.0–1.5% annually in commission alone** — against a strategy whose realistic
expected excess return might be 2–4%.

Three ways round it, none free:

1. **Fewer assets (8–10).** Restores position size, destroys the breadth that
   is the entire rationale. Self-defeating.
2. **IBKR fractional shares.** Solves granularity but not the per-order
   minimum.
3. **More capital.** At A$20,000 the same system pays about 0.3% a year in
   commission, which is workable. This is the honest answer: **the strategy
   wants roughly A$20k+ to express properly.**

There is a real risk of building something whose backtest is dominated by cost
assumptions rather than signal. Model costs from the start, not at the end.

## 5. If it were built — sketch only

**Universe (~18 liquid US-listed ETFs, deliberately spread across classes):**

| Class | Candidates |
|---|---|
| Equity | SPY, EFA, EEM, IWM |
| Rates | IEF, TLT, SHY, TIP |
| Credit | LQD, HYG |
| Commodity | GLD, SLV, DBC, USO, DBA |
| Currency | UUP, FXE, FXY |
| Cash | BIL |

The binding constraint will be inception dates again — several of these start
2006–2008, so the honest window is probably 2008 onward. **Check this before
anything else, exactly as URA determined the last study.**

**Signal.** Own the asset if price > 200-day moving average, or if 12-month
return > 0. Both are standard; test both, do not blend them into something
bespoke.

**Sizing.** Inverse volatility, applied *after* selection. Target roughly equal
risk contribution per position, capped so no single asset exceeds some fixed
share. Unselected weight goes to BIL.

**Rebalance.** Monthly. Not weekly — the published effect is at monthly
horizons, and turnover is the binding cost constraint at this account size.

**Benchmarks.** A 60/40 portfolio, SPY buy-and-hold, and equal-weight
buy-and-hold of the same universe. Beating an equity index outright is the
wrong bar; the honest claim for trend following is *better risk-adjusted return
and shallower drawdowns*, not higher raw return.

**Pass rules — write these down before running anything:**

1. Ret/Vol beats 60/40, net of modelled costs
2. Max drawdown materially shallower than 60/40 (this is the actual selling
   point; if it fails here it has no purpose)
3. ex-best5 does not halve
4. Stable across signal choice (200-SMA vs 12-month) and rebalance frequency
5. Positive in the 2011–2018 window specifically — the period when trend
   following broadly did not work. Passing everywhere *except* there means the
   result is a 2008/2022 artefact

**Data note.** The 2019–2026 window from the sector study is still unspent and
can serve as the holdout. Do not look at it until rules 1–5 pass on training
data.

## 6. Is it recommended?

**As a research project: yes, clearly.** It is the best-evidenced systematic
strategy accessible to a retail account, the mechanism is comprehensible, the
data is free, and — unlike the sector study — the design does not contain a
known structural defect from the outset. It would also be a stronger portfolio
piece, because multi-asset risk allocation is closer to what trading firms
actually do than equity sector rotation is.

**As a place to put money: probably not, at A$5,000.** The costs are too high
relative to a thin expected edge, the strategy is crowded, and the realistic
outcome is a Sharpe modestly better than 60/40 with a decade-long stretch of
underperformance somewhere in it. If the honest goal is compounding, a
systematic index DCA is likely to win on both return and effort.

The two goals are separable and it is worth being clear which one is in play.
Building it to understand risk allocation, cost modelling and portfolio
construction is worth the time regardless of what the backtest says.

**Prior before starting: maybe 35–40% that it clears all five pass rules.**
Higher than the sector study, because the design defect is absent and the
literature is stronger. Still under half, because most systematic ideas fail
and this one is thoroughly picked over.

## 7. Before starting, next time

Three things learned the expensive way in the sector study:

1. **Check inception dates first.** It determined the entire study window and
   took two minutes.
2. **Run the pipeline on randomly generated prices first**, to establish the
   noise floor. A t-stat of 1.2 looked meaningful until random data produced
   it too.
3. **Write the pass rules down before seeing any result**, and treat them as
   binding. That single decision is what kept the last study honest.

And one about process: stop at the first pre-registered failure. The sector
study ran 26 configurations. The answer was visible at roughly configuration 14.

---

*Not investment advice. A design sketch and an assessment of a strategy that
has not been tested.*
