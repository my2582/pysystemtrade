#!/usr/bin/env python3
"""
PIT Universe Builder — single-position momentum rotation (absmom_rotation).

For each rebalance date d, evaluates every candidate using only information
available at d (causal). Eligibility rules:
  1. price history >= min_history_years before d
  2. most recent price within max_staleness_days of d  (not stale at d)
  3. engine vol at d s.t. E_d × min_contracts_held <= capital
      where E_d = mult × dailyDiffVol_d × sqrt(256) × FX_d / vol_target
  4. ADV >= min_adv  (static, exchange ref — known approximation)
  5. asset class not in exclude_asset_classes
  6. name not in china pattern (if --exclude-china)
  7. (optional) asset-family diversity check across the resulting set

Causality: mixed_vol_calc with backfill=False is fully causal (EWMA + slow-EWMA).
Computed once over full history, then indexed by date.

Outputs:
  references/strategy/pit_universe_<label>.parquet         # PIT membership matrix
  references/strategy/pit_universe_<label>_config.yaml     # params lock-in
  references/strategy/pit_universe_<label>_summary.html    # visual summary

Static approximations (flagged, not PIT):
  - ADV: exchange-published ref (current snapshot)
  - Spread cost: not applied here (use repo spreadcosts.csv downstream)
  - Multiplier / contract spec: current config
  - Survivorship: only instruments in current instrumentconfig.csv

Core pysystemtrade not modified.
"""
from __future__ import annotations
import argparse, csv, datetime as dt, glob, os, re, warnings, yaml
warnings.simplefilter("ignore")
import numpy as np, pandas as pd
from sysquant.estimators.vol import mixed_vol_calc

ROOT = "/Users/msyeom/Developer/pysystemtrade"
ADJ_DIR = f"{ROOT}/data/futures/adjusted_prices_csv"
FX_DIR = f"{ROOT}/data/futures/fx_prices_csv"
CFG_PATH = f"{ROOT}/data/futures/csvconfig/instrumentconfig.csv"
OUT_DIR = f"{ROOT}/references/strategy"

# Exchange-published reference ADV (recent typical, conservative; STATIC).
# Sources: CME/EUREX/ICE/JPX/OSE/ASX/CBOT public exchange averages.
ADV_REF = {
    "FED": 200000, "EURIBOR-ICE": 150000, "EURIBOR": 150000,
    "US2": 1000000, "US5": 1500000, "US10": 1500000, "US20": 200000,
    "BUND": 1000000, "BOBL": 700000, "BUXL": 80000, "SHATZ": 600000,
    "OAT": 70000, "BONO": 30000, "BTP": 200000, "GILT": 80000, "JGB": 50000,
    "DAX": 150000, "NIKKEI": 35000, "TOPIX": 45000, "IBEX_mini": 8000,
    "SP500_micro": 1000000, "NASDAQ_micro": 700000, "SP500": 1500000,
    "NASDAQ": 200000, "DOW": 200000, "DOW_mini": 100000, "RUSSELL": 200000,
    "FTSE100": 80000, "FTSE250": 5000, "SPI200": 80000, "CAC": 100000,
    "AEX": 60000, "MIB": 40000, "SMI": 60000, "EUROSTX": 1000000,
    "EU-BANKS": 12000, "EU-DJ-OIL": 7000, "EU-DJ-TELECOM": 5000,
    "EU-AUTO": 10000, "EU-BASIC": 4000, "EU-CHEM": 3000, "EU-CONSTRUCTION": 2000,
    "EU-DJ-FOOD": 2000, "EU-FINSVCS": 2000, "EU-HEALTH": 8000,
    "EU-INDUSTRY": 4000, "EU-INSURE": 6000, "EU-MEDIA": 2000,
    "EU-PERSGOOD": 2000, "EU-REALESTATE": 1500, "EU-RETAIL": 2500,
    "EU-TECH": 6000, "EU-TRAVEL": 2000, "EU-UTILS": 6000,
    "US-STAPLES": 200, "US-UTILS": 200, "US-DISCRETE": 250,
    "US-FINANCE": 4000, "US-HEALTH": 3000, "US-INDUSTRY": 2000,
    "US-MATERIAL": 3000, "US-REALESTATE": 3000, "US-TECH": 8000,
    "COPPER-micro": 15000, "COPPER": 100000, "COPPER_LME": 30000,
    "GOLD_micro": 60000, "GOLD": 200000, "GOLD-mini": 30000,
    "SILVER": 60000, "SILVER-mini": 5000, "PLAT": 50000, "PALLAD": 15000,
    "ALUMINIUM": 15000, "ALUMINIUM_LME": 8000, "NICKEL_LME": 10000,
    "LEANHOG": 70000, "LIVECOW": 50000, "FEEDCOW": 8000,
    "COCOA": 25000, "COCOA_LDN": 7000, "COFFEE": 25000,
    "SUGAR11": 100000, "SUGAR_WHITE": 8000, "COTTON": 30000, "COTTON2": 10000,
    "CORN": 250000, "CORN_mini": 4000, "WHEAT": 80000, "WHEAT_mini": 3000,
    "REDWHEAT": 10000, "RICE": 2000, "OATIES": 1500,
    "SOYBEAN": 200000, "SOYBEAN_mini": 5000, "SOYOIL": 80000, "SOYMEAL": 80000,
    "OJ": 2000, "BUTTER": 400, "CHEESE": 1000, "MILK": 3000,
    "LUMBER-new": 4000, "LUMBER": 1000, "CANOLA": 30000,
    "VIX": 200000, "VIX_mini": 5000, "VSTOXX": 30000, "V2X": 30000,
    "BBCOMM": 20000, "BB3M": 2000,
}

