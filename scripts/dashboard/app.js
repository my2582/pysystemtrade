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
  contractValues: null,
  spreadCosts: null,
  methodology: null,
  charts: {},
  factorPeriod: 'all',
  positionSort: { col: 'Exposure (% NAV)', asc: false },
  selectedInstrument: null,
  instPeriod: 'all',
  sweepData: null,
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

    const [cvText, scText, methText, sweepText] = await Promise.all([
      loadFile('data/contract_values.csv').catch(() => null),
      loadFile('data/spread_costs.csv').catch(() => null),
      loadFile('data/methodology.json').catch(() => null),
      loadFile('sweep_summary.json').catch(() => null),
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
    if (cvText) state.contractValues = parseNumericCSV(cvText);
    if (scText) state.spreadCosts = parseCSV(scText);
    if (methText) state.methodology = JSON.parse(methText);
    if (sweepText) { try { state.sweepData = JSON.parse(sweepText); } catch {} }

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
  renderMethodology();
  renderRollingVol();
  renderAssetClass();
  renderWeightEvolution();
  renderInstrumentSelect();
  renderRunsTable();
  initPeriodSelector();
  renderSweep();
}

// ── Header ──
function renderHeader() {
  if (!state.meta) return;
  const m = state.meta.meta;
  document.getElementById('hm-capital').textContent = `$${(m.capital/1000).toFixed(0)}K`;
  document.getElementById('hm-period').textContent = m.period;
  document.getElementById('hm-instruments').textContent = m.instrument_count;
  document.getElementById('hm-mode').textContent = m.mode.toUpperCase();

  // Executability-aware banner
  const banner = document.getElementById('sim-banner');
  const exec = state.meta.executability;
  if (exec) {
    const { grade, score, tradeable_count, total_count, untradeable_instruments } = exec;
    if (grade === 'THEORETICAL') {
      banner.style.background = '#B85C4A';
      banner.style.color = '#fff';
      banner.innerHTML = `🚫 THEORETICAL BACKTEST — ${total_count - tradeable_count}/${total_count} instruments untradeable (Executability: ${score}%). Results NOT achievable in practice.`;
    } else if (grade === 'RESEARCH') {
      banner.style.background = '#C4A24A';
      banner.style.color = '#232220';
      banner.innerHTML = `⚠ RESEARCH ONLY — Executability ${score}% (${tradeable_count}/${total_count} tradeable). Some results may not be replicable.`;
    } else {
      banner.style.background = '#265844';
      banner.style.color = '#F5E8C1';
      banner.innerHTML = `✅ PRODUCTION GRADE — Executability ${score}% (${tradeable_count}/${total_count} tradeable). Simulated backtest, not live results.`;
    }
  }
}

// ── KPIs ──
function renderKPIs() {
  if (!state.meta) return;
  const s = state.meta.stats;
  const exec = state.meta.executability;
  const isTheoretical = exec && exec.grade === 'THEORETICAL';
  const strikeStyle = isTheoretical ? 'text-decoration:line-through;opacity:0.5' : '';
  // Compute true Max Drawdown from rolling stats (peak-to-trough)
  let trueMDD = s.min; // fallback to worst day
  if (state.rollingStats) {
    const ddValues = state.rollingStats.map(r => r.drawdown_pct).filter(v => !isNaN(v));
    if (ddValues.length > 0) trueMDD = Math.min(...ddValues).toFixed(2);
  }
  const trueCalmar = (parseFloat(s.ann_mean) / Math.abs(parseFloat(trueMDD))).toFixed(4);
  const kpis = [
    { label: 'Net Sharpe', value: s.sharpe, fmt: v => v, cls: '', sub: `t-stat: ${s.t_stat} (stat. significance)` },
    { label: 'Ann Return', value: s.ann_mean, fmt: v => v + '%', cls: 'positive', sub: `Gross SR: ${(parseFloat(s.sharpe) + 0.089).toFixed(3)}` },
    { label: 'Ann Vol', value: s.ann_std, fmt: v => v + '%', cls: '', sub: `Target: 25%` },
    { label: 'Max Drawdown', value: trueMDD, fmt: v => v + '%', cls: 'negative', sub: `Avg DD: ${s.avg_drawdown}% · Worst Day: ${s.min}%` },
    { label: 'Sortino', value: s.sortino, fmt: v => v, cls: '', sub: `Downside risk adj. return` },
    { label: 'Calmar', value: trueCalmar, fmt: v => v, cls: '', sub: `Return / Max DD` },
  ];

  const warningBadge = isTheoretical ? '<div style="color:#B85C4A;font-size:10px;font-weight:700;margin-top:4px">⚠ THEORETICAL</div>' : '';
  document.getElementById('kpi-strip').innerHTML = kpis.map(k => `
    <div class="kpi">
      <div class="kpi__label">${k.label}</div>
      <div class="kpi__value ${k.cls}" style="${strikeStyle}">${k.fmt(k.value)}</div>
      <div class="kpi__sub">${k.sub}</div>
      ${warningBadge}
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
  const exec = state.meta.executability;
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

  // Add executability row
  if (exec) {
    const gradeColors = { PRODUCTION: '#265844', RESEARCH: '#C4A24A', THEORETICAL: '#B85C4A' };
    const gradeIcon = { PRODUCTION: '🟢', RESEARCH: '🟡', THEORETICAL: '🔴' };
    items.push(['Executability', `<span style="color:${gradeColors[exec.grade]};font-weight:700">${gradeIcon[exec.grade]} ${exec.grade} (${exec.score}%)</span>`]);
    items.push(['Tradeable', `${exec.tradeable_count} / ${exec.total_count} instruments`]);
  }

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

// ── Position Table (Bloomberg-level w/ Long/Short sections + sortable) ──
function renderPositionTable() {
  if (!state.positionSnapshot) return;

  const hasAC = state.positionSnapshot[0]?.['Asset Class'] !== undefined;
  const hasExpNav = state.positionSnapshot[0]?.['Exposure (% NAV)'] !== undefined;

  // Split into Long/Short/Flat
  const longs = [], shorts = [], flat = [];
  state.positionSnapshot.forEach(r => {
    const contracts = parseInt(r['Rounded (Contracts)'] || '0');
    if (contracts > 0) longs.push(r);
    else if (contracts < 0) shorts.push(r);
    else flat.push(r);
  });

  // Sort function
  const { col, asc } = state.positionSort;
  function sortRows(arr) {
    return [...arr].sort((a, b) => {
      let va = a[col] ?? a['Instrument'] ?? '';
      let vb = b[col] ?? b['Instrument'] ?? '';
      // Try numeric
      const na = parseFloat(String(va).replace(/[%$,]/g, ''));
      const nb = parseFloat(String(vb).replace(/[%$,]/g, ''));
      if (!isNaN(na) && !isNaN(nb)) {
        return asc ? na - nb : nb - na;
      }
      return asc ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va));
    });
  }

  const sortedLongs = sortRows(longs);
  const sortedShorts = sortRows(shorts);

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

    return `<tr class="clickable-row" onclick="navigateToInstrument('${r.Instrument}')">
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

  // Column definitions for sortable headers
  const colDefs = [
    ...(hasAC ? [{ key: 'Asset Class', label: 'Class', align: '' }] : []),
    { key: 'Instrument', label: 'Instrument', align: '' },
    { key: 'Direction', label: 'Direction', align: '' },
    { key: 'Rounded (Contracts)', label: 'Contracts', align: 'center' },
    ...(hasExpNav ? [{ key: 'Exposure (% NAV)', label: 'Exposure (% NAV)', align: 'right' }] : []),
    ...(hasExpNav ? [{ key: 'Contract Value ($)', label: 'Contract $', align: 'right' }] : []),
    { key: 'Notional Position', label: 'Notional (Optimal)', align: 'right' },
    { key: 'Avg |Position|', label: 'Avg |Pos| (full period)', align: 'right' },
    { key: 'Instrument Weight', label: 'Weight', align: 'right' },
    { key: 'Last Date', label: 'Data Through', align: '' },
  ];

  const headers = `<tr>${colDefs.map(c => {
    const arrow = col === c.key ? (asc ? ' ▲' : ' ▼') : '';
    const style = c.align ? `text-align:${c.align}` : '';
    return `<th class="sortable-th" style="${style}" onclick="handlePositionSort('${c.key}')">${c.label}${arrow}</th>`;
  }).join('')}</tr>`;

  function sectionHtml(title, rows, accentClass) {
    if (rows.length === 0) return '';
    return `<div class="position-section ${accentClass}">
      <div class="position-section__header">${title} <span class="position-section__count">${rows.length}</span></div>
      <table>
        <thead>${headers}</thead>
        <tbody>${rows.map(buildRow).join('')}</tbody>
      </table>
    </div>`;
  }

  let html = sectionHtml('Long Positions', sortedLongs, 'position-section--long');
  html += sectionHtml('Short Positions', sortedShorts, 'position-section--short');

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

function handlePositionSort(colKey) {
  if (state.positionSort.col === colKey) {
    state.positionSort.asc = !state.positionSort.asc;
  } else {
    state.positionSort.col = colKey;
    state.positionSort.asc = false;
  }
  renderPositionTable();
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

// ── Exposure (NAV %) — uses time-series contract values for accuracy ──
function renderExposure() {
  if (!state.notionalPositions) return;
  const cols = Object.keys(state.notionalPositions[0]).filter(k => k !== 'index' && k !== '');
  const capital = state.meta?.meta?.capital || 200000;

  // Build contract value lookup: date -> { instrument -> USD value }
  const cvByDate = {};
  const hasCV = state.contractValues && state.contractValues.length > 0;
  if (hasCV) {
    state.contractValues.forEach(row => {
      const d = row.index || row[''];
      if (d) cvByDate[d] = row;
    });
  }
  // Fallback: latest snapshot values
  const latestCV = {};
  if (state.positionSnapshot) {
    state.positionSnapshot.forEach(r => {
      const cv = parseFloat(r['Contract Value ($)'] || '0');
      if (cv > 0) latestCV[r.Instrument] = cv;
    });
  }

  // Find nearest CV date for a position date
  const cvDates = Object.keys(cvByDate).sort();
  function findNearestCV(dateStr) {
    // Binary search for nearest date <= dateStr
    let lo = 0, hi = cvDates.length - 1, best = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (cvDates[mid] <= dateStr) { best = mid; lo = mid + 1; }
      else hi = mid - 1;
    }
    return best >= 0 ? cvByDate[cvDates[best]] : null;
  }

  const sampled = state.notionalPositions.filter((_, i) => i % 20 === 0);

  const longData = sampled.map(row => {
    const dateStr = row.index || row[''];
    const cvRow = hasCV ? findNearestCV(dateStr) : null;
    let sum = 0;
    cols.forEach(c => {
      const v = row[c];
      if (!isNaN(v) && v > 0) {
        const cv = (cvRow && !isNaN(cvRow[c])) ? cvRow[c] : (latestCV[c] || 0);
        sum += cv > 0 ? (v * cv / capital * 100) : 0;
      }
    });
    return sum;
  });

  const shortData = sampled.map(row => {
    const dateStr = row.index || row[''];
    const cvRow = hasCV ? findNearestCV(dateStr) : null;
    let sum = 0;
    cols.forEach(c => {
      const v = row[c];
      if (!isNaN(v) && v < 0) {
        const cv = (cvRow && !isNaN(cvRow[c])) ? cvRow[c] : (latestCV[c] || 0);
        sum += cv > 0 ? (v * cv / capital * 100) : 0;
      }
    });
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
      plugins: {
        legend: { position: 'top', align: 'end' },
        tooltip: {
          callbacks: {
            label: ctx => `${ctx.dataset.label}: ${ctx.raw.toFixed(1)}%`
          }
        }
      },
      scales: {
        x: { grid: { color: PALETTE.gridLine }, ticks: { maxTicksLimit: 8, font: { size: 10 } } },
        y: { grid: { color: PALETTE.gridLine }, title: { display: true, text: '% of NAV' } }
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
  state.selectedInstrument = inst;

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

  if (state.roundedPositions || state.notionalPositions) {
    const hasBoth = state.roundedPositions && state.notionalPositions;
    const primarySrc = state.roundedPositions || state.notionalPositions;
    const isRounded = !!state.roundedPositions;
    
    let posData = primarySrc.map(r => ({ d: r.index || r[''], v: r[inst] })).filter(p => !isNaN(p.v));
    let idealData = hasBoth
      ? state.notionalPositions.map(r => ({ d: r.index || r[''], v: r[inst] })).filter(p => !isNaN(p.v))
      : [];
    
    // Apply period filter
    const period = state.instPeriod || 'all';
    if (period !== 'all' && posData.length > 0) {
      const lastDate = posData[posData.length - 1].d;
      const cutoff = new Date(lastDate);
      const years = period === '1y' ? 1 : period === '3y' ? 3 : 5;
      cutoff.setFullYear(cutoff.getFullYear() - years);
      const cutoffStr = cutoff.toISOString().substring(0, 10);
      posData = posData.filter(p => p.d >= cutoffStr);
      idealData = idealData.filter(p => p.d >= cutoffStr);
    }
    
    // Sample for performance
    const step = period === '1y' ? 1 : period === '3y' ? 2 : period === '5y' ? 3 : 5;
    const posSampled = posData.filter((_, i) => i % step === 0 || i === posData.length - 1);
    const idealSampled = idealData.filter((_, i) => i % step === 0 || i === idealData.length - 1);

    // Update period button active state
    document.querySelectorAll('#inst-period-btns .period-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.period === period);
    });

    // Build datasets
    const datasets = [];
    
    // Primary: Rounded integer positions (solid stepped)
    datasets.push({
      label: 'Actual (Integer)',
      data: posSampled.map(r => r.v),
      borderColor: PALETTE.green,
      borderWidth: 1.5,
      pointRadius: 0,
      fill: { target: 'origin', above: PALETTE.greenLight, below: PALETTE.charcoal30 + '22' },
      stepped: isRounded,
      order: 1,
    });
    
    // Secondary: Ideal fractional positions (faded smooth dashed)
    if (hasBoth && idealSampled.length > 0) {
      datasets.push({
        label: 'Ideal (Fractional)',
        data: idealSampled.map(r => r.v),
        borderColor: PALETTE.forest + '55',
        borderWidth: 1,
        borderDash: [4, 3],
        pointRadius: 0,
        fill: false,
        stepped: false,
        order: 2,
      });
    }

    destroyChart('chart-inst-position');
    state.charts['chart-inst-position'] = new Chart(document.getElementById('chart-inst-position'), {
      type: 'line',
      data: {
        labels: posSampled.map(r => r.d),
        datasets
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: hasBoth, position: 'top', labels: { font: { size: 10 }, boxWidth: 20, padding: 8 } } },
        scales: {
          x: { grid: { color: PALETTE.gridLine }, ticks: { maxTicksLimit: 8 } },
          y: { grid: { color: PALETTE.gridLine }, title: { display: true, text: 'Contracts' },
            ticks: isRounded ? (() => {
              const vals = posSampled.map(r => r.v);
              const range = Math.max(...vals) - Math.min(...vals);
              return range <= 10 ? { stepSize: 1 } : {};
            })() : {}
          }
        }
      }
    });
  }
}

function setInstPeriod(period) {
  state.instPeriod = period;
  if (state.selectedInstrument) {
    renderInstrumentDetail(state.selectedInstrument);
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

// ── Methodology Tab ──
function renderMethodology() {
  renderMethodologyPipeline();
  renderMethodologyCosts();
  renderMethodologyRisk();
  renderMethodologyRules();
  renderSpreadCostChart();
}

function renderMethodologyPipeline() {
  const m = state.methodology || {};
  const stages = [
    { icon: '📊', title: 'Raw Price Data', desc: `${m.instrument_count || 25} instruments, daily adjusted prices`, detail: `Currency: ${m.base_currency || 'USD'}` },
    { icon: '📐', title: 'Volatility Estimation', desc: `Blended ${m.volatility_calculation?.lookback_days || 35}-day + ${m.volatility_calculation?.slow_vol_years || 20}-year average`, detail: `Slow vol weight: ${((m.volatility_calculation?.proportion_slow_vol || 0.35)*100).toFixed(0)}%` },
    { icon: '📈', title: 'Signal Generation', desc: '11 trading rules across 3 factor families', detail: `Trend (5) + Carry (3) + CS Momentum (3)` },
    { icon: '⚖️', title: 'Forecast Scaling & Capping', desc: `Scaled to avg absolute forecast of 10, capped at ±${m.forecast_cap || 20}`, detail: 'Pre-estimated scalars applied' },
    { icon: '🔀', title: 'Forecast Combination', desc: 'Weighted blend of all rule forecasts per instrument', detail: 'Weights estimated from performance' },
    { icon: '📏', title: 'Position Sizing', desc: `Vol target: ${m.vol_target_pct || 25}%, Capital: $${((m.capital||200000)/1000).toFixed(0)}K`, detail: 'Notional (fractional) positions' },
    { icon: '🤖', title: 'Dynamic Optimization (Mr. Greedy)', desc: 'Integer-position greedy algorithm minimizing tracking error + trade costs', detail: `Shadow cost: ${m.shadow_cost || 10}×, Buffer: ${((m.tracking_error_buffer||0.12)*100).toFixed(0)}%` },
    { icon: '🛡️', title: 'Risk Overlay', desc: '4-factor risk multiplier (0 to 1) applied to entire portfolio', detail: 'Normal risk, Jump vol, Shock corr, Leverage' },
    { icon: '📋', title: 'Final Orders', desc: 'Integer contract positions per instrument', detail: 'Daily evaluation, trade only when needed' },
  ];

  const el = document.getElementById('methodology-pipeline');
  if (!el) return;
  el.innerHTML = `<div class="pipeline-flow">${stages.map((s, i) => `
    <div class="pipeline-stage">
      <div class="pipeline-stage__icon">${s.icon}</div>
      <div class="pipeline-stage__content">
        <div class="pipeline-stage__title">${s.title}</div>
        <div class="pipeline-stage__desc">${s.desc}</div>
        <div class="pipeline-stage__detail">${s.detail}</div>
      </div>
    </div>
    ${i < stages.length - 1 ? '<div class="pipeline-arrow">→</div>' : ''}
  `).join('')}</div>`;
}

function renderMethodologyCosts() {
  const m = state.methodology || {};
  const el = document.getElementById('methodology-costs');
  if (!el) return;

  const layers = [
    { name: 'Spread Cost', value: 'Per instrument', desc: 'Estimated bid-ask half-spread from instrumentconfig.csv. Applied to every simulated trade.' },
    { name: 'Shadow Cost Multiplier', value: `${m.shadow_cost || 10}×`, desc: 'Real trading costs are multiplied by this factor in the optimizer\'s objective function. Prevents trades unless the improvement clearly exceeds friction.' },
    { name: 'Tracking Error Buffer', value: `${((m.tracking_error_buffer||0.12)*100).toFixed(0)}% TE`, desc: 'If tracking error between current & optimal positions is below this threshold, NO trades are executed (no-trade zone).' },
    { name: 'Adjustment Factor', value: 'Proportional', desc: 'When TE exceeds buffer: adj = (TE − buffer) / TE. Only this fraction of desired trades is executed. Prevents over-trading.' },
    { name: 'Cost Multiplier', value: `${m.cost_multiplier || 1.0}×`, desc: 'Global multiplier on all transaction cost estimates. Set to 1.0 for realistic costs, >1.0 for conservative backtesting.' },
    { name: 'Cost Deflator', value: 'Time-varying', desc: 'Adjusts spread costs for historical price levels. Older periods when prices were lower effectively had higher percentage costs.' },
  ];

  el.innerHTML = `<div class="methodology-list">${layers.map(l => `
    <div class="methodology-item">
      <div class="methodology-item__header">
        <span class="methodology-item__name">${l.name}</span>
        <span class="methodology-item__value">${l.value}</span>
      </div>
      <div class="methodology-item__desc">${l.desc}</div>
    </div>
  `).join('')}</div>`;
}

function renderMethodologyRisk() {
  const m = state.methodology || {};
  const ro = m.risk_overlay || {};
  const el = document.getElementById('methodology-risk');
  if (!el) return;

  const controls = [
    { name: 'Normal Risk', limit: `${ro.max_risk_fraction_normal || 2.0}× vol target`, desc: `If portfolio risk > ${ro.max_risk_fraction_normal || 2.0}× the ${m.vol_target_pct || 25}% target (=${((ro.max_risk_fraction_normal || 2.0) * (m.vol_target_pct || 25)).toFixed(0)}%), positions are scaled down.` },
    { name: 'Jump Volatility', limit: `${ro.max_risk_fraction_stdev || 4.0}× vol target`, desc: 'Uses shocked (higher) volatility estimates. Protects against non-stationary vol spikes.' },
    { name: 'Shock Correlation', limit: `${ro.max_risk_limit_sum_abs || 5.0}× vol target`, desc: 'Sum of absolute position risks. Catches extreme concentrated bets that could blow up if correlations spike to 1.' },
    { name: 'Max Leverage', limit: `${ro.max_risk_leverage || 15.0}×`, desc: 'Hard cap on total notional exposure / capital. Prevents excessive leverage regardless of risk estimates.' },
  ];

  el.innerHTML = `
    <div class="methodology-callout">The most conservative (lowest) multiplier from all 4 checks is applied to ALL positions simultaneously.</div>
    <div class="methodology-list">${controls.map(c => `
    <div class="methodology-item">
      <div class="methodology-item__header">
        <span class="methodology-item__name">${c.name}</span>
        <span class="methodology-item__value">${c.limit}</span>
      </div>
      <div class="methodology-item__desc">${c.desc}</div>
    </div>
  `).join('')}</div>
  <div class="methodology-extras">
    <div class="methodology-item">
      <div class="methodology-item__header">
        <span class="methodology-item__name">Forecast Cap</span>
        <span class="methodology-item__value">±${m.forecast_cap || 20}</span>
      </div>
      <div class="methodology-item__desc">All forecasts clamped to [-${m.forecast_cap || 20}, +${m.forecast_cap || 20}]. Prevents extreme signals from creating outsized positions.</div>
    </div>
    <div class="methodology-item">
      <div class="methodology-item__header">
        <span class="methodology-item__name">Correlation Shrinkage</span>
        <span class="methodology-item__value">${((m.correlation_shrinkage || 0.5)*100).toFixed(0)}%</span>
      </div>
      <div class="methodology-item__desc">Off-diagonal correlations shrunk toward zero by ${((m.correlation_shrinkage || 0.5)*100).toFixed(0)}%. Reduces impact of noisy correlation estimates.</div>
    </div>
  </div>`;
}

// ── Factor methodology profiles (static data) ──
const FACTOR_PROFILES = {
  'Trend (EWMAC)': {
    color: '#265844', icon: '📈',
    rationale: 'Captures persistent macro-economic trends and investor under-reaction to new information. Markets that rise (fall) tend to continue rising (falling) due to anchoring bias and slow institutional reallocation.',
    params: 'Each rule is defined by two EWMA half-lives (fast/slow). Smaller numbers (e.g. L16) = faster-reacting, more trades, higher costs. Blending multiple speeds reduces whipsaw losses and smooths regime transitions.',
    profile: [
      { label: 'Return Skew',      value: 'Positive ↑', sub: 'Rare large wins offset frequent small losses', color: '#55B786' },
      { label: 'Win Rate',         value: '~40%',        sub: 'Low — but tail profits are outsized',         color: '#6B6B6B' },
      { label: 'Crisis Alpha',     value: 'Strong ✓',   sub: 'Best in 2008, 2022 systemic dislocations',    color: '#265844' },
      { label: 'Best Environment', value: 'Trending',    sub: 'Strong directional macro regimes',            color: '#265844' },
    ]
  },
  'Carry': {
    color: '#55B786', icon: '💰',
    rationale: 'Collects a structural risk premium embedded in futures term structure. Buys contracts in backwardation (nearby > deferred) and sells in contango, harvesting the roll yield without requiring price direction.',
    params: 'The raw carry signal is the annualized roll yield derived from near vs. deferred contract prices. A smoothing parameter controls signal responsiveness to curve shape changes, reducing noise from temporary distortions.',
    profile: [
      { label: 'Return Skew',      value: 'Negative ↓', sub: 'Steady gains, occasional sharp losses',       color: '#C4B68A' },
      { label: 'Win Rate',         value: '~60%',        sub: 'High — produces consistent daily edge',       color: '#55B786' },
      { label: 'Crisis Alpha',     value: 'Weak ✗',      sub: 'Vulnerable to sudden liquidity shocks',       color: '#B85C4A' },
      { label: 'Best Environment', value: 'Risk-On / Range', sub: 'Diversifies Trend losses in low-vol regimes', color: '#55B786' },
    ]
  },
  'Cross-Sectional Momentum': {
    color: '#C4B68A', icon: '⚖️',
    rationale: 'Tracks capital rotation across the universe. Instead of asking "is this going up?", it asks "is this outperforming its peers?". Buys relative winners and sells relative losers within the same time horizon.',
    params: 'Each rule computes the n-day cumulative return of each instrument, then subtracts the cross-sectional mean to compute a relative rank score. Multiple lookback windows blend to capture different rotation cycles.',
    profile: [
      { label: 'Market Neutrality',    value: 'True ✓',    sub: 'Profits even in uniformly falling markets', color: '#265844' },
      { label: 'Crisis Alpha',         value: 'Moderate',   sub: 'Effective when dispersion persists',        color: '#C4B68A' },
      { label: 'Corr. to Trend',       value: 'Low',        sub: 'Key diversifier — maximises portfolio SR',  color: '#55B786' },
      { label: 'Best Environment',     value: 'High Dispersion', sub: 'Wide spread between winners and losers', color: '#265844' },
    ]
  }
};

function renderFactorProfileCard(profile) {
  const metricsHtml = profile.profile.map(p => `
    <div class="factor-profile__metric">
      <div class="factor-profile__metric-label">${p.label}</div>
      <div class="factor-profile__metric-value" style="color:${p.color}">${p.value}</div>
      <div class="factor-profile__metric-sub">${p.sub}</div>
    </div>
  `).join('');
  return `
    <div class="factor-profile-card" style="border-left-color:${profile.color}">
      <div class="factor-profile__header">
        <span class="factor-profile__icon">${profile.icon}</span>
        <div style="flex:1">
          <div class="factor-profile__section-title" style="color:${profile.color}">Economic Rationale</div>
          <p class="factor-profile__text">${profile.rationale}</p>
        </div>
      </div>
      <div class="factor-profile__section-title" style="color:${profile.color};margin-top:10px">Parameter Meaning</div>
      <p class="factor-profile__text">${profile.params}</p>
      <div class="factor-profile__section-title" style="color:${profile.color};margin-top:10px">Performance Profile</div>
      <div class="factor-profile__grid">${metricsHtml}</div>
    </div>
  `;
}

function renderMethodologyRules() {
  const m = state.methodology || {};
  const rules = m.trading_rules || {};
  const el = document.getElementById('methodology-rules');
  if (!el) return;

  const families = {
    'Trend (EWMAC)': Object.entries(rules).filter(([k]) => k.startsWith('momentum')).sort((a,b) => {
      const pa = parseInt(a[0].replace('momentum','')); const pb = parseInt(b[0].replace('momentum',''));
      return pa - pb;
    }),
    'Carry': Object.entries(rules).filter(([k]) => k.startsWith('carry')).sort((a,b) => {
      const pa = parseInt(a[0].replace('carry','')); const pb = parseInt(b[0].replace('carry',''));
      return pa - pb;
    }),
    'Cross-Sectional Momentum': Object.entries(rules).filter(([k]) => k.startsWith('relmomentum')).sort((a,b) => {
      const pa = parseInt(a[0].replace('relmomentum','')); const pb = parseInt(b[0].replace('relmomentum',''));
      return pa - pb;
    }),
  };

  el.innerHTML = Object.entries(families).map(([family, entries]) => {
    const rowsHtml = entries.map(([name, info]) => {
      const params = info.params || {};
      const paramStr = Object.entries(params).map(([k,v]) => `${k}=${v}`).join(', ');
      return `<tr><td class="td-name">${name}</td><td style="font-family:var(--font-mono);font-size:11px">${paramStr || '—'}</td></tr>`;
    }).join('');
    const profileCard = FACTOR_PROFILES[family] ? renderFactorProfileCard(FACTOR_PROFILES[family]) : '';
    return `
      <div class="methodology-family">
        <div class="methodology-family__title">${family}</div>
        ${profileCard}
        <table class="methodology-rules-table" style="margin-top:var(--space-sm)">
          <thead><tr><th>Rule</th><th>Parameters</th></tr></thead>
          <tbody>${rowsHtml}</tbody>
        </table>
      </div>
    `;
  }).join('');
}

function renderSpreadCostChart() {
  if (!state.spreadCosts) return;
  const sorted = [...state.spreadCosts].sort((a,b) => parseFloat(b.cost_usd) - parseFloat(a.cost_usd));

  destroyChart('chart-spread-costs');
  state.charts['chart-spread-costs'] = new Chart(document.getElementById('chart-spread-costs'), {
    type: 'bar',
    data: {
      labels: sorted.map(r => r.instrument),
      datasets: [{
        data: sorted.map(r => parseFloat(r.cost_usd)),
        backgroundColor: PALETTE.forest50,
        borderColor: PALETTE.forest,
        borderWidth: 1,
        borderRadius: 3,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => `$${ctx.raw.toFixed(2)} per contract`
          }
        }
      },
      scales: {
        x: { grid: { color: PALETTE.gridLine }, title: { display: true, text: 'Cost per Contract (USD)' } },
        y: { grid: { display: false }, ticks: { font: { size: 9 } } }
      }
    }
  });
}

// ── Helpers ──
function destroyChart(id) {
  if (state.charts[id]) { state.charts[id].destroy(); delete state.charts[id]; }
}

// ── Sweep Tab ──
const SWEEP_COLORS = [
  '#265844',   // Production (baseline) — forest
  '#55B786',   // Ags+FX+Metals
  '#42A47C',   // Ags+Metals
  '#6CC494',   // Ags+FX
  '#C4B68A',   // Ags only
  '#8B7355',   // FX+Metals
  '#AC9C72',   // FX only
  '#6B6B6B',   // Metals only
  '#B8A97E',   // Base
];

async function renderSweep() {
  // Load sweep data if not in state
  if (!state.sweepData) {
    try {
      const text = await loadFile('sweep_summary.json');
      state.sweepData = JSON.parse(text);
    } catch {
      const el = document.getElementById('sweep-loading');
      if (el) el.textContent = 'No sweep data available. Run: python scripts/generate_sweep_dashboard.py';
      return;
    }
  }

  const data = state.sweepData;
  renderSweepMetricsTable(data.runs);
  renderSweepEquityChart(data.runs);
  renderSweepRollingSR(data.runs);
  renderSweepMarginalChart(data.marginal_contributions);
  renderSweepCountChart(data.runs);
}

function renderSweepMetricsTable(runs) {
  const container = document.getElementById('sweep-metrics-table');
  if (!container) return;

  const bestSR = Math.max(...runs.map(r => r.sharpe));
  const worstMDD = Math.min(...runs.map(r => r.max_drawdown ?? -999));
  const hasMDD = runs.some(r => r.max_drawdown != null);
  const hasCapital = runs.some(r => r.capital && r.capital > 0);

  // ── Executability explainer card ──
  const explainerHtml = `
    <div style="background:var(--sand-light);border:1px solid var(--border-subtle);border-left:4px solid #C4B68A;
                border-radius:8px;padding:12px 16px;margin-bottom:12px;font-size:12px;line-height:1.6">
      <div style="font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#8B7355;margin-bottom:6px">
        ⚠ Capital ≠ Minimum Required Capital
      </div>
      <p style="color:var(--text-secondary);margin:0">
        <strong>BT Capital</strong> shows the account size used as input for each backtest run.
        This is <em>not</em> the minimum capital required to execute each universe.
        Computing minimum required capital involves per-instrument nominal value, volatility, IDM, and weight calculations via the pysystemtrade <code style="background:#fff;padding:1px 5px;border-radius:3px">System</code> object.
        The $100K Macro Mini (13 inst) universe was specifically designed with micro-contracts to remain tradeable at $100K.
      </p>
    </div>`;

  function fmtCapital(cap) {
    if (!cap || cap === 0) return '—';
    if (cap >= 1000000) return `$${(cap/1000000).toFixed(1)}M`;
    return `$${(cap/1000).toFixed(0)}K`;
  }

  function capitalBadge(cap) {
    if (!cap || cap === 0) return '<span style="color:var(--text-muted)">—</span>';
    const color = cap <= 100000 ? '#8B7355' : cap <= 200000 ? '#265844' : '#55B786';
    const bg = cap <= 100000 ? '#F5E8C133' : cap <= 200000 ? '#26584415' : '#55B78615';
    return `<span style="background:${bg};color:${color};padding:2px 7px;border-radius:4px;font-weight:600;font-size:10px;font-family:var(--font-mono)">${fmtCapital(cap)}</span>`;
  }

  let html = `<table class="data-table">
    <thead><tr>
      <th>Rank</th><th>Universe</th><th>#Inst</th>
      ${hasCapital ? '<th title="Account size used as backtest input — NOT minimum required capital">BT Capital</th>' : ''}
      <th>Sharpe</th>
      <th>Return</th><th>Vol</th><th>Avg DD</th>${hasMDD ? '<th>Max DD</th>' : ''}<th>Sortino</th><th>Skew</th>
      <th>Asset Classes</th>
    </tr></thead><tbody>`;

  runs.forEach((r, i) => {
    const isBest = r.sharpe === bestSR;
    const rowCls = r.is_baseline ? ' style="background:var(--mint)"' : '';
    const srCls = isBest ? ' style="color:var(--forest);font-weight:700"' : '';
    const skewCls = r.skew > 0 ? ' style="color:var(--forest)"' : r.skew < -0.5 ? ' style="color:#8B4513"' : '';
    const star = isBest ? ' ★' : '';
    const tag = r.is_baseline ? ' <span style="background:var(--forest);color:#fff;padding:1px 6px;border-radius:3px;font-size:10px;margin-left:4px">BASELINE</span>' : '';
    const mdd = r.max_drawdown != null ? r.max_drawdown : null;
    const mddCls = mdd != null && mdd === worstMDD ? ' style="color:#B85C4A;font-weight:700"' : '';
    const mddCell = hasMDD ? `<td${mddCls}>${mdd != null ? mdd.toFixed(1) + '%' : '—'}</td>` : '';
    const capitalCell = hasCapital ? `<td>${capitalBadge(r.capital)}</td>` : '';

    html += `<tr${rowCls}>
      <td>${i + 1}</td>
      <td>${r.label}${tag}</td>
      <td>${r.n_instruments}</td>
      ${capitalCell}
      <td${srCls}>${r.sharpe.toFixed(3)}${star}</td>
      <td>${r.ann_return.toFixed(1)}%</td>
      <td>${r.ann_vol.toFixed(1)}%</td>
      <td>${r.avg_drawdown.toFixed(1)}%</td>
      ${mddCell}
      <td>${r.sortino.toFixed(3)}</td>
      <td${skewCls}>${r.skew > 0 ? '+' : ''}${r.skew.toFixed(2)}</td>
      <td style="font-size:10px">${r.classes.join(', ')}</td>
    </tr>`;
  });

  html += '</tbody></table>';
  container.innerHTML = explainerHtml + html;
}

function renderSweepEquityChart(runs) {
  destroyChart('sweepEquity');
  const ctx = document.getElementById('sweep-equity-chart');
  if (!ctx) return;

  const datasets = runs.map((r, i) => ({
    label: `${r.label} (SR ${r.sharpe.toFixed(2)})`,
    data: r.equity_weekly.map(([t, v]) => ({ x: t, y: v })),
    borderColor: SWEEP_COLORS[i % SWEEP_COLORS.length],
    borderWidth: r.is_baseline ? 2.5 : 1.5,
    pointRadius: 0,
    borderDash: r.is_baseline ? [] : (i > 4 ? [4, 2] : []),
    hidden: i > 4 && !r.is_baseline,  // show top 5 + baseline by default
  }));

  state.charts.sweepEquity = new Chart(ctx, {
    type: 'line',
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'bottom',
          labels: { boxWidth: 12, padding: 8, font: { size: 10 } }
        },
        tooltip: {
          callbacks: {
            title: ctx => new Date(ctx[0].parsed.x).toLocaleDateString('en-US', { year: 'numeric', month: 'short' }),
            label: ctx => `${ctx.dataset.label}: $${ctx.parsed.y.toLocaleString()}`
          }
        }
      },
      scales: {
        x: {
          type: 'time',
          time: { unit: 'year' },
          grid: { color: PALETTE.gridLine },
          ticks: { maxTicksLimit: 12 }
        },
        y: {
          grid: { color: PALETTE.gridLine },
          title: { display: true, text: 'Cumulative P&L ($)' },
          ticks: { callback: v => '$' + (v / 1000).toFixed(0) + 'k' }
        }
      }
    }
  });
}

function renderSweepRollingSR(runs) {
  destroyChart('sweepRollingSR');
  const ctx = document.getElementById('sweep-rolling-sr-chart');
  if (!ctx) return;

  const datasets = runs
    .filter(r => r.rolling_sharpe_3y && r.rolling_sharpe_3y.length > 0)
    .map((r, i) => ({
      label: r.label,
      data: r.rolling_sharpe_3y.map(([t, v]) => ({ x: t, y: v })),
      borderColor: SWEEP_COLORS[i % SWEEP_COLORS.length],
      borderWidth: r.is_baseline ? 2.5 : 1.2,
      pointRadius: 0,
      hidden: i > 4 && !r.is_baseline,
    }));

  // Add zero line
  state.charts.sweepRollingSR = new Chart(ctx, {
    type: 'line',
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'bottom',
          labels: { boxWidth: 12, padding: 8, font: { size: 10 } }
        },
        tooltip: {
          callbacks: {
            title: ctx => new Date(ctx[0].parsed.x).toLocaleDateString('en-US', { year: 'numeric', month: 'short' }),
            label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)}`
          }
        }
      },
      scales: {
        x: {
          type: 'time',
          time: { unit: 'year' },
          grid: { color: PALETTE.gridLine },
          ticks: { maxTicksLimit: 12 }
        },
        y: {
          grid: { color: PALETTE.gridLine },
          title: { display: true, text: 'Sharpe Ratio (3Y Rolling)' }
        }
      }
    }
  });
}

function renderSweepMarginalChart(marginal) {
  destroyChart('sweepMarginal');
  const ctx = document.getElementById('sweep-marginal-chart');
  if (!ctx || !marginal) return;

  const labels = marginal.map(m => m.class);
  const values = marginal.map(m => m.contribution);
  const colors = marginal.map(m =>
    m.class === 'Ags' ? PALETTE.forest :
    m.class === 'FX' ? '#C4B68A' : '#6B6B6B'
  );

  state.charts.sweepMarginal = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderRadius: 4,
        barThickness: 36,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => `+${ctx.raw.toFixed(3)} SR`
          }
        }
      },
      scales: {
        x: {
          grid: { color: PALETTE.gridLine },
          title: { display: true, text: 'Marginal SR Contribution vs Base (Eq+Bond)' },
          ticks: { callback: v => '+' + v.toFixed(2) }
        },
        y: { grid: { display: false } }
      }
    }
  });
}

function renderSweepCountChart(runs) {
  destroyChart('sweepCount');
  const ctx = document.getElementById('sweep-count-chart');
  if (!ctx) return;

  const sorted = [...runs].sort((a, b) => a.sharpe - b.sharpe);
  const labels = sorted.map(r => r.label.replace('Production (25, Handcraft)', 'Prod (25)'));
  const counts = sorted.map(r => r.n_instruments);
  const srs = sorted.map(r => r.sharpe);

  // Dynamic x1 axis: give SR values breathing room
  const srMin = Math.min(...srs);
  const srMax = Math.max(...srs);
  const srRange = srMax - srMin || 0.5;
  const srAxisMin = Math.max(0, parseFloat((srMin - srRange * 0.4).toFixed(2)));
  const srAxisMax = parseFloat((srMax + srRange * 0.4).toFixed(2));

  state.charts.sweepCount = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: '# Instruments',
          data: counts,
          backgroundColor: sorted.map(r => r.is_baseline ? PALETTE.forest : PALETTE.green + '99'),
          borderRadius: 4,
          barThickness: 22,
          xAxisID: 'x',
        },
        {
          label: 'Sharpe Ratio',
          data: srs,
          type: 'line',
          borderColor: PALETTE.forest,
          backgroundColor: PALETTE.forest,
          borderWidth: 2.5,
          pointRadius: 6,
          pointBackgroundColor: sorted.map(r => r.is_baseline ? '#fff' : PALETTE.forest),
          pointBorderColor: PALETTE.forest,
          pointBorderWidth: 2,
          tension: 0.3,
          xAxisID: 'x1',
        }
      ]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 10 } } },
        tooltip: {
          callbacks: {
            label: ctx => ctx.dataset.label === 'Sharpe Ratio'
              ? `SR: ${ctx.raw.toFixed(3)}`
              : `# Instruments: ${ctx.raw}`
          }
        }
      },
      scales: {
        x: {
          display: false,
          grid: { display: false },
        },
        y: { grid: { display: false }, ticks: { font: { size: 9 } } },
        x1: {
          position: 'top',
          grid: { color: 'rgba(38,88,68,0.1)', drawOnChartArea: true },
          title: { display: true, text: 'Sharpe Ratio', font: { size: 10 }, color: PALETTE.forest },
          min: srAxisMin,
          max: srAxisMax,
          ticks: { callback: v => v.toFixed(2), font: { size: 9 }, maxTicksLimit: 6, color: PALETTE.forest }
        }
      }
    }
  });
}

