#!/usr/bin/env python3
"""
Minimum-Account-Size Study — mini/micro futures universe (ex-FX, ex-energy).

For each instrument compute the dollar-vol per contract and the minimum USD
account size to hold k = 1..4 contracts at a 30% annualized vol target, then
show how the *tradeable universe* grows with account size.

Method (additive-back-adjustment safe):
    DV_local = pointsize * dailyDiffVol * sqrt(256)         # annual $vol / contract
    dailyDiffVol = engine mixed_vol_calc on PRICE DIFFS     # not pct_change
    MinAccount_USD(k) = k * DV_local / vol_target * fx_to_usd

Outputs a self-contained HTML report. Reads only repo CSVs. Core engine untouched.
"""
import csv, glob, os, warnings, datetime, html as _html
warnings.simplefilter("ignore")
import numpy as np, pandas as pd

ROOT = "/Users/msyeom/Developer/pysystemtrade"
VOL_TARGET = 0.30
TODAY = pd.Timestamp("2026-05-27")
ADJ = f"{ROOT}/data/futures/adjusted_prices_csv"
FXD = f"{ROOT}/data/futures/fx_prices_csv"
OUT = f"{ROOT}/references/strategy/2026-05-27_min_account_universe_study.html"

from sysquant.estimators.vol import mixed_vol_calc

cfg = {r["Instrument"]: r for r in csv.DictReader(open(f"{ROOT}/data/futures/csvconfig/instrumentconfig.csv"))}
have_px = {os.path.basename(p)[:-4] for p in glob.glob(f"{ADJ}/*.csv")}


def fx_to_usd(ccy):
    if ccy == "USD":
        return 1.0, "—"
    f = f"{FXD}/{ccy}USD.csv"
    if not os.path.exists(f):
        return None, "no FX"
    s = pd.read_csv(f)
    v = pd.to_numeric(s[s.columns[1]], errors="coerce").dropna()
    return float(v.iloc[-1]), str(v.index[-1])


def is_minimicro(n):
    n = n.lower()
    return "mini" in n or "micro" in n


CHINA = {"HANG_mini", "HANGENT_mini"}
MEANREV = {"VIX_mini"}
CRYPTO = {"ETHER-micro"}

rows = []
for name, r in cfg.items():
    if not is_minimicro(name) or name not in have_px:
        continue
    if r["AssetClass"] in ("FX", "OilGas"):
        continue
    df = pd.read_csv(f"{ADJ}/{name}.csv")
    d = pd.to_datetime(df[df.columns[0]], errors="coerce")
    s = pd.to_numeric(df[df.columns[1]], errors="coerce")
    s.index = d
    s = s.dropna()
    if len(s) < 60:
        continue
    diffs = s.diff().dropna()
    vol = mixed_vol_calc(diffs, days=35, min_periods=10, slow_vol_years=20, proportion_of_slow_vol=0.35)
    daily_pt_vol = float(vol.dropna().iloc[-1])
    ps = float(r["Pointsize"])
    last_price = float(s.iloc[-1])
    last_date = s.index[-1]
    years = (s.index[-1] - s.index[0]).days / 365.25
    ann_dollar_vol_local = ps * daily_pt_vol * np.sqrt(256)
    ann_perc = ann_dollar_vol_local / (ps * abs(last_price)) * 100 if last_price else np.nan
    fx, fxdate = fx_to_usd(r["Currency"])
    if fx is None:
        continue
    dv_usd = ann_dollar_vol_local * fx
    stale_days = (TODAY - last_date).days
    flags = []
    if stale_days > 120:
        flags.append("STALE")
    if name in CHINA:
        flags.append("China")
    if name in MEANREV:
        flags.append("mean-rev")
    if name in CRYPTO:
        flags.append("crypto")
    if years < 5:
        flags.append("short-hist")
    rows.append(dict(
        name=name, asset=r["AssetClass"], ccy=r["Currency"], last_date=str(last_date.date()),
        stale_days=stale_days, years=years, ann_perc=ann_perc, dv_usd=dv_usd,
        mult=ps, price=last_price, notional_usd=ps * abs(last_price) * fx,
        min1=dv_usd / VOL_TARGET, min2=2 * dv_usd / VOL_TARGET,
        min3=3 * dv_usd / VOL_TARGET, min4=4 * dv_usd / VOL_TARGET,
        flags=flags, current=(stale_days <= 120),
    ))

