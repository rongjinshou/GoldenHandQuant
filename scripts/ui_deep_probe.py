"""投研驾驶舱 UI 深度探针（6σ R5/R6 Measure 阶段测量仪器, Playwright, Windows python 运行）。

只测量不修复: 真交互驱动(快捷键/表单/深链/图表联动/过滤排序) + 亮暗双主题截图
+ axe-core 无障碍扫描 + 重负载渲染计时 + bundle 尺寸。产出 findings 原始数据。

R6 新增三节(不停服务, 一切降级用 page.route 拦截仿真, 零服务端副作用):
    E-网络降级仿真: route abort 切断 /api/** → 实盘页(轮询)陈旧指示/console 堆积/自愈,
      总览页与判决页断网提交的错误呈现与恢复路径。仿真窗口内的 console/请求错误
      打 sim 标记, 不进 findings(计数进 report.degradation)。
    F-键盘全旅程: 六页从 body 连续 Tab(≤60), 记焦点轨迹+可见性(outline/box-shadow
      口径)+关键控件可达性+焦点陷阱; 帮助浮层焦点困留。jobs 空库时用 route fulfill
      仿真 3 行任务材料化钻取按钮。
    G-hover瞬时对比度: light 主题下对 R5 遗留 hover 清单逐个 element.hover() 实测
      前景/合成背景对比度(WCAG); dt-expand/ct-expand 行数不足时 route fulfill 仿真
      60 行材料化。

用法:
    # 先起服务: $WIN_PYTHON -m src.interfaces.cli.quant dashboard
    $WIN_PYTHON scripts/ui_deep_probe.py
    $WIN_PYTHON scripts/ui_deep_probe.py --base http://127.0.0.1:8501 --out data/ui_probe
    $WIN_PYTHON scripts/ui_deep_probe.py --only E    # 只跑网络降级(同理 F/G)

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
        self.simulated = False   # E/F/G 仿真窗口内的探针预期错误 → 打 sim 标记不进 findings
        self.report: dict = {
            "base": base,
            "sections": {},          # 节名 → {status, checks:[{name,ok,detail}], notes}
            "console_errors": [],    # {step,type,text[,sim]}
            "page_errors": [],       # {step,text}
            "failed_requests": [],   # {step,url,status[,sim]}
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
            entry = {"step": self.step, "type": m.type, "text": m.text,
                     "sim": self.simulated}
            if m.type == "error":
                self.report["console_errors"].append(entry)
            elif m.type == "warning":
                self.report["console_warnings"].append(entry)

        page.on("console", on_console)
        page.on("pageerror", lambda e: self.report["page_errors"].append(
            {"step": self.step, "text": str(e)}))
        page.on("response", lambda r: self.report["failed_requests"].append(
            {"step": self.step, "url": r.url, "status": r.status, "sim": self.simulated})
            if r.status >= 400 and not any(s in r.url for s in IGNORED_REQUEST_SUBSTR)
            else None)
        page.on("requestfailed", lambda r: self.report["failed_requests"].append(
            {"step": self.step, "url": r.url, "status": f"FAILED:{r.failure}",
             "sim": self.simulated})
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


# ---------------------------------------------------------------- E 网络降级仿真
# 扫 DOM 可见文本找"断连/陈旧/最后更新"类指示词(证实/证伪页面有无降级提示)
JS_INDICATOR_SCAN = """() => {
  const words = ['断连','连接中断','连接异常','离线','已断开','无法连接','陈旧','已过期',
                 '更新于','最后更新','数据可能', '已恢复','重连'];
  const hits = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (w.nextNode()) {
    const s = (w.currentNode.textContent || '').trim();
    if (!s) continue;
    const el = w.currentNode.parentElement;
    if (el && el.closest('script,style')) continue;
    if (el && el.getBoundingClientRect().height === 0) continue;
    for (const word of words) {
      if (s.includes(word)) { hits.push(s.replace(/\\s+/g, ' ').slice(0, 80)); break; }
    }
  }
  return [...new Set(hits)].slice(0, 12);
}"""


def _abort_route(route) -> None:  # noqa: ANN001
    route.abort()


def _counts(probe: Probe) -> tuple[int, int]:
    return len(probe.report["console_errors"]), len(probe.report["failed_requests"])


def sec_e_network(page: Page, probe: Probe, sec: dict) -> None:
    deg: dict = {"live_timeline": [], "overview": {}, "verdicts": {}}
    probe.report["degradation"] = deg
    t0 = time.monotonic()

    def mark(label: str, **kw: object) -> None:
        entry = {"at_s": round(time.monotonic() - t0, 1), "label": label} | kw
        deg["live_timeline"].append(entry)
        print(f"  [E时间线 +{entry['at_s']}s] {label}"
              + (f" {kw}" if kw else ""))

    # ---- E1 实盘页基线(轮询页典型: 概览端点 5s 一拍) ----
    probe.step = "E:live-baseline"
    page.goto(f"{probe.base}/ui/#/live", wait_until="domcontentloaded")
    hit = wait_any(page, ['[data-testid="live-kpi"]', '[data-testid="live-empty"]'], 15_000)
    time.sleep(3.0)  # 等首轮各端点数据齐
    kpi0 = page.evaluate(
        """() => { const el = document.querySelector('[data-testid=\"live-kpi\"]');
                   return el ? el.innerText.replace(/\\s+/g, ' ').slice(0, 300) : ''; }""")
    ind0 = page.evaluate(JS_INDICATOR_SCAN)
    page.screenshot(path=str(probe.out / "e_live_baseline.png"), full_page=True)
    t0 = time.monotonic()  # 时间线零点 = 基线就绪
    mark("0s 基线: 首屏数据就绪", kpi=kpi0[:120], indicators=ind0)
    check(sec, "E1.1 实盘页首屏数据就绪(基线)", hit == '[data-testid="live-kpi"]',
          f"anchor={hit} KPI={kpi0[:80]!r}", sev="低", evidence="e_live_baseline.png")

    # ---- E2 切断一切 API ≥2 个轮询周期 ----
    probe.step = "E:live-offline(仿真断网)"
    ce0, fr0 = _counts(probe)
    probe.simulated = True
    page.route("**/api/**", _abort_route)
    mark("切断 /api/**(route.abort)")
    try:
        time.sleep(13.0)  # 概览 5s 轮询 ≥2 个周期
        kpi1 = page.evaluate(
            """() => { const el = document.querySelector('[data-testid=\"live-kpi\"]');
                       return el ? el.innerText.replace(/\\s+/g, ' ').slice(0, 300) : ''; }""")
        ind1 = page.evaluate(JS_INDICATOR_SCAN)
        banner1 = page.evaluate(
            """() => { const el = document.querySelector('[data-testid=\"error-banner\"]');
                       return el ? el.innerText.slice(0, 160) : null; }""")
        ce1, fr1 = _counts(probe)
        page.screenshot(path=str(probe.out / "e_live_offline.png"), full_page=True)
        # 断连指示 = 除基线已有词条外新出现的指示词(排除"更新于"类恒显文案的误报)
        new_ind = [s for s in ind1 if s not in ind0]
        sim_console = [e["text"][:120] for e in probe.report["console_errors"][ce0:]]
        mark("13s 断网≥2周期采样", kpi=kpi1[:120], new_indicators=new_ind,
             error_banner=banner1, console_errors_added=ce1 - ce0,
             failed_requests_added=fr1 - fr0,
             console_samples=sim_console[:3])
        check(sec, "E2.1 断网≥2周期后出现陈旧/断连指示",
              bool(new_ind) or bool(banner1),
              f"新指示词={new_ind} 错误横幅={banner1!r} KPI冻结旧值不变={kpi1 == kpi0}",
              sev="高", evidence="e_live_offline.png")
        check(sec, "E2.2 断连期 console 错误不刷屏(13s ≤ 8 条)",
              ce1 - ce0 <= 8,
              f"console error +{ce1 - ce0}, 失败请求 +{fr1 - fr0}, 样例={sim_console[:2]}",
              sev="低", evidence="e_live_offline.png")
    finally:
        page.unroute("**/api/**", _abort_route)
        probe.simulated = False

    # ---- E3 恢复 → 自愈观测 ----
    probe.step = "E:live-recover"
    mark("恢复网络(unroute)")
    recovered_in = None
    try:
        with page.expect_response(
                lambda r: "/api/live/overview" in r.url and r.status == 200,
                timeout=20_000):
            pass
        recovered_in = round(time.monotonic() - t0, 1)
    except Exception:
        pass
    time.sleep(7.0)  # 再等一个多周期让 UI 消化(明细端点 30s 频, 未必都回)
    kpi2 = page.evaluate(
        """() => { const el = document.querySelector('[data-testid=\"live-kpi\"]');
                   return el ? el.innerText.replace(/\\s+/g, ' ').slice(0, 300) : ''; }""")
    ind2 = page.evaluate(JS_INDICATOR_SCAN)
    banner2 = page.evaluate(
        """() => { const el = document.querySelector('[data-testid=\"error-banner\"]');
                   return el ? el.innerText.slice(0, 160) : null; }""")
    page.screenshot(path=str(probe.out / "e_live_recovered.png"), full_page=True)
    mark("恢复后采样", first_200_at_s=recovered_in, kpi=kpi2[:120],
         indicators=[s for s in ind2 if s not in ind0], error_banner=banner2)
    check(sec, "E3.1 恢复后轮询自愈(下一拍 200 且 KPI 有值, 无错误横幅)",
          recovered_in is not None and bool(kpi2) and banner2 is None,
          f"恢复首个 200 于 +{recovered_in}s; KPI={kpi2[:60]!r}; 横幅={banner2!r}; "
          f"恢复提示词={[s for s in ind2 if s not in ind0]}",
          sev="高", evidence="e_live_recovered.png")

    # ---- E4 总览页(一次性加载页典型): 断网提交刷新任务 ----
    probe.step = "E:overview-offline(仿真断网)"
    goto_tab(page, probe, "overview", reload=True)
    wait_any(page, ['[data-testid="kpi-card"]', '[data-testid="overview-empty"]'], 10_000)
    time.sleep(0.8)
    page.evaluate("document.querySelectorAll('main details').forEach(d => d.open = true)")
    jobs_before = len(api_json(probe.base, "/api/jobs?limit=200").get("jobs", []))
    probe.simulated = True
    page.route("**/api/**", _abort_route)
    try:
        page.click('[data-testid="dr-submit"]')
        banner_txt = ""
        try:
            page.wait_for_selector('[data-testid="error-banner"]', timeout=6000)
            banner_txt = page.locator('[data-testid="error-banner"]').first.inner_text()
        except Exception:
            pass
        eb_buttons = page.locator('[data-testid="error-banner"] button').count()
        btn_disabled = page.locator('[data-testid="dr-submit"]').first.is_disabled()
        page.screenshot(path=str(probe.out / "e_overview_offline_submit.png"),
                        full_page=True)
        deg["overview"]["offline_banner"] = banner_txt
        deg["overview"]["banner_buttons"] = eb_buttons
        # R6 契约: 空日期在前端必填校验即拦截(不发请求, 零网络依赖) — 这正是 R6-03a 修复;
        # 断网态下同文案出现即证明拦截先于网络层。
        check(sec, "E4.1 断网+空日期提交 → 前端必填校验拦截(不依赖网络)",
              "必填" in banner_txt,
              f"文案={banner_txt!r}", sev="高", evidence="e_overview_offline_submit.png")
        check(sec, "E4.2 错误横幅带重试/关闭操作", eb_buttons > 0,
              f"横幅内按钮数={eb_buttons}(重试路径=只能再点「提交刷新任务」)",
              sev="中", evidence="e_overview_offline_submit.png")
        check(sec, "E4.3 失败后提交钮恢复可点", not btn_disabled,
              f"disabled={btn_disabled}", sev="中")
    finally:
        page.unroute("**/api/**", _abort_route)
    # 恢复后: 横幅是否自动消退(预期不会 — error 只在下次提交时清零), 再点一次提交
    # (日期留空 → 后端 DataRefreshJobRequest pattern 校验必 422, 不会真起任务, 服务端零副作用)
    time.sleep(1.0)
    banner_after = page.query_selector('[data-testid="error-banner"]') is not None
    page.click('[data-testid="dr-submit"]')
    time.sleep(1.5)
    retry_txt = ""
    el = page.query_selector('[data-testid="error-banner"]')
    if el:
        retry_txt = el.inner_text()
    probe.simulated = False
    page.screenshot(path=str(probe.out / "e_overview_retry_online.png"), full_page=True)
    jobs_after = len(api_json(probe.base, "/api/jobs?limit=200").get("jobs", []))
    deg["overview"] |= {"banner_persists_after_restore": banner_after,
                        "retry_online_banner": retry_txt,
                        "jobs_before": jobs_before, "jobs_after": jobs_after}
    # R6 契约: 空日期恢复后重试仍被前端拦截(必填持续提示属正确行为, 横幅带 ✕ 可关);
    # 服务端零请求零任务 — "可达服务端"旧口径随 422 路径一并退役。
    check(sec, "E4.4 恢复后空日期重试仍前端拦截(必填文案, 服务端零副作用)",
          "必填" in retry_txt and jobs_after == jobs_before,
          f"恢复后旧横幅仍挂着={banner_after}(带✕可关); 重试文案={retry_txt[:120]!r}; "
          f"服务端任务数 {jobs_before}→{jobs_after}",
          sev="中", evidence="e_overview_retry_online.png")

    # ---- E5 判决页: 断网提交因子检验 ----
    probe.step = "E:verdicts-offline(仿真断网)"
    goto_tab(page, probe, "verdicts", reload=True)
    page.wait_for_selector('[data-testid="ft-factors"]', timeout=10_000)
    time.sleep(0.8)
    checked0 = page.locator(".fchip.checked").count()
    clicked_chip = False
    if checked0 == 0:  # 无勾选则勾一个(提交才会走到网络), 事后复原
        page.locator(".fchip:not(.disabled)").first.click()
        clicked_chip = True
        time.sleep(0.3)
    probe.simulated = True
    page.route("**/api/**", _abort_route)
    try:
        page.click('[data-testid="ft-submit"]')
        v_txt = ""
        try:
            page.wait_for_selector(
                '[data-testid="factor-test-form"] [data-testid="error-banner"]',
                timeout=6000)
            v_txt = page.locator(
                '[data-testid="factor-test-form"] [data-testid="error-banner"]'
            ).first.inner_text()
        except Exception:
            pass
        v_buttons = page.locator(
            '[data-testid="factor-test-form"] [data-testid="error-banner"] button').count()
        v_btn_disabled = page.locator('[data-testid="ft-submit"]').first.is_disabled()
        page.screenshot(path=str(probe.out / "e_verdicts_offline_submit.png"),
                        full_page=True)
        deg["verdicts"] = {"offline_banner": v_txt, "banner_buttons": v_buttons,
                           "submit_disabled_after": v_btn_disabled}
        check(sec, "E5.1 判决页断网提交 → 表单内中文网络错误",
              "无法连接" in v_txt,
              f"文案={v_txt!r} 横幅按钮数={v_buttons} 提交钮禁用={v_btn_disabled}",
              sev="高", evidence="e_verdicts_offline_submit.png")
    finally:
        page.unroute("**/api/**", _abort_route)
        probe.simulated = False
    time.sleep(1.0)
    v_after = page.query_selector(
        '[data-testid="factor-test-form"] [data-testid="error-banner"]') is not None
    deg["verdicts"]["banner_persists_after_restore"] = v_after
    if clicked_chip:  # 复原勾选态, 不给后续节留状态
        page.locator(".fchip.checked").first.click()
    sec["notes"] = ("恢复路径: 两页横幅在网络恢复后均不自动消退, 只能靠再次提交清零; "
                    "判决页在线重试会真跑因子检验任务, 探针到断网证据为止不真提交")


# ---------------------------------------------------------------- F 键盘全旅程
# 逐步 Tab 后读 activeElement: 身份(WeakMap 编号, 判环/卡死) + 可见焦点三级口径
# (self: 元素自身 outline/box-shadow; wrapper/state-border: naive-ui 把焦点环画在
# .n-input 等包装层或其 state-border 子元素上 — 元素级口径会假阳性) + 命中目标。
# box-shadow 全透明色(rgba(...,0))视同 none, 防 naive 静息态占位阴影假过。
JS_FOCUS_INFO = """(targets) => {
  const el = document.activeElement || document.body;
  window.__pvIds = window.__pvIds || new WeakMap();
  window.__pvNext = window.__pvNext || 1;
  let id = window.__pvIds.get(el);
  const seen = id !== undefined;
  if (!seen) { id = window.__pvNext++; window.__pvIds.set(el, id); }
  const cs = getComputedStyle(el);
  const r = el.getBoundingClientRect();
  const label = el.getAttribute('data-testid') || el.getAttribute('aria-label')
    || (el.innerText || el.value || '').trim().replace(/\\s+/g, ' ').slice(0, 24)
    || (el.className ? String(el.className).split(' ')[0] : '');
  const shadowVisible = (sh) => {
    if (!sh || sh === 'none') return false;
    const cols = sh.match(/rgba?\\([^)]+\\)/g) || [];
    if (!cols.length) return true;
    return cols.some(c => { const p = c.match(/rgba\\([^)]*,\\s*([\\d.]+)\\)/);
                            return !p || parseFloat(p[1]) > 0; });
  };
  const ringOf = (n) => {
    if (!n) return false;
    const c = getComputedStyle(n);
    return (c.outlineStyle !== 'none' && parseFloat(c.outlineWidth) > 0)
      || shadowVisible(c.boxShadow);
  };
  let ringVia = ringOf(el) ? 'self' : '';
  if (!ringVia) {
    const wrap = el.closest('.n-input, .n-base-selection, .n-date-picker, ' +
                            '.n-checkbox, .n-button, .n-input-number');
    if (wrap) {
      if (ringOf(wrap)) ringVia = 'wrapper';
      else {
        const sb = wrap.querySelector('[class*="state-border"]');
        if (sb && ringOf(sb)) ringVia = 'state-border';
      }
    }
  }
  const hits = (targets || []).filter(t => {
    try { return el.matches(t) || !!el.closest(t); } catch { return false; }
  });
  // 无环元素的兜底探测: blur/refocus 对照边框/底色是否随焦点变化(.chips-box:focus-within
  // /.log-filter:focus 这类仅变色指示; 自定义过渡在 reduced-motion 下归零, 同任务可读settled值)
  let borderDelta = null;
  if (!ringVia && el !== document.body) {
    const chain = [el, el.parentElement, el.closest('.chips-box')]
      .filter((n, i, a) => n && a.indexOf(n) === i);
    const grab = () => chain.map(n => {
      const c = getComputedStyle(n); return c.borderColor + '/' + c.backgroundColor; });
    const f = grab();
    el.blur();
    const b = grab();
    el.focus({ preventScroll: true });
    if (JSON.stringify(f) !== JSON.stringify(b)) {
      borderDelta = f.map((v, i) => v !== b[i]
        ? `${chain[i].tagName.toLowerCase()}.${String(chain[i].className).split(' ')[0]}`
          + `: ${b[i]} → ${v}` : null).filter(Boolean).slice(0, 2);
    }
  }
  return {
    id, seen, tag: el.tagName.toLowerCase(), label,
    cls: el.className ? String(el.className).slice(0, 60) : '',
    isBody: el === document.body,
    ring: !!ringVia, ringVia, borderDelta,
    outline: cs.outlineStyle + ' ' + cs.outlineWidth,
    shadow: cs.boxShadow === 'none' ? 'none' : String(cs.boxShadow).slice(0, 60),
    opacity: cs.opacity, w: Math.round(r.width), h: Math.round(r.height),
    inModal: !!el.closest(
      '[role="dialog"], .n-modal, .n-modal-container, .n-modal-mask, .n-modal-body-wrapper'),
    hits,
  };
}"""

# 目标未命中时的归因: 不在 DOM / 位于折叠 details 内(键盘路径=summary+Enter) / 在但没轮到
JS_TARGET_WHERE = """(sel) => {
  const t = document.querySelector(sel);
  if (!t) return 'absent';
  const d = t.closest('details:not([open])');
  if (d) {
    const s = d.querySelector('summary');
    return 'closed-details:' + ((s && s.innerText) || '').replace(/\\s+/g, ' ').slice(0, 30);
  }
  return 'present';
}"""

# 每页关键控件可达性目标(任务口径): 名称 → 选择器
F_TARGETS: dict[str, dict[str, str]] = {
    "overview": {"提交刷新任务钮": '[data-testid="dr-submit"]'},
    "explorer": {"加载按钮": '[data-testid="explorer-load"]',
                 "最近chip": '[data-testid="explorer-recent"] .recent-chip'},
    "verdicts": {"因子chip": '[data-testid="ft-factor-chip"]',
                 "过滤钮": '[data-testid="verdict-filter"] button'},
    "backtests": {"提交按钮": '[data-testid="bt-submit"]',
                  "删除按钮": '[data-testid="bt-run-delete"]'},
    "live": {},
    "jobs": {"ID钻取按钮": '[data-testid="job-row-drill"]'},
}

FAKE_JOBS = {"jobs": [
    {"job_id": f"probe-f-{i}", "job_type": "backtest", "params": {},
     "status": "succeeded", "created_at": "2026-07-11T09:00:00",
     "started_at": "2026-07-11T09:00:01", "finished_at": "2026-07-11T09:00:05",
     "return_code": 0, "log_path": "", "log_tail": []}
    for i in range(3)
]}


def tab_journey(page: Page, targets: dict[str, str],
                max_tabs: int = 60) -> tuple[list[dict], str | None]:
    """连续 Tab 直到闭环(回到已访元素)或步数封顶, 返回(轨迹, 陷阱描述|None)。

    顺序焦点起点可能残留在页面中部(如探针刚点过按钮), 经过 body 只记边界回绕并
    继续 — 这样起点之前的元素在回绕后也会被覆盖, 不漏测(首轮 explorer 假不可达教训)。"""
    page.evaluate("""() => { window.__pvIds = new WeakMap(); window.__pvNext = 1;
        if (document.activeElement && document.activeElement !== document.body)
          document.activeElement.blur(); }""")
    sel_list = list(targets.values())
    trail: list[dict] = []
    trap: str | None = None
    prev_id, stuck = None, 0
    for i in range(1, max_tabs + 1):
        page.keyboard.press("Tab")
        # naive 焦点环(state-border box-shadow)有 0.3s transition 且不吃 reduced_motion,
        # 立即取样撞过渡起点 alpha≈0 会假阴性(诊断复现) — 定帧 120ms 再读
        time.sleep(0.12)
        info = page.evaluate(JS_FOCUS_INFO, sel_list)
        info["step"] = i
        trail.append(info)
        if info["isBody"]:
            if info["seen"]:
                info["note"] = "二过 body(循环闭合)"
                break
            info["note"] = "经过 body(边界回绕, 继续)"
            prev_id = info["id"]
            continue
        if info["id"] == prev_id:
            stuck += 1
            if stuck >= 2:
                trap = f"第{i}步焦点卡死于 <{info['tag']}> {info['label']!r}(连续3次不动)"
                break
        else:
            stuck = 0
        if info["seen"]:
            info["note"] = "回到已访问元素(循环闭合)"
            break
        prev_id = info["id"]
    return trail, trap


def _journey_checks(page: Page, sec: dict, probe: Probe, tab: str, trail: list[dict],
                    trap: str | None, targets: dict[str, str]) -> None:
    kb = probe.report.setdefault("keyboard", {})
    reached = {name: next((s["step"] for s in trail if sel in s["hits"]), None)
               for name, sel in targets.items()}
    no_ring = [s for s in trail if not s["isBody"] and not s["ring"]]
    ring_via_wrap = [s for s in trail if s.get("ringVia") in ("wrapper", "state-border")]
    invisible = [s for s in trail if not s["isBody"]
                 and (float(s["opacity"]) == 0 or s["w"] == 0 or s["h"] == 0)]
    closed = any("循环闭合" in (s.get("note") or "") for s in trail)
    kb[tab] = {"steps": len(trail), "closed": closed, "trap": trap,
               "targets_reached_at": reached,
               "no_ring": [f"#{s['step']} <{s['tag']}> {s['label']} cls={s['cls'][:40]}"
                           + (f" [仅变色兜底: {'; '.join(s['borderDelta'])}]"
                              if s.get("borderDelta") else " [完全无指示]")
                           for s in no_ring],
               "ring_via_wrapper": [f"#{s['step']} <{s['tag']}> {s['label']}"
                                    for s in ring_via_wrap],
               "invisible_focused": [f"#{s['step']} <{s['tag']}> {s['label']} "
                                     f"op={s['opacity']} {s['w']}x{s['h']}"
                                     for s in invisible],
               "trail": trail}
    check(sec, f"F.{tab}.1 焦点全程可见(self/wrapper/state-border 三级口径)",
          not no_ring,
          f"{len(no_ring)}/{len(trail)} 步无焦点指示"
          + (f": {', '.join(kb[tab]['no_ring'][:6])}" if no_ring else "")
          + (f"; 另 {len(ring_via_wrap)} 步焦点环画在包装层" if ring_via_wrap else ""),
          sev="中")
    for name, sel in targets.items():
        if reached[name] is not None:
            check(sec, f"F.{tab}.2 可达: {name}", True,
                  f"selector={sel} 命中于第 {reached[name]} 步", sev="中")
            continue
        where = page.evaluate(JS_TARGET_WHERE, sel)
        if where.startswith("closed-details:"):
            s_steps = [s["step"] for s in trail if s["tag"] == "summary"]
            check(sec, f"F.{tab}.2 可达: {name}", bool(s_steps),
                  f"位于折叠 details({where.split(':', 1)[1]!r})内; summary "
                  + (f"第 {s_steps} 步可达, Enter 展开后可 Tab 到" if s_steps
                     else "也未在轨迹中 — 完全不可达"), sev="中")
        else:
            check(sec, f"F.{tab}.2 可达: {name}", False,
                  f"selector={sel} {len(trail)} 步内未命中(闭环={closed}, DOM={where})",
                  sev="中")
    check(sec, f"F.{tab}.3 无焦点陷阱", trap is None,
          trap or (f"{len(trail)} 步{'闭环' if closed else '未闭环(可聚焦元素>60)'}"
                   ), sev="高")
    if invisible:
        check(sec, f"F.{tab}.4 聚焦元素均可见(无 opacity0/零尺寸)", False,
              "; ".join(kb[tab]["invisible_focused"][:5]), sev="中")


def sec_f_keyboard(page: Page, probe: Probe, sec: dict) -> None:
    probe.report.setdefault("keyboard", {})
    jobs_mocked = False

    def jobs_mock(route) -> None:  # noqa: ANN001
        if route.request.method == "GET" and re.search(r"/api/jobs(\?|$)",
                                                       route.request.url):
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(FAKE_JOBS))
        else:
            route.fallback()

    for tab, _fname, anchors in TABS:
        probe.step = f"F:{tab}"
        try:
            if tab == "jobs" and not api_json(probe.base, "/api/jobs?limit=5").get("jobs"):
                page.route("**/api/jobs*", jobs_mock)
                jobs_mocked = True
            goto_tab(page, probe, tab, reload=True)
            if tab == "explorer":
                load_explorer_symbol(page)  # 材料化「最近」chips
            wait_any(page, anchors, 10_000)
            time.sleep(1.0)
            trail, trap = tab_journey(page, F_TARGETS.get(tab, {}))
            _journey_checks(page, sec, probe, tab, trail, trap, F_TARGETS.get(tab, {}))
        except Exception as e:
            probe.defect(f"F:{tab} 旅程异常: {e.__class__.__name__}: {e}")
        finally:
            if tab == "jobs" and jobs_mocked:
                page.unroute("**/api/jobs*", jobs_mock)

    # ---- 帮助浮层打开态: 焦点应困于浮层内(困住=正确) ----
    probe.step = "F:hotkey-help-trap"
    try:
        goto_tab(page, probe, "overview", reload=True)
        time.sleep(0.8)
        page.evaluate("document.activeElement && document.activeElement.blur()")
        page.keyboard.press("?")
        page.wait_for_selector('[data-testid="hotkey-help"]', state="visible",
                               timeout=5000)
        first = page.evaluate(JS_FOCUS_INFO, [])  # 打开即观察初始焦点落点
        inside = []
        for _ in range(10):
            page.keyboard.press("Tab")
            inside.append(page.evaluate(JS_FOCUS_INFO, []))
        trapped = all(s["inModal"] for s in inside)
        probe.report["keyboard"]["hotkey_help"] = {
            "trapped": trapped,
            "initial_focus": f"<{first['tag']}> {first['label']} cls={first['cls'][:50]} "
                             f"inModal={first['inModal']}",
            "trail": [f"<{s['tag']}> {s['label']} cls={s['cls'][:50]}"
                      + ("" if s["inModal"] else " [浮层外!]") for s in inside]}
        check(sec, "F.help 帮助浮层打开态焦点困于浮层内(应困住)", trapped,
              f"初始焦点={probe.report['keyboard']['hotkey_help']['initial_focus']}; "
              + "; ".join(probe.report["keyboard"]["hotkey_help"]["trail"][:5]),
              sev="中")
        page.keyboard.press("Escape")
        page.wait_for_selector('[data-testid="hotkey-help"]', state="hidden",
                               timeout=4000)
    except Exception as e:
        probe.defect(f"F:hotkey-help 焦点困留测量异常: {e}")
    sec["notes"] = ("可见性口径: outlineStyle!=none 且 outlineWidth>0, 或 box-shadow!=none; "
                    "jobs 空库时以 route fulfill 仿真 3 行任务材料化钻取按钮"
                    if jobs_mocked else
                    "可见性口径: outlineStyle!=none 且 outlineWidth>0, 或 box-shadow!=none")


# ---------------------------------------------------------------- G hover 瞬时对比度
# 悬停态实测: 前景色 + 沿祖先合成的有效背景色(α 叠加) → WCAG 对比度
JS_CONTRAST = """(el) => {
  const cs = getComputedStyle(el);
  const parse = (c) => { const m = /rgba?\\(([^)]+)\\)/.exec(c || ''); if (!m) return null;
    const p = m[1].split(',').map(parseFloat);
    return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const stack = [];
  for (let n = el; n; n = n.parentElement) {
    const c = parse(getComputedStyle(n).backgroundColor);
    if (c && c[3] > 0) { stack.push(c); if (c[3] >= 1) break; }
  }
  let eff = [255, 255, 255];
  if (stack.length && stack[stack.length - 1][3] >= 1) {
    eff = stack.pop().slice(0, 3);
  } else {
    const rootBg = parse(getComputedStyle(document.documentElement).backgroundColor);
    if (rootBg && rootBg[3] >= 1) eff = rootBg.slice(0, 3);
  }
  for (let i = stack.length - 1; i >= 0; i--) {
    const [r, g, b, a] = stack[i];
    eff = [r * a + eff[0] * (1 - a), g * a + eff[1] * (1 - a), b * a + eff[2] * (1 - a)];
  }
  let fg = parse(cs.color) || [0, 0, 0, 1];
  if (fg[3] < 1) { const a = fg[3];
    fg = [fg[0] * a + eff[0] * (1 - a), fg[1] * a + eff[1] * (1 - a), fg[2] * a + eff[2] * (1 - a)];
  } else fg = fg.slice(0, 3);
  const lum = (c) => { const f = (v) => { v /= 255;
      return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const L1 = lum(fg), L2 = lum(eff);
  const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
  const hex = (c) => '#' + c.map((v) => Math.round(v).toString(16).padStart(2, '0')).join('');
  return { color: hex(fg), colorRaw: cs.color, bg: hex(eff),
           ratio: Math.round(ratio * 100) / 100,
           fontSize: cs.fontSize, fontWeight: cs.fontWeight };
}"""


def _dup_rows(base_url: str, path: str, key: str, id_fields: tuple[str, ...],
              n: int = 60) -> str:
    """取真实一行样本复制 n 份(改 id 防 vue key 撞)作 route fulfill 载荷。"""
    rows = api_json(base_url, path).get(key) or []
    if not rows:
        return ""
    out = []
    for i in range(n):
        row = dict(rows[i % len(rows)])
        for f in id_fields:
            if f in row:
                row[f] = f"{row[f]}-p{i}"
        out.append(row)
    return json.dumps({key: out})


def _measure_hover(page: Page, probe: Probe, sec: dict, idx: int, name: str,
                   selector: str, source: str, shot: str) -> None:
    loc = page.locator(selector).first
    if loc.count() == 0:
        probe.defect(f"G.{idx} {name}: 选择器 {selector} 未命中(无法材料化)")
        return
    loc.scroll_into_view_if_needed()
    pre = page.evaluate(JS_CONTRAST, loc.element_handle())
    loc.hover()
    time.sleep(0.3)  # reduced_motion 下 transition 已归零, 余量防抖
    post = page.evaluate(JS_CONTRAST, loc.element_handle())  # 悬停后重取句柄防重渲染失效
    try:
        loc.screenshot(path=str(probe.out / shot))
    except Exception:
        page.screenshot(path=str(probe.out / shot))
    try:
        px = float(post["fontSize"].replace("px", "") or 0)
    except ValueError:
        px = 0.0
    bold = str(post["fontWeight"]) in ("700", "800", "900", "bold")
    threshold = 3.0 if (px >= 24 or (px >= 18.66 and bold)) else 4.5
    rec = {"target": name, "source": source, "selector": selector,
           "hover_color": post["color"], "hover_bg": post["bg"],
           "ratio": post["ratio"], "threshold": threshold,
           "font": f"{post['fontSize']}/{post['fontWeight']}",
           "ratio_before_hover": pre["ratio"], "color_before_hover": pre["color"]}
    probe.report.setdefault("hover_contrast", []).append(rec)
    check(sec, f"G.{idx} {name} hover 对比度 ≥ {threshold}",
          post["ratio"] >= threshold,
          f"悬停 {post['color']} on {post['bg']} = {post['ratio']}:1 "
          f"(悬停前 {pre['color']} {pre['ratio']}:1, {rec['font']}) [{source}]",
          sev="中", evidence=shot)


def sec_g_hover(page: Page, probe: Probe, sec: dict) -> None:
    probe.report.setdefault("hover_contrast", [])
    # light 主题(R5 遗留清单口径)
    goto_tab(page, probe, "overview", reload=True)
    time.sleep(0.8)
    theme = page.evaluate("document.documentElement.dataset.theme || ''")
    if theme != "light":
        page.click('[data-testid="theme-toggle"]')
        time.sleep(0.8)
        theme = page.evaluate("document.documentElement.dataset.theme || ''")
    check(sec, "G.0 处于 light 主题", theme == "light", f"theme={theme}", sev="低")

    # 1 ThemeToggle(全站页头)
    probe.step = "G:theme-toggle"
    _measure_hover(page, probe, sec, 1, "ThemeToggle:hover",
                   '[data-testid="theme-toggle"]', "ThemeToggle.vue:39",
                   "g_theme_toggle.png")

    # 2/3 dt-sort + dt-expand(执行表; 行数<50 时仿真 60 行材料化「显示全部」钮)
    probe.step = "G:dt-sort/dt-expand(仿真行数)"
    exec_payload = _dup_rows(probe.base, "/api/live/executions?limit=1000",
                             "executions", ("execution_id", "order_ref", "id"))
    exec_mock = (lambda route: route.fulfill(  # noqa: E731
        status=200, content_type="application/json", body=exec_payload)
        if route.request.method == "GET" else route.fallback())
    if exec_payload:
        page.route("**/api/live/executions*", exec_mock)
    try:
        page.goto(f"{probe.base}/ui/#/live/executions", wait_until="domcontentloaded")
        page.wait_for_selector('[data-testid="live-executions"] tbody tr',
                               timeout=10_000)
        time.sleep(0.8)
        _measure_hover(page, probe, sec, 2, "dt-sort:hover",
                       '[data-testid="live-executions"] [data-testid^="dt-sort-"]',
                       "DataTable.vue:226", "g_dt_sort.png")
        _measure_hover(page, probe, sec, 3, "dt-expand:hover",
                       '[data-testid="live-executions"] [data-testid="dt-expand"]',
                       "DataTable.vue:272", "g_dt_expand.png")
    finally:
        if exec_payload:
            page.unroute("**/api/live/executions*", exec_mock)

    # 4 ct-expand(循环表「显示全部」; 同法仿真 60 行)
    probe.step = "G:ct-expand(仿真行数)"
    cyc_payload = _dup_rows(probe.base, "/api/live/cycles?limit=500",
                            "cycles", ("cycle_id",))
    cyc_mock = (lambda route: route.fulfill(  # noqa: E731
        status=200, content_type="application/json", body=cyc_payload)
        if route.request.method == "GET" else route.fallback())
    if cyc_payload:
        page.route("**/api/live/cycles*", cyc_mock)
    try:
        page.goto(f"{probe.base}/ui/#/live/cycles", wait_until="domcontentloaded")
        page.wait_for_selector('[data-testid="live-cycles"]', timeout=10_000)
        time.sleep(0.8)
        _measure_hover(page, probe, sec, 4, "ct-expand:hover",
                       '[data-testid="cycles-expand"]', "CyclesTable.vue:299",
                       "g_ct_expand.png")
    finally:
        if cyc_payload:
            page.unroute("**/api/live/cycles*", cyc_mock)

    # 5/6 行情页: recent-chip + add-panel-btn
    probe.step = "G:explorer-hover"
    goto_tab(page, probe, "explorer", reload=True)
    load_explorer_symbol(page)
    _measure_hover(page, probe, sec, 5, "recent-chip:hover",
                   '[data-testid="explorer-recent"] .recent-chip',
                   "Explorer.vue:608", "g_recent_chip.png")
    _measure_hover(page, probe, sec, 6, "add-panel-btn:hover",
                   '[data-testid="explorer-add-panel"]', "Explorer.vue:689",
                   "g_add_panel_btn.png")

    # 7 param-def--reset(回测页: 勾 micro_value 改 top_n=15 材料化, 测完点它复位)
    probe.step = "G:param-def-reset"
    goto_tab(page, probe, "backtests", reload=True)
    page.wait_for_selector('[data-testid="bt-strategies"]', timeout=10_000)
    time.sleep(0.8)
    if page.query_selector('[data-testid="bt-params-micro_value"]') is None:
        page.locator('[data-testid="bt-strategies"] .strat-item',
                     has_text="micro_value").locator(".n-checkbox").first.click()
        page.wait_for_selector('[data-testid="bt-params-micro_value"]', timeout=5000)
    item = page.locator('[data-testid="bt-params-micro_value"] .param-item',
                        has_text="top_n").first
    inp = item.locator("input").first
    inp.click()
    page.keyboard.press("Control+a")
    page.keyboard.type("15")
    time.sleep(0.5)
    _measure_hover(page, probe, sec, 7, "param-def--reset:hover",
                   '.param-def--reset', "BacktestForm.vue:550",
                   "g_param_def_reset.png")
    reset = page.locator(".param-def--reset")
    if reset.count() > 0:
        reset.first.click()  # 复位默认值, 不留改动
    sec["notes"] = ("清单口径: grep :hover 块内 color 声明含 --accent 的全部规则; "
                    "border-color-only(.filter-seg/.fchip/.vm-nav)与 --c-fail 色 "
                    "(.chip-x/.recent-clear/.run-delete/.panel-remove)不在本节范围")


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
        if e.get("sim"):
            continue  # 仿真断网窗口内的预期错误: 计数在 degradation, 不作缺陷
        key = e["text"][:120]
        if key in seen:
            continue
        seen.add(key)
        findings.append({"instrument": e["step"], "sev": "中",
                         "phenomenon": "浏览器 console error",
                         "repro": f"步骤 {e['step']}", "evidence": e["text"][:400],
                         "detail": e["text"][:400]})
    for e in rep["failed_requests"]:
        if e.get("sim"):
            continue
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
        ("E-网络降级仿真", sec_e_network),
        ("F-键盘全旅程", sec_f_keyboard),
        ("G-hover瞬时对比度", sec_g_hover),
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
