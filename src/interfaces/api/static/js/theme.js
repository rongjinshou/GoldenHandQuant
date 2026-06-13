/* 日间/夜间主题切换 — 持久化 + 广播 gh:theme 供图表重渲染。
 * 首屏防闪: index.html <head> 内联脚本已先行设好 data-theme, 本模块只负责接管按钮。 */
"use strict";

const KEY = "ghq-theme";

function syncButton(theme) {
  const btn = document.getElementById("theme-toggle");
  if (!btn) return;
  // 显示"目标"图标: 当前夜间→显示太阳(去日间), 当前日间→显示月亮(去夜间)
  btn.textContent = theme === "light" ? "☾" : "☀";
  btn.title = theme === "light" ? "切换夜间模式" : "切换日间模式";
  btn.setAttribute("aria-label", btn.title);
}

export function initTheme() {
  const cur = document.documentElement.dataset.theme === "light" ? "light" : "dark";
  document.documentElement.dataset.theme = cur;
  syncButton(cur);

  const btn = document.getElementById("theme-toggle");
  if (!btn) return;
  btn.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem(KEY, next); } catch { /* 隐私模式忽略 */ }
    syncButton(next);
    window.dispatchEvent(new CustomEvent("gh:theme", { detail: next }));
  });
}
