/* ECharts 实例注册表 — 统一暗色主题与 resize */
"use strict";

const registry = [];

export function makeChart(el) {
  const chart = echarts.init(el, "dark");
  registry.push(chart);
  return chart;
}

export function resizeCharts() {
  setTimeout(() => registry.forEach((c) => c.resize()), 0);
}

window.addEventListener("resize", resizeCharts);
