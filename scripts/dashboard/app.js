/* ──────────────────────────────────────────────────────────────────
   ARKI BACKTEST ANALYTICS — Main Application
   ────────────────────────────────────────────────────────────────── */

const PALETTE = {
  forest:     '#265844',
  forest90:   '#265844E6',
  forest50:   '#26584480',
  forest30:   '#2658444D',
  forest15:   '#26584426',
  cream:      '#FDF9EE',
  charcoal:   '#232220',
  charcoal70: '#232220B3',
  charcoal50: '#23222080',
  charcoal30: '#2322204D',
  sand:       '#F5E8C1',
  mint:       '#EFFDF6',
  green:      '#55B786',
  greenLight: '#55B78633',
  gridLine:   '#E8DFC8',
};

const FACTOR_COLORS = {
  momentum4:     PALETTE.forest,
  momentum8:     '#2D6B52',
  momentum16:    '#347E60',
  momentum32:    '#3B916E',
  momentum64:    '#42A47C',
  carry30:       PALETTE.green,
  carry60:       '#6CC494',
  carry125:      '#83D1A2',
  relmomentum20: '#C4B68A',
  relmomentum40: '#B8A97E',
  relmomentum80: '#AC9C72',
  relcarry:      PALETTE.charcoal50,
};

const ASSET_CLASSES = {
  'Equity':       ['SP500_micro','NASDAQ_micro','DAX','NIKKEI','FTSE100','IBEX_mini','FTSECHINAA'],
  'Fixed Income': ['US10','US5','BUND','GILT','JGB'],
  'Metals':       ['GOLD_micro','SILVER','COPPER-micro'],
  'Energy':       ['CRUDE_W','BRENT-LAST','GASOIL'],
  'FX':           ['AUD_micro','MXP','YENEUR'],
  'Agricultural': ['SUGAR11','COTTON','LEANHOG','COCOA_LDN'],
};

const AC_COLORS = {
  'Equity':       PALETTE.forest,
  'Fixed Income': PALETTE.green,
  'Metals':       '#6B6B6B',
  'Energy':       '#42A47C',
  'FX':           '#C4B68A',
  'Agricultural': '#8B7355',
};

// ── Chart.js Global Defaults ──
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.size = 11;
Chart.defaults.color = PALETTE.charcoal70;
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.pointStyleWidth = 10;
Chart.defaults.plugins.tooltip.backgroundColor = PALETTE.charcoal;
Chart.defaults.plugins.tooltip.titleFont = { size: 12, weight: '600' };
Chart.defaults.plugins.tooltip.bodyFont = { size: 11 };
Chart.defaults.plugins.tooltip.cornerRadius = 6;
Chart.defaults.plugins.tooltip.padding = 10;
Chart.defaults.elements.line.tension = 0;

// ── State ──
const state = {
  meta: null,
  rollingStats: null,
  dailyReturns: null,
  factorReturns: null,
  forecastWeights: null,
  positionSnapshot: null,
  notionalPositions: null,
  roundedPositions: null,
  instrumentWeights: null,
  turnover: null,
  registry: null,
  charts: {},
  factorPeriod: 'all',
};

// ── CSV Parser ──
function parseCSV(text) {
  const lines = text.trim().split('\n');
  if (lines.length < 2) return [];
  const headers = lines[0].split(',');
  return lines.slice(1).map(line => {
    const vals = line.split(',');
    const obj = {};
    headers.forEach((h, i) => { obj[h.trim()] = vals[i]?.trim() ?? ''; });
    return obj;
  });
}

function parseNumericCSV(text) {
  const rows = parseCSV(text);
  return rows.map(row => {
    const out = {};
    for (const [k, v] of Object.entries(row)) {
      out[k] = k === 'index' || k === '' ? v : (v === '' ? NaN : parseFloat(v));
    }
    return out;
  });
}

// ── Data Loader ──
async function loadFile(path) {
  const resp = await fetch(path);
  if (!resp.ok) throw new Error(`Failed to load ${path}: ${resp.status}`);
  return resp.text();
}

async function loadJSON(path) {
  const text = await loadFile(path);
  return JSON.parse(text);
}

async function loadData() {
  try {
    const [metaText, rollingText, returnsText, snapshotText, posText] = await Promise.all([
      loadFile('data/dashboard_meta.json').catch(() => null),
      loadFile('data/rolling_stats.csv').catch(() => null),
      loadFile('data/daily_returns.csv').catch(() => null),
      loadFile('data/position_snapshot.csv').catch(() => null),
      loadFile('data/notional_positions.csv').catch(() => null),
    ]);

    const [factorText, fwText, turnoverText, iwText, registryText, rpText] = await Promise.all([
      loadFile('data/factor_returns.csv').catch(() => null),
      loadFile('data/forecast_weights.csv').catch(() => null),
      loadFile('data/turnover.csv').catch(() => null),
      loadFile('data/instrument_weights.csv').catch(() => null),
      loadFile('../../../results/runs/registry.yaml').catch(() => loadFile('data/registry.yaml').catch(() => null)),
      loadFile('data/rounded_positions.csv').catch(() => null),
    ]);

    if (metaText) state.meta = JSON.parse(metaText);
    if (rollingText) state.rollingStats = parseNumericCSV(rollingText);
    if (returnsText) state.dailyReturns = parseNumericCSV(returnsText);
    if (snapshotText) state.positionSnapshot = parseCSV(snapshotText);
    if (posText) state.notionalPositions = parseNumericCSV(posText);
    if (factorText) state.factorReturns = parseNumericCSV(factorText);
    if (fwText) state.forecastWeights = parseCSV(fwText);
    if (turnoverText) state.turnover = parseCSV(turnoverText);
    if (iwText) state.instrumentWeights = parseNumericCSV(iwText);
    if (rpText) state.roundedPositions = parseNumericCSV(rpText);

    if (registryText) {
      try {
        state.registry = parseSimpleYAML(registryText);
      } catch { state.registry = null; }
    }

    renderAll();
  } catch (e) {
    console.error('Data load error:', e);
    document.querySelector('.main').innerHTML = `
      <div class="card" style="text-align:center;padding:var(--space-2xl)">
        <h3 style="color:var(--forest)">Data Not Found</h3>
        <p style="margin-top:var(--space-md);color:var(--text-secondary)">
          Ensure a <code>data/</code> symlink exists pointing to a run directory.<br>
          Run: <code>python scripts/backtest_runner.py dashboard</code>
        </p>
      </div>`;
  }
}

