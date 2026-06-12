/* 任务提交与状态卡片 — 各页表单复用 */
"use strict";

import { $, fetchJSON, postJSON, showError, clearError } from "./api.js";

export async function submitJob(type, payload) {
  return postJSON(`/api/jobs/${type}`, payload);
}

export const STATUS_LABEL = {
  queued: "排队中", running: "运行中", succeeded: "已完成",
  failed: "失败", canceled: "已取消",
};

export function durationOf(job) {
  if (!job.started_at) return "-";
  const end = job.finished_at ? new Date(job.finished_at) : new Date();
  const sec = Math.max(0, (end - new Date(job.started_at)) / 1000);
  return sec < 90 ? `${sec.toFixed(0)}s` : `${(sec / 60).toFixed(1)}min`;
}

export function paramsSummary(job) {
  const p = job.params || {};
  const parts = [];
  if (p.strategies) parts.push(p.strategies.join(","));
  if (p.factors) parts.push(p.factors);
  if (p.model_name) parts.push(p.model_name);
  if (p.symbols) {
    const arr = Array.isArray(p.symbols) ? p.symbols : String(p.symbols).split(",");
    parts.push(arr.length <= 2 ? arr.join(",") : `${arr.slice(0, 2).join(",")}等${arr.length}只`);
  }
  if (p.start_date) parts.push(`${p.start_date}~${p.end_date || ""}`);
  if (p.objective) parts.push(p.objective);
  return parts.join(" · ").slice(0, 90);
}

/* 在 container 内渲染一张实时刷新的任务卡; 终态后停轮询并回调 onDone(job) */
export function attachJobCard(container, jobId, { onDone } = {}) {
  const card = document.createElement("div");
  card.className = "job-card";
  card.innerHTML = `
    <div class="head">
      <span class="badge queued">排队中</span>
      <span class="dim job-meta"></span>
      <button class="btn-danger job-cancel">取消</button>
    </div>
    <pre class="job-log">等待日志…</pre>`;
  container.prepend(card);

  const badge = card.querySelector(".badge");
  const meta = card.querySelector(".job-meta");
  const logEl = card.querySelector(".job-log");
  const cancelBtn = card.querySelector(".job-cancel");
  let timer = null;
  let done = false;
  // Fix #8: 连续失败计数器，达 5 次终止轮询
  let failCount = 0;

  cancelBtn.addEventListener("click", async () => {
    try { await postJSON(`/api/jobs/${jobId}/cancel`); } catch { /* 已结束 */ }
  });

  async function tick() {
    let job;
    try {
      job = await fetchJSON(`/api/jobs/${jobId}?tail=120`);
      // Fix #8: 成功后清零计数器
      failCount = 0;
    } catch {
      // Fix #8: 连续 5 次失败停止轮询
      failCount += 1;
      if (failCount >= 5) {
        clearInterval(timer);
        badge.className = "badge failed";
        badge.textContent = "查询失败";
        logEl.textContent = "查询失败（服务可能已重启）";
        cancelBtn.remove();
      }
      return;
    }
    badge.className = `badge ${job.status}`;
    badge.textContent = STATUS_LABEL[job.status] || job.status;
    meta.textContent = `${job.job_type} · ${paramsSummary(job)} · 耗时 ${durationOf(job)}`;
    if (job.log_tail && job.log_tail.length) {
      logEl.textContent = job.log_tail.join("\n");
      logEl.scrollTop = logEl.scrollHeight;
    }
    const terminal = ["succeeded", "failed", "canceled"].includes(job.status);
    if (terminal && !done) {
      done = true;
      clearInterval(timer);
      cancelBtn.remove();
      if (job.status === "succeeded" && onDone) onDone(job);
    }
  }
  tick();
  timer = setInterval(tick, 2000);
  return card;
}

export async function loadJobsPage() {
  const data = await fetchJSON("/api/jobs?limit=100");
  $("#jobs-empty").classList.toggle("hidden", data.jobs.length > 0);
  $("#jobs-table tbody").innerHTML = data.jobs.map((j) => `
    <tr class="clickable" data-job="${j.job_id}">
      <td><code>${j.job_id}</code></td><td>${j.job_type}</td>
      <td style="text-align:left">${paramsSummary(j)}</td>
      <td><span class="badge ${j.status}">${STATUS_LABEL[j.status] || j.status}</span></td>
      <td>${(j.created_at || "").slice(5, 19)}</td>
      <td>${durationOf(j)}</td>
      <td>${["queued", "running"].includes(j.status)
            ? `<button class="btn-danger" data-cancel="${j.job_id}">取消</button>` : ""}</td>
    </tr>`).join("");
  $("#jobs-table tbody").querySelectorAll("[data-cancel]").forEach((btn) =>
    btn.addEventListener("click", async (ev) => {
      ev.stopPropagation();
      try { await postJSON(`/api/jobs/${btn.dataset.cancel}/cancel`); } catch { /* 已结束 */ }
      // Fix #5: 裸调用加 catch
      loadJobsPage().catch(() => {});
    }));
  $("#jobs-table tbody").querySelectorAll("tr.clickable").forEach((tr) =>
    tr.addEventListener("click", () => showJobLog(tr.dataset.job)));
}

let logTimer = null;

async function showJobLog(jobId) {
  clearInterval(logTimer);
  // Fix #3: 连续失败计数器
  let logFailCount = 0;
  async function tick() {
    try {
      const job = await fetchJSON(`/api/jobs/${jobId}?tail=300`);
      // Fix #3: 成功清零
      logFailCount = 0;
      $("#job-log-title").textContent = `${jobId} · ${STATUS_LABEL[job.status] || job.status}`;
      $("#job-log").textContent = (job.log_tail || []).join("\n") || "（无输出）";
      $("#job-log").scrollTop = $("#job-log").scrollHeight;
      if (["succeeded", "failed", "canceled"].includes(job.status)) clearInterval(logTimer);
    } catch {
      // Fix #3: 连续 5 次失败停止轮询并提示
      logFailCount += 1;
      if (logFailCount >= 5) {
        clearInterval(logTimer);
        $("#job-log").textContent = "任务查询失败（服务可能已重启）";
      }
      // 未达阈值时静默 return
    }
  }
  await tick();
  logTimer = setInterval(tick, 2000);
}

export function initMlForms() {
  $("#ml-train-submit").addEventListener("click", async () => {
    // Fix #5: 清空旧错误
    clearError();
    try {
      const job = await submitJob("ml-train", {
        start_date: $("#ml-start").value, end_date: $("#ml-end").value,
        symbols: $("#ml-symbols").value.trim(),
        model_name: $("#ml-model").value.trim(),
        n_trials: Number($("#ml-trials").value),
      });
      // Fix #5: onDone 加 catch
      attachJobCard($("#ml-job-area"), job.job_id, { onDone: () => loadJobsPage().catch(() => {}) });
    } catch (err) { showError(err.message); }
  });
  $("#ml-eval-submit").addEventListener("click", async () => {
    // Fix #5: 清空旧错误
    clearError();
    try {
      const job = await submitJob("ml-evaluate", {
        model_name: $("#ml-model").value.trim(),
        eval_start: $("#mle-start").value, eval_end: $("#mle-end").value,
      });
      // Fix #5: onDone 加 catch
      attachJobCard($("#ml-job-area"), job.job_id, { onDone: () => loadJobsPage().catch(() => {}) });
    } catch (err) { showError(err.message); }
  });
}