rows.sort(key=lambda x: x["min1"])

# universe-size vs account-size matrix
acct_grid = [10_000, 25_000, 50_000, 75_000, 100_000, 150_000, 200_000, 300_000, 500_000]
matrix = {a: {k: 0 for k in (1, 2, 3, 4)} for a in acct_grid}
matrix_cur = {a: {k: 0 for k in (1, 2, 3, 4)} for a in acct_grid}
for a in acct_grid:
    for x in rows:
        for k in (1, 2, 3, 4):
            if x[f"min{k}"] <= a:
                matrix[a][k] += 1
                if x["current"]:
                    matrix_cur[a][k] += 1


def usd(v):
    if v < 1000:
        return f"${v:,.0f}"
    if v < 10_000:
        return f"${v/1000:,.1f}k"
    if v < 1_000_000:
        return f"${v/1000:,.0f}k"
    return f"${v/1e6:.2f}M"


# ---- SVG line chart: x=account (log), y=#instruments, 4 lines for k ----
def svg_chart(mat, title):
    W, H, ml, mr, mt, mb = 620, 300, 55, 120, 36, 46
    pw, ph = W - ml - mr, H - mt - mb
    xs = acct_grid
    import math
    lx = [math.log10(a) for a in xs]
    lxmin, lxmax = min(lx), max(lx)
    ymax = max(len(rows), 1)
    def px(i): return ml + (lx[i] - lxmin) / (lxmax - lxmin) * pw
    def py(v): return mt + ph - (v / ymax) * ph
    colors = {1: "#2563eb", 2: "#059669", 3: "#d97706", 4: "#dc2626"}
    parts = [f'<svg viewBox="0 0 {W} {H}" width="100%" style="max-width:640px">']
    parts.append(f'<text x="{ml}" y="20" font-size="13" font-weight="700" fill="#111">{title}</text>')
    # y gridlines
    for v in range(0, ymax + 1, max(1, ymax // 5)):
        y = py(v)
        parts.append(f'<line x1="{ml}" y1="{y:.0f}" x2="{ml+pw}" y2="{y:.0f}" stroke="#eee"/>')
        parts.append(f'<text x="{ml-8}" y="{y+4:.0f}" font-size="10" text-anchor="end" fill="#888">{v}</text>')
    # x labels
    for i, a in enumerate(xs):
        parts.append(f'<text x="{px(i):.0f}" y="{mt+ph+16:.0f}" font-size="9" text-anchor="middle" fill="#888">{usd(a)}</text>')
    parts.append(f'<text x="{ml+pw/2:.0f}" y="{H-6}" font-size="10" text-anchor="middle" fill="#666">account size (log)</text>')
    # lines
    for k in (1, 2, 3, 4):
        pts = " ".join(f"{px(i):.1f},{py(mat[a][k]):.1f}" for i, a in enumerate(xs))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{colors[k]}" stroke-width="2.2"/>')
        for i, a in enumerate(xs):
            parts.append(f'<circle cx="{px(i):.1f}" cy="{py(mat[a][k]):.1f}" r="2.6" fill="{colors[k]}"/>')
        ly = py(mat[xs[-1]][k])
        parts.append(f'<text x="{ml+pw+8}" y="{ly+4:.0f}" font-size="10" fill="{colors[k]}">≥{k} ctr ({mat[xs[-1]][k]})</text>')
    parts.append("</svg>")
    return "".join(parts)


def flag_badges(flags):
    cmap = {"STALE": "#9ca3af", "China": "#dc2626", "mean-rev": "#7c3aed", "crypto": "#ea580c", "short-hist": "#d97706"}
    return " ".join(f'<span class="badge" style="background:{cmap.get(f,"#999")}">{f}</span>' for f in flags)


trows = []
for x in rows:
    cls = "stale" if not x["current"] else ""
    trows.append(
        f'<tr class="{cls}"><td class="name">{x["name"]}</td><td>{x["asset"]}</td><td>{x["ccy"]}</td>'
        f'<td class="num">{x["mult"]:g}</td><td class="num">{x["price"]:,.2f}</td><td class="num">{usd(x["notional_usd"])}</td>'
        f'<td class="num">{x["ann_perc"]:.1f}%</td><td class="num">{usd(x["dv_usd"])}</td>'
        f'<td class="num b">{usd(x["min1"])}</td><td class="num">{usd(x["min2"])}</td>'
        f'<td class="num">{usd(x["min3"])}</td><td class="num b">{usd(x["min4"])}</td>'
        f'<td class="dt">{x["last_date"]}</td><td>{flag_badges(x["flags"])}</td></tr>'
    )

mat_rows = []
for a in acct_grid:
    mat_rows.append(
        f'<tr><td class="b">{usd(a)}</td>'
        + "".join(f'<td class="num">{matrix[a][k]}<span class="sub">/{matrix_cur[a][k]}</span></td>' for k in (1, 2, 3, 4))
        + "</tr>"
    )

n_cur = sum(1 for x in rows if x["current"])
gen = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

HTML = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Min-Account-Size Study · mini/micro futures</title>
<style>
 :root{{--bd:#e5e7eb;--mut:#6b7280}}
 *{{box-sizing:border-box}} body{{font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;color:#111;max-width:1040px;margin:0 auto;padding:28px 22px}}
 h1{{font-size:22px;margin:0 0 2px}} h2{{font-size:16px;margin:30px 0 10px;border-bottom:2px solid #111;padding-bottom:5px}}
 .sub0{{color:var(--mut);margin:0 0 18px;font-size:13px}}
 .key{{background:#f0f7ff;border-left:4px solid #2563eb;padding:12px 16px;border-radius:4px;margin:14px 0}}
 .method{{background:#fafafa;border:1px solid var(--bd);border-radius:6px;padding:12px 16px;font-size:12.5px;color:#333}}
 code{{background:#f3f4f6;padding:1px 5px;border-radius:3px;font-size:12px}}
 table{{border-collapse:collapse;width:100%;font-size:12.5px;margin:8px 0}}
 th,td{{border:1px solid var(--bd);padding:5px 8px;text-align:left}}
 th{{background:#f9fafb;font-weight:600}} td.num{{text-align:right;font-variant-numeric:tabular-nums}}
 td.b{{font-weight:700}} td.name{{font-weight:600}} td.dt{{color:var(--mut);font-size:11px}}
 tr.stale{{color:#9ca3af;background:#fcfcfc}} tr.stale td.name{{color:#9ca3af}}
 .badge{{color:#fff;border-radius:3px;padding:1px 6px;font-size:10px;margin-right:2px;white-space:nowrap}}
 .sub{{color:#9ca3af;font-size:10px}}
 .legend{{font-size:12px;color:var(--mut);margin:6px 0}}
 .two{{display:flex;gap:22px;flex-wrap:wrap;align-items:flex-start}}
 ul{{margin:6px 0 6px 18px}} li{{margin:3px 0}}
</style></head><body>

<h1>Minimum Account-Size Study — mini/micro futures (ex-FX, ex-energy)</h1>
<p class="sub0">30% vol target · {len(rows)} instruments ({n_cur} current, {len(rows)-n_cur} stale) · USD-converted · generated {gen}</p>

<div class="key"><b>Why this matters:</b> account size → how many contracts you can hold at the 30% vol target → which instruments are tradeable → universe size → what strategy is viable.
Binding variable is <b>dollar-vol per contract</b> <code>DV = (multiplier × price) × %vol</code> — not %vol alone.
With small capital, only low-DV (small-notional) contracts clear the granularity bar — which steers naturally toward <b>niche / less-crowded markets</b> (ags, micro metals, sector), consistent with the small-AUM edge.</div>

<div class="method"><b>Method.</b>
<code>MinAccount_USD(k) = k × DV_local ÷ 0.30 × fx→USD</code>,
<code>DV_local = pointsize × dailyDiffVol × √256</code>,
where <code>dailyDiffVol</code> = pysystemtrade <code>mixed_vol_calc</code> (35d + 20y slow-vol blend) on <b>price diffs</b> (additive back-adjustment makes <code>pct_change</code> invalid — it explodes where back-adjusted prices cross zero). FX from repo <code>fx_prices_csv</code>. "<i>k-contract basis</i>" = smallest account where the 30%-vol position is ≥ k integer contracts; below k=1 the forced 1-contract position <i>overshoots</i> 30%.</div>

<h2>1 · Per-instrument minimum account size (USD)</h2>
<p class="legend">Sorted by 1-contract minimum (cheapest first). Grey rows = STALE data (frozen, need refresh before trading).</p>
<table>
<thead><tr><th>Instrument</th><th>Asset</th><th>Ccy</th><th>Mult</th><th>Price</th><th>Notional (USD)</th><th>AnnVol</th><th>DV (USD)</th>
<th>1-ctr</th><th>2-ctr</th><th>3-ctr</th><th>4-ctr</th><th>Data as-of</th><th>Flags</th></tr></thead>
<tbody>{''.join(trows)}</tbody></table>

<h2>2 · Universe unlocked by account size</h2>
<p class="legend"># instruments tradeable at ≥ k contracts. Format: <b>total</b><span class="sub">/current-only</span> (current = non-stale data).</p>
<div class="two">
<table style="max-width:430px">
<thead><tr><th>Account</th><th>≥1 ctr</th><th>≥2 ctr</th><th>≥3 ctr</th><th>≥4 ctr</th></tr></thead>
<tbody>{''.join(mat_rows)}</tbody></table>
<div>{svg_chart(matrix, "Universe size vs account size (all data)")}</div>
</div>

<h2>3 · Reading it for a small-AUM niche strategy</h2>
<div class="key"><b>The bottleneck is data currency, not capital.</b> At <b>$50k</b> the <i>potential</i> universe is rich — {matrix[50000][4]} of {len(rows)} instruments clear the ≥4-contract comfort line and {matrix[50000][2]} clear ≥2 contracts. But only <b>{matrix_cur[50000][4]} of those are on current data at ≥4 ctr</b>, because the {n_cur} maintained instruments happen to be the <b>high-DV</b> ones (big indices + high-vol metals). Every cheap niche contract (ags, micro metals, bonds) is STALE. So $50k is plenty — the gate to a real niche rotation is <b>refreshing the data</b> (expand IB backfill), not raising the account.</div>
<ul>
<li>The 1-ctr column is the <b>absolute floor</b> (below it the forced position overshoots 30% vol). The 4-ctr column is the <b>comfort line</b> (integer rounding within ~±12% of target).</li>
<li><b>Small accounts steer toward low-DV, small-notional contracts</b> — agriculturals, micro metals, bonds, sector/vol — the less-crowded "niche" corners, exactly where the small-AUM edge lives (fast signals, micro contracts, thinner markets).</li>
<li><b>High-DV instruments (large index / metals in high-vol regimes) are the binding constraint</b> — they alone push the required account up; the lone current GOLD_micro needs $160k for ≥4 ctr at today's elevated vol.</li>
<li>Single-position rotation needs <b>cross-sectional dispersion</b>: over a too-thin / too-correlated set it degrades to fixed-single. Today's 5 current names are 3 correlated equity indices + 2 metals → thin. Refreshing the cheap ags/bonds/metals legs both widens the universe <i>and</i> lowers correlation.</li>
</ul>

</body></html>"""

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    f.write(HTML)
print(f"wrote {OUT}")
print(f"instruments: {len(rows)} ({n_cur} current)")
print("\nmin-account (USD) by instrument [1ctr / 4ctr], sorted:")
for x in rows:
    fl = ",".join(x["flags"])
    print(f"  {x['name']:<16}{x['asset']:<8}{x['ccy']:<4} vol={x['ann_perc']:>5.1f}%  1ctr={usd(x['min1']):>7}  4ctr={usd(x['min4']):>7}  {fl}")
print("\nuniverse size (total/current) by account:")
for a in acct_grid:
    print(f"  {usd(a):>7}: " + "  ".join(f">={k}ctr {matrix[a][k]:>2}/{matrix_cur[a][k]}" for k in (1,2,3,4)))