// ══════════════════════════════════════════════════════════════════
// ARKI MACRO TAB
// ══════════════════════════════════════════════════════════════════

let macroData = null;
let macroLoaded = false;

async function loadMacroData() {
  if (macroLoaded) return;
  try {
    const text = await loadFile('arki_macro_summary.json');
    macroData = JSON.parse(text);
    macroLoaded = true;
    renderMacroTab();
  } catch (e) {
    console.warn('Arki Macro data not found:', e.message);
  }
}

function renderMacroTab() {
  if (!macroData) return;
  renderMacroKPIs();
  renderMacroEquity();
  renderMacroPeriodTable();
  renderMacroStatsTable();
  renderMacroAnnualTable();
  renderMacroHeatmap();
  renderMacroRollingSR();
  renderMacroCorrelation();
  renderMacroDrawdown();
}

function renderMacroKPIs() {
  const s = macroData.combined.stats;
  const m = macroData.meta;
  const kpis = [
    { label: 'CAGR', value: s.cagr + '%', cls: 'positive', sub: `${s.years} years` },
    { label: 'Sharpe', value: s.sharpe, cls: '', sub: `Monthly basis` },
    { label: 'Sortino', value: s.sortino, cls: '', sub: `Downside adj.` },
    { label: 'Max Drawdown', value: s.max_drawdown + '%', cls: 'negative', sub: `Avg DD: ${s.avg_drawdown}%` },
    { label: 'Correlation', value: m.correlation, cls: '', sub: `Mini vs MF` },
    { label: 'Total Capital', value: '$' + (m.total_capital/1000) + 'K', cls: '', sub: '$100K + $200K' },
  ];
  document.getElementById('macro-kpi-strip').innerHTML = kpis.map(k => `
    <div class="kpi">
      <div class="kpi__label">${k.label}</div>
      <div class="kpi__value ${k.cls}">${k.value}</div>
      <div class="kpi__sub">${k.sub}</div>
    </div>
  `).join('');
}