function parseSimpleYAML(text) {
  try {
    return { raw: text };
  } catch { return null; }
}

// ── Render All ──
function renderAll() {
  renderHeader();
  renderKPIs();
  renderEquityCurve();
  renderDrawdown();
  renderRollingSR();
  renderAnnualReturns();
  renderConfig();
  renderFactorPnL();
  renderFactorTable();
  renderForecastWeights();
  renderPositionSummary();
  renderPositionTable();
  renderActivityTable();
  renderExposure();
  renderTurnover();
  renderRollingVol();
  renderAssetClass();
  renderWeightEvolution();
  renderInstrumentSelect();
  renderRunsTable();
  initPeriodSelector();
}

// ── Header ──
function renderHeader() {
  if (!state.meta) return;
  const m = state.meta.meta;
  document.getElementById('hm-capital').textContent = `$${(m.capital/1000).toFixed(0)}K`;
  document.getElementById('hm-period').textContent = m.period;
  document.getElementById('hm-instruments').textContent = m.instrument_count;
  document.getElementById('hm-mode').textContent = m.mode.toUpperCase();
}

// ── KPIs ──
function renderKPIs() {
  if (!state.meta) return;
  const s = state.meta.stats;
  const kpis = [
    { label: 'Net Sharpe', value: s.sharpe, fmt: v => v, cls: '', sub: `t-stat: ${s.t_stat} (stat. significance)` },
    { label: 'Ann Return', value: s.ann_mean, fmt: v => v + '%', cls: 'positive', sub: `Gross SR: ${(parseFloat(s.sharpe) + 0.089).toFixed(3)}` },
    { label: 'Ann Vol', value: s.ann_std, fmt: v => v + '%', cls: '', sub: `Target: 25%` },
    { label: 'Max Drawdown', value: s.min, fmt: v => v + '%', cls: 'negative', sub: `Avg DD: ${s.avg_drawdown}%` },
    { label: 'Sortino', value: s.sortino, fmt: v => v, cls: '', sub: `Downside risk adj. return` },
    { label: 'Calmar', value: s.calmar, fmt: v => v, cls: '', sub: `Return / Max DD` },
  ];

  document.getElementById('kpi-strip').innerHTML = kpis.map(k => `
    <div class="kpi">
      <div class="kpi__label">${k.label}</div>
      <div class="kpi__value ${k.cls}">${k.fmt(k.value)}</div>
      <div class="kpi__sub">${k.sub}</div>
    </div>
  `).join('');
}

// ── Equity Curve ──
function renderEquityCurve() {
  if (!state.rollingStats) return;

  const data = state.rollingStats.filter(r => !isNaN(r.cumulative_return_pct));
  const sampled = data.filter((_, i) => i % 5 === 0 || i === data.length - 1);
  const dates = sampled.map(r => r.index || r['']);
  const values = sampled.map(r => 100000 * (1 + r.cumulative_return_pct / 100));

  document.getElementById('ec-years').textContent = `${state.meta?.meta?.years || '—'} years`;

  destroyChart('chart-equity');
  state.charts['chart-equity'] = new Chart(document.getElementById('chart-equity'), {
    type: 'line',
    data: {
      labels: dates,
      datasets: [{
        label: 'Growth of $100K',
        data: values,
        borderColor: PALETTE.forest,
        backgroundColor: PALETTE.forest15,
        fill: true,
        borderWidth: 1.5,
        pointRadius: 0,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => '$' + ctx.raw.toLocaleString(undefined, { maximumFractionDigits: 0 }) } },
      },
      scales: {
        x: { grid: { color: PALETTE.gridLine }, ticks: { maxTicksLimit: 10, font: { size: 10 } } },
        y: {
          type: 'logarithmic',
          grid: { color: PALETTE.gridLine },
          ticks: {
            callback: v => {
              if (v >= 1e9) return '$' + (v/1e9).toFixed(0) + 'B';
              if (v >= 1e6) return '$' + (v/1e6).toFixed(0) + 'M';
              if (v >= 1e3) return '$' + (v/1e3).toFixed(0) + 'K';
              return '$' + v;
            }
          }
        }
      }
    }
  });
}

