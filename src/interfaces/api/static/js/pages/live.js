/* 实盘 / 纸面前向页 — KPI 概览 + 分页(概览/持仓/循环/执行/审计/Ticket) */
"use strict";

import { $, fetchJSON, showError, num } from "../api.js";
import { makeChart, resizeCharts, chartTheme, axisStyle, tooltipStyle, vGradient } from "../charts.js";
import { applyGlossary } from "../glossary.js";

let liveEquityChart = null;
let liveTimer = null;

// 5s 轮询不抹除钻取 / 不收起已展开的长表
const expandedCycles = new Set();
const fullView = { cycles: false, executions: false, audit: false };
const ROW_LIMIT = 50; // 长表默认只显示最近 N 行, 余下折叠

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
  initSubnav();
}

/* 子页签: 概览/持仓/循环/执行/审计/Ticket — 同一时刻只显示一个视图 */
function initSubnav() {
  const nav = $("#live-subnav");
  if (!nav) return;
  nav.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      nav.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll("#tab-live .live-view").forEach((v) => v.classList.remove("active"));
      btn.classList.add("active");
      const view = $(`#lv-${btn.dataset.lv}`);
      if (view) view.classList.add("active");
      if (btn.dataset.lv === "overview") resizeCharts();
    });
  });
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

/* 顶部 KPI 条: 总资产 / 累计收益 / 可用资金 / 持仓市值 */
function renderKpis(ov, eq, posCount) {
  const acct = ov.latest_account || {};
  const series = eq.series || [];
  const first = series.length ? series[0].total_asset : null;
  const lastTotal = acct.total_asset ?? (series.length ? series[series.length - 1].total_asset : null);
  // 累计收益 = 自首条快照以来的权益变化; 单条快照无从谈"累计", 显示占位
  let cumHtml = series.length === 1
    ? `<div class="big">—</div><div class="dim">需多次快照累计</div>`
    : `<div class="big">—</div><div class="dim">暂无权益快照</div>`;
  if (series.length >= 2 && first && lastTotal != null && first > 0) {
    const ret = lastTotal / first - 1;
    const cls = ret >= 0 ? "gate-bad" : "gate-good"; // A股: 涨=红 跌=绿
    cumHtml = `<div class="big ${cls}">${ret >= 0 ? "+" : ""}${(ret * 100).toFixed(2)}%</div>`
      + `<div class="dim">起点 ${num(first)}</div>`;
  }
  $("#live-cards").innerHTML = `
    <div class="card"><h3>总资产</h3><div class="big">${num(acct.total_asset)}</div>
      <div class="dim">${(acct.snapshot_time || "").slice(0, 19) || "无快照"} · ${acct.mode || ""}</div></div>
    <div class="card"><h3>累计收益</h3>${cumHtml}</div>
    <div class="card"><h3>可用资金</h3><div class="big">${num(acct.available_cash)}</div>
      <div class="dim">冻结 ${num(acct.frozen_cash)}</div></div>
    <div class="card"><h3>持仓市值</h3><div class="big">${num(acct.market_value)}</div>
      <div class="dim">${posCount} 只持仓</div></div>`;
}

/* 概览页运维卡: 今日活动 / 预算 / 守护 / auto-trade 配置 */
function renderOpsCards(ov, budget, cfg) {
  const at = cfg.auto_trade || {};
  $("#live-ops-cards").innerHTML = `
    <div class="card"><h3>今日活动</h3>
      <div class="big">${ov.cycles_today} <span class="unit">循环</span></div>
      <div class="dim">执行 ${ov.executions_today} 笔（含拒单/失败留痕）</div></div>
    <div class="card"><h3><span data-gloss="budget">今日预算（跨模式）</span></h3>
      <div class="big">${num(budget.submitted_notional)}</div>
      <div class="dim">上限 ${num(budget.daily_notional_cap)} · 余 ${num(budget.remaining)}
        · 单笔顶 ${num(budget.per_order_notional_cap)}</div></div>
    <div class="card"><h3><span data-gloss="daemon">守护状态</span></h3>
      <div class="big" style="font-size:18px">${daemonBadge(cfg)}</div>
      <div class="dim">执行槽位 ${(cfg.today.expected_slots || []).join(" / ") || "-"}</div></div>
    <div class="card"><h3><span data-gloss="at_config">auto-trade 配置（只读）</span></h3>
      <div class="big" style="font-size:16px">
        <span class="badge ${at.mode === "live" ? "fail" : "info"}"${at.mode === "dry_run" ? ' data-gloss="dry_run"' : ""}>${at.mode || "?"}</span>
        <span class="badge ${at.enabled ? "warn" : "info"}">${at.enabled ? "enabled" : "disabled"}</span>
      </div>
      <div class="dim">${at.strategy || ""} · ${(at.symbols || []).length} 标的
        · <span data-gloss="confidence">置信</span>≥${at.min_confidence ?? "?"}</div></div>`;
  applyGlossary($("#live-ops-cards"));
}

