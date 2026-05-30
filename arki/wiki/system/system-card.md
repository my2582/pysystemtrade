# pysystemtrade — system card

> **Status: IN TRANSITION** — baseline **v4** (`arki_production.yaml`) → candidate **dm37** (`dm37_1m.yaml`). Research only; `live_trading: false`; no run formally promoted (`results/runs/registry.yaml`). Session-prime card (SessionStart-injected); fact-only, every number cited.
> `derived_from:` arki_production.yaml · dm37_1m.yaml · results/runs/20260414_0130_dm37_1m_v25/stats.yaml · docs/arki/{strategy_evolution,instrument_universe,universe_sweep_report}.md — `update_on:` any config change / new leading run (re-derive, then re-lint the wiki) — `last_verified:` 2026-05-28 (data → 2026-04-09).

**What it is:** diversified systematic **futures** system on the unmodified pysystemtrade engine (Carver framework). Dynamic optimisation ("Mr. Greedy"); base currency USD. Owner: Minsu Yeom (Arki Finance).

**Config of record — v4 baseline:** `scripts/backtest_config/arki_production.yaml` — **24 instruments** (v4.1, `docs/arki/instrument_universe.md`), **$200k** notional, **25% vol** target (file lines 155–157). Indicative headline (v4, 25-inst predecessor): **Sharpe ≈1.08 · ann 23.1% · vol 21.3%** (`docs/arki/strategy_evolution.md`; sweep "v4 Production" SR 1.081 / skew +0.02). ⚠ Not reproduced from any `results/runs/<run>`, and the doc's config-name map is stale → [lineage.md](lineage.md).

**Leading candidate — dm37:** `scripts/backtest_config/dm37_1m.yaml` — **37 instruments** (DM-only), **$1.0M** notional, **25% vol**. From `results/runs/20260414_0130_dm37_1m_v25/stats.yaml`: **Sharpe 0.9337 · ann 18.57% · vol 19.89% · Sortino 1.335 · Calmar 0.385 · avg DD −12.09% · 56.4y (1969-12-02→2026-04-09)**. (No peak-to-trough MDD cited — registry `max_dd −9.073` is the daily `min`.)

**Trading rules:** EWMAC momentum (4/8/16/32/64) + carry (30/60/125) + relative momentum (20/40/80); handcraft forecast weights, estimated instrument weights (`arki_production.yaml`).

**Data as-of:** 2026-04-09 (dm37 run series end). ⚠ Several instruments frozen 2024-03-28 → [universe.md](universe.md).

**Active workstream (not production):** single-position absmom rotation (top-1, 30% vol, weekly, $50k) — DRAFT, `references/strategy/2026-05-27_absmom_rotation_spec.md`.

**Frozen-core + fork-safety:** never edit upstream-tracked files; all AI-Native artifacts live under `arki/` → [../../README.md](../../README.md).

**Related:** [lineage.md](lineage.md) · [architecture.md](architecture.md) · [universe.md](universe.md) · [../findings/universe-sweep.md](../findings/universe-sweep.md) · [../index.md](../index.md)