// ── Drawdown ──
function renderDrawdown() {
  if (!state.rollingStats) return;
  const data = state.rollingStats.filter(r => !isNaN(r.drawdown_pct));
  const sampled = data.filter((_, i) => i % 5 === 0);

  destroyChart('chart-drawdown');
  state.charts['chart-drawdown'] = new Chart(document.getElementById('chart-drawdown'), {
    type: 'line',
    data: {
      labels: sampled.map(r => r.index || r['']),
      datasets: [{
        label: 'Drawdown %',
        data: sampled.map(r => r.drawdown_pct),
        borderColor: PALETTE.charcoal70,
        backgroundColor: PALETTE.charcoal30 + '44',
        fill: true,
        borderWidth: 1,
        pointRadius: 0,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: PALETTE.gridLine }, ticks: { maxTicksLimit: 8, font: { size: 10 } } },
        y: { grid: { color: PALETTE.gridLine }, ticks: { callback: v => v.toFixed(0) + '%' } }
      }
    }
  });
}

// ── Rolling Sharpe ──
function renderRollingSR() {
  if (!state.rollingStats) return;
  const data = state.rollingStats.filter(r => !isNaN(r.sharpe_1Y));
  const sampled = data.filter((_, i) => i % 10 === 0);

  destroyChart('chart-rolling-sr');
  state.charts['chart-rolling-sr'] = new Chart(document.getElementById('chart-rolling-sr'), {
    type: 'line',
    data: {
      labels: sampled.map(r => r.index || r['']),
      datasets: [
        { label: '1Y SR', data: sampled.map(r => r.sharpe_1Y), borderColor: PALETTE.forest, borderWidth: 1.5, pointRadius: 0 },
        { label: '3Y SR', data: sampled.map(r => r.sharpe_3Y), borderColor: PALETTE.green, borderWidth: 1.5, pointRadius: 0 },
        { label: '5Y SR', data: sampled.map(r => r.sharpe_5Y), borderColor: '#C4B68A', borderWidth: 1.5, pointRadius: 0 },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top', align: 'end' } },
      scales: {
        x: { grid: { color: PALETTE.gridLine }, ticks: { maxTicksLimit: 8, font: { size: 10 } } },
        y: { grid: { color: PALETTE.gridLine } }
      }
    }
  });
}

// ── Annual Returns ──
function renderAnnualReturns() {
  if (!state.dailyReturns) return;

  const yearMap = {};
  const cols = Object.keys(state.dailyReturns[0]).filter(k => k !== 'index' && k !== '');
  state.dailyReturns.forEach(row => {
    const date = row.index || row[''];
    if (!date) return;
    const yr = date.substring(0, 4);
    if (!yearMap[yr]) yearMap[yr] = 0;
    let sum = 0;
    cols.forEach(c => { if (!isNaN(row[c])) sum += row[c]; });
    yearMap[yr] += sum;
  });

  const years = Object.keys(yearMap).sort();
  const returns = years.map(y => yearMap[y]);

  destroyChart('chart-annual');
  state.charts['chart-annual'] = new Chart(document.getElementById('chart-annual'), {
    type: 'bar',
    data: {
      labels: years,
      datasets: [{
        data: returns,
        backgroundColor: returns.map(r => r >= 0 ? PALETTE.green : PALETTE.charcoal50),
        borderRadius: 3,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 9 }, maxRotation: 90 } },
        y: { grid: { color: PALETTE.gridLine }, ticks: { callback: v => v.toFixed(0) + '%' } }
      }
    }
  });
}

// ── Config Panel ──
function renderConfig() {
  if (!state.meta) return;
  const m = state.meta.meta;
  const s = state.meta.stats;
  const items = [
    ['Capital', `$${(m.capital).toLocaleString()}`],
    ['Mode', m.mode],
    ['Vol Target', '25%'],
    ['Period', m.period],
    ['Years', m.years],
    ['Instruments', m.instrument_count],
    ['Trading Rules', '12 (5T + 3C + 3M + 1R)'],
    ['Gross Sharpe', (parseFloat(s.sharpe) + 0.089).toFixed(3)],
    ['Cost Drag', '-0.089 SR'],
    ['t-statistic', s.t_stat],
    ['p-value', s.p_value],
    ['Hit Rate', (parseFloat(s.hitrate)*100).toFixed(1) + '%'],
  ];
  document.getElementById('config-panel').innerHTML = items.map(([k,v]) =>
    `<div class="config-panel__row"><span class="config-panel__key">${k}</span><span class="config-panel__value">${v}</span></div>`
  ).join('');
}

