/* 数据资产总览页 */
"use strict";

import { $, API, fetchJSON, showError, clearError } from "../api.js";
import { submitJob, attachJobCard } from "../jobs.js";

const TABLE_LABELS = {
  instruments: "股票池",
  bars: "日线行情",
  fundamental_snapshots: "基本面快照",
  stock_features: "截面特征",
};

export async function loadOverview() {
  const data = await fetchJSON(`${API}/overview`);
  $("#db-path").textContent = data.db_path;
  $("#feature-version").textContent = data.feature_version;
  $("#meta").textContent = data.db_exists
    ? `判决轮次 ${data.verdict_runs} · 特征版本 v${data.feature_version}`
    : "数据库不存在";

  const cards = $("#overview-cards");
  cards.innerHTML = "";
  let totalRows = 0;
  for (const [table, s] of Object.entries(data.tables)) {
    totalRows += s.rows;
    // 股票池等静态表没有日期区间, 显示 "—" 而非误导性的 "无数据"
    const range = s.min_date ? `${s.min_date} ~ ${s.max_date}` : "—";
    cards.insertAdjacentHTML(
      "beforeend",
      `<div class="card">
         <h3>${TABLE_LABELS[table] || table}</h3>
         <div class="big">${s.rows.toLocaleString()}</div>
         <div class="dim">${s.symbols.toLocaleString()} 只标的 · ${range}</div>
       </div>`
    );
  }
  $("#overview-empty").classList.toggle("hidden", totalRows > 0);
}

export function initRefreshForm() {
  $("#dr-submit").addEventListener("click", async () => {
    clearError();
    try {
      const job = await submitJob("data-refresh", {
        start_date: $("#dr-start").value, end_date: $("#dr-end").value });
      attachJobCard($("#dr-job-area"), job.job_id, {
        onDone: () => loadOverview().catch((e) => showError(e.message)),
      });
    } catch (err) {
      showError(err.message);
    }
  });
}