/* 长表分页渲染: 默认最近 ROW_LIMIT 行, 余下点开 */
function renderBounded(tbody, rows, key, colspan, emptyHtml) {
  if (!rows.length) { tbody.innerHTML = emptyHtml; return; }
  const expanded = fullView[key];
  const shown = expanded ? rows : rows.slice(0, ROW_LIMIT);
  let html = shown.join("");
  if (!expanded && rows.length > ROW_LIMIT) {
    html += `<tr class="more-row" data-more="${key}"><td colspan="${colspan}">`
      + `显示全部 ${rows.length} 条 ▾</td></tr>`;
  }
  tbody.innerHTML = html;
  const more = tbody.querySelector(".more-row");
  if (more) more.addEventListener("click", () => {
    fullView[key] = true;
    loadLive().catch(() => {});
  });
}

async function loadLive() {
  const mode = $("#live-mode")?.value || "";
  const modeQ = mode ? `?mode=${mode}` : "";
  const eqQ = mode ? `?mode=${mode}&limit=2000` : "?limit=2000";
  const auditAction = $("#audit-action")?.value || "";
  const [ov, cyc, exe, pos, eq, budget, cfg, audit, tickets] = await Promise.all([
    fetchJSON("/api/live/overview"),
    fetchJSON("/api/live/cycles?limit=500"),
    fetchJSON("/api/live/executions?limit=1000"),
    fetchJSON(`/api/live/positions${modeQ}`),
    fetchJSON(`/api/live/equity${eqQ}`),
    fetchJSON("/api/live/budget"),
    fetchJSON("/api/live/config"),
    fetchJSON(`/api/live/audit?limit=500${auditAction ? `&action=${auditAction}` : ""}`),
    fetchJSON("/api/live/tickets"),
  ]);

  // 空态: 无库时只显示 KPI 占位 + 空提示, 隐藏分页与各视图
  const hasDb = ov.db_exists;
  $("#live-empty").classList.toggle("hidden", hasDb);
  $("#live-subnav").classList.toggle("hidden", !hasDb);
  document.querySelectorAll("#tab-live .live-view").forEach(
    (v) => v.classList.toggle("hidden", !hasDb));

  renderKpis(ov, eq, pos.positions.length);
  renderOpsCards(ov, budget, cfg);

  // 子页签计数
  $("#lv-cnt-pos").textContent = pos.positions.length;
  $("#lv-cnt-cyc").textContent = cyc.cycles.length;
  $("#lv-cnt-exe").textContent = exe.executions.length;
  $("#lv-cnt-aud").textContent = audit.logs.length;
  $("#lv-cnt-tk").textContent = tickets.tickets.length;

  // ---- 权益曲线 (需 ≥2 个快照才成曲线; 单点显示提示而非空图框) ----
  const hasEquity = eq.series.length >= 2;
  $("#live-equity-chart").classList.toggle("hidden", !hasEquity);
  const eqHint = $("#live-equity-hint");
  if (eqHint) {
    eqHint.classList.toggle("hidden", hasEquity);
    eqHint.textContent = eq.series.length === 1
      ? "已有 1 条权益快照——多次同步后将绘制权益曲线（scripts/sync_live_account.py --watch 30 持续采样）。"
      : "暂无权益快照。";
  }
  if (hasEquity) {
    if (!liveEquityChart) {
      liveEquityChart = makeChart($("#live-equity-chart"));
    } else {
      resizeCharts();
    }
    const tc = chartTheme();
    const modes = [...new Set(eq.series.map((r) => r.mode))];
    const timeline = [...new Set(eq.series.map((r) => r.snapshot_time))].sort();
    const tsIndex = new Map(timeline.map((t, i) => [t, i]));
    const wan = (v) => (Math.abs(v) >= 10000 ? `${(v / 10000).toFixed(1)}万` : `${v}`);
    liveEquityChart.setOption({
      backgroundColor: "transparent",
      animation: false,
      textStyle: { color: tc.text },
      color: tc.series,
      title: { text: "账户权益（循环快照）", left: 14, top: 10,
        textStyle: { fontSize: 13, fontWeight: 600, color: tc.text } },
      tooltip: { trigger: "axis", ...tooltipStyle(tc),
        axisPointer: { type: "line", lineStyle: { color: tc.axis, type: "dashed" } } },
      legend: { top: 9, right: 14, itemWidth: 16, itemHeight: 8,
        textStyle: { color: tc.dim, fontSize: 11 } },
      grid: { left: 70, right: 24, top: 46, bottom: 40 },
      xAxis: { type: "category", boundaryGap: false,
        data: timeline.map((t) => t.slice(5, 16)), ...axisStyle(tc), splitLine: { show: false } },
      yAxis: { type: "value", scale: true, ...axisStyle(tc),
        axisLabel: { color: tc.dim, fontSize: 11, formatter: wan } },
      series: modes.map((m, i) => {
        const data = new Array(timeline.length).fill(null);
        eq.series.filter((r) => r.mode === m)
          .forEach((r) => { data[tsIndex.get(r.snapshot_time)] = r.total_asset; });
        const col = tc.series[i % tc.series.length];
        return { name: `总资产(${m})`, type: "line", smooth: 0.25, showSymbol: false,
                 connectNulls: true, data, lineStyle: { color: col, width: 2.2 },
                 itemStyle: { color: col },
                 ...(i === 0 ? { areaStyle: { color: vGradient(tc.goldArea[0], tc.goldArea[1]) } } : {}) };
      }),
    }, true);
  }

  // ---- 持仓 ----
  $("#live-pos-time").textContent = pos.snapshot_time
    ? `快照 ${pos.snapshot_time.slice(0, 19)}` : "";
  $("#live-positions tbody").innerHTML = pos.positions.map((r) => {
    const vol = r.total_volume || 0;
    const cost = r.average_cost ?? 0;
    const last = r.last_price; // 同步脚本填; 无则回退成本
    const mktPx = (last != null && last > 0) ? last : cost;
    const mktVal = vol * mktPx;
    const pnl = (last != null && last > 0) ? (last - cost) * vol : null;
    const pnlCls = pnl == null ? "" : pnl >= 0 ? "gate-bad" : "gate-good"; // A股 涨红跌绿
    const pnlTxt = pnl == null ? "-"
      : `${pnl >= 0 ? "+" : ""}${num(pnl)}${cost > 0 ? ` (${pnl >= 0 ? "+" : ""}${((mktPx / cost - 1) * 100).toFixed(1)}%)` : ""}`;
    return `<tr><td>${r.symbol}</td><td>${vol}</td>
        <td>${r.available_volume}</td><td>${cost.toFixed(3)}</td>
        <td>${last != null && last > 0 ? last.toFixed(3) : "-"}</td>
        <td>${num(mktVal)}</td><td class="${pnlCls}">${pnlTxt}</td></tr>`;
  }).join("") || `<tr><td colspan="7" class="gate-na">无持仓快照</td></tr>`;

  // ---- 循环 (分页 + 行内钻取) ----
  const cycleRows = cyc.cycles.map((c) => `
    <tr class="clickable" data-cycle="${c.cycle_id}">
      <td>${c.cycle_time.slice(0, 19)}</td>
      <td><span class="badge ${c.mode === "live" ? "fail" : "info"}">${c.mode}</span></td>
      <td>${c.strategy}</td><td>${c.signals_generated}</td><td>${c.orders_submitted}</td>
      <td>${c.orders_rejected}</td><td>${c.orders_failed}</td>
      <td>${num(c.notional_submitted)}</td>
      <td style="text-align:left">${c.note || ""}</td></tr>`);
  renderBounded($("#live-cycles tbody"), cycleRows, "cycles", 9,
    `<tr><td colspan="9" class="gate-na">暂无循环</td></tr>`);

  async function expandCycleRow(tr) {
    let d;
    try {
      d = await fetchJSON(`/api/live/cycles/${tr.dataset.cycle}/executions`);
    } catch (e) {
      showError(e.message);
      return;
    }
    const rows = d.executions.map((e) =>
      `<tr><td>${e.symbol}</td><td>${e.direction}</td><td>${e.status}</td>
           <td>${num(e.notional)}</td><td>${e.reject_reason || ""}</td></tr>`).join("")
      || `<tr><td colspan="5">该循环无执行记录</td></tr>`;
    tr.insertAdjacentHTML("afterend",
      `<tr class="row-detail"><td colspan="9"><table>${rows}</table></td></tr>`);
  }

  $("#live-cycles tbody").querySelectorAll("tr.clickable").forEach((tr) => {
    tr.addEventListener("click", async () => {
      const next = tr.nextElementSibling;
      if (next && next.classList.contains("row-detail")) {
        next.remove();
        expandedCycles.delete(tr.dataset.cycle);
        return;
      }
      expandedCycles.add(tr.dataset.cycle);
      await expandCycleRow(tr);
    });
  });
  for (const cycleId of expandedCycles) {
    const tr = $("#live-cycles tbody").querySelector(`tr[data-cycle="${cycleId}"]`);
    if (tr) {
      try { await expandCycleRow(tr); } catch { /* 静默 */ }
    } else {
      expandedCycles.delete(cycleId);
    }
  }

  // ---- 执行 (分页) ----
  const exeRows = exe.executions.map((e) => `
    <tr><td>${e.submitted_at.slice(0, 19)}</td><td>${e.symbol}</td>
        <td class="${e.direction === "BUY" ? "gate-bad" : "gate-good"}">${e.direction}</td>
        <td>${e.exec_price != null ? e.exec_price.toFixed(2) : "-"}</td>
        <td>${e.volume ?? "-"}</td><td>${e.notional != null ? num(e.notional) : "-"}</td>
        <td>${e.confidence != null ? e.confidence.toFixed(2) : "-"}</td>
        <td><span class="badge ${STATUS_BADGE[e.status] || "info"}">${e.status}</span></td>
        <td style="text-align:left">${e.reject_reason || ""}</td></tr>`);
  renderBounded($("#live-executions tbody"), exeRows, "executions", 9,
    `<tr><td colspan="9" class="gate-na">暂无执行记录</td></tr>`);

  // ---- 审计 (分页) ----
  const auditRows = audit.logs.map((r) => `
    <tr><td>${(r.timestamp || "").slice(0, 19)}</td><td>${r.action}</td>
        <td>${r.resource_type || ""}:${r.resource_id || ""}</td>
        <td style="text-align:left"><code>${escHtml(String(r.details || "")).slice(0, 120)}</code></td></tr>`);
  renderBounded($("#live-audit tbody"), auditRows, "audit", 4,
    `<tr><td colspan="4" class="gate-na">暂无审计记录</td></tr>`);

  // ---- Ticket ----
  function escHtml(s) { return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])); }
  function kvTicket(c) {
    if (!c || typeof c !== "object") return `<div class="tk-empty">内容不可读</div>`;
    const dirCls = c.direction === "BUY" ? "gate-bad" : c.direction === "SELL" ? "gate-good" : "";
    const dirText = c.direction === "BUY" ? "买入 BUY"
      : c.direction === "SELL" ? "卖出 SELL" : (c.direction ?? "-");
    const fin = c.final_status || c.status;
    const finCls = /FILLED/.test(fin || "") ? "gate-good"
      : /REJECT|FAIL/.test(fin || "") ? "gate-bad" : "";
    const cell = (k, v, cls = "") => (v === undefined || v === null || v === "") ? ""
      : `<div class="tk-cell"><span class="tk-k">${k}</span>`
        + `<span class="tk-v ${cls}">${escHtml(v)}</span></div>`;
    return `<div class="tk-grid">
      ${cell("标的", c.symbol)}
      ${cell("方向", dirText, dirCls)}
      ${cell("委托价", c.price)}
      ${cell("数量", c.volume)}
      ${cell("金额", c.notional != null ? Number(c.notional).toLocaleString() : null)}
      ${cell("状态", fin, finCls)}
      ${cell("委托号", c.order_id)}
      ${cell("提交时刻", (c.submitted_at || c.requested_at || "").slice(0, 19))}
    </div>`;
  }
  $("#live-tickets").innerHTML = tickets.tickets.map((t) => `
    <details class="ticket-item" open><summary>${escHtml(String(t.file || ""))}</summary>
      ${kvTicket(t.content)}
      <details class="ticket-raw"><summary>原始 JSON</summary>
        <pre class="ticket-pre">${escHtml(JSON.stringify(t.content, null, 2))}</pre></details>
    </details>`
  ).join("") || `<p class="empty">暂无 ticket</p>`;

  resizeCharts();
}

// 主题切换 → 实盘页可见时重渲染权益图换肤
window.addEventListener("gh:theme", () => {
  if ($("#tab-live")?.classList.contains("active")) loadLive().catch(() => {});
});
