# Lab notebook — 5 September 2026

Everything I did, in the order I did it. Setup from nothing, every test, what
broke, and why I stopped. Written so I can rebuild this from scratch later.

About five hours total, from no Python installed to a finished study.

---

## Part 1 — Environment (Windows 11)

### What I installed

| Item | Version | Where from | Notes |
|---|---|---|---|
| Python | **3.13.15** | python.org → Windows installer (64-bit) | see below |
| VS Code | current | code.visualstudio.com | no sign-in needed |
| Python extension | Microsoft | VS Code Marketplace | brings Pylance + Debugger |
| Jupyter extension | Microsoft | VS Code Marketplace | brings 4 companion extensions |

### Packages

```
numpy 2.5.2 · pandas 3.0.5 · yfinance 1.7.0
matplotlib 3.11.1 · pyarrow 25.0.1 · jupyter 1.1.1
```

### Don't just install the newest Python

Latest stable at the time was 3.14.7, with 3.15 in alpha. **I deliberately used
3.13.15.**

Packages ship precompiled wheels per Python version. When a new Python drops,
numpy and pandas take months to publish wheels for it, and until they do
`pip install pandas` tries to compile from C source and fails if you don't have a
compiler. Rule of thumb: don't use a Python released in the last six months for
data work.

### The exact sequence

```powershell
# 1. Install Python. TICK "Add python.exe to PATH" on the first installer
#    screen — it's off by default and missing it breaks everything after.
python --version                       # expect 3.13.15

# 2. Project folder
cd ~
mkdir quant
cd quant

# 3. Virtual environment
python -m venv .venv                   # ~10s, prints nothing
.\.venv\Scripts\Activate.ps1

#    If you get "running scripts is disabled on this system":
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned    # Y, then retry
#    You know it worked when the prompt starts with (.venv)

# 4. Packages
python -m pip install --upgrade pip
python -m pip install numpy pandas yfinance matplotlib pyarrow jupyter
python -c "import pandas, yfinance, pyarrow; print('OK', pandas.__version__)"
```

In VS Code: **File → Open Folder** → the `quant` folder → trust the authors →
`Ctrl+Shift+P` → `Python: Select Interpreter` → pick the `.venv` one marked
**Workspace**, not the one marked Global.

### Things that went wrong

| What I saw | Why | Fix |
|---|---|---|
| `Activate.ps1 cannot be loaded` | PowerShell blocks scripts by default | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, once |
| `Select Interpreter` → "No matching results" | I used `Ctrl+P` (Go to File) not `Ctrl+Shift+P` (Command Palette). Without the `>` it searches filenames | use `Ctrl+Shift+P`, or type `>` first |
| `NameError: yf is not defined` | that notebook only imported pandas and numpy | add `import yfinance as yf` |
| `mkdir %USERNAME%` made a folder literally called that | `%VAR%` is CMD syntax, not PowerShell | use `cd ~` |
| One ticker came back all-NaN | yfinance's SQLite cache throws `database is locked` under parallel download | re-run, or fetch it on its own. **Now handled automatically in `01_pull_data.py`** |

### The worst bug of the night

XLP downloaded empty, but the script printed `missing tickers: []` and everything
looked fine — the column existed, it was just full of NaN. If I hadn't caught it,
the whole study would have run with one asset permanently missing and produced
believable, wrong numbers.

**The lesson, now baked into the code:** data bugs here don't crash. They produce
plausible results. So every load is followed by explicit NaN, duplicate,
non-positive and extreme-move checks.

---

## Part 2 — What I tested, in order

### A — Data and inception dates

Pulled 17 tickers back to 2004, then asked when each one actually starts. URA
(2010-11-05) is the constraint, so that's the panel start. This decided the entire
study window before I wrote a line of strategy code.

Why it matters: start earlier and the strategy quietly has fewer things to pick
from in the early years, which isn't comparable to later and makes the result look
better than it was.

