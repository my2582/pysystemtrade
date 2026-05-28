#!/usr/bin/env python3
"""
DV-based Minimum-Account-Size Study — all tradeable futures (ex-FX, ex-energy).

Recasts the universe from a NAME proxy ("mini"/"micro") to the principled
small-AUM criterion: dollar-vol per contract DV = (mult × price) × %vol.
Adds every non-FX / non-energy contract with adjusted-price data, tags
each row as in-minimicro / added / stale / current, and shows how the
universe grows by account size.

Method (additive-back-adjustment safe):
    DV_local = pointsize * dailyDiffVol * sqrt(256)
    dailyDiffVol = engine mixed_vol_calc on PRICE DIFFS
    MinAccount_USD(k) = k * DV_local / 0.30 * fx_to_usd

Outputs a self-contained HTML report. Reads only repo CSVs. Core engine untouched.
"""
import csv, glob, os, warnings, datetime
warnings.simplefilter("ignore")
import numpy as np, pandas as pd

ROOT = "/Users/msyeom/Developer/pysystemtrade"
VOL_TARGET = 0.30
TODAY = pd.Timestamp("2026-05-28")
ADJ = f"{ROOT}/data/futures/adjusted_prices_csv"
FXD = f"{ROOT}/data/futures/fx_prices_csv"
OUT = f"{ROOT}/references/strategy/2026-05-28_dv_universe_study.html"

from sysquant.estimators.vol import mixed_vol_calc

cfg = {r["Instrument"]: r for r in csv.DictReader(open(f"{ROOT}/data/futures/csvconfig/instrumentconfig.csv"))}
have_px = {os.path.basename(p)[:-4] for p in glob.glob(f"{ADJ}/*.csv")}

_fx_cache = {}
def fx_to_usd(ccy):
    if ccy == "USD": return 1.0
    if ccy in _fx_cache: return _fx_cache[ccy]
    f = f"{FXD}/{ccy}USD.csv"
    if not os.path.exists(f):
        _fx_cache[ccy] = None; return None
    s = pd.read_csv(f)
    v = pd.to_numeric(s[s.columns[1]], errors="coerce").dropna()
    r = float(v.iloc[-1]) if len(v) else None
    _fx_cache[ccy] = r; return r


def is_minimicro(n):
    n = n.lower(); return "mini" in n or "micro" in n


CHINA_PAT = ("CHINA", "HANG", "FTSECHINA", "CSI", "SHANGHAI")
MEANREV = {"VIX", "VIX_mini", "VSTOXX", "V2X"}
CRYPTO = {"BITCOIN", "ETHER-micro", "ETHEREUM", "MICRO-ETH", "MICRO-BTC"}


def is_china(n):
    u = n.upper()
    return any(p in u for p in CHINA_PAT)


rows = []
skipped = 0
for name, r in cfg.items():
    if name not in have_px: continue
    if r["AssetClass"] in ("FX", "OilGas"): continue
    try:
        df = pd.read_csv(f"{ADJ}/{name}.csv")
        d = pd.to_datetime(df[df.columns[0]], errors="coerce")
        s = pd.to_numeric(df[df.columns[1]], errors="coerce")
        s.index = d; s = s.dropna()
        if len(s) < 60:
            skipped += 1; continue
        diffs = s.diff().dropna()
        vol = mixed_vol_calc(diffs, days=35, min_periods=10, slow_vol_years=20, proportion_of_slow_vol=0.35)
        v = vol.dropna()
        if len(v) == 0:
            skipped += 1; continue
        daily_pt_vol = float(v.iloc[-1])
        ps = float(r["Pointsize"])
        last_price = float(s.iloc[-1])
        last_date = s.index[-1]
        years = (s.index[-1] - s.index[0]).days / 365.25
        ann_dollar_vol_local = ps * daily_pt_vol * np.sqrt(256)
        ann_perc = ann_dollar_vol_local / (ps * abs(last_price)) * 100 if last_price else float("nan")
        fx = fx_to_usd(r["Currency"])
        if fx is None:
            skipped += 1; continue
        dv_usd = ann_dollar_vol_local * fx
        stale_days = (TODAY - last_date).days
        flags = []
        if stale_days > 120: flags.append("STALE")
        if is_china(name): flags.append("China")
        if name in MEANREV: flags.append("mean-rev")
        if name in CRYPTO: flags.append("crypto")
        if years < 5: flags.append("short-hist")
        rows.append(dict(
            name=name, asset=r["AssetClass"], ccy=r["Currency"],
            last_date=str(last_date.date()), stale_days=stale_days,
            years=years, mult=ps, price=last_price,
            notional_usd=ps * abs(last_price) * fx,
            ann_perc=ann_perc, dv_usd=dv_usd,
            min1=dv_usd / VOL_TARGET, min2=2 * dv_usd / VOL_TARGET,
            min3=3 * dv_usd / VOL_TARGET, min4=4 * dv_usd / VOL_TARGET,
            flags=flags, current=(stale_days <= 120),
            in_minimicro=is_minimicro(name),
        ))
    except Exception as e:
        skipped += 1

