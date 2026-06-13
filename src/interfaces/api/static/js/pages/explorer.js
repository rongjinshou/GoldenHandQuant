/* 个股查看页 */
"use strict";

import { $, API, fetchJSON, showError, clearError } from "../api.js";
import { makeChart, chartTheme, axisStyle, tooltipStyle } from "../charts.js";

const DEFAULT_FEATURES = ["return_20d", "volatility_20d"];
const FEATURE_CHOICES = [
  "return_5d", "return_20d", "return_60d", "volatility_20d", "volatility_60d",
  "turnover_rate", "avg_turnover_20d", "rsi_14", "macd", "ma_20",
  "skewness_20d", "illiquidity_20d", "obv_slope_20d",
];

let klineChart = null;
let featureChart = null;

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

let lastKline = null;

function renderKline(symbol, data) {
  if (!klineChart) klineChart = makeChart($("#kline-chart"));
  const t = chartTheme();
  klineChart.setOption({
    backgroundColor: "transparent",
    animation: false,
    textStyle: { color: t.text },
    title: { text: `${symbol} 前复权日线`, left: 14, top: 10,
      textStyle: { fontSize: 13, fontWeight: 600, color: t.text } },
    tooltip: { trigger: "axis", axisPointer: { type: "cross", lineStyle: { color: t.axis } },
      ...tooltipStyle(t) },
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    grid: [
      { left: 58, right: 22, top: 46, height: "54%" },
      { left: 58, right: 22, top: "74%", height: "17%" },
    ],
    xAxis: [
      { type: "category", data: data.dates, gridIndex: 0, ...axisStyle(t), splitLine: { show: false } },
      { type: "category", data: data.dates, gridIndex: 1, ...axisStyle(t),
        axisLabel: { show: false }, splitLine: { show: false } },
    ],
    yAxis: [
      { scale: true, gridIndex: 0, ...axisStyle(t) },
      { gridIndex: 1, ...axisStyle(t), axisLabel: { show: false }, splitLine: { show: false } },
    ],
    dataZoom: [{ type: "inside", xAxisIndex: [0, 1] }, { type: "slider", xAxisIndex: [0, 1],
      height: 16, bottom: 8, borderColor: "transparent",
      fillerColor: `${t.gold}22`, handleStyle: { color: t.gold },
      textStyle: { color: t.dim } }],
    series: [
      {
        name: symbol, type: "candlestick", data: data.ohlc,
        itemStyle: { color: t.up, color0: t.down, borderColor: t.up, borderColor0: t.down },
      },
      { name: "成交量", type: "bar", data: data.volume, xAxisIndex: 1, yAxisIndex: 1,
        itemStyle: { color: t.vol } },
    ],
  }, true);
}

async function loadKline() {
  const symbol = pickedSymbol();
  if (!symbol) return;
  const data = await fetchJSON(`${API}/bars/${symbol}?${rangeParams()}`);
  lastKline = { symbol, data };
  renderKline(symbol, data);
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
  lastFeature = { symbol, names, data };
  renderFeature(symbol, names, data);
}

let lastFeature = null;

function renderFeature(symbol, names, data) {
  if (!featureChart) featureChart = makeChart($("#feature-chart"));
  const t = chartTheme();
  featureChart.setOption({
    backgroundColor: "transparent",
    animation: false,
    textStyle: { color: t.text },
    color: t.series,
    title: { text: `${symbol} 截面特征（T-1 信息口径）`, left: 14, top: 10,
      textStyle: { fontSize: 13, fontWeight: 600, color: t.text } },
    tooltip: { trigger: "axis", ...tooltipStyle(t),
      axisPointer: { type: "line", lineStyle: { color: t.axis, type: "dashed" } } },
    legend: { top: 9, right: 14, itemWidth: 16, itemHeight: 8,
      textStyle: { color: t.dim, fontSize: 11 } },
    grid: { left: 58, right: 22, top: 46, bottom: 40 },
    xAxis: { type: "category", data: data.dates, boundaryGap: false,
      ...axisStyle(t), splitLine: { show: false } },
    yAxis: { type: "value", scale: true, ...axisStyle(t) },
    dataZoom: [{ type: "inside" }],
    series: names.map((n) => ({
      name: n, type: "line", data: data.series[n], smooth: 0.2,
      showSymbol: false, connectNulls: false, lineStyle: { width: 1.6 },
    })),
  }, true);
}

export function initExplorer() {
  initFeaturePicker();

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
}

// 主题切换 → 已加载的 K线/特征图重渲染换肤
window.addEventListener("gh:theme", () => {
  if (lastKline) renderKline(lastKline.symbol, lastKline.data);
  if (lastFeature) renderFeature(lastFeature.symbol, lastFeature.names, lastFeature.data);
});