// ── Factor P&L with Period Filter ──
function renderFactorPnL(period) {
  if (!state.factorReturns || state.factorReturns.length === 0) return;
  period = period || state.factorPeriod || 'all';

  const cols = Object.keys(state.factorReturns[0]).filter(k => k !== 'index' && k !== '');
  const groups = { Trend: [], Carry: [], 'CS Momentum': [], 'Rel Carry': [] };
  cols.forEach(c => {
    if (c.startsWith('relmomentum')) groups['CS Momentum'].push(c);
    else if (c === 'relcarry') groups['Rel Carry'].push(c);
    else if (c.startsWith('momentum')) groups.Trend.push(c);
    else if (c.startsWith('carry')) groups.Carry.push(c);
  });

  // Apply period filter
  let filtered = state.factorReturns;
  if (period !== 'all') {
    const lastDate = state.factorReturns[state.factorReturns.length - 1].index || state.factorReturns[state.factorReturns.length - 1][''];
    const lastYear = parseInt(lastDate.substring(0, 4));
    const lastMonth = parseInt(lastDate.substring(5, 7));
    let cutoff;
    if (period === 'ytd') {
      cutoff = `${lastYear}-01-01`;
    } else {
      const years = parseInt(period);
      cutoff = `${lastYear - years}-${String(lastMonth).padStart(2, '0')}-01`;
    }
    filtered = state.factorReturns.filter(r => {
      const d = r.index || r[''];
      return d >= cutoff;
    });
  }

  const sampled = filtered.filter((_, i) => i % Math.max(1, Math.floor(filtered.length / 500)) === 0);
  const dates = sampled.map(r => r.index || r['']);

  const datasets = [];
  const groupColors = {
    'Trend': PALETTE.forest,
    'Carry': PALETTE.green,
    'CS Momentum': '#C4B68A',
    'Rel Carry': PALETTE.charcoal50,
  };

  for (const [gName, gCols] of Object.entries(groups)) {
    if (gCols.length === 0) continue;
    let cum = 0;
    const cumData = sampled.map(row => {
      let sum = 0;
      gCols.forEach(c => { if (!isNaN(row[c])) sum += row[c]; });
      cum += sum;
      return cum;
    });
    datasets.push({
      label: gName,
      data: cumData,
      borderColor: groupColors[gName],
      backgroundColor: groupColors[gName] + '22',
      fill: true,
      borderWidth: 1.5,
      pointRadius: 0,
    });
  }

  destroyChart('chart-factor-pnl');
  state.charts['chart-factor-pnl'] = new Chart(document.getElementById('chart-factor-pnl'), {
    type: 'line',
    data: { labels: dates, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top', align: 'end' } },
      scales: {
        x: { grid: { color: PALETTE.gridLine }, ticks: { maxTicksLimit: 8, font: { size: 10 } } },
        y: { grid: { color: PALETTE.gridLine }, ticks: { callback: v => v.toFixed(0) + '%' } }
      }
    }
  });
}

function initPeriodSelector() {
  const btns = document.querySelectorAll('#factor-period-selector .period-btn');
  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      btns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.factorPeriod = btn.dataset.period;
      renderFactorPnL(btn.dataset.period);
    });
  });
}

// ── Factor Table ──
function renderFactorTable() {
  if (!state.factorReturns) return;
  const cols = Object.keys(state.factorReturns[0]).filter(k => k !== 'index' && k !== '');

  const stats = cols.map(c => {
    const vals = state.factorReturns.map(r => r[c]).filter(v => !isNaN(v));
    const mean = vals.reduce((a,b) => a+b, 0) / vals.length;
    const std = Math.sqrt(vals.reduce((a,b) => a + (b-mean)**2, 0) / vals.length);
    return {
      rule: c,
      annReturn: (mean * 256).toFixed(2),
      annVol: (std * Math.sqrt(256)).toFixed(2),
      sharpe: std > 0 ? ((mean * 256) / (std * Math.sqrt(256))).toFixed(3) : '0.000',
    };
  }).sort((a,b) => parseFloat(b.sharpe) - parseFloat(a.sharpe));

  const html = `<table>
    <thead><tr><th>Rule</th><th>Ann Return %</th><th>Ann Vol %</th><th>Sharpe</th></tr></thead>
    <tbody>${stats.map(s => `
      <tr>
        <td class="td-name">${s.rule}</td>
        <td class="${parseFloat(s.annReturn)>=0?'td-positive':'td-negative'}">${s.annReturn}</td>
        <td>${s.annVol}</td>
        <td class="${parseFloat(s.sharpe)>=0?'td-positive':'td-negative'}">${s.sharpe}</td>
      </tr>`).join('')}
    </tbody></table>`;
  document.getElementById('factor-table').innerHTML = html;
}

// ── Forecast Weights ──
function renderForecastWeights() {
  if (!state.forecastWeights || state.forecastWeights.length === 0) return;

  const rules = Object.keys(state.forecastWeights[0]).filter(k => k !== '' && k !== 'instrument');
  const instruments = state.forecastWeights.map(r => r[''] || r.instrument).slice(0, 15);

  const datasets = rules.map(rule => ({
    label: rule,
    data: state.forecastWeights.slice(0, 15).map(r => parseFloat(r[rule]) * 100 || 0),
    backgroundColor: FACTOR_COLORS[rule] || PALETTE.charcoal30,
    borderRadius: 2,
  }));

  destroyChart('chart-forecast-weights');
  state.charts['chart-forecast-weights'] = new Chart(document.getElementById('chart-forecast-weights'), {
    type: 'bar',
    data: { labels: instruments, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top', labels: { font: { size: 9 } } } },
      scales: {
        x: { stacked: true, grid: { display: false }, ticks: { font: { size: 9 } } },
        y: { stacked: true, max: 100, grid: { color: PALETTE.gridLine }, ticks: { callback: v => v + '%' } }
      }
    }
  });
}

// ── Position Summary Strip ──
function renderPositionSummary() {
  if (!state.positionSnapshot) return;
  const rows = state.positionSnapshot;
  const capital = state.meta?.meta?.capital || 200000;

  let longCount = 0, shortCount = 0, flatCount = 0;
  let grossLong = 0, grossShort = 0;

  rows.forEach(r => {
    const contracts = parseInt(r['Rounded (Contracts)'] || '0');
    const expNav = parseFloat(r['Exposure (% NAV)'] || '0');
    if (contracts > 0) { longCount++; grossLong += Math.abs(expNav); }
    else if (contracts < 0) { shortCount++; grossShort += Math.abs(expNav); }
    else flatCount++;
  });

  const netExp = grossLong - grossShort;
  const grossExp = grossLong + grossShort;

  const strip = [
    { label: 'Long', value: longCount, sub: `${grossLong.toFixed(1)}% NAV` },
    { label: 'Short', value: shortCount, sub: `${grossShort.toFixed(1)}% NAV` },
    { label: 'Flat', value: flatCount, sub: 'No position' },
    { label: 'Net Exposure', value: `${netExp >= 0 ? '+' : ''}${netExp.toFixed(1)}%`, sub: 'Long - Short' },
    { label: 'Gross Exposure', value: `${grossExp.toFixed(1)}%`, sub: '|Long| + |Short|' },
  ];

  document.getElementById('position-summary').innerHTML = strip.map(s => `
    <div class="kpi">
      <div class="kpi__label">${s.label}</div>
      <div class="kpi__value" style="font-size:24px">${s.value}</div>
      <div class="kpi__sub">${s.sub}</div>
    </div>
  `).join('');
}

