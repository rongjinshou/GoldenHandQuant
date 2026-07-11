"""投研驾驶舱 UI 深度探针（6σ R5 Measure 阶段测量仪器, Playwright, Windows python 运行）。

只测量不修复: 真交互驱动(快捷键/表单/深链/图表联动/过滤排序) + 亮暗双主题截图
+ axe-core 无障碍扫描 + 重负载渲染计时 + bundle 尺寸。产出 findings 原始数据。

用法:
    # 先起服务: $WIN_PYTHON -m src.interfaces.cli.quant dashboard
    $WIN_PYTHON scripts/ui_deep_probe.py
    $WIN_PYTHON scripts/ui_deep_probe.py --base http://127.0.0.1:8501 --out data/ui_probe

分节执行, 单节异常不中断全局(记为仪器缺陷继续跑)。报告: <out>/probe_report.json。
退出码: 0 = 跑完(无论 findings 多少); 2 = 探针自身没跑起来。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import traceback
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

sys.stdout.reconfigure(encoding="utf-8")  # Windows 管道下中文不炸

VIEWPORT = {"width": 1680, "height": 1050}
AXE_JS = Path("frontend/node_modules/axe-core/axe.min.js")
IGNORED_REQUEST_SUBSTR = ("favicon.ico",)

# 与 scripts/ui_smoke.py 同一锚点约定
TABS = [
    ("overview", "01-overview", ['[data-testid="kpi-card"]', '[data-testid="overview-empty"]']),
    ("explorer", "02-explorer", ['[data-testid="kline-chart"] canvas']),
    ("verdicts", "03-verdicts", ['[data-testid="ft-factor-chip"]']),
    ("backtests", "04-backtests", ['[data-testid="bt-strategies"]']),
    ("live", "05-live", ['[data-testid="live-kpi"]', '[data-testid="live-empty"]']),
    ("jobs", "06-jobs", ['[data-testid="jobs-table"]']),
]


# ---------------------------------------------------------------- 报告骨架
class Probe:
    """探针状态容器: 事件按当前节打标, 汇总 findings。"""

    def __init__(self, base: str, out: Path) -> None:
        self.base = base
        self.out = out
        self.step = "init"
        self.report: dict = {
            "base": base,
            "sections": {},          # 节名 → {status, checks:[{name,ok,detail}], notes}
            "console_errors": [],    # {step,type,text}
            "page_errors": [],       # {step,text}
            "failed_requests": [],   # {step,url,status}
            "console_warnings": [],
            "findings": [],          # 汇总编号后的缺陷
            "instrument_defects": [],  # 仪器自身问题(选择器失效/节崩溃)
            "axe": {"pages": [], "impact_counts": {}, "unique_rules": []},
            "timing": {},
            "bundle": {},
        }

    # -- 事件捕获(挂在 page 上) --
    def wire(self, page: Page) -> None:
        def on_console(m):  # noqa: ANN001
            entry = {"step": self.step, "type": m.type, "text": m.text}
            if m.type == "error":
                self.report["console_errors"].append(entry)
            elif m.type == "warning":
                self.report["console_warnings"].append(entry)

        page.on("console", on_console)
        page.on("pageerror", lambda e: self.report["page_errors"].append(
            {"step": self.step, "text": str(e)}))
        page.on("response", lambda r: self.report["failed_requests"].append(
            {"step": self.step, "url": r.url, "status": r.status})
            if r.status >= 400 and not any(s in r.url for s in IGNORED_REQUEST_SUBSTR)
            else None)
        page.on("requestfailed", lambda r: self.report["failed_requests"].append(
            {"step": self.step, "url": r.url, "status": f"FAILED:{r.failure}"})
            if not any(s in r.url for s in IGNORED_REQUEST_SUBSTR) else None)

    def defect(self, text: str) -> None:
        self.report["instrument_defects"].append({"step": self.step, "text": text})
        print(f"  [仪器缺陷] {text}")


def check(sec: dict, name: str, ok: bool, detail: str = "", sev: str = "中",
          evidence: str = "") -> bool:
    """记录一条测量结果; 失败自带严重度与证据线索(汇总期转 finding)。"""
    sec["checks"].append({"name": name, "ok": bool(ok), "detail": detail,
                          "sev": sev, "evidence": evidence})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return bool(ok)


def wait_any(page: Page, selectors: list[str], timeout_ms: int = 10_000) -> str | None:
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        for sel in selectors:
            if page.query_selector(sel) is not None:
                return sel
        time.sleep(0.2)
    return None


def goto_tab(page: Page, probe: Probe, tab: str, reload: bool = False) -> None:
    """进入页签: reload=True 走整页 goto(状态清零), 否则点导航(SPA 内切)。"""
    if reload:
        page.goto(f"{probe.base}/ui/#/{tab}", wait_until="domcontentloaded")
        page.wait_for_selector('[data-testid="app-shell"]', timeout=10_000)
    else:
        page.click(f'[data-testid="nav-{tab}"]')
    page.wait_for_selector(f'[data-testid="page-{tab}"]', timeout=10_000)


def canvas_hash(page: Page, css: str) -> object:
    """canvas 稀疏像素哈希 — 判定图表是否重绘/两次渲染是否不同。"""
    return page.evaluate(
        """(css) => {
          const c = document.querySelector(css);
          if (!c) return null;
          const ctx = c.getContext('2d');
          if (!ctx) return 'noctx';
          const w = c.width, h = c.height;
          if (!w || !h) return 'empty';
          let hash = 7;
          const step = Math.max(1, Math.floor(h / 24));
          for (let y = 0; y < h; y += step) {
            const row = ctx.getImageData(0, y, w, 1).data;
            for (let x = 0; x < row.length; x += 48) hash = ((hash * 33) ^ row[x]) >>> 0;
          }
          return hash;
        }""",
        css,
    )


def settled_hash(page: Page, css: str) -> object:
    """把鼠标停到角落再取像素哈希 — axisPointer/dataZoom 把手标签都画进 canvas,
    悬停残留会污染哈希(首轮 A4.4 假阳性教训), 先离场等淡出再采样。"""
    page.mouse.move(5, 5)
    time.sleep(0.7)
    return canvas_hash(page, css)


def load_explorer_symbol(page: Page, symbol: str = "000021.SZ") -> None:
    """行情页填一个库内标的并加载, 等 K 线 canvas。"""
    page.fill('[data-testid="explorer-symbol-input"] input', symbol)
    page.click('[data-testid="explorer-load"]')
    page.wait_for_selector('[data-testid="kline-chart"] canvas', timeout=15_000)
    time.sleep(1.2)  # 图表渲染余量


def api_json(base: str, path: str) -> dict:
    with urllib.request.urlopen(f"{base}{path}", timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------------------------------------------------------------- A1 快捷键
def sec_a1_hotkeys(page: Page, probe: Probe, sec: dict) -> None:
    goto_tab(page, probe, "overview", reload=True)
    time.sleep(1.0)
    page.evaluate("document.activeElement && document.activeElement.blur()")

    page.keyboard.press("3")
    time.sleep(0.6)
    h = page.evaluate("location.hash")
    check(sec, "A1.1 按 '3' 切到判决页", "verdicts" in h, f"hash={h}", sev="中")

    page.keyboard.press("?")
    try:
        page.wait_for_selector('[data-testid="hotkey-help"]', state="visible", timeout=4000)
        page.screenshot(path=str(probe.out / "a1_help_open.png"))
        check(sec, "A1.2 按 '?' 打开快捷键帮助浮层", True, evidence="a1_help_open.png")
    except Exception:
        page.screenshot(path=str(probe.out / "a1_help_open.png"))
        check(sec, "A1.2 按 '?' 打开快捷键帮助浮层", False,
              "4s 内未见 [data-testid=hotkey-help]", sev="中", evidence="a1_help_open.png")

    page.keyboard.press("Escape")
    try:
        page.wait_for_selector('[data-testid="hotkey-help"]', state="hidden", timeout=4000)
        check(sec, "A1.3 Esc 关闭帮助浮层", True)
    except Exception:
        check(sec, "A1.3 Esc 关闭帮助浮层", False, "浮层未关闭", sev="中")

    # 输入框聚焦时数字键让路
    goto_tab(page, probe, "backtests")
    page.wait_for_selector('[data-testid="bt-symbols-input"]', timeout=8000)
    page.focus('[data-testid="bt-symbols-input"]')
    page.keyboard.press("2")
    time.sleep(0.5)
    h = page.evaluate("location.hash")
    ok = "backtests" in h
    check(sec, "A1.4 input 聚焦时按 '2' 不切页", ok, f"hash={h}", sev="中")
    # 顺带: input 聚焦时 '?' 不应弹帮助
    page.keyboard.press("?")
    time.sleep(0.4)
    modal = page.query_selector('[data-testid="hotkey-help"]')
    visible = bool(modal) and modal.is_visible()
    check(sec, "A1.5 input 聚焦时按 '?' 不弹帮助", not visible, sev="低")
    if visible:
        page.keyboard.press("Escape")
    # 清残留输入(bt-symbols-input 是普通 input, 里面留了 '2?' 文本)
    page.fill('[data-testid="bt-symbols-input"]', "")
    page.keyboard.press("Escape")


# ---------------------------------------------------------------- A2 回测参数面板
def sec_a2_bt_params(page: Page, probe: Probe, sec: dict) -> None:
    goto_tab(page, probe, "backtests", reload=True)
    page.wait_for_selector('[data-testid="bt-strategies"]', timeout=10_000)
    time.sleep(0.8)

    box = page.locator('[data-testid="bt-strategies"] .strat-item',
                       has_text="micro_value").locator(".n-checkbox")
    box.first.click()
    try:
        page.wait_for_selector('[data-testid="bt-params-micro_value"]', timeout=5000)
        check(sec, "A2.1 勾选 micro_value 出现参数面板", True)
    except Exception:
        check(sec, "A2.1 勾选 micro_value 出现参数面板", False,
              "未见 bt-params-micro_value", sev="高")
        return

    item = page.locator('[data-testid="bt-params-micro_value"] .param-item',
                        has_text="top_n").first
    def_text = item.locator(".param-def").first.inner_text()
    inp = item.locator("input").first
    inp.click()
    page.keyboard.press("Control+a")
    page.keyboard.type("15")
    time.sleep(0.5)
    cls = item.get_attribute("class") or ""
    page.screenshot(path=str(probe.out / "a2_params_overridden.png"))
    check(sec, "A2.2 top_n 改 15 → 「已改」高亮类出现",
          "param-item--overridden" in cls,
          f"class={cls!r} 默认标注={def_text!r}", sev="中",
          evidence="a2_params_overridden.png")

    reset_btn = item.locator(".param-def--reset")
    has_reset = reset_btn.count() > 0
    check(sec, "A2.3 已改后「默认 9」变可点按钮", has_reset,
          f"默认标注文本={def_text!r}", sev="中")
    if has_reset:
        reset_btn.first.click()
        time.sleep(0.5)
        val = inp.input_value()
        cls2 = item.get_attribute("class") or ""
        page.screenshot(path=str(probe.out / "a2_params_reset.png"))
        check(sec, "A2.4 点「默认 9」回默认且高亮消失",
              val == "9" and "param-item--overridden" not in cls2,
              f"input={val!r} class={cls2!r}", sev="中", evidence="a2_params_reset.png")
    # 不点提交


# ---------------------------------------------------------------- A3 深链 + 前进后退
def sec_a3_deeplink(page: Page, probe: Probe, sec: dict) -> None:
    runs = api_json(probe.base, "/api/research/backtests")["runs"]
    non_latest = [r["run_id"] for r in runs[1:]
                  if (r.get("strategies") or [{}])[0].get("equity_curve", {}).get("dates")]
    if not non_latest:
        check(sec, "A3.0 数据前置: 存在非最新且有曲线的 run", False, "库内不足", sev="低")
        return
    rid = non_latest[-1]  # 取最老的一条, 与默认选中(最新)差异最大
    sec["notes"] = f"深链目标 run={rid}, 最新 run={runs[0]['run_id']}"

    page.goto(f"{probe.base}/ui/#/backtests?run={rid}", wait_until="domcontentloaded")
    page.wait_for_selector('[data-testid="page-backtests"]', timeout=10_000)
    try:
        page.wait_for_selector(".run-row.active", timeout=8000)
    except Exception:
        pass
    time.sleep(1.5)
    active_id = ""
    el = page.query_selector(".run-row.active .run-id")
    if el:
        active_id = el.inner_text().strip()
    page.screenshot(path=str(probe.out / "a3_deeplink.png"), full_page=True)
    check(sec, f"A3.1 深链 ?run={rid} 详情选中该轮", active_id == rid,
          f"左轨激活行 run_id={active_id!r}", sev="高", evidence="a3_deeplink.png")

    # 制造一条历史(SPA 内 push), 然后后退/前进
    page.click('[data-testid="nav-overview"]')
    page.wait_for_selector('[data-testid="page-overview"]', timeout=8000)
    errs_before = len(probe.report["page_errors"])
    page.go_back()
    time.sleep(1.2)
    h_back = page.evaluate("location.hash")
    el = page.query_selector(".run-row.active .run-id")
    back_id = el.inner_text().strip() if el else ""
    page.go_forward()
    time.sleep(1.0)
    h_fwd = page.evaluate("location.hash")
    errs_after = len(probe.report["page_errors"])
    check(sec, "A3.2 后退回到 ?run= 深链且选中恢复",
          "backtests" in h_back and back_id == rid,
          f"hash={h_back} 激活={back_id!r}", sev="中")
    check(sec, "A3.3 前进回总览且无页面异常",
          "overview" in h_fwd and errs_after == errs_before,
          f"hash={h_fwd} 新增 pageerror={errs_after - errs_before}", sev="高")


# ---------------------------------------------------------------- A4 行情页
def sec_a4_explorer(page: Page, probe: Probe, sec: dict) -> None:
    goto_tab(page, probe, "explorer", reload=True)
    load_explorer_symbol(page)

    recent = page.query_selector('[data-testid="explorer-recent"]')
    page.screenshot(path=str(probe.out / "a4_recent_chip.png"))
    check(sec, "A4.1 加载后「最近：」组合 chips 出现", recent is not None,
          sev="中", evidence="a4_recent_chip.png")

    if recent is not None:
        errs_before = len(probe.report["page_errors"])
        with page.expect_response(lambda r: "/api/research/bars/000021.SZ" in r.url,
                                  timeout=10_000):
            page.click('[data-testid="explorer-recent"] .recent-chip')
        page.wait_for_selector('[data-testid="kline-chart"] canvas', timeout=15_000)
        time.sleep(1.2)
        check(sec, "A4.2 点最近 chip 重载不炸",
              len(probe.report["page_errors"]) == errs_before, sev="高")

    # 特征勾选 60日收益 → 曲线集合变化(aria-label 列表 + 像素双证据)
    panel = '[data-testid="feature-chart"]'
    aria_before = page.evaluate(
        f"""() => {{ const el = document.querySelector('{panel} [role="img"]');
                     return el ? el.getAttribute('aria-label') : null; }}""")
    hash_before = canvas_hash(page, f"{panel} canvas")
    page.screenshot(path=str(probe.out / "a4_feature_before.png"), full_page=True)
    cb = page.locator(f"{panel} .n-checkbox", has_text="60日收益")
    if cb.count() == 0:
        probe.defect("A4.3 未找到「60日收益」勾选框(选择器 .n-checkbox has_text)")
        return
    try:
        with page.expect_response(
                lambda r: "/api/research/features/000021.SZ" in r.url
                and "return_60d" in r.url, timeout=10_000):
            cb.first.click()
        got_response = True
    except Exception:
        got_response = False
        cb_checked = "n-checkbox--checked" in (cb.first.get_attribute("class") or "")
        probe.defect(f"A4.3 勾选后 10s 未见 return_60d 请求(checkbox checked={cb_checked})")
    try:
        page.wait_for_selector('[data-testid="feature-fetching"]', state="hidden",
                               timeout=10_000)
    except Exception:
        pass
    time.sleep(1.2)
    aria_after = page.evaluate(
        f"""() => {{ const el = document.querySelector('{panel} [role="img"]');
                     return el ? el.getAttribute('aria-label') : null; }}""")
    hash_after = canvas_hash(page, f"{panel} canvas")
    page.screenshot(path=str(probe.out / "a4_feature_after.png"), full_page=True)
    label_ok = bool(aria_after) and "60日收益" in aria_after and (
        not aria_before or "60日收益" not in aria_before)
    check(sec, "A4.3 勾选「60日收益」→ 特征图曲线集合变化",
          got_response and hash_before != hash_after and label_ok,
          f"请求={got_response} 像素变={hash_before != hash_after} "
          f"aria前={aria_before!r} aria后={aria_after!r}", sev="中",
          evidence="a4_feature_before.png / a4_feature_after.png")

    # K 线 slider 拖动 → 特征图窗口跟动(connect 联动)。像素哈希一律 settled_hash
    # (鼠标离场取样): axisPointer 十字线与 dataZoom 把手标签都画进 canvas, 会造假变化。
    kline_css = '[data-testid="kline-chart"] canvas'
    kbox = page.query_selector(kline_css).bounding_box()
    f_before = settled_hash(page, f"{panel} canvas")
    k_before = settled_hash(page, kline_css)
    page.screenshot(path=str(probe.out / "a4_zoom_before.png"), full_page=True)
    # slider: bottom 8 高 16 → 纵向中心 = 底边-16; 右把手贴绘图区右缘(grid 右缩进 ~26px,
    # 逐偏移试抓 — 首轮 -30 落在满窗填充区, 拖动是无效 no-op)
    sy = kbox["y"] + kbox["height"] - 16
    method, k_after = "", k_before
    for inset in (26, 21, 16):
        sx_from = kbox["x"] + kbox["width"] - inset
        page.mouse.move(sx_from, sy)
        page.mouse.down()
        page.mouse.move(kbox["x"] + kbox["width"] * 0.55, sy, steps=20)
        page.mouse.up()
        k_after = settled_hash(page, kline_css)
        if k_after != k_before:
            method = f"slider右把手拖动(inset={inset})"
            break
    if k_after == k_before:  # 把手都没抓到 → 退回滚轮缩放(inside dataZoom)
        method = "滚轮缩放(把手拖动未生效)"
        page.mouse.move(kbox["x"] + kbox["width"] / 2, kbox["y"] + kbox["height"] * 0.35)
        page.mouse.wheel(0, -600)
        k_after = settled_hash(page, kline_css)
    f_after = settled_hash(page, f"{panel} canvas")
    page.screenshot(path=str(probe.out / "a4_zoom_after.png"), full_page=True)
    check(sec, "A4.4 K线缩放联动特征图窗口",
          k_after != k_before and f_after != f_before,
          f"方式={method} K线变={k_after != k_before} 特征图变={f_after != f_before}",
          sev="中", evidence="a4_zoom_before.png / a4_zoom_after.png")


# ---------------------------------------------------------------- A5 判决页
def sec_a5_verdicts(page: Page, probe: Probe, sec: dict) -> None:
    goto_tab(page, probe, "verdicts", reload=True)
    page.wait_for_selector('[data-testid="verdict-filter"]', timeout=10_000)
    time.sleep(0.8)

    cards_all = page.locator('[data-testid="verdict-card"]').count()
    fail_btn = page.locator('[data-testid="verdict-filter"] button', has_text="FAIL")
    fail_label = fail_btn.first.inner_text().strip()
    m = re.search(r"(\d+)", fail_label)
    expect_fail = int(m.group(1)) if m else -1
    fail_btn.first.click()
    time.sleep(0.6)
    cards_fail = page.locator('[data-testid="verdict-card"]').count()
    page.screenshot(path=str(probe.out / "a5_fail_filter.png"), full_page=True)
    check(sec, "A5.1 点 FAIL 过滤卡片数变化且与计数一致",
          cards_fail != cards_all and cards_fail == expect_fail,
          f"全部={cards_all} FAIL钮={fail_label!r} 过滤后={cards_fail}",
          sev="中", evidence="a5_fail_filter.png")

    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector('[data-testid="verdict-filter"]', timeout=10_000)
    time.sleep(1.0)
    pressed = page.locator('[data-testid="verdict-filter"] button',
                           has_text="FAIL").first.get_attribute("aria-pressed")
    cards_after = page.locator('[data-testid="verdict-card"]').count()
    page.screenshot(path=str(probe.out / "a5_after_reload.png"), full_page=True)
    check(sec, "A5.2 刷新后 FAIL 过滤仍激活(sessionStorage)",
          pressed == "true" and cards_after == cards_fail,
          f"aria-pressed={pressed!r} 卡片数={cards_after}", sev="中",
          evidence="a5_after_reload.png")
    # 复位视角, 不给后续节留过滤态
    page.locator('[data-testid="verdict-filter"] button', has_text="全部").first.click()

    # P1 组标一键全勾
    group = page.locator(".factor-group").filter(
        has=page.locator('[data-testid="ft-group-toggle"]', has_text=re.compile(r"^P1$")))
    if group.count() == 0:
        probe.defect("A5.3 未定位到 P1 因子组(.factor-group + ft-group-toggle)")
        return
    total = group.locator(".fchip").count()
    disabled = group.locator(".fchip.disabled").count()
    before = group.locator(".fchip.checked").count()
    group.locator('[data-testid="ft-group-toggle"]').first.click()
    time.sleep(0.5)
    after = group.locator(".fchip.checked").count()
    page.screenshot(path=str(probe.out / "a5_p1_group.png"), full_page=True)
    check(sec, "A5.3 点 P1 组标 → 该组可用 chips 全勾",
          after == total - disabled and after > before,
          f"组内={total} 禁用={disabled} 勾前={before} 勾后={after}",
          sev="中", evidence="a5_p1_group.png")


# ---------------------------------------------------------------- A6 实盘执行表排序
def sec_a6_live_sort(page: Page, probe: Probe, sec: dict) -> None:
    page.goto(f"{probe.base}/ui/#/live/executions", wait_until="domcontentloaded")
    page.wait_for_selector('[data-testid="page-live"]', timeout=10_000)
    try:
        page.wait_for_selector('[data-testid="live-executions"] tbody tr', timeout=10_000)
    except Exception:
        check(sec, "A6.0 数据前置: 执行表有行", False, "执行表无数据行, 排序无从测", sev="低")
        return
    time.sleep(0.5)

    def first_row() -> str:
        return page.locator('[data-testid="live-executions"] tbody tr').first.inner_text()

    row0 = first_row()
    btn = page.locator('[data-testid="dt-sort-submitted_at"]')
    if btn.count() == 0:
        probe.defect("A6.1 未找到 dt-sort-submitted_at 排序按钮")
        return
    btn.first.click()
    time.sleep(0.4)
    sort1 = page.evaluate(
        """() => { const th = document.querySelector('[data-testid="live-executions"] th[aria-sort]');
                   return th ? th.getAttribute('aria-sort') : null; }""")
    row1 = first_row()
    btn.first.click()
    time.sleep(0.4)
    sort2 = page.evaluate(
        """() => { const th = document.querySelector('[data-testid="live-executions"] th[aria-sort]');
                   return th ? th.getAttribute('aria-sort') : null; }""")
    row2 = first_row()
    page.screenshot(path=str(probe.out / "a6_sort.png"), full_page=True)
    ok = sort1 == "descending" and sort2 == "ascending" and (row1 != row2 or row0 != row1)
    check(sec, "A6.1 执行表点「时间」→ aria-sort 出现且行序变化", ok,
          f"一击={sort1} 二击={sort2} 首行变化: 原→降={row0 != row1} 降→升={row1 != row2}",
          sev="中", evidence="a6_sort.png")


# ---------------------------------------------------------------- A7 任务日志过滤
def sec_a7_jobs_filter(page: Page, probe: Probe, sec: dict) -> None:
    goto_tab(page, probe, "jobs", reload=True)
    page.wait_for_selector('[data-testid="job-log-filter"]', timeout=10_000)
    time.sleep(1.0)
    rows = page.locator('[data-testid="job-row"]').count()
    if rows > 0:  # 有任务就先钻取一条真日志, 让 M 更有代表性
        page.locator('[data-testid="job-row-drill"]').first.click()
        time.sleep(1.5)
    page.fill('[data-testid="job-log-filter"]', "ZZZ__绝无命中串__42")
    time.sleep(0.5)
    cnt = page.query_selector('[data-testid="job-log-filter-count"]')
    text = cnt.inner_text().strip() if cnt else "(未出现)"
    page.screenshot(path=str(probe.out / "a7_filter_zero.png"), full_page=True)
    check(sec, "A7.1 无命中过滤串 → 0/M 计数显示",
          bool(cnt) and re.match(r"^0/\d+\s*行$", text) is not None,
          f"任务行数={rows} 计数文本={text!r}", sev="中", evidence="a7_filter_zero.png")
    sec["notes"] = f"探针时任务列表 {rows} 行(空库则 M=占位文案 1 行)"
    page.fill('[data-testid="job-log-filter"]', "")


# ---------------------------------------------------------------- B/C 主题扫描 + axe
def scan_theme(page: Page, probe: Probe, sec: dict, theme: str) -> None:
    """六页逐页: 等锚点 → 截图 <theme>_*.png → axe.run 收 violations。"""
    axe_path = str(AXE_JS)
    for tab, fname, anchors in TABS:
        probe.step = f"{theme}:{tab}"
        try:
            goto_tab(page, probe, tab)
            if tab == "explorer":
                load_explorer_symbol(page)
            hit = wait_any(page, anchors)
            page.evaluate("document.querySelectorAll('main details').forEach(d => d.open = true)")
            time.sleep(1.2 if tab != "explorer" else 2.0)
            shot = probe.out / f"{theme}_{fname}.png"
            page.screenshot(path=str(shot), full_page=True)
            check(sec, f"{theme} 主题 {tab} 锚点就绪+截图", hit is not None,
                  f"anchor={hit}", sev="中", evidence=shot.name)
        except Exception as e:
            probe.defect(f"{theme}:{tab} 截图节异常: {e}")
            continue
        # ---- axe ----
        try:
            if page.evaluate("typeof window.axe === 'undefined'"):
                page.add_script_tag(path=axe_path)
            res = page.evaluate(
                """() => axe.run(document, {resultTypes: ['violations']}).then(r =>
                     r.violations.map(v => ({
                       id: v.id, impact: v.impact, help: v.help,
                       nodes: v.nodes.length,
                       first: v.nodes[0] ? v.nodes[0].target.join(' >> ') : '',
                       samples: v.nodes.slice(0, 5).map(n => ({
                         target: n.target.join(' >> '),
                         data: (n.any && n.any[0] && n.any[0].data) || null,
                       })),
                     })))""")
            probe.report["axe"]["pages"].append(
                {"theme": theme, "page": tab, "violations": res})
            counts: dict[str, int] = {}
            for v in res:
                counts[v["impact"]] = counts.get(v["impact"], 0) + 1
            print(f"  [axe] {theme}/{tab}: {counts or '无 violations'}")
        except Exception as e:
            probe.defect(f"axe {theme}:{tab} 运行失败: {e}")


def sec_b_light_and_axe(page: Page, probe: Probe, sec: dict) -> None:
    goto_tab(page, probe, "overview", reload=True)
    time.sleep(0.8)
    theme0 = page.evaluate("document.documentElement.dataset.theme || ''")
    # 先扫默认主题(通常 dark), 再切换扫另一主题 — 双主题 axe 全覆盖
    scan_theme(page, probe, sec, theme0 or "dark")

    probe.step = "theme-toggle"
    page.click('[data-testid="theme-toggle"]')
    time.sleep(0.8)
    theme1 = page.evaluate("document.documentElement.dataset.theme || ''")
    check(sec, "B.0 主题切换钮生效(documentElement data-theme 翻转)",
          theme1 != theme0 and theme1 in ("light", "dark"),
          f"{theme0!r} → {theme1!r}", sev="高")
    scan_theme(page, probe, sec, theme1 or "light")


# ---------------------------------------------------------------- D 重负载计时
def sec_d_heavy(page: Page, probe: Probe, sec: dict) -> None:
    runs = api_json(probe.base, "/api/research/backtests")["runs"]
    heavy = max(
        (r for r in runs if (r["strategies"][0].get("trade_count") or 0) >= 5000),
        key=lambda r: r["strategies"][0].get("trade_count") or 0, default=None)
    small = next((r for r in runs
                  if r["run_id"] != (heavy or {}).get("run_id")
                  and (r["strategies"][0].get("trade_count") or 0) > 0
                  and (r["strategies"][0].get("trade_count") or 0) < 1000), None)
    if heavy is None or small is None:
        check(sec, "D.0 数据前置: 重负载 run + 轻 run 都在库", False,
              f"heavy={bool(heavy)} small={bool(small)}", sev="低")
        return
    h_id, h_trades = heavy["run_id"], heavy["strategies"][0]["trade_count"]
    curve_pts = len(heavy["strategies"][0]["equity_curve"]["dates"])
    sec["notes"] = (f"重负载 run={h_id}({h_trades} 笔, 曲线 {curve_pts} 点), "
                    f"基线 run={small['run_id']}({small['strategies'][0]['trade_count']} 笔)")

    goto_tab(page, probe, "backtests", reload=True)
    page.wait_for_selector('[data-testid="bt-run-row"]', timeout=10_000)
    time.sleep(2.0)

    def click_run(rid: str) -> None:
        page.locator('[data-testid="bt-run-row"]').filter(
            has=page.locator(".run-id", has_text=rid)
        ).locator('[data-testid="bt-run-select"]').first.click()

    # 先选轻 run 让图表落到基线状态
    click_run(small["run_id"])
    time.sleep(3.0)
    base_hash = canvas_hash(page, '[data-testid="bt-chart"] canvas')

    # 点击重 run → 轮询 canvas 像素哈希, 最后一次变化时刻 = 重绘完成
    t0 = time.monotonic()
    click_run(h_id)
    first_change = last_change = None
    prev, stable = base_hash, 0
    while time.monotonic() - t0 < 90:
        h = canvas_hash(page, '[data-testid="bt-chart"] canvas')
        now = time.monotonic() - t0
        if h != prev:
            prev = h
            if first_change is None:
                first_change = now
            last_change, stable = now, 0
        else:
            stable += 1
            if last_change is not None and stable >= 8:  # ~0.8s 无像素变化 → 稳定
                break
        time.sleep(0.1)
    page.screenshot(path=str(probe.out / "d_heavy_after.png"), full_page=True)
    probe.report["timing"] = {
        "run_id": h_id, "trade_count": h_trades, "equity_points": curve_pts,
        "first_paint_s": round(first_change, 2) if first_change else None,
        "render_complete_s": round(last_change, 2) if last_change else None,
        "note": "点击 run 行 → 净值图 canvas 像素最后一次变化(含 0.1s 轮询粒度; "
                "截面策略无首标的基准请求, 纯前端渲染)",
    }
    check(sec, "D.1 重负载 run 净值图渲染计时",
          last_change is not None,
          f"首次重绘 {probe.report['timing']['first_paint_s']}s, "
          f"渲染完成 {probe.report['timing']['render_complete_s']}s",
          sev="低", evidence="d_heavy_after.png")

    # bundle 尺寸(构建产物 static/assets)
    assets = Path("src/interfaces/api/static/assets")
    js = css = other = 0
    files = []
    if assets.is_dir():
        for p in assets.iterdir():
            n = p.stat().st_size
            files.append((p.name, n))
            if p.suffix == ".js":
                js += n
            elif p.suffix == ".css":
                css += n
            else:
                other += n
    files.sort(key=lambda x: -x[1])
    probe.report["bundle"] = {
        "js_bytes": js, "css_bytes": css, "other_bytes": other,
        "total_bytes": js + css + other, "file_count": len(files),
        "top5": [{"file": f, "bytes": b} for f, b in files[:5]],
    }
    check(sec, "D.2 bundle 尺寸测量", assets.is_dir(),
          f"JS {js / 1024:.0f}KB / CSS {css / 1024:.0f}KB / 共 {(js + css + other) / 1024:.0f}KB "
          f"({len(files)} 文件)", sev="低")


# ---------------------------------------------------------------- 汇总
def summarize(probe: Probe) -> None:
    rep = probe.report
    findings: list[dict] = []

    for sec_name, sec in rep["sections"].items():
        for c in sec.get("checks", []):
            if not c["ok"]:
                findings.append({
                    "instrument": sec_name, "sev": c["sev"],
                    "phenomenon": f"{c['name']} 未达预期",
                    "repro": c["name"], "evidence": c["evidence"] or c["detail"],
                    "detail": c["detail"],
                })
    for e in rep["page_errors"]:
        findings.append({"instrument": e["step"], "sev": "高",
                         "phenomenon": "页面未捕获异常(pageerror)",
                         "repro": f"步骤 {e['step']}", "evidence": e["text"][:400],
                         "detail": e["text"][:400]})
    seen = set()
    for e in rep["console_errors"]:
        key = e["text"][:120]
        if key in seen:
            continue
        seen.add(key)
        findings.append({"instrument": e["step"], "sev": "中",
                         "phenomenon": "浏览器 console error",
                         "repro": f"步骤 {e['step']}", "evidence": e["text"][:400],
                         "detail": e["text"][:400]})
    for e in rep["failed_requests"]:
        findings.append({"instrument": e["step"], "sev": "中",
                         "phenomenon": f"HTTP 失败请求 {e['status']}",
                         "repro": f"步骤 {e['step']}", "evidence": e["url"],
                         "detail": e["url"]})

    # axe 汇总: serious/critical 逐条 finding(按 主题+页+规则 去重), moderate 记数
    impact_counts: dict[str, int] = {}
    rules: dict[str, dict] = {}
    for pg in rep["axe"]["pages"]:
        for v in pg["violations"]:
            impact_counts[v["impact"]] = impact_counts.get(v["impact"], 0) + v["nodes"]
            key = v["id"]
            r = rules.setdefault(key, {"id": v["id"], "impact": v["impact"],
                                       "help": v["help"], "pages": [], "nodes": 0})
            r["pages"].append(f"{pg['theme']}/{pg['page']}")
            r["nodes"] += v["nodes"]
    rep["axe"]["impact_counts"] = impact_counts
    rep["axe"]["unique_rules"] = sorted(rules.values(), key=lambda r: r["id"])
    for r in rules.values():
        if r["impact"] in ("serious", "critical"):
            findings.append({
                "instrument": "axe-core", "sev": "高" if r["impact"] == "critical" else "中",
                "phenomenon": f"axe {r['impact']}: {r['id']} — {r['help']}",
                "repro": f"axe.run 于 {', '.join(sorted(set(r['pages'])))}",
                "evidence": f"共 {r['nodes']} 个节点命中",
                "detail": f"nodes={r['nodes']}",
            })

    for i, f in enumerate(findings, 1):
        f["no"] = f"F-{i:02d}"
    rep["findings"] = findings


def main() -> int:
    parser = argparse.ArgumentParser(description="驾驶舱 UI 深度探针(Measure 仪器)")
    parser.add_argument("--base", default=os.environ.get("UI_BASE", "http://127.0.0.1:8501"))
    parser.add_argument("--out", default="data/ui_probe")
    parser.add_argument("--only", default="",
                        help="只跑名字含该子串的节(如 A4); 报告另存 probe_report_<only>.json 不覆盖全量")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    probe = Probe(args.base, out)

    sections = [
        ("A1-快捷键", sec_a1_hotkeys),
        ("A2-回测参数面板", sec_a2_bt_params),
        ("A3-深链前进后退", sec_a3_deeplink),
        ("A4-行情交互", sec_a4_explorer),
        ("A5-判决过滤", sec_a5_verdicts),
        ("A6-实盘排序", sec_a6_live_sort),
        ("A7-任务日志过滤", sec_a7_jobs_filter),
        ("B/C-双主题扫描+axe", sec_b_light_and_axe),
        ("D-重负载计时", sec_d_heavy),
    ]
    if args.only:
        sections = [(n, f) for n, f in sections if args.only in n]
        if not sections:
            print(f"--only={args.only!r} 无匹配节")
            return 2

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        # reduced_motion: 令 tokens.css 的动效时长归零, 杜绝 axe 在入场动画中途采样
        # 把 α 混合色误判为前景色(Gage R&R 教训: 曾把 FactorCard 白字测成 #000000)
        page = browser.new_page(viewport=VIEWPORT, reduced_motion="reduce")
        probe.wire(page)
        for name, fn in sections:
            probe.step = name
            print(f"\n== {name} ==")
            sec = {"checks": [], "notes": ""}
            probe.report["sections"][name] = sec
            try:
                fn(page, probe, sec)
                sec["status"] = ("PASS" if all(c["ok"] for c in sec["checks"])
                                 else "FAIL") if sec["checks"] else "NO-CHECK"
            except Exception as e:
                sec["status"] = "INSTRUMENT-ERROR"
                probe.defect(f"{name} 节崩溃: {e.__class__.__name__}: {e}")
                traceback.print_exc()
                try:
                    page.screenshot(path=str(out / f"err_{name.split('-')[0]}.png"),
                                    full_page=True)
                except Exception:
                    pass
        browser.close()

    summarize(probe)
    suffix = f"_{re.sub(r'[^A-Za-z0-9]+', '', args.only)}" if args.only else ""
    report_path = out / f"probe_report{suffix}.json"
    report_path.write_text(json.dumps(probe.report, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    print("\n==== 测量项汇总 ====")
    for name, sec in probe.report["sections"].items():
        print(f"  {sec['status']:>16}  {name}"
              + (f"  ({sec['notes']})" if sec.get("notes") else ""))
    print(f"findings: {len(probe.report['findings'])} 条, "
          f"axe impact: {probe.report['axe']['impact_counts']}, "
          f"仪器缺陷: {len(probe.report['instrument_defects'])} 条")
    print(f"报告: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
