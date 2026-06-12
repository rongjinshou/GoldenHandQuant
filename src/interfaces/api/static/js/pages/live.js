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

export function initLive() {
  const modeEl = $("#live-mode");
  const auditEl = $("#audit-action");
  if (modeEl) modeEl.addEventListener("change", () => loadLive().catch((e) => showError(e.message)));
  if (auditEl) auditEl.addEventListener("change", () => loadLive().catch((e) => showError(e.message)));
}

function daemonBadge(cfg) {
  const slots = cfg.today.expected_slots || [];
  const now = new Date().toTimeString().slice(0, 5);
  const due = slots.filter((s) => s <= now).length;
  const n = cfg.today.cycles_today;
  if (!slots.length) return `<span class="badge info">未配置槽位</span>`;
  if (due === 0) return `<span class="badge info">今日未到执行时刻</span>`;
  if (n >= due) return `<span class="badge pass">槽位已覆盖 ${n}/${due}</span>`;
  return `<span class="badge warn">槽位缺口 ${n}/${due} — 守护可能未运行</span>`;
}

function renderOpsCards(budget, cfg) {
  const at = cfg.auto_trade || {};
  $("#live-ops-cards").innerHTML = `
    <div class="card"><h3>今日预算（跨模式）</h3>
      <div class="big">${num(budget.submitted_notional)}</div>
      <div class="dim">上限 ${num(budget.daily_notional_cap)} · 余 ${num(budget.remaining)}
        · 单笔顶 ${num(budget.per_order_notional_cap)}</div></div>
    <div class="card"><h3>守护状态</h3>
      <div class="big" style="font-size:18px">${daemonBadge(cfg)}</div>
      <div class="dim">执行槽位 ${(cfg.today.expected_slots || []).join(" / ") || "-"}</div></div>
    <div class="card"><h3>auto-trade 配置（只读）</h3>
      <div class="big" style="font-size:16px">
        <span class="badge ${at.mode === "live" ? "fail" : "info"}">${at.mode || "?"}</span>
        <span class="badge ${at.enabled ? "warn" : "info"}">${at.enabled ? "enabled" : "disabled"}</span>
      </div>
      <div class="dim">${at.strategy || ""} · ${(at.symbols || []).length} 标的
        · 置信≥${at.min_confidence ?? "?"}</div></div>`;
}

async function loadLive() {
  const mode = $("#live-mode")?.value || "";
  const modeQ = mode ? `?mode=${mode}` : "";
  const auditAction = $("#audit-action")?.value || "";
  const [ov, cyc, exe, pos, eq, budget, cfg, audit, tickets] = await Promise.all([
    fetchJSON("/api/live/overview"),
    fetchJSON("/api/live/cycles"),
    fetchJSON("/api/live/executions"),
    fetchJSON(`/api/live/positions${modeQ}`),
    fetchJSON(`/api/live/equity${modeQ}`),
    fetchJSON("/api/live/budget"),
    fetchJSON("/api/live/config"),
    fetchJSON(`/api/live/audit?limit=50${auditAction ? `&action=${auditAction}` : ""}`),
    fetchJSON("/api/live/tickets"),
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

  renderOpsCards(budget, cfg);

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
    <tr class="clickable" data-cycle="${c.cycle_id}">
      <td>${c.cycle_time.slice(0, 19)}</td>
      <td><span class="badge ${c.mode === "live" ? "fail" : "info"}">${c.mode}</span></td>
      <td>${c.strategy}</td><td>${c.signals_generated}</td><td>${c.orders_submitted}</td>
      <td>${c.orders_rejected}</td><td>${c.orders_failed}</td>
      <td>${num(c.notional_submitted)}</td>
      <td style="text-align:left">${c.note || ""}</td></tr>`
  ).join("") || `<tr><td colspan="9" class="gate-na">暂无循环</td></tr>`;

  $("#live-cycles tbody").querySelectorAll("tr.clickable").forEach((tr) => {
    tr.addEventListener("click", async () => {
      const next = tr.nextElementSibling;
      if (next && next.classList.contains("row-detail")) { next.remove(); return; }
      const d = await fetchJSON(`/api/live/cycles/${tr.dataset.cycle}/executions`);
      const rows = d.executions.map((e) =>
        `<tr><td>${e.symbol}</td><td>${e.direction}</td><td>${e.status}</td>
             <td>${num(e.notional)}</td><td>${e.reject_reason || ""}</td></tr>`).join("")
        || `<tr><td colspan="5">该循环无执行记录</td></tr>`;
      tr.insertAdjacentHTML("afterend",
        `<tr class="row-detail"><td colspan="9"><table>${rows}</table></td></tr>`);
    });
  });

  $("#live-executions tbody").innerHTML = exe.executions.map((e) => `
    <tr><td>${e.submitted_at.slice(0, 19)}</td><td>${e.symbol}</td>
        <td class="${e.direction === "BUY" ? "gate-bad" : "gate-good"}">${e.direction}</td>
        <td>${e.exec_price != null ? e.exec_price.toFixed(2) : "-"}</td>
        <td>${e.volume ?? "-"}</td><td>${e.notional != null ? num(e.notional) : "-"}</td>
        <td>${e.confidence != null ? e.confidence.toFixed(2) : "-"}</td>
        <td><span class="badge ${STATUS_BADGE[e.status] || "info"}">${e.status}</span></td>
        <td style="text-align:left">${e.reject_reason || ""}</td></tr>`
  ).join("") || `<tr><td colspan="9" class="gate-na">暂无执行记录</td></tr>`;

  $("#live-audit tbody").innerHTML = audit.logs.map((r) => `
    <tr><td>${(r.timestamp || "").slice(0, 19)}</td><td>${r.action}</td>
        <td>${r.resource_type || ""}:${r.resource_id || ""}</td>
        <td style="text-align:left"><code>${String(r.details || "").slice(0, 120)}</code></td></tr>`
  ).join("") || `<tr><td colspan="4" class="gate-na">暂无审计记录</td></tr>`;

  $("#live-tickets").innerHTML = tickets.tickets.map((t) => `
    <details class="ticket-item"><summary>${t.file}</summary>
      <pre class="ticket-pre">${JSON.stringify(t.content, null, 2)}</pre></details>`
  ).join("") || `<p class="empty">暂无 ticket</p>`;

  resizeCharts();
}