// ── Position Table (Bloomberg-level) ──
function renderPositionTable() {
  if (!state.positionSnapshot) return;

  // Check if new columns exist
  const hasAC = state.positionSnapshot[0]?.['Asset Class'] !== undefined;
  const hasExpNav = state.positionSnapshot[0]?.['Exposure (% NAV)'] !== undefined;

  // Split active vs flat
  const active = [];
  const flat = [];
  state.positionSnapshot.forEach(r => {
    const contracts = parseInt(r['Rounded (Contracts)'] || '0');
    if (contracts !== 0) active.push(r);
    else flat.push(r);
  });

  // Sort active by |Exposure| desc
  active.sort((a, b) => Math.abs(parseFloat(b['Exposure (% NAV)'] || b['Avg |Position|'] || '0')) - Math.abs(parseFloat(a['Exposure (% NAV)'] || a['Avg |Position|'] || '0')));

  function acBadge(ac) {
    const cls = (ac || '').toLowerCase().replace(/\s+/g, '-');
    return `<span class="ac-badge ac-badge--${cls}">${ac || '—'}</span>`;
  }

  function dirBadge(dir) {
    const cls = (dir || 'flat').toLowerCase();
    const icon = cls === 'long' ? '▲' : cls === 'short' ? '▼' : '—';
    return `<span class="dir-badge dir-badge--${cls}">${icon} ${dir}</span>`;
  }

  function buildRow(r) {
    const notional = parseFloat(r['Notional Position'] || '0');
    const contracts = parseInt(r['Rounded (Contracts)'] || '0');
    const contractVal = parseFloat(r['Contract Value ($)'] || '0');
    const expNav = parseFloat(r['Exposure (% NAV)'] || '0');
    const direction = r['Direction'] || (contracts > 0 ? 'Long' : contracts < 0 ? 'Short' : 'Flat');

    return `<tr>
      ${hasAC ? `<td>${acBadge(r['Asset Class'])}</td>` : ''}
      <td class="td-name">${r.Instrument}</td>
      <td>${dirBadge(direction)}</td>
      <td style="font-weight:600;text-align:center">${contracts}</td>
      ${hasExpNav ? `<td class="${expNav>=0?'td-positive':'td-negative'}" style="text-align:right">${expNav.toFixed(1)}%</td>` : ''}
      ${hasExpNav ? `<td style="text-align:right;font-size:11px">${contractVal > 0 ? '$'+contractVal.toLocaleString(undefined,{maximumFractionDigits:0}) : '—'}</td>` : ''}
      <td class="${notional>=0?'td-positive':'td-negative'}" style="text-align:right">${notional.toFixed(2)}</td>
      <td style="text-align:right">${parseFloat(r['Avg |Position|'] || '0').toFixed(2)}</td>
      <td style="text-align:right">${(parseFloat(r['Instrument Weight'] || '0')*100).toFixed(1)}%</td>
      <td style="font-size:11px">${(r['Last Date']||'').substring(0,10)}</td>
    </tr>`;
  }

  const headers = `<tr>
    ${hasAC ? '<th>Class</th>' : ''}
    <th>Instrument</th>
    <th>Direction</th>
    <th style="text-align:center">Contracts</th>
    ${hasExpNav ? '<th style="text-align:right">Exposure (% NAV)</th>' : ''}
    ${hasExpNav ? '<th style="text-align:right">Contract $</th>' : ''}
    <th style="text-align:right">Notional (Optimal)</th>
    <th style="text-align:right">Avg |Pos| (full period)</th>
    <th style="text-align:right">Weight</th>
    <th>Data Through</th>
  </tr>`;

  let html = `<table>
    <thead>${headers}</thead>
    <tbody>${active.map(buildRow).join('')}</tbody>
  </table>`;

  // Flat positions collapsible
  if (flat.length > 0) {
    html += `<div class="flat-section">
      <button class="flat-toggle" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'; this.textContent=this.textContent.includes('Show')?'▾ Hide ${flat.length} Flat Positions':'▸ Show ${flat.length} Flat Positions'">▸ Show ${flat.length} Flat Positions</button>
      <div style="display:none">
        <table>
          <thead>${headers}</thead>
          <tbody>${flat.map(buildRow).join('')}</tbody>
        </table>
      </div>
    </div>`;
  }

  document.getElementById('position-table').innerHTML = html;
}