function renderMacroEquity() {
  const toDate = pts => pts.map(p => new Date(p[0]));
  const toVal = pts => pts.map(p => p[1]);

  destroyChart('macro-equity-chart');
  state.charts['macro-equity-chart'] = new Chart(document.getElementById('macro-equity-chart'), {
    type: 'line',
    data: {
      labels: toDate(macroData.combined.equity_monthly),
      datasets: [
        {
          label: 'Arki Macro (Combined)',
          data: toVal(macroData.combined.equity_monthly),
          borderColor: PALETTE.forest,
          backgroundColor: PALETTE.forest15,
          fill: true,
          borderWidth: 2,
          pointRadius: 0,
        },
        {
          label: 'Macro Mini ($100K)',
          data: toVal(macroData.macro_mini.equity_monthly),
          borderColor: PALETTE.green,
          borderWidth: 1.5,
          pointRadius: 0,
          borderDash: [4, 2],
        },
        {
          label: 'Multi-Factor ($200K)',
          data: toVal(macroData.multi_factor.equity_monthly),
          borderColor: '#C4B68A',
          borderWidth: 1.5,
          pointRadius: 0,
          borderDash: [6, 3],
        },
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top', align: 'end' },
        tooltip: {
          callbacks: {
            title: ctx => {
              const d = ctx[0].label;
              return typeof d === 'object' ? d.toLocaleDateString('en-US', {year:'numeric',month:'short'}) : d;
            },
            label: ctx => `${ctx.dataset.label}: ${ctx.raw.toFixed(2)}×`
          }
        },
      },
      scales: {
        x: {
          type: 'time',
          time: { unit: 'year', displayFormats: { year: 'yyyy' } },
          grid: { color: PALETTE.gridLine },
          ticks: { maxTicksLimit: 12, font: { size: 10 } }
        },
        y: {
          type: 'logarithmic',
          grid: { color: PALETTE.gridLine },
          ticks: {
            callback: v => {
              if (v >= 1000) return v.toFixed(0) + '×';
              if (v >= 100) return v.toFixed(0) + '×';
              if (v >= 10) return v.toFixed(0) + '×';
              return v.toFixed(1) + '×';
            }
          }
        }
      }
    }
  });
}

