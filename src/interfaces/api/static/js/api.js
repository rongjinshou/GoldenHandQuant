/* 基础 fetch / 错误条 / 数字格式化 — 全页共用 */
"use strict";

export const $ = (sel) => document.querySelector(sel);
export const API = "/api/research";

export async function fetchJSON(url) {
  const resp = await fetch(url);
  if (!resp.ok) {
    const body = await resp.text();
    if (resp.status === 503 && (window.__activeJobs || 0) > 0) {
      throw new Error("后台任务运行中，数据库写锁占用，稍后自动恢复");
    }
    throw new Error(`${resp.status} ${url}: ${body.slice(0, 200)}`);
  }
  return resp.json();
}

export async function postJSON(url, payload) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload ?? {}),
  });
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const detail = typeof body.detail === "string"
      ? body.detail : JSON.stringify(body.detail ?? body).slice(0, 300);
    throw new Error(`${resp.status}: ${detail}`);
  }
  return body;
}

export function showError(msg) {
  const el = $("#error-banner");
  el.textContent = `⚠ ${msg}`;
  el.classList.remove("hidden");
}

export function clearError() {
  $("#error-banner").classList.add("hidden");
}

export const f4 = (v) => v.toFixed(4);
export const f3 = (v) => v.toFixed(3);
export const f2 = (v) => v.toFixed(2);
export const pct = (v) => `${(v * 100).toFixed(2)}%`;
export const num = (v) => (v === null || v === undefined ? "-" : Number(v).toLocaleString());
