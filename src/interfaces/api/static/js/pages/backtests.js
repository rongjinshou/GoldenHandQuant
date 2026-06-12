/* 回测页 */
"use strict";

import { $, API, fetchJSON, pct, f3, showError, clearError } from "../api.js";
import { makeChart, resizeCharts } from "../charts.js";
import { submitJob, attachJobCard } from "../jobs.js";

let btChart = null;
let btRuns = [];

export async function loadBacktests() {
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

  if (!btChart) btChart = makeChart($("#bt-chart"));
  const withCurve = run.strategies.filter((s) => (s.equity_curve.dates || []).length);
  const dates = (withCurve[0] || { equity_curve: { dates: [] } }).equity_curve.dates;
  // 回撤序列: v / 历史峰值 - 1 (前端现算, 与净值同轴联动)
  const drawdown = (values) => {
    let peak = -Infinity;
    return values.map((v) => {
      peak = Math.max(peak, v);
      return peak > 0 ? +((v / peak - 1) * 100).toFixed(2) : 0;
    });
  };
  btChart.setOption({
    backgroundColor: "transparent",
    animation: false,
    title: { text: `净值与回撤 · ${run.run_id}`, textStyle: { fontSize: 13 } },
    tooltip: { trigger: "axis" },
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    legend: { top: 4, right: 10, textStyle: { fontSize: 11 } },
    grid: [
      { left: 80, right: 20, top: 40, height: "52%" },
      { left: 80, right: 20, top: "70%", height: "22%" },
    ],
    xAxis: [
      { type: "category", data: dates, gridIndex: 0, axisLabel: { show: false } },
      { type: "category", data: dates, gridIndex: 1 },
    ],
    yAxis: [
      { type: "value", scale: true, gridIndex: 0 },
      { type: "value", gridIndex: 1, axisLabel: { formatter: "{value}%" },
        max: 0 },
    ],
    dataZoom: [{ type: "inside", xAxisIndex: [0, 1] }],
    series: [
      ...withCurve.map((s) => ({
        name: s.strategy, type: "line", data: s.equity_curve.values,
        showSymbol: false, xAxisIndex: 0, yAxisIndex: 0,
      })),
      ...withCurve.map((s) => ({
        name: `回撤 ${s.strategy}`, type: "line",
        data: drawdown(s.equity_curve.values),
        showSymbol: false, xAxisIndex: 1, yAxisIndex: 1,
        areaStyle: { opacity: 0.25 }, lineStyle: { width: 1 },
      })),
    ],
  }, true);
  resizeCharts();
}

let strategyMeta = [];

export async function initBacktestForm() {
  const data = await fetchJSON("/api/meta/strategies");
  strategyMeta = data.strategies;
  const box = $("#bt-strategies");
  box.innerHTML = strategyMeta.map((s) => `
    <label title="${s.description}">
      <input type="checkbox" value="${s.name}" ${s.name === "dual_ma" ? "checked" : ""}>
      ${s.name}<span class="group-title">[${s.strategy_type === "cross_section" ? "截面" : "时序"}]</span>
    </label>`).join("");
  box.querySelectorAll("input").forEach((cb) =>
    cb.addEventListener("change", renderParamInputs));
  renderParamInputs();
  $("#bt-submit").addEventListener("click", submitBacktest);
}

function selectedStrategies() {
  return [...document.querySelectorAll("#bt-strategies input:checked")].map((c) => c.value);
}

function renderParamInputs() {
  const names = selectedStrategies();
  const rows = [];
  for (const name of names) {
    const meta = strategyMeta.find((s) => s.name === name);
    for (const [key, val] of Object.entries(meta.default_params || {})) {
      if (typeof val === "object") continue; // 字典参数(权重)走配置文件, 设计 DD-8
      rows.push(`<label>${name}.${key}
        <input data-strat="${name}" data-key="${key}" value="${val}" size="8"></label>`);
    }
  }
  $("#bt-params").innerHTML = rows.join("");
  const hasCross = names.some((n) =>
    strategyMeta.find((s) => s.name === n)?.strategy_type === "cross_section");
  $("#bt-hint").classList.toggle("hidden", !hasCross);
  $("#bt-hint").textContent =
    "截面策略需基本面通道（QMT 客户端在线，或配置 Tushare），且全市场回测耗时数分钟。";
}

async function submitBacktest() {
  clearError();
  const strategies = selectedStrategies();
  if (!strategies.length) { showError("至少选择一个策略"); return; }
  const payload = {
    strategies,
    start_date: $("#bt-start").value,
    end_date: $("#bt-end").value,
  };
  const symbols = $("#bt-symbols").value.trim();
  if (symbols) payload.symbols = symbols.split(",").map((s) => s.trim()).filter(Boolean);
  const capital = Number($("#bt-capital").value);
  if (capital > 0) payload.initial_capital = capital;
  if ($("#bt-config").value) payload.config = $("#bt-config").value;
  const params = {};
  document.querySelectorAll("#bt-params input").forEach((inp) => {
    const meta = strategyMeta.find((s) => s.name === inp.dataset.strat);
    const dflt = String((meta.default_params || {})[inp.dataset.key]);
    if (inp.value !== dflt) {
      (params[inp.dataset.strat] ??= {})[inp.dataset.key] = inp.value;
    }
  });
  if (Object.keys(params).length) payload.params = params;
  try {
    const job = await submitJob("backtest", payload);
    attachJobCard($("#bt-job-area"), job.job_id, {
      onDone: () => loadBacktests().catch((e) => showError(e.message)),
    });
  } catch (err) {
    showError(err.message);
  }
}
