/* GoldenHandQuant 投研驾驶舱 — 原生 JS, 无构建链 (设计 D1) */
"use strict";

const $ = (sel) => document.querySelector(sel);
const API = "/api/research";

// ---------- 基础设施 ----------

async function fetchJSON(url) {
  const resp = await fetch(url);
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`${resp.status} ${url}: ${body.slice(0, 200)}`);
  }
  return resp.json();
}

function showError(msg) {
  const el = $("#error-banner");
  el.textContent = `⚠ ${msg}`;
  el.classList.remove("hidden");
}

function clearError() {
  $("#error-banner").classList.add("hidden");
}

// ---------- 页签 ----------

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $(`#tab-${btn.dataset.tab}`).classList.add("active");
    location.hash = btn.dataset.tab;
    if (btn.dataset.tab === "explorer") resizeCharts();
    if (btn.dataset.tab === "backtests") loadBacktests().catch((e) => showError(e.message));
    setLivePolling(btn.dataset.tab === "live");
  });
});

// ---------- 数据资产 ----------

const TABLE_LABELS = {
  instruments: "股票池",
  bars: "日线行情",
  fundamental_snapshots: "基本面快照",
  stock_features: "截面特征",
};

async function loadOverview() {
  const data = await fetchJSON(`${API}/overview`);
  $("#db-path").textContent = data.db_path;
  $("#feature-version").textContent = data.feature_version;
  $("#meta").textContent = data.db_exists
    ? `判决轮次 ${data.verdict_runs} · 特征版本 v${data.feature_version}`
    : "数据库不存在";

  const cards = $("#overview-cards");
  cards.innerHTML = "";
  let totalRows = 0;
  for (const [table, s] of Object.entries(data.tables)) {
    totalRows += s.rows;
    const range = s.min_date ? `${s.min_date} ~ ${s.max_date}` : "无数据";
    cards.insertAdjacentHTML(
      "beforeend",
      `<div class="card">
         <h3>${TABLE_LABELS[table] || table}</h3>
         <div class="big">${s.rows.toLocaleString()}</div>
         <div class="dim">${s.symbols.toLocaleString()} 只标的 · ${range}</div>
       </div>`
    );
  }
  $("#overview-empty").classList.toggle("hidden", totalRows > 0);
}

// ---------- 因子判决 ----------

const GATES = {
  ic_mean: (v) => v >= 0.02,
  ir: (v) => v >= 0.3,
  monotonicity_score: (v) => v >= 0.6,
  long_short_return: (v) => v > 0,
  oos_long_short_return: (v) => v > 0,
};

function gateCell(name, value, fmt) {
  if (value === null || value === undefined) return `<td class="gate-na">-</td>`;
  const cls = name in GATES ? (GATES[name](value) ? "gate-good" : "gate-bad") : "";
  return `<td class="${cls}">${fmt(value)}</td>`;
}

const f4 = (v) => v.toFixed(4);
const f3 = (v) => v.toFixed(3);
const f2 = (v) => v.toFixed(2);
const pct = (v) => `${(v * 100).toFixed(2)}%`;

let verdictRuns = [];

async function loadVerdicts() {
  const data = await fetchJSON(`${API}/verdicts`);
  verdictRuns = data.runs;
  const select = $("#run-select");
  select.innerHTML = "";
  $("#verdicts-empty").classList.toggle("hidden", verdictRuns.length > 0);
  verdictRuns.forEach((run, i) => {
    select.insertAdjacentHTML(
      "beforeend",
      `<option value="${i}">${run.run_id}（${run.created_at.slice(0, 19)}）</option>`
    );
  });
  select.onchange = () => renderRun(verdictRuns[Number(select.value)]);
  if (verdictRuns.length) renderRun(verdictRuns[0]);
}