function renderMacroPeriodTable() {
  const periods = ['ytd', '1y', '3y', '5y', '10y', '20y', 'since_inception'];
  const labels = {'ytd':'YTD','1y':'1 Year','3y':'3 Year','5y':'5 Year','10y':'10 Year','20y':'20 Year','since_inception':'Since Inception'};

  let html = `<table>
    <thead><tr><th>Period</th><th>Arki Macro</th><th>Macro Mini</th><th>Multi-Factor</th></tr></thead>
    <tbody>`;
  periods.forEach(p => {
    const c = macroData.combined.period_returns[p];
    const m = macroData.macro_mini.period_returns[p];
    const f = macroData.multi_factor.period_returns[p];
    const fmt = v => v !== null && v !== undefined ? `<span class="${v>=0?'td-positive':'td-negative'}">${v.toFixed(2)}%</span>` : '—';
    html += `<tr><td style="font-weight:600">${labels[p]}</td><td>${fmt(c)}</td><td>${fmt(m)}</td><td>${fmt(f)}</td></tr>`;
  });
  html += '</tbody></table>';
  document.getElementById('macro-period-table').innerHTML = html;
}

function renderMacroStatsTable() {
  const metrics = [
    ['Total Return', 'total_return', '%'], ['CAGR', 'cagr', '%'], ['Ann Vol', 'ann_vol', '%'],
    ['Sharpe', 'sharpe', ''], ['Sortino', 'sortino', ''], ['Calmar', 'calmar', ''],
    ['Max Drawdown', 'max_drawdown', '%'], ['Avg Drawdown', 'avg_drawdown', '%'],
    ['Skew', 'skew', ''], ['Kurtosis', 'kurtosis', ''],
    ['Hit Rate', 'hit_rate', '%'], ['Gain/Loss Ratio', 'gain_loss_ratio', ''],
    ['Profit Factor', 'profit_factor', ''],
    ['Best Month', 'best_month', '%'], ['Worst Month', 'worst_month', '%'],
  ];

  let html = `<table>
    <thead><tr><th>Metric</th><th>Arki Macro</th><th>Macro Mini</th><th>Multi-Factor</th></tr></thead>
    <tbody>`;
  metrics.forEach(([label, key, suffix]) => {
    const c = macroData.combined.stats[key];
    const m = macroData.macro_mini.stats[key];
    const f = macroData.multi_factor.stats[key];
    const fmt = v => v !== undefined ? v + suffix : '—';
    html += `<tr><td style="font-weight:500">${label}</td><td>${fmt(c)}</td><td>${fmt(m)}</td><td>${fmt(f)}</td></tr>`;
  });
  html += '</tbody></table>';
  document.getElementById('macro-stats-table').innerHTML = html;
}

