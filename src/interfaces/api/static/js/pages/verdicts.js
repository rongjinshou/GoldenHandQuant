/* 因子判决页 */
"use strict";

import { $, API, fetchJSON, f4, f3, f2, pct, showError, clearError } from "../api.js";
import { submitJob, attachJobCard } from "../jobs.js";
import { applyGlossary } from "../glossary.js";

const GATES = {
  ic_mean: (v) => v >= 0.02,
  ir: (v) => v >= 0.3,
  monotonicity_score: (v) => v >= 0.6,
  long_short_return: (v) => v > 0,
  oos_long_short_return: (v) => v > 0,
  // long-only 记分牌门槛 (与 verdict.py 同步; 单一真相源收敛留作债 D2)
  excess_ir: (v) => v >= 0.5,
  excess_positive_rate: (v) => v >= 0.52,
  top_excess_return: (v) => v > 0,
  oos_top_excess_return: (v) => v > 0,
};

function gateCell(name, value, fmt) {
  if (value === null || value === undefined) return `<td class="gate-na">-</td>`;
  const cls = name in GATES ? (GATES[name](value) ? "gate-good" : "gate-bad") : "";
  return `<td class="${cls}">${fmt(value)}</td>`;
}

let verdictRuns = [];

export async function loadVerdicts() {
  const data = await fetchJSON(`${API}/verdicts`);
  verdictRuns = data.runs;
  const select = $("#run-select");
  select.innerHTML = "";
  $("#verdicts-empty").classList.toggle("hidden", verdictRuns.length > 0);
  verdictRuns.forEach((run, i) => {
    select.insertAdjacentHTML(
      "beforeend",
      `<option value="${i}">${run.run_id}（${run.created_at.slice(0, 19)}）</option>`
    );
  });
  select.onchange = () => renderRun(verdictRuns[Number(select.value)]);
  if (verdictRuns.length) renderRun(verdictRuns[0]);
}

function renderRun(run) {
  const p = run.params || {};
  const longOnly = p.objective === "long_only";
  const scorecard = longOnly ? "长多(Top超额)" : "多空";
  $("#run-params").textContent =
    `${p.start || "?"} → ${p.end || "?"} · 切分 ${p.split || "无"} · ` +
    `${p.rebalance_days || 1} 日调仓 · ${scorecard}记分牌 · ` +
    `${p.universe_count || "?"} 只 · 特征 v${p.feature_version || "?"}`;

  // 可切换表头随 objective 变化
  $("#th-stability").textContent = longOnly ? "超额IR" : "IR";
  $("#th-posrate").textContent = longOnly ? "超额正率" : "IC正率";
  $("#th-realize-is").textContent = longOnly ? "Top超额(IS)" : "多空(IS)";
  $("#th-realize-oos").textContent = longOnly ? "Top超额(OOS)" : "多空(OOS)";

  const tbody = $("#verdict-table tbody");
  tbody.innerHTML = "";
  for (const f of run.factors) {
    const badge = f.passed
      ? `<span class="badge pass">PASS</span>`
      : `<span class="badge fail">FAIL</span>`;
    const stabilityCell = longOnly
      ? gateCell("excess_ir", f.excess_ir, f2)
      : gateCell("ir", f.ir, f3);
    const posrateCell = longOnly
      ? gateCell("excess_positive_rate", f.excess_positive_rate, pct)
      : gateCell("ic_positive_rate", f.ic_positive_rate, pct);
    const realizeIsCell = longOnly
      ? gateCell("top_excess_return", f.top_excess_return, pct)
      : gateCell("long_short_return", f.long_short_return, pct);
    const realizeOosCell = longOnly
      ? gateCell("oos_top_excess_return", f.oos_top_excess_return, pct)
      : gateCell("oos_long_short_return", f.oos_long_short_return, pct);
    tbody.insertAdjacentHTML(
      "beforeend",
      `<tr>
         <td>${f.factor_id}</td><td>${f.factor_name || ""}</td>
         <td><code>${f.expression || ""}</code></td>
         ${gateCell("ic_mean", f.ic_mean, f4)}
         ${stabilityCell}
         ${posrateCell}
         ${gateCell("monotonicity_score", f.monotonicity_score, f2)}
         ${realizeIsCell}
         ${gateCell("oos_ic_mean", f.oos_ic_mean, f4)}
         ${gateCell("oos_ir", f.oos_ir, f3)}
         ${realizeOosCell}
         <td>${f.score != null ? f.score.toFixed(0) : "-"}（${f.grade || "-"}）</td>
         <td>${badge}</td>
       </tr>
       <tr class="reasons-row"><td colspan="13">${(f.reasons || []).join(" ｜ ")}</td></tr>`
    );
  }
}

export async function initFactorForm() {
  const data = await fetchJSON("/api/meta/factors");
  const byId = Object.fromEntries(data.factors.map((f) => [f.factor_id, f]));
  const html = [];
  for (const [group, ids] of Object.entries(data.groups)) {
    html.push(`<span class="group-title" data-gloss="factor_group">${group}</span>`);
    for (const id of ids) {
      const f = byId[id];
      const dis = f.field_ready === false;
      html.push(`<label class="${dis ? "disabled" : ""}"
        title="${f.expression}${dis ? "（数据管道缺字段，禁用）" : ""}">
        <input type="checkbox" value="${id}" ${dis ? "disabled" : ""}
               ${group === "P0" && !dis ? "checked" : ""}>${id} ${f.name}</label>`);
    }
  }
  $("#ft-factors").innerHTML = html.join("");
  applyGlossary($("#ft-factors"));
  $("#ft-factors").addEventListener("change", updateFtHint);
  $("#ft-split").addEventListener("change", updateFtHint);
  $("#ft-submit").addEventListener("click", submitFactorTest);
  updateFtHint();
}

function ftSelected() {
  return [...document.querySelectorAll("#ft-factors input:checked")].map((c) => c.value);
}

function updateFtHint() {
  const many = ftSelected().length > 1;
  const noSplit = !$("#ft-split").value;
  const show = many && noSplit;
  $("#ft-hint").classList.toggle("hidden", !show);
  if (show) $("#ft-hint").textContent =
    "多因子批量检验未设 IS/OOS 切分——存在多重检验风险，建议保留切分日期。";
}

async function submitFactorTest() {
  clearError();
  const ids = ftSelected();
  if (!ids.length) { showError("至少勾选一个因子"); return; }
  const payload = {
    factors: ids.join(","),
    start_date: $("#ft-start").value,
    end_date: $("#ft-end").value,
    objective: $("#ft-objective").value,
    num_layers: Number($("#ft-layers").value),
    rebalance_days: Number($("#ft-rebalance").value),
    cost_rate: Number($("#ft-cost").value),
  };
  if ($("#ft-split").value) payload.split_date = $("#ft-split").value;
  try {
    const job = await submitJob("factor-test", payload);
    attachJobCard($("#ft-job-area"), job.job_id, {
      onDone: () => loadVerdicts().catch((e) => showError(e.message)),
    });
  } catch (err) {
    showError(err.message);
  }
}
