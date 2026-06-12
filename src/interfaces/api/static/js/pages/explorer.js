/* 个股查看页 */
"use strict";

import { $, API, fetchJSON, showError, clearError } from "../api.js";
import { makeChart } from "../charts.js";

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

async function loadKline() {
  const symbol = pickedSymbol();
  if (!symbol) return;
  const data = await fetchJSON(`${API}/bars/${symbol}?${rangeParams()}`);
  if (!klineChart) klineChart = makeChart($("#kline-chart"));
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
  if (!featureChart) featureChart = makeChart($("#feature-chart"));
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
