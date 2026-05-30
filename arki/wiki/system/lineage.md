# Lineage — strategy / config version spine

Status: current (summary of the promotion log). Source:
[`../../../docs/arki/strategy_evolution.md`](../../../docs/arki/strategy_evolution.md). Numbers below are
quoted from that doc; cite it for detail.

## Version history (diversified CTA, $200k baseline)

| Ver | Date | Inst | Sharpe | Return | MaxDD | Change |
|---|---|---|---|---|---|---|
| v1 | 2026-04-04 | 16 | 0.59 | 12.2% | −15.8% | initial production config |
| v2 (micro) | 2026-04-04 | 16 | 0.62 | 12.2% | −16.0% | micro contracts (SP500→SP500_micro, GOLD→GOLD_micro) |
| v2-db | 2026-04-05 | 16 | 0.62 | 12.2% | −16.0% | backend csv→db (`dbFuturesSimData`) |
| v3 | 2026-04-05 | 25 | 0.84 | 20.7% | −14.9% | +9 instruments (Ags / FX / Equity) |
| v4 (optimized) | 2026-04-05 | 25 | **1.08** | 23.1% | −14.7% | estimated IDM + per-instrument forecast weights; vol 24.6%→21.3% |
| v4-fresh | 2026-04-05 | 25 | 1.07 | 22.9% | −17.0% | IB data refreshed to 2026-04 |

Key design decisions (full rationale in the source): (1) **fixed equal instrument weights** at $200k —
`use_instrument_weight_estimates: True` zeroed out 40/47 instruments, so weights are held 1/N while IDM +
forecast weights are estimated; (2) **25-instrument universe** beats both the 7-inst static-optimizer pick
(SR 0.49) and 35/47-inst estimated-weight experiments (SR ≈0.50); (3) estimated IDM + forecast weights took
v3→v4 (SR 0.84→1.08).

## ⚠ Config-name drift (reconcile before trusting the doc)

`strategy_evolution.md` is **stale on file names** vs the actual `scripts/backtest_config/` tree:

| `strategy_evolution.md` says | Reality on disk |
|---|---|
| `arki_production.yaml` = v2 (16 inst) | `arki_production.yaml` holds the **24-inst v4.1** universe ($200k, 25% vol) |
| `arki_v4_optimized.yaml` = v4 ★ current best | **No such file exists** |
| `arki_v3_25inst.yaml` = v3 | not present |

So the v4 Sharpe ≈1.08 is **indicative** (25-inst v4, not reproduced from a committed `results/runs/<run>`),
and the current `arki_production.yaml` is the 24-inst **v4.1** (FTSECHINAA removed). Treat the doc's metrics
as historical and the file contents as authoritative for "what runs today."

## Beyond v4: the dm37 candidate

The latest actual run, `results/runs/20260414_0130_dm37_1m_v25/` (config `dm37_1m.yaml`), is a **37-instrument,
$1M** expansion not covered by `strategy_evolution.md` — Sharpe 0.9337 (`stats.yaml`). It is the **leading
candidate**, not promoted. Config files `arki_v5_dynamic.yaml` / `arki_v5b_factor_tilt.yaml` also exist as
later experiments. Current truth: [system-card.md](system-card.md).
