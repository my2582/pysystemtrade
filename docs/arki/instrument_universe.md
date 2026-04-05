# Instrument Universe

## Current Universe: 25 Instruments (v4)

| # | Instrument | Asset Class | Contract Value ($) | Status |
|---|---|---|---|---|
| 1 | SP500_micro | Equity | 26,519 | Affordable |
| 2 | NASDAQ_micro | Equity | 42,637 | Affordable |
| 3 | DAX | Equity | 23,313 | Affordable |
| 4 | NIKKEI | Equity | 5,358,500 | Large (produces small positions) |
| 5 | FTSE100 | Equity | 104,380 | Large (produces small positions) |
| 6 | IBEX_mini | Equity | 12,499 | Affordable — **added in v3** |
| 7 | FTSECHINAA | Equity | 13,389 | Affordable — **added in v3** |
| 8 | US10 | Bond | 111,016 | Large (produces small positions) |
| 9 | US5 | Bond | 106,576 | Large (produces small positions) |
| 10 | BUND | Bond | 125,550 | Large (produces small positions) |
| 11 | GILT | Bond | 88,580 | Marginal |
| 12 | JGB | Bond | 132,780,000 | Large (produces tiny positions) |
| 13 | GOLD_micro | Metals | 22,550 | Affordable |
| 14 | SILVER | Metals | 59,309 | Marginal |
| 15 | COPPER-micro | Metals | 10,619 | Affordable |
| 16 | CRUDE_W | Energy | 116,054 | Large (produces small positions) |
| 17 | BRENT-LAST | Energy | 130,139 | Large (produces small positions) |
| 18 | GASOIL | Energy | 150,979 | Large — **added in v3** |
| 19 | AUD_micro | FX | 7,110 | Affordable |
| 20 | MXP | FX | 32,460 | Affordable — **added in v3** |
| 21 | YENEUR | FX | 23,145,465 | Large — **added in v3** |
| 22 | SUGAR11 | Agricultural | 24,797 | Affordable — **added in v3** |
| 23 | COTTON | Agricultural | 45,690 | Affordable — **added in v3** |
| 24 | LEANHOG | Agricultural | 46,177 | Affordable — **added in v3** |
| 25 | COCOA_LDN | Agricultural | 45,087 | Affordable — **added in v3** |

### Asset Class Distribution

| Asset Class | Count | Instruments |
|---|---|---|
| Equity | 7 | SP500_micro, NASDAQ_micro, DAX, NIKKEI, FTSE100, IBEX_mini, FTSECHINAA |
| Bond | 5 | US10, US5, BUND, GILT, JGB |
| Metals | 3 | GOLD_micro, SILVER, COPPER-micro |
| Energy | 3 | CRUDE_W, BRENT-LAST, GASOIL |
| FX | 3 | AUD_micro, MXP, YENEUR |
| Agricultural | 4 | SUGAR11, COTTON, LEANHOG, COCOA_LDN |

---

## Selection Criteria

### Size Classification ($200K capital)

| Category | Contract Value | Can hold position? | Count |
|---|---|---|---|
| Affordable | < $50K | Yes (multiple contracts) | 15 |
| Marginal | $50K–$100K | Yes (0.5–2 contracts) | 2 |
| Large | > $100K | Limited (0–1 contracts via dynamic optimizer) | 8 |

### pysystemtrade Built-in Filters

The system applies these filters at initialization:

1. **Duplicate instruments** (`defaults.yaml → duplicate_instruments`) — removes full-size when micro exists (e.g. SP500 excluded, SP500_micro kept)
2. **Bad markets** (`defaults.yaml → bad_markets`) — high cost or low liquidity (e.g. CHEESE, RICE, INR)
3. **Trading restrictions** (`defaults.yaml → trading_restrictions`) — regulatory (e.g. US sector futures)
4. **Auto-remove** — instruments with zero optimal position are excluded from weight estimation

### What We Excluded from the 56 Parquet Instruments

| Excluded | Reason |
|---|---|
| GOLD, SP500 | Duplicate (keep micro versions) |
| CHEESE, INR, RICE, EURIBOR | Bad market (defaults.yaml) |
| US-DISCRETE, US-STAPLES, US-UTILS | Trading restrictions |
| BOBL, BONO, OAT, BUTTER, CHFJPY, CLP, etc. | Not yet included — expansion candidates |

---

## Expansion Candidates

These instruments have parquet data but are not in the current universe:

| Instrument | Asset Class | Contract $ | Notes |
|---|---|---|---|
| BOBL | Bond | 116K | German 5Y — adds EU bond curve granularity |
| OAT | Bond | 127K | French bond — adds sovereign spread |
| COFFEE | Agricultural | 50K | Marginal size, high trend SR |
| REDWHEAT | Agricultural | 29K | Affordable, adds grain diversification |
| LIVECOW | Agricultural | 88K | Marginal, decorrelated from lean hog |
| EU-BANKS | Equity Sector | 10K | Very affordable, EU sector exposure |
| EU-DJ-OIL | Equity Sector | 30K | Affordable, energy equity |
| SPI200 | Equity | 185K | Australian equity — geographic diversification |
| OJ | Agricultural | 44K | Affordable, very uncorrelated |
| FEEDCOW | Agricultural | 175K | Too large at $200K |

### Priority for Next Expansion

1. **COFFEE** — marginal but high trend SR
2. **REDWHEAT** — affordable, grain diversification
3. **EU-BANKS** — very affordable, new sector
4. **OJ** — affordable, uncorrelated

---

## Data Freshness

Many instruments have stale parquet data (last updated 2024-03-28). IB Gateway connection is required to refresh:

| Status | Count | Action |
|---|---|---|
| Current (2026+) | ~12 | No action |
| Stale (2024-03) | ~44 | Update via IB Gateway |
