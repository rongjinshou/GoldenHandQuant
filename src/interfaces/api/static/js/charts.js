/* ECharts 实例注册表 + 暗/亮主题调色 + resize
 * 图表颜色全部由各 setOption 通过 chartTheme() 显式控制, 不依赖 ECharts 命名主题,
 * 这样 html[data-theme] 切换后重渲染即可换肤。 */
"use strict";

const registry = [];

export function makeChart(el) {
  const chart = echarts.init(el);
  registry.push(chart);
  return chart;
}

export function resizeCharts() {
  setTimeout(() => registry.forEach((c) => c.resize()), 0);
}
window.addEventListener("resize", resizeCharts);

/* 当前图表调色板（随 html[data-theme] 切换）。
   A 股语义: 涨/买=红(up), 跌/卖=绿(down); 金为品牌主序列色。 */
export function chartTheme() {
  const light = document.documentElement.dataset.theme === "light";
  return light ? {
    panelBg: "#ffffff",
    text: "#1c2430", dim: "#5b6675", split: "rgba(0,0,0,.055)", axis: "rgba(0,0,0,.16)",
    gold: "#bf8a1e", up: "#d8453a", down: "#1f9d57", benchmark: "#9aa5b3",
    vol: "rgba(47,127,214,.28)",
    tipBg: "rgba(255,255,255,.97)", tipBorder: "#d8dee7", tipText: "#1c2430",
    series: ["#bf8a1e", "#2a8fb0", "#8a5cc4", "#c2702a", "#3a7bd0"],
    overlay: ["#7c4fc0", "#c2702a", "#6b7480"],
    goldArea: ["rgba(191,138,30,.26)", "rgba(191,138,30,0)"],
  } : {
    panelBg: "#141a22",
    text: "#e7ecf3", dim: "#8a95a4", split: "rgba(255,255,255,.05)", axis: "rgba(255,255,255,.13)",
    gold: "#e9b949", up: "#ff6f61", down: "#4cc66e", benchmark: "#8b949e",
    vol: "rgba(95,168,255,.28)",
    tipBg: "rgba(20,26,34,.96)", tipBorder: "#313c4a", tipText: "#d9e1ec",
    series: ["#e9b949", "#46b3c9", "#b48ce6", "#d98a4a", "#5fa8ff"],
    overlay: ["#8957e5", "#db6d28", "#6e7681"],
    goldArea: ["rgba(233,185,73,.30)", "rgba(233,185,73,0)"],
  };
}

/* 通用坐标轴/网格样式 */
export function axisStyle(t) {
  return {
    axisLine: { lineStyle: { color: t.axis } },
    axisTick: { show: false },
    axisLabel: { color: t.dim, fontSize: 11 },
    splitLine: { lineStyle: { color: t.split } },
  };
}

/* 通用 tooltip 样式 (毛玻璃浮层) */
export function tooltipStyle(t) {
  return {
    backgroundColor: t.tipBg, borderColor: t.tipBorder, borderWidth: 1,
    textStyle: { color: t.tipText, fontSize: 12 },
    extraCssText: "backdrop-filter: blur(6px); border-radius: 9px;"
      + " box-shadow: 0 10px 30px rgba(0,0,0,.28); padding: 8px 11px;",
  };
}

/* 竖直渐变 (ECharts JSON LinearGradient, 免 import echarts.graphic) */
export function vGradient(c0, c1) {
  return {
    type: "linear", x: 0, y: 0, x2: 0, y2: 1,
    colorStops: [{ offset: 0, color: c0 }, { offset: 1, color: c1 }],
  };
}