// ── Historical Activity Table (Interactive) ──
function renderActivityTable() {
  if (!state.roundedPositions || state.roundedPositions.length === 0) return;
  const cols = Object.keys(state.roundedPositions[0]).filter(k => k !== 'index' && k !== '');

  const stats = cols.map(inst => {
    let nonZero = 0, total = 0, maxPos = 0;
    state.roundedPositions.forEach(row => {
      const v = row[inst];
      if (isNaN(v)) return;
      total++;
      if (Math.abs(v) > 0) nonZero++;
      if (Math.abs(v) > maxPos) maxPos = Math.abs(v);
    });
    const pct = total > 0 ? (nonZero / total * 100) : 0;
    let badge = '';
    if (pct >= 80) badge = '<span style="color:var(--forest);font-weight:600">● Active</span>';
    else if (pct >= 30) badge = '<span style="color:#C4B68A;font-weight:600">● Moderate</span>';
    else badge = '<span style="color:#B85C4A;font-weight:600">● Low</span>';
    return { inst, nonZero, total, pct, maxPos: Math.round(maxPos), badge };
  }).sort((a, b) => b.pct - a.pct);

  const html = `<table>
    <thead><tr>
      <th>Instrument</th>
      <th>Trading Days</th>
      <th>Active %</th>
      <th style="text-align:center">Max Contracts</th>
      <th>Status <span class="info-tip" title="Active (≥80%): Position held for ≥80% of the backtest period. Moderate (30-80%): Intermittent participation. Low (<30%): Rarely had a position.">ⓘ</span></th>
    </tr></thead>
    <tbody>${stats.map(s => `<tr class="clickable-row" onclick="navigateToInstrument('${s.inst}')">
      <td class="td-name">${s.inst}</td>
      <td>${s.nonZero.toLocaleString()} / ${s.total.toLocaleString()}</td>
      <td><div style="display:flex;align-items:center;gap:8px"><div style="width:60px;height:6px;border-radius:3px;background:var(--bg-tertiary, #e8e0cc);overflow:hidden"><div style="width:${Math.min(s.pct,100)}%;height:100%;background:var(--forest);border-radius:3px"></div></div>${s.pct.toFixed(1)}%</div></td>
      <td style="text-align:center;font-weight:600">${s.maxPos}</td>
      <td>${s.badge}</td>
    </tr>`).join('')}</tbody></table>`;
  document.getElementById('activity-table').innerHTML = html;
}

// Navigate to Instrument Deep-Dive from Activity table click
function navigateToInstrument(inst) {
  // Switch to instrument tab
  document.querySelectorAll('.tab-nav__item').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));

  const instTab = document.querySelector('[data-tab="instrument"]');
  instTab.classList.add('active');
  document.getElementById('tab-instrument').classList.add('active');

  // Select the instrument
  const select = document.getElementById('instrument-select');
  select.value = inst;
  select.dispatchEvent(new Event('change'));
}

// ── Exposure (NAV %) ──
function renderExposure() {
  if (!state.notionalPositions) return;
  const cols = Object.keys(state.notionalPositions[0]).filter(k => k !== 'index' && k !== '');
  const sampled = state.notionalPositions.filter((_, i) => i % 20 === 0);
  const capital = state.meta?.meta?.capital || 200000;

  // Try to get contract values from snapshot
  const contractValues = {};
  if (state.positionSnapshot) {
    state.positionSnapshot.forEach(r => {
      const cv = parseFloat(r['Contract Value ($)'] || '0');
      if (cv > 0) contractValues[r.Instrument] = cv;
    });
  }

  const hasContractValues = Object.keys(contractValues).length > 0;

  const longData = sampled.map(row => {
    let sum = 0;
    cols.forEach(c => {
      const v = row[c];
      if (!isNaN(v) && v > 0) {
        if (hasContractValues && contractValues[c]) {
          sum += (v * contractValues[c] / capital * 100);
        } else {
          sum += v; // Fallback to contracts
        }
      }
    });
    return sum;
  });

  const shortData = sampled.map(row => {
    let sum = 0;
    cols.forEach(c => {
      const v = row[c];
      if (!isNaN(v) && v < 0) {
        if (hasContractValues && contractValues[c]) {
          sum += (v * contractValues[c] / capital * 100);
        } else {
          sum += v;
        }
      }
    });
    return sum;
  });

  const yLabel = hasContractValues ? '% of NAV' : 'Contracts';

  destroyChart('chart-exposure');
  state.charts['chart-exposure'] = new Chart(document.getElementById('chart-exposure'), {
    type: 'line',
    data: {
      labels: sampled.map(r => r.index || r['']),
      datasets: [
        { label: 'Long', data: longData, borderColor: PALETTE.green, backgroundColor: PALETTE.greenLight, fill: true, borderWidth: 1, pointRadius: 0 },
        { label: 'Short', data: shortData, borderColor: PALETTE.charcoal70, backgroundColor: PALETTE.charcoal30 + '44', fill: true, borderWidth: 1, pointRadius: 0 },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top', align: 'end' },
        tooltip: {
          callbacks: {
            label: ctx => `${ctx.dataset.label}: ${ctx.raw.toFixed(1)}${hasContractValues ? '%' : ''}`
          }
        }
      },
      scales: {
        x: { grid: { color: PALETTE.gridLine }, ticks: { maxTicksLimit: 8, font: { size: 10 } } },
        y: { grid: { color: PALETTE.gridLine }, title: { display: true, text: yLabel } }
      }
    }
  });
}

// ── Turnover ──
function renderTurnover() {
  if (!state.turnover) return;
  const sorted = [...state.turnover].sort((a,b) => parseFloat(b.annualized_turnover) - parseFloat(a.annualized_turnover)).slice(0, 20);

  destroyChart('chart-turnover');
  state.charts['chart-turnover'] = new Chart(document.getElementById('chart-turnover'), {
    type: 'bar',
    data: {
      labels: sorted.map(r => r.instrument),
      datasets: [{
        data: sorted.map(r => parseFloat(r.annualized_turnover)),
        backgroundColor: PALETTE.forest50,
        borderColor: PALETTE.forest,
        borderWidth: 1,
        borderRadius: 3,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: PALETTE.gridLine }, title: { display: true, text: 'Full-Position Turnovers / Year' } },
        y: { grid: { display: false }, ticks: { font: { size: 9 } } }
      }
    }
  });
}