**Worked.** Two minutes, and it set the honest boundary.

### B — Split the data and pre-register

Train 2011-08-23 → 2018-12-31. Test 2019-01-01 → 2026-09-04, never loaded.

Pass rules written down **before** producing any results:
1. Ret/Vol beats the benchmark, after costs
2. ex-best5 doesn't fall by more than half
3. Holds up across n_top 2–5

**This was the best decision I made all night.** Every later test was tempting to
read charitably. Having the criteria in writing made that impossible.

### C — Test 1, information coefficient

Does the ranking predict anything at all? Cheapest possible gate — if the IC is
flat, stop before building any execution machinery.

Result: 11 of 12 cells positive, mom120 t-stats 2.89 / 2.28 / 1.42 and stable
across horizons.

**Looked like it worked. It didn't.** I'd run the same pipeline on randomly
generated prices first, and that produced t-stats of 1.0–1.2 and a 7% spread out
of nothing, which set the noise floor. And IC scores the whole cross-section while
the portfolio only holds three names — those two came apart badly at the next
step.

### D — Test 2, portfolio vs benchmarks

The finding that reframed the whole thing: mom120 and blend had statistically
identical ICs but produced 6.57% and 14.39% CAGR. Two near-identical signals, same
185 periods, 8-point gap. That's not skill, that's a few periods.

**Worth doing.** It's the reason I didn't stop at Test 1 with a false positive.

I also checked composition by year here, and it was genuinely encouraging — real
rotation, and it found the 2016 miners and 2017 lithium runs on its own.
Encouraging, and still not enough.

### E — Test 3, risk adjustment

Added volatility, drawdown and ex-best5. This is where it broke: 0.96 Ret/Vol
against SPY's 1.19, and ex-best5 collapsing from 14.39% to 7.29%.

**The top-1 result was the giveaway.** The single highest-ranked asset returned
5.25% at 22% vol with a negative ex-best5. If the signal were real its strongest
expression should be its best result. It was the worst.

**Worth doing.** Return on its own had been misleading me for three tests.

### F — Test 4, let the index compete

My diagnosis after Test 3 was that the strategy is forced to be concentrated and
can never just hold the market. Fix: let SPY and BIL into the ranking.

**SPY got picked 0.5% of the time.** The fix never engaged — which was the answer.
Raw-return ranking structurally can't select a diversified index, because an index
almost never has a top-3 trailing return against individual sectors.

I added realistic costs at this step too (8bp/side ≈ 1.6%/yr).

### G — Test 5, QQQ instead

Ran this on a friend's suggestion. I flagged up front that it was test 26, a
post-hoc change, on a benchmark chosen with hindsight — so whatever it returned
carried weak evidence either way.

QQQ got picked **32.4%** of the time, so the structural objection was answered.
And it still lost to buy-and-hold QQQ on return (14.23 vs 17.21), volatility (15.4
vs 13.8) and outlier dependence (7.17 vs 12.64), all at once.

**This is the test that settles it.** Given the ability to hold the index, it held
it a third of the time and earned the index return. The other two-thirds it
substituted thematics, and on net those substitutions destroyed value.

### H — Stop

Reasons, written at the time:

- 26 configurations against one training window. The garden of forking paths is
  real, and a marginal pass at test 27 would mean almost nothing.
- The holdout is one-shot. Spending it on something that failed training would
  waste the only clean evidence I have.
- Base rate. Most published equity anomalies decay after publication, and the
  prior on a retail systematic strategy beating an index after costs is low.
- Personal. The records I was analysing document seven years of holding losers too
  long — winners 34 days, losers 108. Running test 27 would have been the same
  instinct in different clothes, and this was the cheapest possible chance not to
  do it.

---

## Part 3 — Things I considered and rejected

