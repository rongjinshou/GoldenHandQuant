/* 回测页 */
"use strict";

import { $, API, fetchJSON, pct, f3 } from "../api.js";
import { makeChart, resizeCharts } from "../charts.js";

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