CHINA_PAT = ("CHINA", "HANG", "FTSECHINA", "CSI", "SHANGHAI")
BDAY = 252  # trading days per year


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--capital", type=float, default=50000)
    p.add_argument("--n-positions", type=int, default=1)
    p.add_argument("--vol-target", type=float, default=0.30)
    p.add_argument("--min-contracts-held", type=int, default=3)
    p.add_argument("--lookback-momentum", type=int, default=252)
    p.add_argument("--min-history-years", type=float, default=5)
    p.add_argument("--min-adv-contracts", type=int, default=1000)
    p.add_argument("--max-staleness-days", type=int, default=15)
    p.add_argument("--rebalance-freq", default="W-FRI", help="pandas offset alias")
    p.add_argument("--exclude-asset-classes", default="FX,OilGas")
    p.add_argument("--exclude-china", action="store_true", default=True)
    p.add_argument("--no-exclude-china", dest="exclude_china", action="store_false")
    p.add_argument("--min-asset-classes", type=int, default=0,
                   help="Optional: enforce ≥K asset families per rebalance date (0 = off)")
    p.add_argument("--start", default="2010-01-01")
    p.add_argument("--end", default=None, help="default = today")
    p.add_argument("--label", default=None, help="default = c<cap>_n<N>_v<vt>_k<minctr>")
    return p.parse_args()


def slug_label(args) -> str:
    if args.label:
        return args.label
    return f"c{int(args.capital/1000)}k_n{args.n_positions}_v{int(args.vol_target*100)}_k{args.min_contracts_held}"


def family(asset: str, name: str) -> str:
    """Asset-family normalization for diversity check / reporting."""
    if asset == "Bond":
        if name in ("FED", "EURIBOR", "EURIBOR-ICE", "SONIA", "SOFR", "SOFR3M",
                    "EURODOLLAR", "SHATZ", "KR3"):
            return "Rates"
        return "Bonds"
    return {"Sector": "Sectors", "Equity": "Equity", "Ags": "Ags",
            "Metals": "Metals", "Vol": "Vol", "Housing": "Housing"}.get(asset, asset)


def is_china(name: str) -> bool:
    u = name.upper()
    return any(p in u for p in CHINA_PAT)