| Idea | Why not |
|---|---|
| **Leveraged ETFs (SOXL, TQQQ, 3x)** | Leverage multiplies return and vol together, so Ret/Vol stays put, then decay and financing come off the top. It amplifies an edge, it doesn't make one. There was no excess Sharpe here to lever |
| **Options overlay** | Nothing to lever, plus 3–10% spreads on thematic ETF options against something already losing to the benchmark. Also the wrong instrument for 4–14 day holds (theta) |
| **Vol-scaled ranking** | Would demote exactly the high-vol breakouts the strategy exists to catch — it would have excluded the 2016 miners and 2017 lithium trades. Raw ranking imports beta; vol-scaling excludes the payoff. No setting gets both |
| **Bigger equity universe (add SOXL etc.)** | Breadth needs *uncorrelated* assets. Nine of fifteen holdings are already slices of the same index. More US equity adds zero independent bets. And picking SOXL now because it worked recently is the same hindsight bias I already declared |
| **ASX instead of US** | moomoo's OpenAPI covers HK/US/A-share/SG/JP, not Australia; their AU "API Skills" launch does US and HK stocks only. You can't algo-trade the ASX on that platform. The ASX also has a small ETF universe, wide micro-cap spreads and thin listed options |
| **Rebuilding my original discretionary strategy** | Post-2020: profit factor 1.05, 51% win rate, five trades carrying everything. Announcement-driven micro-cap trading can't be automated and gets eaten by spreads. Nothing there to recover |
| **Intraday / scalping** | My own records answer it: the 63 trades held 0–3 days were the worst bucket in the file. Arithmetically dead at retail cost structures |

## Part 4 — Where the method came from

Before writing anything I read through a couple of open-source quantitative
finance codebases, looking for reusable components rather than strategies.

The genuinely useful thing was the **factor IC/IR analysis pattern** — measuring
whether a signal predicts forward returns, and sorting assets into quantiles to
see whether the relationship is monotonic, *before* building any strategy around
it. That's the standard institutional first screen and it's what Test 1 here is.
It changed the order I did things in: the instinct is to build a strategy and see
if it makes money, but the professional move is to check the signal carries
information at all, because if it doesn't then everything downstream is decoration.

Also worth copying if I ever run something live: credentials in the OS keyring
rather than a config file, plugins that structurally can't place orders, a human
approval gate on anything that trades, and an audit log.

Neither codebase contained a strategy. Both were infrastructure. Which is the
point — alpha isn't on GitHub.

## Part 5 — Tooling notes for next time

- **Notebooks to explore, scripts for the record.** I ran the session in `.ipynb`
  files; `src/*.py` is the cleaned re-runnable version. Keep both.
- **Run All before trusting anything.** Notebook state survives edits, so a cell
  can pass using a variable that no longer exists in the code.
- **Pin an explicit end date.** My original pull had no `end`, so it ran to "today"
  and would silently change on every rerun. `common.DOWNLOAD_END` fixes that.
- **Save the data, hash the data.** `data/manifest.txt` records SHA256, shape, date
  range and package versions so future drift shows up instead of hiding.
- **Test on random data first.** Running the pipeline on synthetic random-walk
  prices set the noise floor and caught logic errors before there were real
  results to get excited about.
- **Run the packaged code before publishing it.** I found a crash in the cleaned-up
  version that the notebook never hit, because the notebook handled cash
  separately. Would have been sitting in a public repo otherwise.

## Part 6 — If I come back to this

The multi-asset trend project. **Not** as a modification of this one — new
universe, fresh pre-registration, its own train/test split. The 2019–2026 window
here is unspent and could serve as its holdout.

Sketch only, deliberately not designed yet:
- Universe: equity indices, Treasuries across the curve, gold, broad commodities,
  major FX, international and EM equity
- Signal: time-series trend (own price vs own moving average) rather than
  cross-sectional ranking — which sidesteps the volatility-bias defect entirely
- Rebalance: monthly
- Sizing: inverse volatility, applied after selection
- Benchmark: 60/40, and a published managed-futures index

Leave it a few days first, so it's a considered choice and not a reaction to this
result.
