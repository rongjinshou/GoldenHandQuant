/* 实盘 / 纸面前向页 */
"use strict";

import { $, fetchJSON, showError, num } from "../api.js";
import { makeChart, resizeCharts } from "../charts.js";

let liveEquityChart = null;
let liveTimer = null;

const STATUS_BADGE = {
  DRY_RUN: "info", SUBMITTED: "info", FILLED: "pass", PARTIAL: "warn",
  ALIVE: "warn", TIMEOUT_CANCELED: "warn", TIMEOUT_UNCANCELED: "fail",
  CANCELED: "warn", REJECTED: "fail", FAILED: "fail",
};

export function setLivePolling(on) {
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
  $("#live-cards").innerHTML = `
    <div class="card"><h3>总资产</h3><div class="big">${num(acct.total_asset)}</div>
      <div class="dim">${(acct.snapshot_time || "").slice(0, 19) || "无快照"} · ${acct.mode || ""}</div></div>
    <div class="card"><h3>可用资金</h3><div class="big">${num(acct.available_cash)}</div>
      <div class="dim">冻结 ${num(acct.frozen_cash)}</div></div>
    <div class="card"><h3>今日循环</h3><div class="big">${ov.cycles_today}</div>
      <div class="dim">执行时刻命中次数</div></div>
    <div class="card"><h3>今日执行</h3><div class="big">${ov.executions_today}</div>
      <div class="dim">含拒单/失败留痕</div></div>`;

  if (!liveEquityChart) liveEquityChart = makeChart($("#live-equity-chart"));
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