function renderMacroAnnualTable() {
  const years = macroData.annual_returns;
  let html = `<table>
    <thead><tr><th>Year</th><th>Arki Macro</th><th>Macro Mini</th><th>Multi-Factor</th></tr></thead>
    <tbody>`;
  // Show in reverse order (most recent first)
  [...years].reverse().forEach(y => {
    const fmt = v => v !== null && v !== undefined ? `<span class="${v>=0?'td-positive':'td-negative'}">${v.toFixed(2)}%</span>` : '—';
    html += `<tr><td style="font-weight:600">${y.year}</td><td>${fmt(y.combined)}</td><td>${fmt(y.mini)}</td><td>${fmt(y.mf)}</td></tr>`;
  });
  html += '</tbody></table>';
  document.getElementById('macro-annual-table').innerHTML = html;
}

function renderMacroHeatmap() {
  const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const data = macroData.monthly_returns;
  const years = Object.keys(data).sort().reverse();

  function heatColor(val) {
    if (val === undefined || val === null) return 'background:#f8f4e8';
    const abs = Math.min(Math.abs(val), 10);
    const intensity = Math.round(40 + abs * 18);
    if (val >= 0) return `background:rgba(85,183,134,${intensity/100});color:${abs>4?'#fff':'#265844'}`;
    return `background:rgba(184,92,74,${intensity/100});color:${abs>4?'#fff':'#7a3322'}`;
  }

  let html = `<table class="heatmap-table">
    <thead><tr><th>Year</th>${monthNames.map(m => `<th>${m}</th>`).join('')}<th style="font-weight:700">Annual</th></tr></thead>
    <tbody>`;
  years.forEach(y => {
    const row = data[y];
    let yearTotal = 1;
    let cells = monthNames.map((_, i) => {
      const val = row[String(i+1)];
      if (val !== undefined) yearTotal *= (1 + val/100);
      const display = val !== undefined ? val.toFixed(1) : '';
      return `<td style="${heatColor(val)};text-align:center;font-size:11px;font-weight:500;padding:4px 6px">${display}</td>`;
    }).join('');
    const annRet = (yearTotal - 1) * 100;
    html += `<tr><td style="font-weight:700;padding:4px 8px">${y}</td>${cells}<td style="${heatColor(annRet)};text-align:center;font-weight:700;padding:4px 8px">${annRet.toFixed(1)}</td></tr>`;
  });
  html += '</tbody></table>';
  document.getElementById('macro-heatmap').innerHTML = html;
}

