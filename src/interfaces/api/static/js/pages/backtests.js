/* 回测页 */
"use strict";

import { $, API, fetchJSON, pct, f3, showError, clearError } from "../api.js";
import { makeChart, resizeCharts, chartTheme, axisStyle, tooltipStyle, vGradient } from "../charts.js";
import { submitJob, attachJobCard } from "../jobs.js";
import { applyGlossary } from "../glossary.js";

let btChart = null;
let btRuns = [];

let currentBtRun = null;

export async function loadBacktests() {
  const data = await fetchJSON(`${API}/backtests`);
  btRuns = data.runs;
  $("#bt-empty").classList.toggle("hidden", btRuns.length > 0);
  const select = $("#bt-run-select");
  const overlay = $("#bt-overlay");
  select.innerHTML = "";
  overlay.innerHTML = `<option value="">无</option>`;
  btRuns.forEach((run, i) => {
    const names = esc(run.strategies.map((s) => s.strategy).join(", "));
    select.insertAdjacentHTML(
      "beforeend", `<option value="${i}">${run.run_id}（${names}）</option>`);
    overlay.insertAdjacentHTML(
      "beforeend", `<option value="${i}">${run.run_id}（${names}）</option>`);
  });
  const rerender = () => {
    if (currentBtRun) renderBtRun(currentBtRun).catch((e) => showError(e.message));
  };
  select.onchange = () => {
    currentBtRun = btRuns[Number(select.value)];
    rerender();
  };
  $("#bt-benchmark").onchange = rerender;
  overlay.onchange = rerender;
  if (btRuns.length) {
    currentBtRun = btRuns[0];
    await renderBtRun(currentBtRun);
  }
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

/* 基准: 同额资金买入持有 — 对齐净值日期, 取当日或之前最近收盘价折算 */
async function fetchBenchmarkSeries(symbol, dates, initialCapital) {
  if (!symbol || !dates.length) return null;
  const bars = await fetchJSON(
    `${API}/bars/${symbol}?start=${dates[0]}&end=${dates[dates.length - 1]}`);
  if (!bars.dates.length) return null;
  const closeByDate = new Map(
    bars.dates.map((d, i) => [d, bars.ohlc[i][1]]));  // ECharts 约定 [o,c,l,h]
  let base = null;
  let last = null;
  const values = dates.map((d) => {
    if (closeByDate.has(d)) last = closeByDate.get(d);
    if (last === null) return null;       // 基准晚于回测起点上市 → 前段空
    if (base === null) base = last;
    return +(initialCapital * (last / base)).toFixed(2);
  });
  // 评审: 基准日期与净值日期完全不相交 → 等同无行情, 不许显示 0.00% 假基准
  if (values.every((v) => v === null)) return null;
  return values;
}

/* 买卖事件 → 散点: 按 (日期,方向) 聚合 (截面策略调仓日几十笔不糊成一团);
   y 取该策略自己日期轴上的净值 (评审: 多策略日期轴可能不一致);
   精修: 小三角 + 同底色描边光环(从线上分离) + 阴影 + 偏移(买在线下/卖在线上不挡线)。
   A股配色 买=红▲ 卖=绿▼。 */
function tradeScatter(s, axisIdx, t) {
  const own = new Map((s.equity_curve.dates || []).map((d, i) => [d, i]));
  const grouped = { BUY: new Map(), SELL: new Map() };
  for (const tr of s.trades || []) {
    const g = grouped[tr.direction];
    if (!g || !axisIdx.has(tr.date) || !own.has(tr.date)) continue;
    if (!g.has(tr.date)) g.set(tr.date, []);
    g.get(tr.date).push(tr);
  }
  // 用 path 字形 (而非 triangle+rotate): 图例也能正确显示 ▲买/▼卖 区分形状
  const UP = "path://M0,-9 L9,7 L-9,7 Z";    // ▲ 顶点朝上
  const DOWN = "path://M0,9 L9,-7 L-9,-7 Z"; // ▼ 顶点朝下
  const mk = (dir, color, sym, offY) => ({
    name: `${dir === "BUY" ? "买" : "卖"}·${s.strategy}`,
    type: "scatter", xAxisIndex: 0, yAxisIndex: 0,
    symbol: sym, symbolOffset: [0, offY], z: 14,
    itemStyle: {
      color, borderColor: t.panelBg, borderWidth: 2,
      shadowBlur: 6, shadowColor: "rgba(0,0,0,.4)",
    },
    symbolSize: (_, q) => Math.min(9 + (q.data.trades.length - 1) * 1.6, 16),
    data: [...grouped[dir].entries()].map(([d, ts]) => ({
      value: [d, s.equity_curve.values[own.get(d)]], trades: ts,
    })),
  });
  const out = [];
  if (grouped.BUY.size) out.push(mk("BUY", t.up, UP, 11));      // 买 红▲ 落在线下方
  if (grouped.SELL.size) out.push(mk("SELL", t.down, DOWN, -11)); // 卖 绿▼ 落在线上方
  return out;
}

function chartTooltipFormatter(params) {
  if (!params.length) return "";
  const lines = [params[0].axisValueLabel];
  for (const q of params) {
    const ts = q.data && q.data.trades;
    if (ts) {
      // 评审: tooltip 走 HTML 渲染, DB 字符串一律 esc, 数值经 Number 收口
      const head = ts.slice(0, 3).map((t) =>
        `${t.direction === "BUY" ? "买入" : "卖出"} ${esc(t.symbol)} `
        + `${Number(t.volume)}股@${Number(t.price)}`
        + (t.direction === "SELL"
          ? `（${t.pnl >= 0 ? "+" : ""}${Number(t.pnl).toFixed(2)}）` : ""));
      lines.push(`${q.marker}${head.join("；")}`
        + (ts.length > 3 ? ` 等${ts.length}笔` : ""));
    } else if (q.value !== null && q.value !== undefined) {
      const v = q.seriesName.startsWith("回撤")
        ? `${q.value}%` : Math.round(q.value).toLocaleString();
      lines.push(`${q.marker}${esc(q.seriesName)}: ${v}`);
    }
  }
  return lines.join("<br>");
}

/* 配色由 chartTheme() 提供 (主策略=品牌金主角线; overlay/基准独立色; 随日夜换肤)。 */

/* 渲染代号: 三个 onchange + 任务回调并发触发 async 渲染, 旧渲染过期即弃 (评审 blocker) */
let renderSeq = 0;

async function renderBtRun(run) {
  const seq = ++renderSeq;
  const withCurve = run.strategies.filter((s) => (s.equity_curve.dates || []).length);
  // 评审: 旧 CLI 行可能无曲线, 基准/超额/缩放一律配对首个有曲线的策略
  const first = withCurve[0] || run.strategies[0] || {};
  const p = first.params || {};
  const dates = first.equity_curve?.dates || [];
  const metaEl = $("#bt-run-meta");
  metaEl.classList.add("meta-strip");
  const rm = (label, val, cls = "") =>
    `<span class="rm"><i>${label}</i><b class="${cls}">${val}</b></span>`;
  metaEl.innerHTML =
    rm("入库", run.created_at.slice(0, 19)) +
    rm("来源", esc(p.source || "?")) +
    rm("初始资金", first.initial_capital ? first.initial_capital.toLocaleString() : "?") +
    `<span class="rm-div"></span>` +
    `<span class="rm rm-wide">${runTargetHtml(p)}</span>`;
  applyGlossary(metaEl);
  // 评审: 截断的买卖留痕必须明示, 不许后段标记凭空消失
  const cut = run.strategies.find(
    (s) => (s.trades || []).length === 2000 && s.trade_count > 2000);
  if (cut) {
    metaEl.insertAdjacentHTML("beforeend",
      `<span class="rm rm-warn">⚠ 买卖标记仅前 2000 笔 (共 ${cut.trade_count})</span>`);
  }

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
         <td>${esc(s.strategy)}</td>
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
  const t = chartTheme();
  const axisIdx = new Map(dates.map((d, i) => [d, i]));
  // 评审: 非首策略日期轴可能不一致, 一律按自身日期映射到共享轴
  const alignToAxis = (s, values) => {
    if (s === first) return values;
    const own = new Map(s.equity_curve.dates.map((d, i) => [d, i]));
    return dates.map((d) => (own.has(d) ? values[own.get(d)] : null));
  };
  // 回撤序列: v / 历史峰值 - 1 (前端现算, 与净值同轴联动)
  const drawdown = (values) => {
    let peak = -Infinity;
    return values.map((v) => {
      peak = Math.max(peak, v);
      return peak > 0 ? +((v / peak - 1) * 100).toFixed(2) : 0;
    });
  };

  // ---- 基准: 同额买入持有 (设计 §8.3, 不入库, /bars 现算) ----
  const benchSel = $("#bt-benchmark").value;
  const benchSym = benchSel === "first_symbol" ? (p.symbols || [])[0] : benchSel;
  let benchSeries = null;
  let benchNote = "";
  if (benchSym && dates.length) {
    try {
      benchSeries = await fetchBenchmarkSeries(benchSym, dates, first.initial_capital);
      if (!benchSeries) benchNote = `基准 ${esc(benchSym)} 无本地行情`;
    } catch { benchNote = "基准行情加载失败"; }
  }
  if (seq !== renderSeq) return; // 评审 blocker: 过期渲染丢弃, 防 meta/图表串台
  let benchHtml = "";
  if (benchSeries) {
    const k = benchSeries.findIndex((v) => v !== null);
    const bv = benchSeries.filter((v) => v !== null);
    if (bv.length < 2) {
      benchSeries = null;
      benchHtml = `<span class="rm rm-warn">基准 ${esc(benchSym)} 区间内行情不足</span>`;
    } else {
      const benchReturn = bv[bv.length - 1] / bv[0] - 1;
      // 评审: 基准晚于回测起点时, 策略收益重算到同一子窗口再比, 不许窗口错配
      const sv = first.equity_curve.values;
      const stratReturn = sv[k] > 0 ? sv[sv.length - 1] / sv[k] - 1 : 0;
      const alpha = stratReturn - benchReturn;
      benchHtml =
        `<span class="rm-div"></span>`
        + `<span class="rm" data-gloss="benchmark"><i>基准·${esc(benchSym)}买入持有</i>`
        + `<b>${pct(benchReturn)}</b></span>`
        + `<span class="rm"><i>超额</i><b class="${alpha >= 0 ? "gate-good" : "gate-bad"}">`
        + `${pct(alpha)}</b></span>`
        + (k > 0 ? `<span class="rm rm-note">自 ${dates[k]} 同窗口径</span>` : "");
    }
  } else if (benchNote) {
    benchHtml = `<span class="rm rm-warn">${benchNote}</span>`;
  }
  if (benchHtml) {
    metaEl.insertAdjacentHTML("beforeend", benchHtml);
    applyGlossary(metaEl);
  }

  // ---- 叠加对比: 另一轮 run 重定基到相同起点资金 (设计 §8.3, 评审: 防窗口外收益误读) ----
  const overlayIdx = $("#bt-overlay").value;
  const overlaySeries = [];
  if (overlayIdx !== "" && btRuns[Number(overlayIdx)]
      && btRuns[Number(overlayIdx)].run_id !== run.run_id) {
    const other = btRuns[Number(overlayIdx)];
    let anyOverlap = false;
    other.strategies.forEach((s, si) => {
      const od = s.equity_curve.dates || [];
      if (!od.length) return;
      // 重定基: 以进入当前轴的首个可见点为锚, 锚点对齐当前 run 的初始资金
      let anchor = null;
      const data = new Array(dates.length).fill(null);
      od.forEach((d, i) => {
        const j = axisIdx.get(d);
        if (j === undefined) return;
        const v = s.equity_curve.values[i];
        if (anchor === null && v > 0) anchor = v;
        if (anchor) data[j] = +((first.initial_capital || 1) * (v / anchor)).toFixed(2);
      });
      if (anchor === null) return;
      anyOverlap = true;
      const rebased = s.start_date !== first.start_date;
      overlaySeries.push({
        name: `${other.run_id.slice(-6)}·${s.strategy}${rebased ? "(重定基)" : ""}`,
        type: "line", data, smooth: 0.25,
        showSymbol: false, xAxisIndex: 0, yAxisIndex: 0, connectNulls: true,
        lineStyle: { width: 1.2, type: "dashed", opacity: .85,
                     color: t.overlay[si % t.overlay.length] },
        itemStyle: { color: t.overlay[si % t.overlay.length] },
      });
    });
    if (!anyOverlap) {
      metaEl.insertAdjacentHTML("beforeend",
        `<span class="rm rm-warn">叠加轮与当前区间无重叠日期</span>`);
    }
  }

  const wan = (v) => (Math.abs(v) >= 10000 ? `${(v / 10000).toFixed(1)}万` : `${v}`);
  btChart.setOption({
    backgroundColor: "transparent",
    animation: false,
    textStyle: { color: t.text },
    color: t.series,
    title: { text: `净值与回撤 · ${run.run_id}`, left: 14, top: 10,
      textStyle: { fontSize: 13, fontWeight: 600, color: t.text } },
    tooltip: { trigger: "axis", formatter: chartTooltipFormatter, ...tooltipStyle(t),
      axisPointer: { type: "line", lineStyle: { color: t.axis, type: "dashed" } } },
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    legend: { top: 9, right: 14, itemWidth: 16, itemHeight: 8, itemGap: 14,
      textStyle: { color: t.dim, fontSize: 11 } },
    grid: [
      { left: 66, right: 26, top: 46, height: "50%" },
      { left: 66, right: 26, top: "72%", height: "19%" },
    ],
    xAxis: [
      { type: "category", data: dates, gridIndex: 0, boundaryGap: false,
        ...axisStyle(t), axisLabel: { show: false }, splitLine: { show: false } },
      { type: "category", data: dates, gridIndex: 1, boundaryGap: false,
        ...axisStyle(t), splitLine: { show: false } },
    ],
    yAxis: [
      { type: "value", scale: true, gridIndex: 0, ...axisStyle(t),
        axisLabel: { color: t.dim, fontSize: 11, formatter: wan } },
      { type: "value", gridIndex: 1, max: 0, ...axisStyle(t),
        axisLabel: { color: t.dim, fontSize: 11, formatter: "{value}%" } },
    ],
    dataZoom: [{ type: "inside", xAxisIndex: [0, 1] }],
    series: [
      // 策略净值: 平滑 + 主策略金色渐变面积 (其余仅描线避免叠加糊面)
      ...withCurve.map((s, si) => ({
        name: s.strategy, type: "line", smooth: 0.25,
        data: alignToAxis(s, s.equity_curve.values),
        showSymbol: false, xAxisIndex: 0, yAxisIndex: 0, connectNulls: true, z: 6 - si,
        lineStyle: { color: t.series[si % t.series.length], width: si === 0 ? 2.4 : 1.6 },
        itemStyle: { color: t.series[si % t.series.length] },
        ...(si === 0 ? { areaStyle: { color: vGradient(t.goldArea[0], t.goldArea[1]) } } : {}),
      })),
      ...(benchSeries ? [{
        name: "基准买入持有", type: "line", data: benchSeries, smooth: 0.25,
        showSymbol: false, xAxisIndex: 0, yAxisIndex: 0, connectNulls: true,
        lineStyle: { width: 1.5, type: "dashed", color: t.benchmark },
        itemStyle: { color: t.benchmark }, z: 4,
      }] : []),
      ...overlaySeries,
      ...withCurve.flatMap((s) => tradeScatter(s, axisIdx, t)),
      ...withCurve.map((s, si) => ({
        name: `回撤 ${s.strategy}`, type: "line", smooth: 0.25,
        data: alignToAxis(s, drawdown(s.equity_curve.values)),
        showSymbol: false, xAxisIndex: 1, yAxisIndex: 1, connectNulls: true,
        areaStyle: { color: vGradient(
          `${t.series[si % t.series.length]}33`, `${t.series[si % t.series.length]}00`) },
        lineStyle: { width: 1, color: t.series[si % t.series.length] },
        itemStyle: { color: t.series[si % t.series.length] },
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

// 主题切换 → 当前回测图重渲染换肤 (数据已在 currentBtRun, 无需重新拉取)
window.addEventListener("gh:theme", () => {
  if (currentBtRun) renderBtRun(currentBtRun).catch(() => {});
});
