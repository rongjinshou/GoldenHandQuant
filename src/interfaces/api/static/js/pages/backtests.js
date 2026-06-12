/* 回测页 */
"use strict";

import { $, API, fetchJSON, pct, f3, showError, clearError } from "../api.js";
import { makeChart, resizeCharts } from "../charts.js";
import { submitJob, attachJobCard } from "../jobs.js";
import { applyGlossary } from "../glossary.js";

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

function typeOf(name) {
  return strategyMeta.find((s) => s.name === name)?.strategy_type;
}

/* params 来自 DB(历史 CLI 写入不可假定干净), 进 innerHTML 前转义 */
function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/* run meta: 类型徽章 + 回测对象（设计 DD-10: 时序显示标的 chips, 截面显示抽样池说明） */
function runTargetHtml(p) {
  const names = (p.strategies || []).map(esc);
  const badges = names.map((n) => typeOf(n) === "cross_section"
    ? `<span class="group-title" data-gloss="cs_strategy">[截面]</span>${n}`
    : typeOf(n) === undefined ? n
    : `<span class="group-title" data-gloss="ts_strategy">[时序]</span>${n}`).join(" ");
  const anyCross = names.some((n) => typeOf(n) === "cross_section");
  if (anyCross) {
    return `${badges} · <span class="run-target" data-gloss="cs_strategy">对象: 全市场抽样池</span>`;
  }
  const syms = (p.symbols || []).map(esc);
  if (!syms.length) return badges;
  const shown = syms.slice(0, 8);
  const more = syms.length - shown.length;
  return `${badges} · 标的 ` +
    shown.map((s) => `<span class="chip chip-ro">${s}</span>`).join(" ") +
    (more > 0
      ? ` <span class="chip chip-ro" title="${syms.join(", ")}">+${more}</span>`
      : "");
}

