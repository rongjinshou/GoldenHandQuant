/* 任务提交与状态卡片 — 各页表单复用 */
"use strict";

import { $, fetchJSON, postJSON } from "./api.js";

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
  if (p.start_date) parts.push(`${p.start_date}~${p.end_date || ""}`);
  if (p.objective) parts.push(p.objective);
  return parts.join(" · ").slice(0, 80);
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

  cancelBtn.addEventListener("click", async () => {
    try { await postJSON(`/api/jobs/${jobId}/cancel`); } catch { /* 已结束 */ }
  });

  async function tick() {
    let job;
    try {
      job = await fetchJSON(`/api/jobs/${jobId}?tail=120`);
    } catch { return; }
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
