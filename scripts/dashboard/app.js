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
  'Equity':       ['SP500_micro','NASDAQ_micro','DAX','NIKKEI','FTSE100'],
  'Fixed Income': ['US10','US5','BUND','GILT','JGB'],
  'Metals':       ['GOLD_micro','SILVER','COPPER-micro'],
  'Energy':       ['CRUDE_W','BRENT-LAST'],
  'FX':           ['AUD_micro'],
};

const AC_COLORS = {
  'Equity':       PALETTE.forest,
  'Fixed Income': PALETTE.green,
  'Metals':       PALETTE.charcoal70,
  'Energy':       '#42A47C',
  'FX':           '#C4B68A',
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
  instrumentWeights: null,
  turnover: null,
  registry: null,
  charts: {},
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
    // Load all data files in parallel
    const [metaText, rollingText, returnsText, snapshotText, posText] = await Promise.all([
      loadFile('data/dashboard_meta.json').catch(() => null),
      loadFile('data/rolling_stats.csv').catch(() => null),
      loadFile('data/daily_returns.csv').catch(() => null),
      loadFile('data/position_snapshot.csv').catch(() => null),
      loadFile('data/notional_positions.csv').catch(() => null),
    ]);

    const [factorText, fwText, turnoverText, iwText, registryText] = await Promise.all([
      loadFile('data/factor_returns.csv').catch(() => null),
      loadFile('data/forecast_weights.csv').catch(() => null),
      loadFile('data/turnover.csv').catch(() => null),
      loadFile('data/instrument_weights.csv').catch(() => null),
      loadFile('../../../results/runs/registry.yaml').catch(() => loadFile('data/registry.yaml').catch(() => null)),
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

    if (registryText) {
      // Simple YAML parser for registry (flat structure)
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
  // Minimal YAML parser for the registry (handles our known format)
  // Returns the registry structure
  try {
    // Just store raw text; we'll parse runs from the table instead
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
  renderPositionTable();
  renderExposure();
  renderTurnover();
  renderRollingVol();
  renderAssetClass();
  renderWeightEvolution();
  renderInstrumentSelect();
  renderRunsTable();
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
    { label: 'Net Sharpe', value: s.sharpe, fmt: v => v, cls: '' },
    { label: 'Ann Return', value: s.ann_mean, fmt: v => v + '%', cls: 'positive' },
    { label: 'Ann Vol', value: s.ann_std, fmt: v => v + '%', cls: '' },
    { label: 'Max Drawdown', value: s.min, fmt: v => v + '%', cls: 'negative' },
    { label: 'Sortino', value: s.sortino, fmt: v => v, cls: '' },
    { label: 'Calmar', value: s.calmar, fmt: v => v, cls: '' },
  ];

  document.getElementById('kpi-strip').innerHTML = kpis.map(k => `
    <div class="kpi">
      <div class="kpi__label">${k.label}</div>
      <div class="kpi__value ${k.cls}">${k.fmt(k.value)}</div>
      <div class="kpi__sub">${k.label === 'Net Sharpe' ? `t-stat: ${s.t_stat}` : k.label === 'Ann Return' ? `Gross SR: ${(parseFloat(s.sharpe) + 0.089).toFixed(3)}` : k.label === 'Max Drawdown' ? `Avg DD: ${s.avg_drawdown}%` : k.label === 'Ann Vol' ? `Target: 25%` : k.label === 'Sortino' ? `Skew: ${s.skew}` : `Hit: ${(parseFloat(s.hitrate)*100).toFixed(1)}%`}</div>
    </div>
  `).join('');
}

// ── Equity Curve ──
function renderEquityCurve() {
  if (!state.rollingStats) return;

  const data = state.rollingStats.filter(r => !isNaN(r.cumulative_return_pct));
  // Sample every 5th point for performance
  const sampled = data.filter((_, i) => i % 5 === 0 || i === data.length - 1);
  const dates = sampled.map(r => r.index || r['']);
  // Convert cumulative_return_pct to growth of $100K (log scale)
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

  // Compute annual returns
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

// ── Factor P&L ──
function renderFactorPnL() {
  if (!state.factorReturns || state.factorReturns.length === 0) return;

  const cols = Object.keys(state.factorReturns[0]).filter(k => k !== 'index' && k !== '');
  // Aggregate into 4 factor groups
  const groups = { Trend: [], Carry: [], 'CS Momentum': [], 'Rel Carry': [] };
  cols.forEach(c => {
    if (c.startsWith('relmomentum')) groups['CS Momentum'].push(c);
    else if (c === 'relcarry') groups['Rel Carry'].push(c);
    else if (c.startsWith('momentum')) groups.Trend.push(c);
    else if (c.startsWith('carry')) groups.Carry.push(c);
  });

  const sampled = state.factorReturns.filter((_, i) => i % 10 === 0);
  const dates = sampled.map(r => r.index || r['']);

  // Compute cumulative for each group
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

// ── Position Table ──
function renderPositionTable() {
  if (!state.positionSnapshot) return;
  const rows = state.positionSnapshot.sort((a,b) => Math.abs(parseFloat(b['Avg |Position|'])) - Math.abs(parseFloat(a['Avg |Position|'])));

  const html = `<table>
    <thead><tr><th>Instrument</th><th>Last Date</th><th>Notional</th><th>Contracts</th><th>Avg |Pos|</th><th>Weight</th></tr></thead>
    <tbody>${rows.map(r => {
      const notional = parseFloat(r['Notional Position']);
      return `<tr>
        <td class="td-name">${r.Instrument}</td>
        <td>${(r['Last Date']||'').substring(0,10)}</td>
        <td class="${notional>=0?'td-positive':'td-negative'}">${notional.toFixed(2)}</td>
        <td style="font-weight:600">${r['Rounded (Contracts)']}</td>
        <td>${parseFloat(r['Avg |Position|']).toFixed(2)}</td>
        <td>${(parseFloat(r['Instrument Weight'])*100).toFixed(1)}%</td>
      </tr>`;
    }).join('')}</tbody></table>`;
  document.getElementById('position-table').innerHTML = html;
}

// ── Exposure ──
function renderExposure() {
  if (!state.notionalPositions) return;
  const cols = Object.keys(state.notionalPositions[0]).filter(k => k !== 'index' && k !== '');
  const sampled = state.notionalPositions.filter((_, i) => i % 20 === 0);

  const longData = sampled.map(row => {
    let sum = 0;
    cols.forEach(c => { const v = row[c]; if (!isNaN(v) && v > 0) sum += v; });
    return sum;
  });
  const shortData = sampled.map(row => {
    let sum = 0;
    cols.forEach(c => { const v = row[c]; if (!isNaN(v) && v < 0) sum += v; });
    return sum;
  });

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
      plugins: { legend: { position: 'top', align: 'end' } },
      scales: {
        x: { grid: { color: PALETTE.gridLine }, ticks: { maxTicksLimit: 8, font: { size: 10 } } },
        y: { grid: { color: PALETTE.gridLine }, title: { display: true, text: 'Contracts' } }
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
        x: { grid: { color: PALETTE.gridLine }, title: { display: true, text: 'Annual Turnover' } },
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

  // Top 10 by latest weight
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

  // Compute instrument stats
  const vals = state.dailyReturns.map(r => r[inst]).filter(v => !isNaN(v));
  const mean = vals.reduce((a,b) => a+b, 0) / vals.length;
  const std = Math.sqrt(vals.reduce((a,b) => a + (b-mean)**2, 0) / vals.length);
  const annReturn = mean * 256;
  const annVol = std * Math.sqrt(256);
  const sr = annVol > 0 ? annReturn / annVol : 0;

  const snapshot = state.positionSnapshot?.find(r => r.Instrument === inst);
  const weight = snapshot ? (parseFloat(snapshot['Instrument Weight'])*100).toFixed(1) + '%' : '—';
  const contracts = snapshot ? snapshot['Rounded (Contracts)'] : '—';

  document.getElementById('inst-kpis').innerHTML = [
    { label: 'Sharpe', value: sr.toFixed(3) },
    { label: 'Ann Return', value: annReturn.toFixed(2) + '%' },
    { label: 'Weight', value: weight },
    { label: 'Contracts', value: contracts },
  ].map(k => `<div class="kpi"><div class="kpi__label">${k.label}</div><div class="kpi__value">${k.value}</div></div>`).join('');

  // Equity curve
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

  // Position history
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
  // Try to load registry
  fetch('data/registry.yaml').then(r => r.ok ? r.text() : null).catch(() => null).then(text => {
    if (!text) {
      // Try loading from runs directory
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
  // Very simple YAML parser for our known structure
  // Extract run blocks
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