function renderMacroRollingSR() {
  const toDate = pts => pts.map(p => new Date(p[0]));
  const toVal = pts => pts.map(p => p[1]);
  const rs = macroData.rolling_sharpe_3y;

  destroyChart('macro-rolling-sr-chart');
  state.charts['macro-rolling-sr-chart'] = new Chart(document.getElementById('macro-rolling-sr-chart'), {
    type: 'line',
    data: {
      labels: toDate(rs.combined),
      datasets: [
        { label: 'Combined', data: toVal(rs.combined), borderColor: PALETTE.forest, borderWidth: 2, pointRadius: 0 },
        { label: 'Macro Mini', data: toVal(rs.mini), borderColor: PALETTE.green, borderWidth: 1.5, pointRadius: 0, borderDash: [4,2] },
        { label: 'Multi-Factor', data: toVal(rs.mf), borderColor: '#C4B68A', borderWidth: 1.5, pointRadius: 0, borderDash: [6,3] },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top', align: 'end' },
        tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.raw.toFixed(3)}` } },
      },
      scales: {
        x: { type: 'time', time: { unit: 'year' }, grid: { color: PALETTE.gridLine }, ticks: { maxTicksLimit: 10, font: { size: 10 } } },
        y: { grid: { color: PALETTE.gridLine }, ticks: { callback: v => v.toFixed(1) } }
      }
    }
  });
}

function renderMacroCorrelation() {
  const rc = macroData.rolling_correlation;
  if (!rc || rc.length === 0) return;

  destroyChart('macro-corr-chart');
  state.charts['macro-corr-chart'] = new Chart(document.getElementById('macro-corr-chart'), {
    type: 'line',
    data: {
      labels: rc.map(p => new Date(p[0])),
      datasets: [{
        label: 'Rolling 3Y Correlation',
        data: rc.map(p => p[1]),
        borderColor: PALETTE.forest,
        backgroundColor: PALETTE.forest15,
        fill: true,
        borderWidth: 1.5,
        pointRadius: 0,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => `ρ = ${ctx.raw.toFixed(3)}` } },
      },
      scales: {
        x: { type: 'time', time: { unit: 'year' }, grid: { color: PALETTE.gridLine }, ticks: { maxTicksLimit: 10, font: { size: 10 } } },
        y: { min: -0.5, max: 1, grid: { color: PALETTE.gridLine }, ticks: { callback: v => v.toFixed(1) } }
      }
    }
  });
}

function renderMacroDrawdown() {
  const dd = macroData.drawdown;

  destroyChart('macro-drawdown-chart');
  state.charts['macro-drawdown-chart'] = new Chart(document.getElementById('macro-drawdown-chart'), {
    type: 'line',
    data: {
      labels: dd.combined.map(p => new Date(p[0])),
      datasets: [
        { label: 'Combined', data: dd.combined.map(p => p[1] * 100), borderColor: PALETTE.forest, backgroundColor: PALETTE.forest15, fill: true, borderWidth: 1.5, pointRadius: 0 },
        { label: 'Macro Mini', data: dd.mini.map(p => p[1] * 100), borderColor: PALETTE.green, borderWidth: 1, pointRadius: 0, borderDash: [4,2] },
        { label: 'Multi-Factor', data: dd.mf.map(p => p[1] * 100), borderColor: '#C4B68A', borderWidth: 1, pointRadius: 0, borderDash: [6,3] },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top', align: 'end' } },
      scales: {
        x: { type: 'time', time: { unit: 'year' }, grid: { color: PALETTE.gridLine }, ticks: { maxTicksLimit: 10, font: { size: 10 } } },
        y: { grid: { color: PALETTE.gridLine }, ticks: { callback: v => v.toFixed(0) + '%' } }
      }
    }
  });
}


// ══════════════════════════════════════════════════════════════════
// SMALLER ARKI MACRO TAB (reuses macro helpers with different data/IDs)
// ══════════════════════════════════════════════════════════════════

let smallerMacroData = null;
let smallerMacroLoaded = false;

async function loadSmallerMacroData() {
  if (smallerMacroLoaded) return;
  try {
    const text = await loadFile('arki_macro_smaller.json');
    smallerMacroData = JSON.parse(text);
    smallerMacroLoaded = true;
    renderSmallerMacroTab();
  } catch (e) {
    console.warn('Smaller Macro data not found:', e.message);
  }
}

function renderSmallerMacroTab() {
  if (!smallerMacroData) return;
  const d = smallerMacroData;
  const prefix = 'smaller-macro';

  // KPIs
  const s = d.combined.stats, m = d.meta;
  const kpis = [
    { label: 'CAGR', value: s.cagr+'%', cls: 'positive', sub: `${s.years} years` },
    { label: 'Sharpe', value: s.sharpe, cls: '', sub: 'Monthly basis' },
    { label: 'Sortino', value: s.sortino, cls: '', sub: 'Downside adj.' },
    { label: 'Max Drawdown', value: s.max_drawdown+'%', cls: 'negative', sub: `Avg DD: ${s.avg_drawdown}%` },
    { label: 'Correlation', value: m.correlation, cls: '', sub: 'Mini vs MF' },
    { label: 'Total Capital', value: '$'+(m.total_capital/1000)+'K', cls: '', sub: `$${m.mini_capital/1000}K + $${m.mf_capital/1000}K` },
  ];
  document.getElementById(`${prefix}-kpi-strip`).innerHTML = kpis.map(k => `
    <div class="kpi"><div class="kpi__label">${k.label}</div><div class="kpi__value ${k.cls}">${k.value}</div><div class="kpi__sub">${k.sub}</div></div>
  `).join('');

  // Equity
  const toDate = pts => pts.map(p => new Date(p[0]));
  const toVal = pts => pts.map(p => p[1]);
  destroyChart(`${prefix}-equity-chart`);
  state.charts[`${prefix}-equity-chart`] = new Chart(document.getElementById(`${prefix}-equity-chart`), {
    type: 'line',
    data: {
      labels: toDate(d.combined.equity_monthly),
      datasets: [
        { label: d.meta.label, data: toVal(d.combined.equity_monthly), borderColor: PALETTE.forest, backgroundColor: PALETTE.forest15, fill: true, borderWidth: 2, pointRadius: 0 },
        { label: `Mini ($${m.mini_capital/1000}K)`, data: toVal(d.macro_mini.equity_monthly), borderColor: PALETTE.green, borderWidth: 1.5, pointRadius: 0, borderDash: [4,2] },
        { label: `MF ($${m.mf_capital/1000}K)`, data: toVal(d.multi_factor.equity_monthly), borderColor: '#C4B68A', borderWidth: 1.5, pointRadius: 0, borderDash: [6,3] },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top', align: 'end' }, tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.raw.toFixed(2)}×` } } },
      scales: {
        x: { type: 'time', time: { unit: 'year' }, grid: { color: PALETTE.gridLine }, ticks: { maxTicksLimit: 12, font: { size: 10 } } },
        y: { type: 'logarithmic', grid: { color: PALETTE.gridLine }, ticks: { callback: v => v >= 10 ? v.toFixed(0)+'×' : v.toFixed(1)+'×' } }
      }
    }
  });

  // Tables (reuse macro helpers with different element IDs)
  renderGenericPeriodTable(d, `${prefix}-period-table`);
  renderGenericStatsTable(d, `${prefix}-stats-table`);
  renderGenericAnnualTable(d, `${prefix}-annual-table`);
  renderGenericHeatmap(d, `${prefix}-heatmap`);

  // Rolling SR
  destroyChart(`${prefix}-rolling-sr-chart`);
  state.charts[`${prefix}-rolling-sr-chart`] = new Chart(document.getElementById(`${prefix}-rolling-sr-chart`), {
    type: 'line',
    data: {
      labels: toDate(d.rolling_sharpe_3y.combined),
      datasets: [
        { label: 'Combined', data: toVal(d.rolling_sharpe_3y.combined), borderColor: PALETTE.forest, borderWidth: 2, pointRadius: 0 },
        { label: 'Mini', data: toVal(d.rolling_sharpe_3y.mini), borderColor: PALETTE.green, borderWidth: 1.5, pointRadius: 0, borderDash: [4,2] },
        { label: 'MF', data: toVal(d.rolling_sharpe_3y.mf), borderColor: '#C4B68A', borderWidth: 1.5, pointRadius: 0, borderDash: [6,3] },
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top', align: 'end' } },
      scales: { x: { type: 'time', time: { unit: 'year' }, grid: { color: PALETTE.gridLine } }, y: { grid: { color: PALETTE.gridLine }, ticks: { callback: v => v.toFixed(1) } } } }
  });

  // Correlation
  const rc = d.rolling_correlation;
  if (rc && rc.length > 0) {
    destroyChart(`${prefix}-corr-chart`);
    state.charts[`${prefix}-corr-chart`] = new Chart(document.getElementById(`${prefix}-corr-chart`), {
      type: 'line',
      data: { labels: rc.map(p => new Date(p[0])), datasets: [{ label: 'ρ', data: rc.map(p => p[1]), borderColor: PALETTE.forest, backgroundColor: PALETTE.forest15, fill: true, borderWidth: 1.5, pointRadius: 0 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
        scales: { x: { type: 'time', time: { unit: 'year' }, grid: { color: PALETTE.gridLine } }, y: { min: -0.5, max: 1, grid: { color: PALETTE.gridLine } } } }
    });
  }

  // Drawdown
  destroyChart(`${prefix}-drawdown-chart`);
  state.charts[`${prefix}-drawdown-chart`] = new Chart(document.getElementById(`${prefix}-drawdown-chart`), {
    type: 'line',
    data: {
      labels: d.drawdown.combined.map(p => new Date(p[0])),
      datasets: [
        { label: 'Combined', data: d.drawdown.combined.map(p => p[1]*100), borderColor: PALETTE.forest, backgroundColor: PALETTE.forest15, fill: true, borderWidth: 1.5, pointRadius: 0 },
        { label: 'Mini', data: d.drawdown.mini.map(p => p[1]*100), borderColor: PALETTE.green, borderWidth: 1, pointRadius: 0, borderDash: [4,2] },
        { label: 'MF', data: d.drawdown.mf.map(p => p[1]*100), borderColor: '#C4B68A', borderWidth: 1, pointRadius: 0, borderDash: [6,3] },
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top', align: 'end' } },
      scales: { x: { type: 'time', time: { unit: 'year' }, grid: { color: PALETTE.gridLine } }, y: { grid: { color: PALETTE.gridLine }, ticks: { callback: v => v.toFixed(0)+'%' } } } }
  });
}

// ── Generic renderers (shared by both macro tabs) ──

function renderGenericPeriodTable(d, elId) {
  const periods = ['ytd','1y','3y','5y','10y','20y','since_inception'];
  const labels = {ytd:'YTD','1y':'1 Year','3y':'3 Year','5y':'5 Year','10y':'10 Year','20y':'20 Year',since_inception:'Since Inception'};
  let html = `<table><thead><tr><th>Period</th><th>Combined</th><th>Macro Mini</th><th>Multi-Factor</th></tr></thead><tbody>`;
  periods.forEach(p => {
    const fmt = v => v !== null && v !== undefined ? `<span class="${v>=0?'td-positive':'td-negative'}">${v.toFixed(2)}%</span>` : '—';
    html += `<tr><td style="font-weight:600">${labels[p]}</td><td>${fmt(d.combined.period_returns[p])}</td><td>${fmt(d.macro_mini.period_returns[p])}</td><td>${fmt(d.multi_factor.period_returns[p])}</td></tr>`;
  });
  html += '</tbody></table>';
  document.getElementById(elId).innerHTML = html;
}

function renderGenericStatsTable(d, elId) {
  const metrics = [['Total Return','total_return','%'],['CAGR','cagr','%'],['Ann Vol','ann_vol','%'],['Sharpe','sharpe',''],['Sortino','sortino',''],['Calmar','calmar',''],['Max Drawdown','max_drawdown','%'],['Avg Drawdown','avg_drawdown','%'],['Skew','skew',''],['Kurtosis','kurtosis',''],['Hit Rate','hit_rate','%'],['Gain/Loss','gain_loss_ratio',''],['Profit Factor','profit_factor',''],['Best Month','best_month','%'],['Worst Month','worst_month','%']];
  let html = `<table><thead><tr><th>Metric</th><th>Combined</th><th>Macro Mini</th><th>Multi-Factor</th></tr></thead><tbody>`;
  metrics.forEach(([label,key,suf]) => {
    const fmt = v => v !== undefined ? v+suf : '—';
    html += `<tr><td style="font-weight:500">${label}</td><td>${fmt(d.combined.stats[key])}</td><td>${fmt(d.macro_mini.stats[key])}</td><td>${fmt(d.multi_factor.stats[key])}</td></tr>`;
  });
  html += '</tbody></table>';
  document.getElementById(elId).innerHTML = html;
}

function renderGenericAnnualTable(d, elId) {
  let html = `<table><thead><tr><th>Year</th><th>Combined</th><th>Mini</th><th>MF</th></tr></thead><tbody>`;
  [...d.annual_returns].reverse().forEach(y => {
    const fmt = v => v !== null && v !== undefined ? `<span class="${v>=0?'td-positive':'td-negative'}">${v.toFixed(2)}%</span>` : '—';
    html += `<tr><td style="font-weight:600">${y.year}</td><td>${fmt(y.combined)}</td><td>${fmt(y.mini)}</td><td>${fmt(y.mf)}</td></tr>`;
  });
  html += '</tbody></table>';
  document.getElementById(elId).innerHTML = html;
}

function renderGenericHeatmap(d, elId) {
  const mns = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const data = d.monthly_returns;
  const years = Object.keys(data).sort().reverse();
  function hc(v) {
    if (v === undefined || v === null) return 'background:#f8f4e8';
    const a = Math.min(Math.abs(v),10), i = Math.round(40+a*18);
    return v >= 0 ? `background:rgba(85,183,134,${i/100});color:${a>4?'#fff':'#265844'}` : `background:rgba(184,92,74,${i/100});color:${a>4?'#fff':'#7a3322'}`;
  }
  let html = `<table class="heatmap-table"><thead><tr><th>Year</th>${mns.map(m=>`<th>${m}</th>`).join('')}<th style="font-weight:700">Annual</th></tr></thead><tbody>`;
  years.forEach(y => {
    const row = data[y]; let yt = 1;
    let cells = mns.map((_,i) => { const v = row[String(i+1)]; if (v !== undefined) yt *= (1+v/100); return `<td style="${hc(v)};text-align:center;font-size:11px;font-weight:500;padding:4px 6px">${v !== undefined ? v.toFixed(1) : ''}</td>`; }).join('');
    const ar = (yt-1)*100;
    html += `<tr><td style="font-weight:700;padding:4px 8px">${y}</td>${cells}<td style="${hc(ar)};text-align:center;font-weight:700;padding:4px 8px">${ar.toFixed(1)}</td></tr>`;
  });
  html += '</tbody></table>';
  document.getElementById(elId).innerHTML = html;
}


// ══════════════════════════════════════════════════════════════════
// MACRO COMPARISON TAB
// ══════════════════════════════════════════════════════════════════

let compareData = null;
let compareLoaded = false;

async function loadCompareData() {
  if (compareLoaded) return;
  try {
    const text = await loadFile('arki_macro_comparison.json');
    compareData = JSON.parse(text);
    compareLoaded = true;
    renderCompareTab();
  } catch (e) {
    console.warn('Comparison data not found:', e.message);
  }
}

function renderCompareTab() {
  if (!compareData) return;
  const orig = compareData.scenarios.original;
  const small = compareData.scenarios.smaller;
  const toDate = pts => pts.map(p => new Date(p[0]));
  const toVal = pts => pts.map(p => p[1]);

  // Comparison table
  const metrics = [
    ['Total Capital', v => '$'+(v.total_capital/1000)+'K'],
    ['Mini Capital', v => '$'+(v.mini_capital/1000)+'K'],
    ['MF Capital', v => '$'+(v.mf_capital/1000)+'K'],
    ['CAGR', v => v.stats.cagr+'%'],
    ['Sharpe', v => v.stats.sharpe],
    ['Sortino', v => v.stats.sortino],
    ['Max Drawdown', v => v.stats.max_drawdown+'%'],
    ['Avg Drawdown', v => v.stats.avg_drawdown+'%'],
    ['Calmar', v => v.stats.calmar],
    ['Ann Vol', v => v.stats.ann_vol+'%'],
    ['Hit Rate', v => v.stats.hit_rate+'%'],
    ['Correlation', v => v.correlation],
    ['Best Month', v => v.stats.best_month+'%'],
    ['Worst Month', v => v.stats.worst_month+'%'],
    ['Profit Factor', v => v.stats.profit_factor],
  ];

  let html = `<table><thead><tr><th>Metric</th><th>Arki Macro ($300K)</th><th>Smaller Macro ($250K)</th><th>Delta</th></tr></thead><tbody>`;
  metrics.forEach(([label, fn]) => {
    const ov = fn(orig), sv = fn(small);
    const oParsed = parseFloat(ov), sParsed = parseFloat(sv);
    let delta = '';
    if (!isNaN(oParsed) && !isNaN(sParsed)) {
      const d = sParsed - oParsed;
      const sign = d >= 0 ? '+' : '';
      const cls = (label.includes('Drawdown') || label === 'Ann Vol') ? (d <= 0 ? 'td-positive' : 'td-negative') : (d >= 0 ? 'td-positive' : 'td-negative');
      delta = `<span class="${cls}">${sign}${d.toFixed(2)}</span>`;
    }
    html += `<tr><td style="font-weight:600">${label}</td><td>${ov}</td><td>${sv}</td><td>${delta}</td></tr>`;
  });
  html += '</tbody></table>';
  document.getElementById('macro-compare-table').innerHTML = html;

  // Equity overlay
  destroyChart('macro-compare-equity-chart');
  state.charts['macro-compare-equity-chart'] = new Chart(document.getElementById('macro-compare-equity-chart'), {
    type: 'line',
    data: {
      labels: toDate(orig.equity_monthly),
      datasets: [
        { label: 'Arki Macro ($300K)', data: toVal(orig.equity_monthly), borderColor: PALETTE.forest, borderWidth: 2, pointRadius: 0 },
        { label: 'Smaller Macro ($250K)', data: toVal(small.equity_monthly), borderColor: PALETTE.green, borderWidth: 2, borderDash: [6,3], pointRadius: 0 },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top', align: 'end' }, tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.raw.toFixed(2)}×` } } },
      scales: {
        x: { type: 'time', time: { unit: 'year' }, grid: { color: PALETTE.gridLine }, ticks: { maxTicksLimit: 12, font: { size: 10 } } },
        y: { type: 'logarithmic', grid: { color: PALETTE.gridLine }, ticks: { callback: v => v >= 10 ? v.toFixed(0)+'×' : v.toFixed(1)+'×' } }
      }
    }
  });

  // Period returns comparison
  const periods = ['ytd','1y','3y','5y','10y','20y','since_inception'];
  const plabels = {ytd:'YTD','1y':'1Y','3y':'3Y','5y':'5Y','10y':'10Y','20y':'20Y',since_inception:'SI'};
  let phtml = `<table><thead><tr><th>Period</th><th>Arki Macro</th><th>Smaller Macro</th><th>Delta</th></tr></thead><tbody>`;
  periods.forEach(p => {
    const ov = orig.period_returns[p], sv = small.period_returns[p];
    const fmt = v => v !== null && v !== undefined ? `<span class="${v>=0?'td-positive':'td-negative'}">${v.toFixed(2)}%</span>` : '—';
    let delta = '';
    if (ov != null && sv != null) {
      const d = sv - ov;
      delta = `<span class="${d>=0?'td-positive':'td-negative'}">${d>=0?'+':''}${d.toFixed(2)}%</span>`;
    }
    phtml += `<tr><td style="font-weight:600">${plabels[p]}</td><td>${fmt(ov)}</td><td>${fmt(sv)}</td><td>${delta}</td></tr>`;
  });
  phtml += '</tbody></table>';
  document.getElementById('macro-compare-period-table').innerHTML = phtml;

  // Drawdown overlay
  destroyChart('macro-compare-drawdown-chart');
  state.charts['macro-compare-drawdown-chart'] = new Chart(document.getElementById('macro-compare-drawdown-chart'), {
    type: 'line',
    data: {
      labels: orig.drawdown.map(p => new Date(p[0])),
      datasets: [
        { label: 'Arki Macro', data: orig.drawdown.map(p => p[1]*100), borderColor: PALETTE.forest, backgroundColor: PALETTE.forest15, fill: true, borderWidth: 1.5, pointRadius: 0 },
        { label: 'Smaller Macro', data: small.drawdown.map(p => p[1]*100), borderColor: PALETTE.green, borderWidth: 1.5, pointRadius: 0, borderDash: [6,3] },
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top', align: 'end' } },
      scales: { x: { type: 'time', time: { unit: 'year' }, grid: { color: PALETTE.gridLine } }, y: { grid: { color: PALETTE.gridLine }, ticks: { callback: v => v.toFixed(0)+'%' } } } }
  });
}


// ══════════════════════════════════════════════════════════════════
// UNIVERSE INFO TAB
// ══════════════════════════════════════════════════════════════════

let universeData = null;
let universeLoaded = false;

async function loadUniverseData() {
  if (universeLoaded) return;
  try {
    const text = await loadFile('arki_universe_info.json');
    universeData = JSON.parse(text);
    universeLoaded = true;
    renderUniverseTab();
  } catch (e) {
    console.warn('Universe data not found:', e.message);
  }
}

function renderUniverseTab() {
  if (!universeData || universeData.length === 0) return;
  const fmt = v => v !== null && v !== undefined ? v.toLocaleString() : '—';
  const ccySymbol = { USD: '$', EUR: '€', GBP: '£', JPY: '¥', AUD: 'A$', CAD: 'C$', CHF: 'CHF ', CNY: '¥', HKD: 'HK$', SGD: 'S$', MXP: 'MX$', BRL: 'R$', KRW: '₩' };
  const fmtNominal = (v, ccy) => {
    if (v === null || v === undefined) return '—';
    const sym = ccySymbol[ccy] || (ccy ? ccy + ' ' : '$');
    return sym + Math.round(v).toLocaleString();
  };

  // Sort by asset class then instrument
  const sorted = [...universeData].sort((a,b) => (a.asset_class+a.instrument).localeCompare(b.asset_class+b.instrument));

  let html = `<table>
    <thead><tr>
      <th>Instrument</th><th>Description</th><th>Asset Class</th><th>CCY</th>
      <th style="text-align:right">Point Size</th><th style="text-align:right">Latest Price</th>
      <th style="text-align:right">Nominal Value (1 contract)</th>
      <th style="text-align:center">Universe Tier</th>
    </tr></thead><tbody>`;

  let prevClass = '';
  sorted.forEach(r => {
    if (r.asset_class !== prevClass) {
      html += `<tr><td colspan="8" style="background:var(--forest,#265844);color:#fff;font-weight:700;padding:6px 12px;font-size:12px">${r.asset_class || 'Unknown'}</td></tr>`;
      prevClass = r.asset_class;
    }
    const nomColor = r.nominal_value && r.nominal_value > 100000 ? 'color:#B85C4A;font-weight:600' : '';
    
    // Badges for universe tiers
    const badges = [];
    if (r.in_13) badges.push('<span style="background:#55B786;color:#fff;padding:2px 6px;border-radius:4px;font-size:10px;margin-right:4px">$100K (13)</span>');
    if (r.in_25) badges.push('<span style="background:#265844;color:#FFF;padding:2px 6px;border-radius:4px;font-size:10px">$250K (25)</span>');

    html += `<tr>
      <td style="font-weight:600;font-family:var(--font-mono,monospace);font-size:12px">${r.instrument}</td>
      <td style="font-size:12px">${r.description}</td>
      <td style="font-size:12px">${r.asset_class}</td>
      <td style="font-size:12px;text-align:center">${r.currency}</td>
      <td style="text-align:right;font-family:var(--font-mono);font-size:12px">${fmt(r.pointsize)}</td>
      <td style="text-align:right;font-family:var(--font-mono);font-size:12px">${fmt(r.latest_price)}</td>
      <td style="text-align:right;font-family:var(--font-mono);font-size:12px;${nomColor}">${fmtNominal(r.nominal_value, r.currency)}</td>
      <td style="text-align:center;white-space:nowrap">${badges.join('')}</td>
    </tr>`;
  });
  html += '</tbody></table>';
  document.getElementById('universe-table').innerHTML = html;
}


// ── Tab Navigation ──
// ══════════════════════════════════════════════════════════════════
// FACTOR SR DECOMPOSITION TAB (Method B)
// ══════════════════════════════════════════════════════════════════

function renderFactorComboTab() {
  if (!state.factorReturns || state.factorReturns.length === 0) {
    document.getElementById('factor-combo-kpis').innerHTML = '<p style="color:var(--text-muted);padding:16px">No factor_returns.csv data available for this run.</p>';
    return;
  }

  const rows = state.factorReturns;
  const cols = Object.keys(rows[0]).filter(k => k !== 'index' && k !== '');

  // Classify rules into 3 groups
  const groups = {
    'Trend (EWMAC)':          cols.filter(c => c.startsWith('momentum')),
    'Carry':                  cols.filter(c => c.startsWith('carry')),
    'CS Momentum':            cols.filter(c => c.startsWith('relmomentum')),
  };

  // Compute equal-weighted group daily returns
  function groupReturn(row, keys) {
    const vals = keys.map(k => parseFloat(row[k]) || 0).filter(v => !isNaN(v));
    return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
  }

  const trendRets  = rows.map(r => groupReturn(r, groups['Trend (EWMAC)']));
  const carryRets  = rows.map(r => groupReturn(r, groups['Carry']));
  const csmomRets  = rows.map(r => groupReturn(r, groups['CS Momentum']));
  const dates      = rows.map(r => r.index || r['']);

  // 4 cumulative combinations (equal-weighted across included groups)
  const combos = [
    { label: 'Trend only',             weights: [1, 0, 0] },
    { label: 'Trend + Carry',          weights: [0.5, 0.5, 0] },
    { label: 'Trend + Carry + CSMom',  weights: [1/3, 1/3, 1/3] },
  ];

  function comboSeries(w) {
    return rows.map((_, i) => w[0]*trendRets[i] + w[1]*carryRets[i] + w[2]*csmomRets[i]);
  }

  function annualStats(rets) {
    const mean = rets.reduce((a, b) => a + b, 0) / rets.length;
    const variance = rets.reduce((s, r) => s + (r - mean) ** 2, 0) / rets.length;
    const std = Math.sqrt(variance);
    const annMean = mean * 256;
    const annStd = std * Math.sqrt(256);
    const sr = annStd > 0 ? annMean / annStd : 0;
    const cumRets = rets.reduce((acc, r) => { acc.push((acc[acc.length-1] || 1) * (1 + r/100)); return acc; }, []);
    const maxDD = cumRets.reduce((state, v, i) => {
      const peak = Math.max(...cumRets.slice(0, i + 1));
      return Math.min(state, (v - peak) / peak * 100);
    }, 0);
    return { annMean: annMean.toFixed(1), annStd: annStd.toFixed(1), sr: sr.toFixed(3), maxDD: maxDD.toFixed(1), cumRets };
  }

  const comboData = combos.map(c => ({ ...c, rets: comboSeries(c.weights), ...annualStats(comboSeries(c.weights)) }));

  const COLORS = [PALETTE.charcoal30 || '#888', PALETTE.green || '#55B786', PALETTE.forest || '#265844'];

  // KPI strip
  const kpiEl = document.getElementById('factor-combo-kpis');
  if (kpiEl) {
    const lastSR = comboData[comboData.length - 1];
    const firstSR = comboData[0];
    const srLift = (parseFloat(lastSR.sr) - parseFloat(firstSR.sr)).toFixed(3);
    kpiEl.innerHTML = [
      ...comboData.map((c, i) => `<div class="kpi"><div class="kpi__label">${c.label}</div><div class="kpi__value" style="color:${COLORS[i]}">${c.sr}</div><div class="kpi__sub">Sharpe Ratio</div></div>`),
      `<div class="kpi"><div class="kpi__label">SR Lift (3-factor vs Trend)</div><div class="kpi__value positive">+${srLift}</div><div class="kpi__sub">Diversification gain</div></div>`,
    ].join('');
  }

  // Equity curve chart
  destroyChart('factor-combo-equity-chart');
  const ecCtx = document.getElementById('factor-combo-equity-chart');
  if (ecCtx) {
    state.charts['factor-combo-equity-chart'] = new Chart(ecCtx, {
      type: 'line',
      data: {
        labels: dates,
        datasets: comboData.map((c, i) => ({
          label: c.label,
          data: c.cumRets.map(v => ((v - 1) * 100).toFixed(2)),
          borderColor: COLORS[i],
          backgroundColor: i === 2 ? PALETTE.forest15 || '#26584415' : 'transparent',
          fill: i === 2,
          borderWidth: i === 2 ? 2.5 : 1.5,
          borderDash: i === 0 ? [6,3] : i === 1 ? [3,2] : [],
          pointRadius: 0,
        }))
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: 'top', align: 'end' },
          tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.raw}%` } },
        },
        scales: {
          x: { grid: { color: PALETTE.gridLine }, ticks: { maxTicksLimit: 12, font: { size: 10 } } },
          y: { grid: { color: PALETTE.gridLine }, ticks: { callback: v => v + '%' } }
        }
      }
    });
  }

  // SR bar chart
  destroyChart('factor-combo-sr-chart');
  const srCtx = document.getElementById('factor-combo-sr-chart');
  if (srCtx) {
    state.charts['factor-combo-sr-chart'] = new Chart(srCtx, {
      type: 'bar',
      data: {
        labels: comboData.map(c => c.label),
        datasets: [{
          label: 'Sharpe Ratio',
          data: comboData.map(c => parseFloat(c.sr)),
          backgroundColor: COLORS,
          borderRadius: 6,
          barThickness: 40,
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => `SR: ${ctx.raw.toFixed(3)}` } } },
        scales: {
          x: { grid: { display: false } },
          y: { grid: { color: PALETTE.gridLine }, title: { display: true, text: 'Sharpe Ratio' }, beginAtZero: true }
        }
      }
    });
  }

  // Correlation matrix table
  const corrEl = document.getElementById('factor-combo-corr-table');
  if (corrEl) {
    const series = [trendRets, carryRets, csmomRets];
    const names = ['Trend', 'Carry', 'CS Momentum'];
    function corr(a, b) {
      const n = Math.min(a.length, b.length);
      const ma = a.slice(0, n).reduce((s, v) => s + v, 0) / n;
      const mb = b.slice(0, n).reduce((s, v) => s + v, 0) / n;
      const cov = a.slice(0, n).reduce((s, v, i) => s + (v - ma) * (b[i] - mb), 0) / n;
      const sa = Math.sqrt(a.slice(0, n).reduce((s, v) => s + (v - ma) ** 2, 0) / n);
      const sb = Math.sqrt(b.slice(0, n).reduce((s, v) => s + (v - mb) ** 2, 0) / n);
      return sa && sb ? cov / (sa * sb) : 0;
    }
    let html = `<table><thead><tr><th></th>${names.map(n => `<th>${n}</th>`).join('')}</tr></thead><tbody>`;
    series.forEach((row, i) => {
      html += `<tr><td style="font-weight:600">${names[i]}</td>`;
      series.forEach((col, j) => {
        const v = corr(row, col);
        const bg = i === j ? 'background:#26584418' : v > 0.3 ? 'background:#B85C4A22' : v < -0.1 ? 'background:#55B78622' : '';
        html += `<td style="text-align:center;${bg}">${v.toFixed(3)}</td>`;
      });
      html += '</tr>';
    });
    html += '</tbody></table>';
    corrEl.innerHTML = html;
  }

  // Rolling 3Y Sharpe
  destroyChart('factor-combo-rolling-sr-chart');
  const rCtx = document.getElementById('factor-combo-rolling-sr-chart');
  if (rCtx) {
    const window = 756; // ~3 years trading days
    function rollingSR(rets, w) {
      return rets.map((_, i) => {
        if (i < w) return null;
        const slice = rets.slice(i - w, i);
        const mean = slice.reduce((a, b) => a + b, 0) / w;
        const std = Math.sqrt(slice.reduce((s, v) => s + (v - mean) ** 2, 0) / w);
        return std > 0 ? (mean / std) * Math.sqrt(256) : null;
      });
    }
    state.charts['factor-combo-rolling-sr-chart'] = new Chart(rCtx, {
      type: 'line',
      data: {
        labels: dates,
        datasets: comboData.map((c, i) => ({
          label: c.label,
          data: rollingSR(c.rets, window),
          borderColor: COLORS[i],
          borderWidth: i === 2 ? 2 : 1.5,
          borderDash: i === 0 ? [6, 3] : i === 1 ? [3, 2] : [],
          pointRadius: 0,
          spanGaps: false,
        }))
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'top', align: 'end' }, tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.raw?.toFixed(3) ?? ''}` } } },
        scales: {
          x: { grid: { color: PALETTE.gridLine }, ticks: { maxTicksLimit: 10, font: { size: 10 } } },
          y: { grid: { color: PALETTE.gridLine }, title: { display: true, text: '3Y Rolling Sharpe' } }
        }
      }
    });
  }
}

document.querySelectorAll('.tab-nav__item').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab-nav__item').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');

    // Lazy-load data per tab
    if (tab.dataset.tab === 'macro' && !macroLoaded) loadMacroData();
    if (tab.dataset.tab === 'smaller-macro' && !smallerMacroLoaded) loadSmallerMacroData();
    if (tab.dataset.tab === 'macro-compare' && !compareLoaded) loadCompareData();
    if (tab.dataset.tab === 'universe' && !universeLoaded) loadUniverseData();
    if (tab.dataset.tab === 'sweep') renderSweep();
    if (tab.dataset.tab === 'factor-combo') renderFactorComboTab();
  });
});

// ── Init ──
loadData();