function renderBtRun(run) {
  const first = run.strategies[0] || {};
  const p = first.params || {};
  const metaEl = $("#bt-run-meta");
  metaEl.innerHTML =
    `入库 ${run.created_at.slice(0, 19)} · 来源 ${esc(p.source || "?")} · ` +
    `初始资金 ${first.initial_capital ? first.initial_capital.toLocaleString() : "?"}` +
    `<br>${runTargetHtml(p)}`;
  applyGlossary(metaEl);

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
      ${s.name}<span class="group-title"
        data-gloss="${s.strategy_type === "cross_section" ? "cs_strategy" : "ts_strategy"}"
        >[${s.strategy_type === "cross_section" ? "截面" : "时序"}]</span>
    </label>`).join("");
  applyGlossary(box);
  box.querySelectorAll("input").forEach((cb) =>
    cb.addEventListener("change", renderParamInputs));
  initSymbolChips();
  renderParamInputs();
  $("#bt-submit").addEventListener("click", submitBacktest);
}

/* ---- 标的 chips + 联想（设计 DD-9）---- */

let btSymbols = [];
const SYMBOL_RE = /^\d{6}\.(SH|SZ|BJ)$/;

function renderSymbolChips() {
  const box = $("#bt-symbols-box");
  const input = $("#bt-symbols-input");
  box.querySelectorAll(".chip").forEach((c) => c.remove());
  for (const sym of btSymbols) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = sym;
    const x = document.createElement("button");
    x.className = "chip-x";
    x.type = "button";
    x.textContent = "×";
    x.addEventListener("click", () => {
      btSymbols = btSymbols.filter((s) => s !== sym);
      renderSymbolChips();
    });
    chip.appendChild(x);
    box.insertBefore(chip, input);
  }
}

/* 文本 → chips（支持逗号/空格/分号分隔的粘贴串）; 返回非法 token */
function commitSymbolText(text) {
  const tokens = text.split(/[\s,，;；]+/).map((t) => t.trim().toUpperCase()).filter(Boolean);
  const bad = [];
  for (const t of tokens) {
    if (SYMBOL_RE.test(t)) {
      if (!btSymbols.includes(t)) btSymbols.push(t);
    } else {
      bad.push(t);
    }
  }
  renderSymbolChips();
  return bad;
}

/* 就近报错: 标的输入框下方的内联提示（评审: 顶部横幅离表单太远） */
function symErr(msg) {
  const el = $("#bt-symbols-err");
  el.classList.toggle("hidden", !msg);
  el.textContent = msg || "";
}

function initSymbolChips() {
  const input = $("#bt-symbols-input");
  const list = $("#bt-symbol-list");
  let timer = null;
  input.addEventListener("input", (e) => {
    const v = input.value.trim().toUpperCase();
    // 完整代码（datalist 点选 / 手输完成）→ 即时成 chip
    if (SYMBOL_RE.test(v)) {
      clearTimeout(timer); // 评审: 在途防抖会把清空后的 datalist 填回旧候选
      commitSymbolText(v);
      input.value = "";
      list.innerHTML = "";
      symErr("");
      return;
    }
    // 粘贴 / 末尾敲分隔符 → 拆分（评审: 编辑残留非法串时逐键重拆会跳光标, 故收窄触发条件）
    const isPaste = e.inputType === "insertFromPaste";
    const endsSep = /[,，;；\s]$/.test(input.value);
    if ((isPaste && /[,，;；\s]/.test(input.value)) || endsSep) {
      clearTimeout(timer);
      const bad = commitSymbolText(input.value);
      input.value = bad.join(",");
      list.innerHTML = "";
      symErr(bad.length
        ? `已忽略非法标的: ${bad.join(", ")}（格式 6位代码.SH/SZ/BJ，可修正后回车）` : "");
      return;
    }
    clearTimeout(timer);
    const q = input.value.trim();
    if (!q) { list.innerHTML = ""; return; }
    timer = setTimeout(async () => {
      try {
        const sug = await fetchJSON(`${API}/symbols?q=${encodeURIComponent(q)}`);
        if (input.value.trim() !== q) return; // 评审: 过期响应丢弃
        list.dataset.q = q; // Enter 取候选时校验对应关系
        list.innerHTML = sug
          .map((s) => `<option value="${s.symbol}">${s.name}</option>`).join("");
      } catch { /* 联想失败静默 */ }
    }, 200);
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const v = input.value.trim().toUpperCase();
      if (!v) return;
      clearTimeout(timer);
      if (SYMBOL_RE.test(v)) {
        commitSymbolText(v);
        input.value = "";
        list.innerHTML = "";
        symErr("");
        return;
      }
      // 编辑后的残留串（含分隔符）→ 重新拆分
      if (/[,，;；\s]/.test(v)) {
        const bad = commitSymbolText(v);
        input.value = bad.join(",");
        symErr(bad.length ? `仍有非法标的: ${bad.join(", ")}` : "");
        return;
      }
      // 名称搜索快捷路径: 仅当候选确属当前输入（评审: 防过期候选静默入列）
      const first = list.querySelector("option");
      if (first && list.dataset.q === input.value.trim()) {
        commitSymbolText(first.value);
        input.value = "";
        list.innerHTML = "";
        symErr("");
        return;
      }
      symErr("格式 6位代码.SH/SZ/BJ；输名称请稍候联想加载后回车或点选");
    } else if (e.key === "Backspace" && !input.value && btSymbols.length) {
      btSymbols.pop();
      renderSymbolChips();
    }
  });
}

function selectedStrategies() {
  return [...document.querySelectorAll("#bt-strategies input:checked")].map((c) => c.value);
}

function renderParamInputs() {
  const names = selectedStrategies();
  // 评审: 重建前暂存用户已改的参数值, 重建后回填（勾第二个策略不应重置第一个的参数）
  const kept = {};
  document.querySelectorAll("#bt-params input").forEach((inp) => {
    kept[`${inp.dataset.strat}.${inp.dataset.key}`] = inp.value;
  });
  const rows = [];
  for (const name of names) {
    const meta = strategyMeta.find((s) => s.name === name);
    for (const [key, val] of Object.entries(meta.default_params || {})) {
      if (typeof val === "object") continue; // 字典参数(权重)走配置文件, 设计 DD-8
      const keep = kept[`${name}.${key}`];
      rows.push(`<label>${name}.${key}
        <input data-strat="${name}" data-key="${key}" value="${keep ?? val}" size="8"></label>`);
    }
  }
  $("#bt-params").innerHTML = rows.join("");
  const hasCross = names.some((n) => typeOf(n) === "cross_section");
  $("#bt-hint").classList.toggle("hidden", !hasCross);
  $("#bt-hint").textContent =
    "截面策略需基本面通道（QMT 客户端在线，或配置 Tushare），且全市场回测耗时数分钟。" +
    "回测对象为全市场抽样池，下方标的输入不生效。";
  // 设计 DD-10: 含截面策略时禁用标的 chips（与 compare_strategies 语义一致）
  const input = $("#bt-symbols-input");
  $("#bt-symbols-box").classList.toggle("disabled", hasCross);
  input.disabled = hasCross;
  input.placeholder = hasCross
    ? "截面策略回测对象 = 全市场抽样池，此处不生效"
    : "输入代码/名称联想，回车或点选添加";
}

async function submitBacktest() {
  clearError();
  const strategies = selectedStrategies();
  if (!strategies.length) { showError("至少选择一个策略"); return; }
  // Fix #6: 非法初始资金提示
  const raw = $("#bt-capital").value.trim();
  if (raw !== "" && !(Number(raw) > 0)) { showError("初始资金须为正数"); return; }
  const payload = {
    strategies,
    start_date: $("#bt-start").value,
    end_date: $("#bt-end").value,
  };
  // 残留在输入框的文本先转 chips, 再取 chips 集合（截面禁用时不传, 见 DD-10）
  const symInput = $("#bt-symbols-input");
  if (!symInput.disabled && symInput.value.trim()) {
    const bad = commitSymbolText(symInput.value);
    symInput.value = bad.join(",");
    if (bad.length) { symErr(`非法标的: ${bad.join(", ")}（格式 6位代码.SH/SZ/BJ）`); return; }
    symErr("");
  }
  if (!symInput.disabled && btSymbols.length) payload.symbols = [...btSymbols];
  const capital = Number(raw);
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