// ── Rolling Volatility ──
function renderRollingVol() {
  if (!state.rollingStats) return;
  const data = state.rollingStats.filter(r => !isNaN(r.ann_vol_1Y));
  const sampled = data.filter((_, i) => i % 10 === 0);

  destroyChart('chart-rolling-vol');
  state.charts['chart-rolling-vol'] = new Chart(document.getElementById('chart-rolling-vol'), {
    type: 'line',
    data: {
      labels: sampled.map(r => r.index || r['']),
      datasets: [
        { label: 'Realized 1Y Vol', data: sampled.map(r => r.ann_vol_1Y), borderColor: PALETTE.forest, borderWidth: 1.5, pointRadius: 0 },
        { label: 'Target (25%)', data: sampled.map(() => 25), borderColor: PALETTE.charcoal30, borderWidth: 1, borderDash: [5,5], pointRadius: 0 },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top', align: 'end' } },
      scales: {
        x: { grid: { color: PALETTE.gridLine }, ticks: { maxTicksLimit: 8 } },
        y: { grid: { color: PALETTE.gridLine }, ticks: { callback: v => v + '%' } }
      }
    }
  });
}

// ── Asset Class Exposure ──
function renderAssetClass() {
  if (!state.positionSnapshot) return;
  const acWeights = {};
  for (const [ac, insts] of Object.entries(ASSET_CLASSES)) {
    acWeights[ac] = 0;
    insts.forEach(inst => {
      const row = state.positionSnapshot.find(r => r.Instrument === inst);
      if (row) acWeights[ac] += parseFloat(row['Instrument Weight']) || 0;
    });
  }

  destroyChart('chart-asset-class');
  state.charts['chart-asset-class'] = new Chart(document.getElementById('chart-asset-class'), {
    type: 'doughnut',
    data: {
      labels: Object.keys(acWeights),
      datasets: [{
        data: Object.values(acWeights).map(v => (v*100).toFixed(1)),
        backgroundColor: Object.keys(acWeights).map(ac => AC_COLORS[ac] || PALETTE.charcoal30),
        borderWidth: 2,
        borderColor: '#FFFFFF',
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'right', labels: { font: { size: 11 } } },
        tooltip: { callbacks: { label: ctx => `${ctx.label}: ${ctx.raw}%` } }
      }
    }
  });
}

// ── Weight Evolution ──
function renderWeightEvolution() {
  if (!state.instrumentWeights || state.instrumentWeights.length === 0) return;
  const cols = Object.keys(state.instrumentWeights[0]).filter(k => k !== 'index' && k !== '');

  const lastRow = state.instrumentWeights[state.instrumentWeights.length - 1];
  const sorted = cols.sort((a,b) => (lastRow[b]||0) - (lastRow[a]||0)).slice(0, 10);
  const sampled = state.instrumentWeights.filter((_, i) => i % 50 === 0);

  const datasets = sorted.map((col, idx) => ({
    label: col,
    data: sampled.map(r => (r[col] || 0) * 100),
    borderColor: Object.values(FACTOR_COLORS)[idx % 12],
    borderWidth: 1.5,
    pointRadius: 0,
    fill: false,
  }));

  destroyChart('chart-weight-evolution');
  state.charts['chart-weight-evolution'] = new Chart(document.getElementById('chart-weight-evolution'), {
    type: 'line',
    data: { labels: sampled.map(r => r.index || r['']), datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top', labels: { font: { size: 9 } } } },
      scales: {
        x: { grid: { color: PALETTE.gridLine }, ticks: { maxTicksLimit: 8, font: { size: 10 } } },
        y: { grid: { color: PALETTE.gridLine }, ticks: { callback: v => v.toFixed(0) + '%' } }
      }
    }
  });
}

// ── Instrument Deep-Dive ──
function renderInstrumentSelect() {
  if (!state.meta) return;
  const select = document.getElementById('instrument-select');
  state.meta.instruments.sort().forEach(inst => {
    const opt = document.createElement('option');
    opt.value = inst;
    opt.textContent = inst;
    select.appendChild(opt);
  });

  select.addEventListener('change', () => {
    const inst = select.value;
    if (!inst) { document.getElementById('instrument-detail').style.display = 'none'; return; }
    document.getElementById('instrument-detail').style.display = 'block';
    renderInstrumentDetail(inst);
  });
}

function renderInstrumentDetail(inst) {
  if (!state.dailyReturns) return;

  const vals = state.dailyReturns.map(r => r[inst]).filter(v => !isNaN(v));
  const mean = vals.reduce((a,b) => a+b, 0) / vals.length;
  const std = Math.sqrt(vals.reduce((a,b) => a + (b-mean)**2, 0) / vals.length);
  const annReturn = mean * 256;
  const annVol = std * Math.sqrt(256);
  const sr = annVol > 0 ? annReturn / annVol : 0;

  const snapshot = state.positionSnapshot?.find(r => r.Instrument === inst);
  const weight = snapshot ? (parseFloat(snapshot['Instrument Weight'])*100).toFixed(1) + '%' : '—';
  const contracts = snapshot ? snapshot['Rounded (Contracts)'] : '—';
  const ac = snapshot?.['Asset Class'] || '—';

  document.getElementById('inst-kpis').innerHTML = [
    { label: 'Sharpe', value: sr.toFixed(3) },
    { label: 'Ann Return', value: annReturn.toFixed(2) + '%' },
    { label: 'Weight', value: weight },
    { label: 'Contracts', value: contracts },
  ].map(k => `<div class="kpi"><div class="kpi__label">${k.label}</div><div class="kpi__value">${k.value}</div></div>`).join('');

  const dates = state.dailyReturns.map(r => r.index || r['']);
  let cum = 0;
  const cumData = state.dailyReturns.map(r => { const v = r[inst]; if (!isNaN(v)) cum += v; return cum; });
  const sampled = dates.map((d, i) => ({ d, v: cumData[i] })).filter((_, i) => i % 5 === 0);

  destroyChart('chart-inst-equity');
  state.charts['chart-inst-equity'] = new Chart(document.getElementById('chart-inst-equity'), {
    type: 'line',
    data: {
      labels: sampled.map(r => r.d),
      datasets: [{ data: sampled.map(r => r.v), borderColor: PALETTE.forest, borderWidth: 1.5, pointRadius: 0, fill: { target: 'origin', above: PALETTE.forest15, below: PALETTE.charcoal30 + '22' } }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: PALETTE.gridLine }, ticks: { maxTicksLimit: 6 } },
        y: { grid: { color: PALETTE.gridLine }, ticks: { callback: v => v.toFixed(0) + '%' } }
      }
    }
  });

  if (state.notionalPositions) {
    const posData = state.notionalPositions.map(r => r[inst]).filter(v => !isNaN(v));
    const posDates = state.notionalPositions.filter(r => !isNaN(r[inst])).map(r => r.index || r['']);
    const posSampled = posDates.map((d, i) => ({ d, v: posData[i] })).filter((_, i) => i % 5 === 0);

    destroyChart('chart-inst-position');
    state.charts['chart-inst-position'] = new Chart(document.getElementById('chart-inst-position'), {
      type: 'line',
      data: {
        labels: posSampled.map(r => r.d),
        datasets: [{ data: posSampled.map(r => r.v), borderColor: PALETTE.green, borderWidth: 1, pointRadius: 0, fill: { target: 'origin', above: PALETTE.greenLight, below: PALETTE.charcoal30 + '22' } }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: PALETTE.gridLine }, ticks: { maxTicksLimit: 6 } },
          y: { grid: { color: PALETTE.gridLine }, title: { display: true, text: 'Contracts' } }
        }
      }
    });
  }
}

