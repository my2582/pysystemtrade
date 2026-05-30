# Instrument universe

Status: current (in transition: 24 v4.1 → 37 dm37). Source:
[`../../../docs/arki/instrument_universe.md`](../../../docs/arki/instrument_universe.md).

## v4.1 production universe — 24 instruments ($200k baseline)

From `scripts/backtest_config/arki_production.yaml` (FTSECHINAA removed = v4.1):

| Class | n | Instruments |
|---|---|---|
| Equity | 6 | SP500_micro, NASDAQ_micro, DAX, NIKKEI, FTSE100, IBEX_mini |
| Bond | 5 | US10, US5, BUND, GILT, JGB |
| Metals | 3 | GOLD_micro, SILVER, COPPER-micro |
| Energy (OilGas) | 3 | CRUDE_W, BRENT-LAST, GASOIL |
| FX | 3 | AUD_micro, MXP, YENEUR |
| Agricultural | 4 | SUGAR11, COTTON, LEANHOG, COCOA_LDN |

**Selection rule:** at $200k, prefer affordable contracts (< $50k contract value) plus proven
large-contract instruments; exclude duplicates (full→micro), bad/illiquid markets, and trading-restricted
US sector futures. The sweep ([../findings/universe-sweep.md](../findings/universe-sweep.md)) found
25-inst + OilGas + handcraft optimal — **do not cut below 25**.

## dm37 candidate universe — 37 instruments ($1M)

`scripts/backtest_config/dm37_1m.yaml` ("DM-only 37 instruments, $1M, vol 25%") adds developed-market
equities/rates and more ags/softs (e.g. TOPIX, SPI200, OAT, BOBL, BONO, COFFEE, OJ, REDWHEAT, LIVECOW,
FEEDCOW, EU-BANKS, EU-DJ-OIL, EU-DJ-TELECOM, CHFJPY) and drops MXP. Full traded list:
`results/runs/20260414_0130_dm37_1m_v25/stats.yaml`.

## ⚠ Data-currency caveat (binding constraint)

Per the min-account study (`references/strategy/2026-05-27_min_account_universe_study.html`) and the absmom
spec, **many instruments are frozen at 2024-03-28** — only a handful carry current data. Data currency, not
capital, is the binding constraint for any single-position rotation. The IB price-accumulation pipeline
(`references/research/2026-05-27-ibkr-panama-price-accumulation-pipeline.md`) traces the root cause; the
refresh plan is tracked in agent memory (`price-universe-refresh-plan`).