function renderRun(run) {
  const p = run.params || {};
  $("#run-params").textContent =
    `${p.start || "?"} → ${p.end || "?"} · 切分 ${p.split || "无"} · ` +
    `${p.rebalance_days || 1} 日调仓 · ${p.universe_count || "?"} 只 · 特征 v${p.feature_version || "?"}`;

  const tbody = $("#verdict-table tbody");
  tbody.innerHTML = "";
  for (const f of run.factors) {
    const badge = f.passed
      ? `<span class="badge pass">PASS</span>`
      : `<span class="badge fail">FAIL</span>`;
    tbody.insertAdjacentHTML(
      "beforeend",
      `<tr>
         <td>${f.factor_id}</td><td>${f.factor_name || ""}</td>
         <td><code>${f.expression || ""}</code></td>
         ${gateCell("ic_mean", f.ic_mean, f4)}
         ${gateCell("ir", f.ir, f3)}
         ${gateCell("ic_positive_rate", f.ic_positive_rate, pct)}
         ${gateCell("monotonicity_score", f.monotonicity_score, f2)}
         ${gateCell("long_short_return", f.long_short_return, pct)}
         ${gateCell("oos_ic_mean", f.oos_ic_mean, f4)}
         ${gateCell("oos_ir", f.oos_ir, f3)}
         ${gateCell("oos_long_short_return", f.oos_long_short_return, pct)}
         <td>${f.score != null ? f.score.toFixed(0) : "-"}（${f.grade || "-"}）</td>
         <td>${badge}</td>
       </tr>
       <tr class="reasons-row"><td colspan="13">${(f.reasons || []).join(" ｜ ")}</td></tr>`
    );
  }
}

// ---------- 个股查看 ----------

let klineChart = null;
let featureChart = null;
const DEFAULT_FEATURES = ["return_20d", "volatility_20d"];
const FEATURE_CHOICES = [
  "return_5d", "return_20d", "return_60d", "volatility_20d", "volatility_60d",
  "turnover_rate", "avg_turnover_20d", "rsi_14", "macd", "ma_20",
  "skewness_20d", "illiquidity_20d", "obv_slope_20d",
];

function initFeaturePicker() {
  const box = $("#feature-picker");
  box.innerHTML = "<span style='color:var(--text-dim)'>特征:</span>";
  for (const name of FEATURE_CHOICES) {
    const checked = DEFAULT_FEATURES.includes(name) ? "checked" : "";
    box.insertAdjacentHTML(
      "beforeend",
      `<label><input type="checkbox" value="${name}" ${checked}>${name}</label>`
    );
  }
  box.querySelectorAll("input").forEach((cb) =>
    cb.addEventListener("change", () => loadFeatures())
  );
}

function pickedSymbol() {
  return ($("#symbol-input").value || "").split(/\s/)[0].trim();
}

function rangeParams() {
  const params = new URLSearchParams();
  if ($("#start-input").value) params.set("start", $("#start-input").value);
  if ($("#end-input").value) params.set("end", $("#end-input").value);
  return params;
}

async function loadKline() {
  const symbol = pickedSymbol();
  if (!symbol) return;
  const data = await fetchJSON(`${API}/bars/${symbol}?${rangeParams()}`);
  if (!klineChart) klineChart = echarts.init($("#kline-chart"), "dark");
  klineChart.setOption({
    backgroundColor: "transparent",
    animation: false,
    title: { text: `${symbol} 前复权日线`, textStyle: { fontSize: 13 } },
    tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    grid: [
      { left: 60, right: 20, top: 40, height: "55%" },
      { left: 60, right: 20, top: "72%", height: "18%" },
    ],
    xAxis: [
      { type: "category", data: data.dates, gridIndex: 0 },
      { type: "category", data: data.dates, gridIndex: 1, axisLabel: { show: false } },
    ],
    yAxis: [
      { scale: true, gridIndex: 0 },
      { gridIndex: 1, axisLabel: { show: false }, splitLine: { show: false } },
    ],
    dataZoom: [{ type: "inside", xAxisIndex: [0, 1] }, { type: "slider", xAxisIndex: [0, 1] }],
    series: [
      {
        name: symbol, type: "candlestick", data: data.ohlc,
        itemStyle: { color: "#f85149", color0: "#3fb950",
                     borderColor: "#f85149", borderColor0: "#3fb950" },
      },
      { name: "成交量", type: "bar", data: data.volume, xAxisIndex: 1, yAxisIndex: 1,
        itemStyle: { color: "#4d9fff55" } },
    ],
  }, true);
}