// ── Run Comparison Table ──
function renderRunsTable() {
  const el = document.getElementById('runs-table');
  fetch('data/registry.yaml').then(r => r.ok ? r.text() : null).catch(() => null).then(text => {
    if (!text) {
      fetch('../../../results/runs/registry.yaml').then(r => r.ok ? r.text() : null).catch(() => null).then(text2 => {
        if (!text2) {
          el.innerHTML = '<p style="color:var(--text-muted);padding:var(--space-md)">No registry found. Run backtests with <code>backtest_runner.py</code> to populate.</p>';
          return;
        }
        buildRunsTable(el, text2);
      });
      return;
    }
    buildRunsTable(el, text);
  });
}

function buildRunsTable(el, yamlText) {
  const lines = yamlText.split('\n');
  const runs = [];
  let current = null;

  for (const line of lines) {
    if (line.match(/^\s*- id:/)) {
      if (current) runs.push(current);
      current = { id: line.split(':').slice(1).join(':').trim().replace(/['"]/g, '') };
    } else if (current && line.match(/^\s+\w+:/)) {
      const m = line.match(/^\s+(\w+):\s*(.*)$/);
      if (m) {
        const key = m[1].trim();
        const val = m[2].trim().replace(/['"]/g, '');
        if (['label','timestamp'].includes(key)) current[key] = val;
        else if (['net_sharpe','ann_return','ann_vol','max_dd','sortino','capital','vol_target','instruments'].includes(key)) {
          current[key] = val;
        } else if (key === 'period') current[key] = val;
        else if (key === 'mode') current[key] = val;
      }
    }
  }
  if (current) runs.push(current);

  if (runs.length === 0) {
    el.innerHTML = '<p style="color:var(--text-muted);padding:var(--space-md)">Registry is empty.</p>';
    return;
  }

  el.innerHTML = `<table>
    <thead><tr><th>Run ID</th><th>Label</th><th>Sharpe</th><th>Return %</th><th>Vol %</th><th>Max DD %</th><th>Sortino</th><th>#Inst</th><th>Mode</th></tr></thead>
    <tbody>${runs.map(r => `
      <tr>
        <td class="td-name" style="font-family:var(--font-mono);font-size:11px">${r.id || '—'}</td>
        <td class="td-name">${r.label || '—'}</td>
        <td class="td-positive">${r.net_sharpe || '—'}</td>
        <td>${r.ann_return || '—'}</td>
        <td>${r.ann_vol || '—'}</td>
        <td class="td-negative">${r.max_dd || '—'}</td>
        <td>${r.sortino || '—'}</td>
        <td>${r.instruments || '—'}</td>
        <td>${r.mode || '—'}</td>
      </tr>`).join('')}
    </tbody></table>`;
}

// ── Helpers ──
function destroyChart(id) {
  if (state.charts[id]) { state.charts[id].destroy(); delete state.charts[id]; }
}

// ── Tab Navigation ──
document.querySelectorAll('.tab-nav__item').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab-nav__item').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');
  });
});

// ── Init ──
loadData();