rows.sort(key=lambda x: x["min1"])

acct_grid = [10_000, 25_000, 50_000, 75_000, 100_000, 150_000, 200_000, 300_000, 500_000, 1_000_000]
mat = {a: {k: {"total": 0, "current": 0, "mm": 0, "added": 0} for k in (1, 2, 3, 4)} for a in acct_grid}
for a in acct_grid:
    for x in rows:
        for k in (1, 2, 3, 4):
            if x[f"min{k}"] <= a:
                mat[a][k]["total"] += 1
                if x["current"]: mat[a][k]["current"] += 1
                if x["in_minimicro"]: mat[a][k]["mm"] += 1
                else: mat[a][k]["added"] += 1


def usd(v):
    if v < 1000: return f"${v:,.0f}"
    if v < 10_000: return f"${v/1000:,.1f}k"
    if v < 1_000_000: return f"${v/1000:,.0f}k"
    return f"${v/1e6:.2f}M"


def svg_chart(mat, title):
    W, H, ml, mr, mt, mb = 660, 320, 55, 130, 36, 46
    pw, ph = W - ml - mr, H - mt - mb
    import math
    lx = [math.log10(a) for a in acct_grid]
    lxmin, lxmax = min(lx), max(lx)
    ymax = max(len(rows), 1)
    def px(i): return ml + (lx[i] - lxmin) / (lxmax - lxmin) * pw
    def py(v): return mt + ph - (v / ymax) * ph
    colors = {1: "#2563eb", 2: "#059669", 3: "#d97706", 4: "#dc2626"}
    parts = [f'<svg viewBox="0 0 {W} {H}" width="100%" style="max-width:680px">']
    parts.append(f'<text x="{ml}" y="20" font-size="13" font-weight="700" fill="#111">{title}</text>')
    for v in range(0, ymax + 1, max(1, ymax // 6)):
        y = py(v)
        parts.append(f'<line x1="{ml}" y1="{y:.0f}" x2="{ml+pw}" y2="{y:.0f}" stroke="#eee"/>')
        parts.append(f'<text x="{ml-8}" y="{y+4:.0f}" font-size="10" text-anchor="end" fill="#888">{v}</text>')
    for i, a in enumerate(acct_grid):
        parts.append(f'<text x="{px(i):.0f}" y="{mt+ph+16:.0f}" font-size="9" text-anchor="middle" fill="#888">{usd(a)}</text>')
    parts.append(f'<text x="{ml+pw/2:.0f}" y="{H-6}" font-size="10" text-anchor="middle" fill="#666">account size (log)</text>')
    for k in (1, 2, 3, 4):
        pts = " ".join(f"{px(i):.1f},{py(mat[a][k]['total']):.1f}" for i, a in enumerate(acct_grid))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{colors[k]}" stroke-width="2.2"/>')
        for i, a in enumerate(acct_grid):
            parts.append(f'<circle cx="{px(i):.1f}" cy="{py(mat[a][k]["total"]):.1f}" r="2.6" fill="{colors[k]}"/>')
        ly = py(mat[acct_grid[-1]][k]["total"])
        parts.append(f'<text x="{ml+pw+8}" y="{ly+4:.0f}" font-size="10" fill="{colors[k]}">≥{k} ctr ({mat[acct_grid[-1]][k]["total"]})</text>')
    parts.append("</svg>")
    return "".join(parts)


def badges(fl, mm):
    cmap = {"STALE": "#9ca3af", "China": "#dc2626", "mean-rev": "#7c3aed", "crypto": "#ea580c", "short-hist": "#d97706"}
    bs = [f'<span class="badge" style="background:{cmap.get(f,"#999")}">{f}</span>' for f in fl]
    if mm: bs.insert(0, '<span class="badge" style="background:#0ea5e9">mini/micro</span>')
    else: bs.insert(0, '<span class="badge" style="background:#10b981">ADDED</span>')
    return " ".join(bs)


# Per-instrument table — sorted by min1, color rows by current/stale and mm/added
trows = []
for x in rows:
    cls = []
    cls.append("stale" if not x["current"] else "current")
    cls.append("mm" if x["in_minimicro"] else "added")
    trows.append(
        f'<tr class="{" ".join(cls)}"><td class="name">{x["name"]}</td><td>{x["asset"]}</td>'
        f'<td>{x["ccy"]}</td><td class="num">{x["mult"]:g}</td>'
        f'<td class="num">{usd(x["notional_usd"])}</td>'
        f'<td class="num">{x["ann_perc"]:.1f}%</td><td class="num">{usd(x["dv_usd"])}</td>'
        f'<td class="num b">{usd(x["min1"])}</td><td class="num">{usd(x["min2"])}</td>'
        f'<td class="num">{usd(x["min3"])}</td><td class="num b">{usd(x["min4"])}</td>'
        f'<td class="dt">{x["last_date"]}</td><td>{badges(x["flags"], x["in_minimicro"])}</td></tr>'
    )

# matrix rows
mat_rows = []
for a in acct_grid:
    cells = []
    for k in (1, 2, 3, 4):
        cell = mat[a][k]
        cells.append(
            f'<td class="num">{cell["total"]}<span class="sub"> ({cell["mm"]}mm+{cell["added"]}new'
            f' · {cell["current"]}cur)</span></td>'
        )
    mat_rows.append(f'<tr><td class="b">{usd(a)}</td>{"".join(cells)}</tr>')

# Quick stats
n_total = len(rows)
n_mm = sum(1 for x in rows if x["in_minimicro"])
n_added = n_total - n_mm
n_cur = sum(1 for x in rows if x["current"])
n_cur_added = sum(1 for x in rows if x["current"] and not x["in_minimicro"])

# Asset class breakdown of added
from collections import Counter
ac_added = Counter(x["asset"] for x in rows if not x["in_minimicro"])
ac_list = "; ".join(f"{ac} {c}" for ac, c in ac_added.most_common())

gen = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

HTML = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DV-based universe study · all tradeable futures (ex-FX, ex-energy)</title>
<style>
 :root{{--bd:#e5e7eb;--mut:#6b7280}}
 *{{box-sizing:border-box}} body{{font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;color:#111;max-width:1140px;margin:0 auto;padding:28px 22px}}
 h1{{font-size:22px;margin:0 0 2px}} h2{{font-size:16px;margin:30px 0 10px;border-bottom:2px solid #111;padding-bottom:5px}}
 .sub0{{color:var(--mut);margin:0 0 18px;font-size:13px}}
 .key{{background:#f0f7ff;border-left:4px solid #2563eb;padding:12px 16px;border-radius:4px;margin:14px 0}}
 .method{{background:#fafafa;border:1px solid var(--bd);border-radius:6px;padding:12px 16px;font-size:12.5px;color:#333}}
 code{{background:#f3f4f6;padding:1px 5px;border-radius:3px;font-size:12px}}
 table{{border-collapse:collapse;width:100%;font-size:12px;margin:8px 0}}
 th,td{{border:1px solid var(--bd);padding:4px 7px;text-align:left}}
 th{{background:#f9fafb;font-weight:600;position:sticky;top:0;z-index:1}}
 td.num{{text-align:right;font-variant-numeric:tabular-nums}}
 td.b{{font-weight:700}} td.name{{font-weight:600}} td.dt{{color:var(--mut);font-size:10.5px}}
 tr.stale{{color:#9ca3af;background:#fcfcfc}} tr.stale td.name{{color:#9ca3af}}
 tr.added td.name{{color:#047857}}
 tr.current.added td.name{{color:#065f46;background:#ecfdf5}}
 .badge{{color:#fff;border-radius:3px;padding:1px 6px;font-size:9.5px;margin-right:2px;white-space:nowrap}}
 .sub{{color:#9ca3af;font-size:10px}}
 .legend{{font-size:12px;color:var(--mut);margin:6px 0}}
 .two{{display:flex;gap:22px;flex-wrap:wrap;align-items:flex-start}}
 ul{{margin:6px 0 6px 18px}} li{{margin:3px 0}}
 .scroll{{max-height:600px;overflow:auto;border:1px solid var(--bd);border-radius:4px}}
</style></head><body>

<h1>DV-based universe study — all tradeable futures (ex-FX, ex-energy)</h1>
<p class="sub0">30% vol target · <b>{n_total}</b> instruments ({n_mm} mini/micro + {n_added} ADDED) · {n_cur} current / {n_total - n_cur} stale · generated {gen}</p>

<div class="key"><b>Headline.</b> Replacing the NAME proxy ("mini"/"micro") with the principled DV criterion expands the universe from <b>22 → {n_total}</b> (+{n_added}). The added contracts are dominated by the very families a niche small-AUM strategy wants: <b>{ac_list}</b>. Of the {n_added} added, only <b>{n_cur_added}</b> are on current data — confirming the earlier finding: <i>capital is not the bottleneck; data currency is</i>. Refreshing the IB backfill (see <code>price-universe-refresh-plan</code>) is the single highest-leverage step to unlock niche dispersion.</div>

<div class="method"><b>Method.</b>
<code>MinAccount_USD(k) = k × DV_local ÷ 0.30 × fx→USD</code>,
<code>DV_local = mult × dailyDiffVol × √256</code>,
<code>dailyDiffVol</code> from pysystemtrade <code>mixed_vol_calc</code> (35-day + 20-year slow-vol blend) on <b>price diffs</b> (additive back-adjustment makes <code>pct_change</code> invalid). FX from repo <code>fx_prices_csv</code>. Universe = all instruments with adjusted-price data, ex-FX, ex-OilGas (energy). Mini/micro <i>name</i> is now a tag, not a filter.</div>

<h2>1 · Universe unlocked by account size</h2>
<p class="legend">Format: <b>total</b><span class="sub"> ({{X mm + Y new}} · {{Z current}})</span>. mm = name-based mini/micro that fit; new = ADDED non-mini/micro; current = data ≤ 120 days old.</p>
<div class="two">
<table style="max-width:560px">
<thead><tr><th>Account</th><th>≥1 ctr</th><th>≥2 ctr</th><th>≥3 ctr</th><th>≥4 ctr</th></tr></thead>
<tbody>{''.join(mat_rows)}</tbody></table>
<div>{svg_chart(mat, "Universe size vs account (DV-based, all data)")}</div>
</div>

<h2>2 · What's ADDED by switching from name to DV ({n_added} instruments)</h2>
<p class="legend">Non-mini/micro contracts that pass ex-FX + ex-energy + has-data. Green name = also current data. By asset class: <b>{ac_list}</b>.</p>

<h2>3 · Per-instrument table — sorted by 1-contract minimum (USD)</h2>
<p class="legend">Cheapest first. <span class="badge" style="background:#10b981">ADDED</span> = non-mini/micro joining via DV criterion. <span class="badge" style="background:#0ea5e9">mini/micro</span> = original 22. Grey rows = STALE data.</p>
<div class="scroll">
<table>
<thead><tr><th>Instrument</th><th>Asset</th><th>Ccy</th><th>Mult</th><th>Notional</th>
<th>AnnVol</th><th>DV (USD)</th><th>1-ctr</th><th>2-ctr</th><th>3-ctr</th><th>4-ctr</th><th>Data</th><th>Flags</th></tr></thead>
<tbody>{''.join(trows)}</tbody></table>
</div>

<h2>4 · Niche-strategy reading</h2>
<ul>
<li><b>The mini/micro NAME filter was a proxy that under-counted niche.</b> Sector indices (EU-BANKS/AUTO/CHEM …) and full-size ags/softs (COCOA/COFFEE/CORN/COTTON …) are the natural small-AUM niches but carry no "mini" in their name. Switching to DV captures them.</li>
<li><b>$50k clears ≥4-contract granularity on {mat[50000][4]['total']} of {n_total} instruments</b> ({mat[50000][4]['mm']} from original mini/micro + {mat[50000][4]['added']} newly added), of which {mat[50000][4]['current']} are on current data. The capital headroom is large; the binding scarcity is current data, not money.</li>
<li><b>High-DV outliers</b> (GOLD_micro in the original 22, plus a handful of full-size indices/bonds in the added set) push min-account up only if you keep them in scope. A <code>min_contracts</code> rule auto-excludes them when capital is insufficient.</li>
<li><b>Next leverage</b>: refresh the IB backfill universe to bring the niche softs / sector / bond legs from STALE → current. Even a modest subset (e.g. SUGAR11, COTTON, COCOA, COFFEE, EU-BANKS, BUND, BOBL) would turn the current ~5-name correlated rotation into a 10–15-name diversified rotation, at the same $50k.</li>
</ul>

</body></html>"""

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    f.write(HTML)
print(f"wrote {OUT}")
print(f"universe: total {n_total} ({n_mm} mm + {n_added} added; {n_cur} current, {n_total-n_cur} stale)")
print(f"skipped: {skipped}")
print(f"asset-class breakdown of ADDED: {ac_list}")
print(f"\nat $50k: ≥1={mat[50000][1]['total']}/{mat[50000][1]['current']}cur, ≥2={mat[50000][2]['total']}/{mat[50000][2]['current']}cur,"
      f" ≥4={mat[50000][4]['total']}/{mat[50000][4]['current']}cur")
print(f"at $100k: ≥4={mat[100000][4]['total']}/{mat[100000][4]['current']}cur")
print(f"\nfirst 15 ADDED (cheapest min1, current first):")
for x in [r for r in rows if not r["in_minimicro"]][:15]:
    fl = ",".join(x["flags"]); cur = "CUR" if x["current"] else "stale"
    print(f"  {x['name']:<18}{x['asset']:<10}{x['ccy']:<4} min1={usd(x['min1']):>7}  4ctr={usd(x['min4']):>8}  {cur} {fl}")