async function loadFeatures() {
  const symbol = pickedSymbol();
  if (!symbol) return;
  const names = [...document.querySelectorAll("#feature-picker input:checked")]
    .map((cb) => cb.value);
  if (!names.length) return;
  const params = rangeParams();
  params.set("names", names.join(","));
  const data = await fetchJSON(`${API}/features/${symbol}?${params}`);
  if (!featureChart) featureChart = echarts.init($("#feature-chart"), "dark");
  featureChart.setOption({
    backgroundColor: "transparent",
    animation: false,
    title: { text: `${symbol} 截面特征（T-1 信息口径）`, textStyle: { fontSize: 13 } },
    tooltip: { trigger: "axis" },
    legend: { top: 4, right: 10, textStyle: { fontSize: 11 } },
    grid: { left: 60, right: 20, top: 40, bottom: 40 },
    xAxis: { type: "category", data: data.dates },
    yAxis: { type: "value", scale: true },
    dataZoom: [{ type: "inside" }],
    series: names.map((n) => ({
      name: n, type: "line", data: data.series[n],
      showSymbol: false, connectNulls: false,
    })),
  }, true);
}

function resizeCharts() {
  setTimeout(() => {
    if (klineChart) klineChart.resize();
    if (featureChart) featureChart.resize();
    if (btChart) btChart.resize();
    if (liveEquityChart) liveEquityChart.resize();
  }, 0);
}

// ---------- 回测 ----------

let btChart = null;
let btRuns = [];

async function loadBacktests() {
  const data = await fetchJSON(`${API}/backtests`);
  btRuns = data.runs;
  $("#bt-empty").classList.toggle("hidden", btRuns.length > 0);
  const select = $("#bt-run-select");
  select.innerHTML = "";
  btRuns.forEach((run, i) => {
    const names = run.strategies.map((s) => s.strategy).join(", ");
    select.insertAdjacentHTML(
      "beforeend",
      `<option value="${i}">${run.run_id}（${names}）</option>`
    );
  });
  select.onchange = () => renderBtRun(btRuns[Number(select.value)]);
  if (btRuns.length) renderBtRun(btRuns[0]);
}

function renderBtRun(run) {
  const first = run.strategies[0] || {};
  const p = first.params || {};
  $("#bt-run-meta").textContent =
    `入库 ${run.created_at.slice(0, 19)} · 来源 ${p.source || "?"} · ` +
    `初始资金 ${first.initial_capital ? first.initial_capital.toLocaleString() : "?"}`;

  const tbody = $("#bt-table tbody");
  tbody.innerHTML = "";
  const signed = (v, fmt) => {
    if (v === null || v === undefined) return `<td class="gate-na">-</td>`;
    const cls = v > 0 ? "gate-good" : v < 0 ? "gate-bad" : "";
    return `<td class="${cls}">${fmt(v)}</td>`;
  };
  for (const s of run.strategies) {
    tbody.insertAdjacentHTML(
      "beforeend",
      `<tr>
         <td>${s.strategy}</td>
         <td>${s.start_date} ~ ${s.end_date}</td>
         ${signed(s.total_return, pct)}
         ${signed(s.annualized_return, pct)}
         <td class="${s.max_drawdown > 0.2 ? "gate-bad" : ""}">${pct(s.max_drawdown)}</td>
         ${signed(s.sharpe_ratio, f3)}
         ${signed(s.sortino_ratio, f3)}
         ${signed(s.calmar_ratio, f3)}
         <td>${pct(s.win_rate)}</td>
         <td>${s.trade_count}</td>
         <td>${pct(s.turnover_rate)}</td>
       </tr>`
    );
  }

  if (!btChart) btChart = echarts.init($("#bt-chart"), "dark");
  const withCurve = run.strategies.filter((s) => (s.equity_curve.dates || []).length);
  btChart.setOption({
    backgroundColor: "transparent",
    animation: false,
    title: { text: `净值曲线 · ${run.run_id}`, textStyle: { fontSize: 13 } },
    tooltip: { trigger: "axis" },
    legend: { top: 4, right: 10, textStyle: { fontSize: 11 } },
    grid: { left: 80, right: 20, top: 40, bottom: 40 },
    xAxis: { type: "category", data: (withCurve[0] || { equity_curve: { dates: [] } }).equity_curve.dates },
    yAxis: { type: "value", scale: true },
    dataZoom: [{ type: "inside" }],
    series: withCurve.map((s) => ({
      name: s.strategy, type: "line", data: s.equity_curve.values,
      showSymbol: false,
    })),
  }, true);
  resizeCharts();
}

