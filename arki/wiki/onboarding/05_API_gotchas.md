# 05 — API gotchas (reference; consult as needed)

**Prerequisite**: [04_lessons_distilled.md](04_lessons_distilled.md). **Time**: keep as reference; ~3 minutes for first scan.

Concrete API mistakes that wasted hours in past sessions. Save yourself.

---

## pysystemtrade engine

### Position attribution: lagged convention

`pandl_t+1` uses `position_t` (end-of-day t position earns t→t+1 return). When computing sign-episode trade attribution, you MUST shift position by +1 day. Otherwise reconciliation diverges by hundreds of percent.

```python
pos_eod = pos.ffill().fillna(0).round().astype(int)
pos_held = pos_eod.shift(1).fillna(0)  # ← THIS shift is required
```

Demonstrated by: 2026-05-29 Martin recon_diff = -409% bug, caught by `diag {instrument}: sum_ret_on_flat=-409.06`. After shift: recon_diff = -1.17% (clean).

### `acc.percent.as_ts` is a property, NOT a method

```python
acc = system.accounts.portfolio(roundpositions=True)
pct = acc.percent
daily = pct.as_ts        # ✓ property, no parens
# daily = pct.as_ts()    # ✗ TypeError: 'Series' object is not callable
```

### `acc.percent.curve()` IS a method

Inconsistency to remember:

```python
nav_cumpct = acc.percent.curve()    # cumulative %, NOT NAV — multiply by 100 / add 1 to get NAV
nav = (1.0 + nav_cumpct / 100.0)
```

### Back-adjusted prices can be NEGATIVE

`system.rawdata.get_daily_prices("US10")` returns panama-adjusted prices that go negative in early history (US10 < 0 around 1985). Implications:

- `price_ratio_return = exit / entry - 1` is meaningless when prices straddle zero.
- Use `price_diff = exit - entry` instead.
- Use vol-normalised `U = ΔX / σ̂` for stationary measurement (Martin §1).

### maxDD convention: native is additive cumsum (can exceed −100%)

`acc.percent.drawdown()` computes drawdown on the cumsum-percent curve, which can show maxDD below −100% (legitimate under its convention but reads wrongly to owners). For owner-readable maxDD bounded in [−100, 0]:

```python
daily_frac = daily_pct_points.fillna(0) / 100.0
eq = (1.0 + daily_frac).cumprod().clip(lower=1e-6)
dd = (eq / eq.cummax() - 1.0) * 100  # geometric, bounded
```

Always report BOTH in stats; show geometric in cheatsheet headlines.

### `forecast_cap = 20` is the default and it BITES

chapter-15 default config caps the combined forecast at `±20`. If you want a pure-linear test, you must override `cfg.forecast_cap = 9999` explicitly. Otherwise your "linear" baseline is `linear + §4 capping`.

Demonstrated by: 2026-05-29 Step 3 ablation, where `max_observed_combined_forecast = 20.00` at cap=20 (binding) vs 37.41 at cap=9999.

---

## `ata` (arki-trade-analysis)

### `NavLoader` signature: tuple, not single Series

```python
def my_nav_loader(system):
    def loader():
        # ...
        return nav, None     # ✓ tuple of (nav_series, benchmark_or_None)
        # return nav         # ✗ ValueError: not enough values to unpack
    return loader
```

### `PysystemtradeAdapter` position_source is buffered | subsystem only

Cannot inject custom position via constructor. To use a custom (e.g. effective) position:

```python
adapter = PysystemtradeAdapter(system=system, instruments=[instr])
adapter._positions[instr] = my_custom_position_series  # inject directly
build_report(cfg)
```

### Trade dataclass does NOT track long/short side

`Trade(trade_id, ticker, entry_date, exit_date, ..., realized_return, months_held)`. No `side` field. `_detect_roundtrips` discards sign. Realized return is `exit/entry - 1`, which is wrong for shorts and meaningless for back-adjusted negative prices.

Workaround for now: read direction from positions externally. Long/short distinction is NOT shown in the standard ata trade report.

### Trade definition: position roundtrip, NOT sign episode

`ata`: trade = maximal interval of non-zero position. A short → long flip WITHOUT crossing zero is ONE trade.
`scripts/martin_single_instrument_backtest.py`: trade = sign-episode (sign change = new trade).

Different counts. Use the same definition consistently within an analysis.

---

## `arki-trade-analysis` package install

The package lives at `~/Developer/arki-trade-analysis/`. Install in this project's venv:

```bash
venv/bin/pip install -e ~/Developer/arki-trade-analysis[parquet]
```

The reference wrapper is `arki/scripts/build_pst_trade_analysis.py` — clone and adapt for new variants.

---

## File and path conventions

### Run dirs

```
ars/runs/<UTC>_<slug>/
```

UTC format: `YYYYMMDDTHHMMSSZ`. Slug grammar: lowercase + underscores + no dates inside.

### Evidence pack dirs

```
ars/evidence_packs/<slug>/
```

NO timestamp in the dir name. The pre-registration timestamp is the immutable anchor.

### Trade analysis outputs

```
arki/results/<YYYY-MM-DD>/<slug>_trade_analysis/
```

Date in folder. These are gitignored (large HTML files); delivered to Obsidian inbox instead.

---

## Memory paths

`~/.claude/projects/-Users-msyeom-Developer-pysystemtrade/memory/` contains the persistent auto-memory. The index is `MEMORY.md`. Pointers worth knowing:

- `arki-wiki-source-of-truth` — wiki at `arki/wiki/` is the source of truth, memory is a cache of pointers
- `ars-experiment-promotion-framework` — the framework we adopted on 2026-05-29
- `ars-run-report-standard` — Tier-1 report template
- `momentum-literature-references` — user-provided Martin (2023) + Hanauer (2022) PDFs
- `momentum-studies-2026-05-29-results` — verdict map for the 5-experiment batch

---

## Common error signatures and what they mean

| Error | Likely cause | Fix |
|---|---|---|
| `ValueError: not enough values to unpack (expected 2, got 1)` in `ata.builder` | NavLoader returns single Series | wrap in `(nav, None)` tuple |
| `TypeError: 'Series' object is not callable` on `as_ts()` | calling property as method | remove `()` |
| recon_diff > 100% | position not lagged for attribution | `pos.shift(1)` before grouping |
| maxDD < -100% in summary | additive cumsum convention | switch to geometric for owner display |
| skew_per_trade vs paper M^(-1/2) prediction mismatch | sign-episode vs fixed-M aggregation | use the paper's method, OR explicitly note divergence |
| paper Fig 1 cited as gate source | Rule 1 violation | replace with section + equation |

---

You are ready. Go to `ars/PROMOTION.md` for the full framework spec; `ars/LESSONS.md` for the append-only failure log; `docs/standards/ai_native_research_primitives.md` for future direction.