def load_fx_series(ccy: str) -> pd.Series | None:
    if ccy == "USD":
        return None  # signal: trivially 1.0
    f = f"{FX_DIR}/{ccy}USD.csv"
    if not os.path.exists(f):
        return None
    df = pd.read_csv(f)
    s = pd.to_numeric(df[df.columns[1]], errors="coerce")
    s.index = pd.to_datetime(df[df.columns[0]], errors="coerce")
    return s.dropna().sort_index()


def fx_at(fx_series: pd.Series | None, d: pd.Timestamp) -> float | None:
    if fx_series is None:
        return 1.0  # USD
    sub = fx_series.loc[:d]
    if len(sub) == 0:
        return None
    return float(sub.iloc[-1])


def load_price(name: str) -> pd.Series | None:
    f = f"{ADJ_DIR}/{name}.csv"
    if not os.path.exists(f):
        return None
    df = pd.read_csv(f)
    s = pd.to_numeric(df[df.columns[1]], errors="coerce")
    s.index = pd.to_datetime(df[df.columns[0]], errors="coerce")
    s = s.dropna().sort_index()
    if len(s) < 60:
        return None
    return s


def build_candidate_cache(args, cfg: dict) -> dict:
    """Pre-compute per-instrument time series needed for PIT evaluation."""
    excl_classes = set(s.strip() for s in args.exclude_asset_classes.split(","))
    cache = {}
    fx_cache = {}
    for name, r in cfg.items():
        if r["AssetClass"] in excl_classes:
            continue
        if args.exclude_china and is_china(name):
            continue
        s = load_price(name)
        if s is None:
            continue
        ccy = r["Currency"]
        if ccy not in fx_cache:
            fx_cache[ccy] = load_fx_series(ccy)
        if ccy != "USD" and fx_cache[ccy] is None:
            continue  # no FX series for this ccy → drop
        # Engine vol with backfill=False (PIT-safe)
        diffs = s.diff().dropna()
        vol = mixed_vol_calc(
            diffs, days=35, min_periods=10,
            slow_vol_years=20, proportion_of_slow_vol=0.35,
            backfill=False,
        )
        vol = vol.dropna()
        if len(vol) == 0:
            continue
        cache[name] = {
            "price": s,
            "vol": vol,
            "asset": r["AssetClass"],
            "family": family(r["AssetClass"], name),
            "mult": float(r["Pointsize"]),
            "ccy": ccy,
            "adv": ADV_REF.get(name),
        }
    return cache, fx_cache


def eligible_at(name: str, info: dict, d: pd.Timestamp, args,
                fx_cache: dict) -> tuple[bool, dict]:
    """PIT eligibility check at date d. Returns (ok, diagnostics)."""
    diag = {}
    s = info["price"]
    # 1. inception / min history
    first = s.index[0]
    if (d - first).days < args.min_history_years * 365.25:
        return False, {"reason": "min_history"}
    # 2. recent-price-at-or-before-d (staleness AT d)
    sub_p = s.loc[:d]
    if len(sub_p) == 0:
        return False, {"reason": "no_price_yet"}
    price_d = float(sub_p.iloc[-1])
    last_px_date = sub_p.index[-1]
    if (d - last_px_date).days > args.max_staleness_days:
        return False, {"reason": "stale", "stale_days": (d - last_px_date).days}
    # 3. vol at d
    sub_v = info["vol"].loc[:d]
    if len(sub_v) == 0:
        return False, {"reason": "no_vol_yet"}
    diff_vol = float(sub_v.iloc[-1])
    if not np.isfinite(diff_vol) or diff_vol <= 0:
        return False, {"reason": "bad_vol"}
    # 4. FX at d
    fx = fx_at(fx_cache.get(info["ccy"]), d)
    if fx is None or not np.isfinite(fx) or fx <= 0:
        return False, {"reason": "no_fx_yet"}
    # 5. min_capital_E at d
    E_d = info["mult"] * diff_vol * np.sqrt(BDAY) * fx / args.vol_target
    diag["E"] = E_d
    # capital allows k contracts of this instrument?
    if E_d * args.min_contracts_held > args.capital:
        return False, {"reason": "capital_short", "E": E_d}
    # 6. ADV (static)
    adv = info["adv"]
    if adv is None or adv < args.min_adv_contracts:
        return False, {"reason": "adv_low" if adv is not None else "adv_missing",
                       "adv": adv}
    return True, diag