// ---------- 实盘 / 纸面前向 ----------

let liveEquityChart = null;
let liveTimer = null;

const STATUS_BADGE = {
  DRY_RUN: "info", SUBMITTED: "info", FILLED: "pass", PARTIAL: "warn",
  ALIVE: "warn", TIMEOUT_CANCELED: "warn", TIMEOUT_UNCANCELED: "fail",
  CANCELED: "warn", REJECTED: "fail", FAILED: "fail",
};

function setLivePolling(on) {
  if (on) {
    loadLive().catch((e) => showError(e.message));
    if (!liveTimer) liveTimer = setInterval(
      () => loadLive().catch(() => {}), 5000);
  } else if (liveTimer) {
    clearInterval(liveTimer);
    liveTimer = null;
  }
}

async function loadLive() {
  const [ov, cyc, exe, pos, eq] = await Promise.all([
    fetchJSON("/api/live/overview"),
    fetchJSON("/api/live/cycles"),
    fetchJSON("/api/live/executions"),
    fetchJSON("/api/live/positions"),
    fetchJSON("/api/live/equity"),
  ]);

  $("#live-empty").classList.toggle("hidden", ov.db_exists);

  const acct = ov.latest_account || {};
  const num = (v) => (v === null || v === undefined ? "-" : Number(v).toLocaleString());
  $("#live-cards").innerHTML = `
    <div class="card"><h3>总资产</h3><div class="big">${num(acct.total_asset)}</div>
      <div class="dim">${(acct.snapshot_time || "").slice(0, 19) || "无快照"} · ${acct.mode || ""}</div></div>
    <div class="card"><h3>可用资金</h3><div class="big">${num(acct.available_cash)}</div>
      <div class="dim">冻结 ${num(acct.frozen_cash)}</div></div>
    <div class="card"><h3>今日循环</h3><div class="big">${ov.cycles_today}</div>
      <div class="dim">执行时刻命中次数</div></div>
    <div class="card"><h3>今日执行</h3><div class="big">${ov.executions_today}</div>
      <div class="dim">含拒单/失败留痕</div></div>`;

  if (!liveEquityChart) liveEquityChart = echarts.init($("#live-equity-chart"), "dark");
  // dry_run 与 live 是两条独立曲线, 混排成一条会出现锯齿假象
  const modes = [...new Set(eq.series.map((r) => r.mode))];
  const timeline = [...new Set(eq.series.map((r) => r.snapshot_time))].sort();
  const tsIndex = new Map(timeline.map((t, i) => [t, i]));
  liveEquityChart.setOption({
    backgroundColor: "transparent",
    animation: false,
    title: { text: "账户权益（循环快照）", textStyle: { fontSize: 13 } },
    tooltip: { trigger: "axis" },
    legend: { top: 4, right: 10, textStyle: { fontSize: 11 } },
    grid: { left: 90, right: 20, top: 40, bottom: 40 },
    xAxis: { type: "category", data: timeline.map((t) => t.slice(5, 16)) },
    yAxis: { type: "value", scale: true },
    series: modes.map((m) => {
      const data = new Array(timeline.length).fill(null);
      eq.series.filter((r) => r.mode === m)
        .forEach((r) => { data[tsIndex.get(r.snapshot_time)] = r.total_asset; });
      return { name: `总资产(${m})`, type: "line", showSymbol: false,
               connectNulls: true, data };
    }),
  }, true);

  $("#live-pos-time").textContent = pos.snapshot_time
    ? `快照 ${pos.snapshot_time.slice(0, 19)}` : "";
  $("#live-positions tbody").innerHTML = pos.positions.map((r) => `
    <tr><td>${r.symbol}</td><td>${r.total_volume}</td>
        <td>${r.available_volume}</td><td>${(r.average_cost ?? 0).toFixed(3)}</td></tr>`
  ).join("") || `<tr><td colspan="4" class="gate-na">无持仓快照</td></tr>`;

  $("#live-cycles tbody").innerHTML = cyc.cycles.map((c) => `
    <tr><td>${c.cycle_time.slice(0, 19)}</td>
        <td><span class="badge ${c.mode === "live" ? "fail" : "info"}">${c.mode}</span></td>
        <td>${c.strategy}</td><td>${c.signals_generated}</td><td>${c.orders_submitted}</td>
        <td>${c.orders_rejected}</td><td>${c.orders_failed}</td>
        <td>${num(c.notional_submitted)}</td>
        <td style="text-align:left">${c.note || ""}</td></tr>`
  ).join("") || `<tr><td colspan="9" class="gate-na">暂无循环</td></tr>`;

  $("#live-executions tbody").innerHTML = exe.executions.map((e) => `
    <tr><td>${e.submitted_at.slice(0, 19)}</td><td>${e.symbol}</td>
        <td class="${e.direction === "BUY" ? "gate-bad" : "gate-good"}">${e.direction}</td>
        <td>${e.exec_price != null ? e.exec_price.toFixed(2) : "-"}</td>
        <td>${e.volume ?? "-"}</td><td>${e.notional != null ? num(e.notional) : "-"}</td>
        <td>${e.confidence != null ? e.confidence.toFixed(2) : "-"}</td>
        <td><span class="badge ${STATUS_BADGE[e.status] || "info"}">${e.status}</span></td>
        <td style="text-align:left">${e.reject_reason || ""}</td></tr>`
  ).join("") || `<tr><td colspan="9" class="gate-na">暂无执行记录</td></tr>`;

  resizeCharts();
}

// symbol 搜索联想
let searchTimer = null;
$("#symbol-input").addEventListener("input", (e) => {
  clearTimeout(searchTimer);
  const q = e.target.value.trim();
  if (!q) return;
  searchTimer = setTimeout(async () => {
    try {
      const list = await fetchJSON(`${API}/symbols?q=${encodeURIComponent(q)}`);
      $("#symbol-list").innerHTML = list
        .map((s) => `<option value="${s.symbol}">${s.name}</option>`)
        .join("");
    } catch { /* 联想失败静默 */ }
  }, 200);
});

$("#load-symbol").addEventListener("click", async () => {
  clearError();
  try {
    await Promise.all([loadKline(), loadFeatures()]);
  } catch (err) {
    showError(err.message);
  }
});

window.addEventListener("resize", resizeCharts);

// ---------- 启动 ----------

(async function init() {
  initFeaturePicker();
  const tab = location.hash.replace("#", "");
  if (tab && ["overview", "verdicts", "explorer", "backtests", "live"].includes(tab)) {
    document.querySelector(`.tab[data-tab="${tab}"]`).click();
  }
  try {
    await Promise.all([loadOverview(), loadVerdicts()]);
  } catch (err) {
    showError(err.message);
  }
})();
