/* 启动: 页签路由 + 各页装配 + 全局任务指示灯 */
"use strict";

import { $, fetchJSON, showError } from "./api.js";
import { resizeCharts } from "./charts.js";
import { loadOverview, initRefreshForm } from "./pages/overview.js";
import { loadVerdicts, initFactorForm } from "./pages/verdicts.js";
import { initExplorer } from "./pages/explorer.js";
import { loadBacktests, initBacktestForm } from "./pages/backtests.js";
import { setLivePolling } from "./pages/live.js";

const TABS = ["overview", "verdicts", "explorer", "backtests", "live", "jobs"];

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $(`#tab-${btn.dataset.tab}`).classList.add("active");
    location.hash = btn.dataset.tab;
    if (btn.dataset.tab === "explorer") resizeCharts();
    if (btn.dataset.tab === "backtests") loadBacktests().catch((e) => showError(e.message));
    setLivePolling(btn.dataset.tab === "live");
  });
});

// 全局任务指示灯（Task 13 完整接管; 先保底显示活跃数）
async function pollIndicator() {
  try {
    const data = await fetchJSON("/api/jobs?limit=20");
    const active = data.jobs.filter(
      (j) => j.status === "queued" || j.status === "running").length;
    window.__activeJobs = active;
    $("#job-indicator").classList.toggle("hidden", active === 0);
    $("#job-count").textContent = String(active);
  } catch { /* 指示灯失败静默 */ }
}
setInterval(pollIndicator, 5000);

(async function init() {
  initExplorer();
  initBacktestForm().catch(() => {});
  initFactorForm().catch(() => {});
  initRefreshForm();
  const tab = location.hash.replace("#", "");
  if (tab && TABS.includes(tab)) {
    document.querySelector(`.tab[data-tab="${tab}"]`).click();
  }
  pollIndicator();
  try {
    await Promise.all([loadOverview(), loadVerdicts()]);
  } catch (err) {
    showError(err.message);
  }
})();