def build_membership(args, cache: dict, fx_cache: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (membership_bool, E_values) both indexed by rebalance_date × instrument."""
    end = pd.Timestamp(args.end) if args.end else pd.Timestamp.today().normalize()
    start = pd.Timestamp(args.start)
    rebal_dates = pd.date_range(start, end, freq=args.rebalance_freq)
    names = sorted(cache.keys())
    mem = pd.DataFrame(False, index=rebal_dates, columns=names)
    E = pd.DataFrame(np.nan, index=rebal_dates, columns=names)
    for d in rebal_dates:
        for name in names:
            ok, diag = eligible_at(name, cache[name], d, args, fx_cache)
            mem.loc[d, name] = ok
            if "E" in diag:
                E.loc[d, name] = diag["E"]
    # Optional asset-class diversity check (drop dates that fail)
    if args.min_asset_classes > 0:
        for d in rebal_dates:
            picked = [n for n in names if mem.loc[d, n]]
            fams = set(cache[n]["family"] for n in picked)
            if len(fams) < args.min_asset_classes:
                # Skip this date's universe (signal will skip too)
                mem.loc[d, :] = False
    return mem, E


def write_config_snapshot(args, label: str, n_candidates: int, n_eligible_mean: float):
    out = {
        "label": label,
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "parameters": {
            "capital_usd": args.capital,
            "n_positions": args.n_positions,
            "vol_target": args.vol_target,
            "min_contracts_held": args.min_contracts_held,
            "lookback_momentum_days": args.lookback_momentum,
            "min_history_years": args.min_history_years,
            "min_adv_contracts": args.min_adv_contracts,
            "max_staleness_days": args.max_staleness_days,
            "rebalance_freq": args.rebalance_freq,
            "exclude_asset_classes": args.exclude_asset_classes.split(","),
            "exclude_china": args.exclude_china,
            "min_asset_classes": args.min_asset_classes,
            "start": args.start, "end": args.end or "today",
        },
        "results_summary": {
            "n_candidates_after_static_filters": n_candidates,
            "mean_universe_size": float(n_eligible_mean),
        },
        "static_approximations_flagged": [
            "ADV from exchange-published references (current snapshot, not PIT)",
            "Spread cost: not applied in this filter (downstream)",
            "Multiplier / contract spec: current config (assumed stable over history)",
            "Survivorship: only instruments present in current instrumentconfig.csv",
        ],
    }
    p = f"{OUT_DIR}/pit_universe_{label}_config.yaml"
    with open(p, "w") as f:
        yaml.safe_dump(out, f, sort_keys=False, default_flow_style=False)
    return p


def write_summary_html(args, label: str, mem: pd.DataFrame, cache: dict) -> str:
    # Universe size over time
    size = mem.sum(axis=1)
    # Asset-family over time
    fams = sorted(set(cache[n]["family"] for n in mem.columns))
    fam_ts = pd.DataFrame(0, index=mem.index, columns=fams)
    for n in mem.columns:
        f = cache[n]["family"]
        fam_ts[f] += mem[n].astype(int)
    # Latest date members
    last_d = mem.index[-1]
    last_members = sorted([n for n in mem.columns if mem.loc[last_d, n]])
    # transitions: how often each instrument enters/exits
    enters = (mem.astype(int).diff() == 1).sum(axis=0)
    n_enters = enters.sort_values(ascending=False)
    # SVG: universe size over time (small inline)
    def svg_line(series, ymax, title):
        W, H, ml, mr, mt, mb = 720, 220, 50, 60, 30, 30
        pw, ph = W - ml - mr, H - mt - mb
        n = len(series)
        if n < 2:
            return f"<svg width='{W}' height='{H}'><text x='10' y='20'>(no data)</text></svg>"
        xs = [ml + i * pw / (n - 1) for i in range(n)]
        ys = [mt + ph - (max(0, v) / ymax) * ph for v in series.values]
        parts = [f"<svg viewBox='0 0 {W} {H}' width='100%' style='max-width:740px'>"]
        parts.append(f"<text x='{ml}' y='18' font-size='13' font-weight='600'>{title}</text>")
        # gridlines y
        for q in (0, 0.25, 0.5, 0.75, 1.0):
            y = mt + ph * (1 - q)
            v = int(ymax * q)
            parts.append(f"<line x1='{ml}' y1='{y}' x2='{ml+pw}' y2='{y}' stroke='#eee'/>")
            parts.append(f"<text x='{ml-6}' y='{y+4}' font-size='10' text-anchor='end' fill='#888'>{v}</text>")
        # year ticks
        years = sorted(set(d.year for d in series.index))
        for yr in years[::max(1, len(years)//8)]:
            i = next((i for i, d in enumerate(series.index) if d.year == yr), None)
            if i is None: continue
            x = xs[i]
            parts.append(f"<text x='{x}' y='{H-10}' font-size='10' text-anchor='middle' fill='#888'>{yr}</text>")
        path = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
        parts.append(f"<polyline points='{path}' fill='none' stroke='#2a4a6b' stroke-width='1.6'/>")
        parts.append("</svg>")
        return "".join(parts)
    ymax = max(int(size.max() * 1.15), 5)
    chart1 = svg_line(size, ymax, "Universe size over time")
    # Stacked family ribbon — simple: show one family as line
    fam_charts = ""
    for f in fams:
        fam_charts += svg_line(fam_ts[f], max(int(fam_ts[f].max() * 1.2), 3), f"{f} count over time")

    # latest members table
    rows = []
    for n in last_members:
        info = cache[n]
        rows.append(f"<tr><td>{n}</td><td>{info['family']}</td><td>{info['asset']}</td><td>{info['ccy']}</td><td class='num'>{info['mult']:g}</td><td class='num'>{info['adv']:,}</td></tr>")

    transitions_rows = []
    for n, k in n_enters[n_enters > 0].head(15).items():
        transitions_rows.append(f"<tr><td>{n}</td><td class='num'>{int(k)}</td></tr>")

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>PIT universe summary — {label}</title>
<style>
body{{font:14px/1.55 -apple-system,sans-serif;color:#111;max-width:1100px;margin:0 auto;padding:30px 22px}}
h1{{font-size:22px;margin:0 0 6px}} h2{{font-size:15px;margin:24px 0 6px;border-bottom:2px solid #111;padding-bottom:3px}}
.sub{{color:#666;font-size:13px;margin-bottom:14px}}
.box{{background:#fafafa;border:1px solid #e5e5e5;padding:12px 16px;border-radius:4px;font-size:13px;margin:10px 0}}
table{{border-collapse:collapse;width:100%;font-size:12.5px;margin:8px 0}}
th,td{{border:1px solid #e5e5e5;padding:4px 8px;text-align:left}}
th{{background:#f9fafb;font-weight:600}} td.num{{text-align:right;font-variant-numeric:tabular-nums}}
code{{background:#f3f3f3;padding:1px 5px;border-radius:3px;font-size:12px}}
.cap{{font-size:11px;color:#666;font-style:italic;margin-top:4px}}
</style></head><body>

<h1>PIT universe — <code>{label}</code></h1>
<div class="sub">Capital ${args.capital:,.0f} · n_positions={args.n_positions} · vol_target={args.vol_target:.0%} ·
min_contracts={args.min_contracts_held} · rebalance={args.rebalance_freq} · {args.start} → {args.end or 'today'}</div>

<div class="box">
<b>Eligibility rules (causal at each date d):</b>
<ol>
<li>Has ≥ {args.min_history_years}y of price history before d</li>
<li>Most recent price within {args.max_staleness_days} days of d</li>
<li>E<sub>d</sub> × {args.min_contracts_held} ≤ ${args.capital:,.0f}  where E<sub>d</sub> = mult × σ<sub>d</sub> × √256 × FX<sub>d</sub> / {args.vol_target}</li>
<li>ADV ≥ {args.min_adv_contracts:,} contracts/day (STATIC, exchange ref)</li>
<li>Asset class not in [{args.exclude_asset_classes}]</li>
<li>{'China-exposed names excluded' if args.exclude_china else 'China kept'}</li>
{f'<li>Asset-family diversity ≥ {args.min_asset_classes}</li>' if args.min_asset_classes else ''}
</ol>
<b>Static approximations</b>: ADV (current snapshot), spread cost (not applied here), multiplier (current), survivorship (current config only).
</div>

<h2>Universe size over time</h2>
{chart1}
<div class="cap">Number of eligible instruments at each rebalance date. Drops indicate vol spikes or instruments aging out / data gaps.</div>

<h2>Latest rebalance ({last_d.date()}) — {len(last_members)} members</h2>
<table><thead><tr><th>Instrument</th><th>Family</th><th>AssetClass</th><th>Ccy</th><th>Mult</th><th>ADV</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>

<h2>Most-flickering instruments (membership entries)</h2>
<table><thead><tr><th>Instrument</th><th># entries</th></tr></thead><tbody>{''.join(transitions_rows) or '<tr><td colspan=2>(none)</td></tr>'}</tbody></table>
<div class="cap">Instruments that frequently enter/exit are vol-regime-sensitive. Stability is desirable for rotation continuity.</div>

<h2>By asset family — count over time</h2>
{fam_charts}

</body></html>"""
    p = f"{OUT_DIR}/pit_universe_{label}_summary.html"
    with open(p, "w") as f:
        f.write(html)
    return p


def main():
    args = parse_args()
    label = slug_label(args)
    os.makedirs(OUT_DIR, exist_ok=True)

    cfg = {r["Instrument"]: r for r in csv.DictReader(open(CFG_PATH))}
    print(f"[1/4] Loading candidates from {len(cfg)} instruments...")
    cache, fx_cache = build_candidate_cache(args, cfg)
    print(f"      -> {len(cache)} candidates after static filters (ex-classes, ex-china, has-data, has-FX)")

    print(f"[2/4] Building PIT membership matrix ({args.start} -> {args.end or 'today'}, freq={args.rebalance_freq})...")
    mem, E = build_membership(args, cache, fx_cache)
    mean_size = float(mem.sum(axis=1).mean())
    print(f"      -> {len(mem)} rebalance dates · mean universe size = {mean_size:.1f}")

    # Write outputs
    print(f"[3/4] Writing outputs...")
    mem_path = f"{OUT_DIR}/pit_universe_{label}.parquet"
    mem.to_parquet(mem_path)
    # also E values for diagnostics
    E.to_parquet(f"{OUT_DIR}/pit_universe_{label}_E.parquet")
    cfg_path = write_config_snapshot(args, label, len(cache), mean_size)
    html_path = write_summary_html(args, label, mem, cache)
    print(f"      -> {mem_path}")
    print(f"      -> {cfg_path}")
    print(f"      -> {html_path}")

    # Verify: print latest universe
    print(f"\n[4/4] Verify — latest rebalance ({mem.index[-1].date()}):")
    last_members = sorted([n for n in mem.columns if mem.loc[mem.index[-1], n]])
    print(f"  {len(last_members)} members: {', '.join(last_members)}")
    # Family breakdown
    from collections import Counter
    fams = Counter(cache[n]["family"] for n in last_members)
    print(f"  by family: {dict(fams)}")


if __name__ == "__main__":
    main()
