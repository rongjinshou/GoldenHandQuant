"""投研驾驶舱 UI 冒烟 + 截图脚本（Playwright, Windows python 运行）。

用途: 让 Claude/开发者在无人值守下"看到"前端 —— 逐页签截图 + 收集浏览器
console 错误 / 失败请求, 形成可机读的冒烟报告。截图供人眼或多模态模型审视觉。

用法:
    # 先起服务: $WIN_PYTHON -m src.interfaces.cli.quant dashboard
    $WIN_PYTHON scripts/ui_smoke.py                 # 只读冒烟: 6 页签截图
    $WIN_PYTHON scripts/ui_smoke.py --deep          # 加交互: 真提交一个小回测并等完成
    $WIN_PYTHON scripts/ui_smoke.py --out data/ui_screenshots --base http://127.0.0.1:8501

退出码: 0 = 全部锚点就绪且无 console 错误; 1 = 有问题（详见末尾 JSON 报告）。
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")  # Windows 管道下中文不炸

VIEWPORT = {"width": 1680, "height": 1050}

# ui-v2(Vue): 锚点走 data-testid 约定(设计 0704 §5.2), 页签=路由导航。
# 每页签: (tab key, 截图文件名, 就绪锚点列表[满足其一即可])
TABS = [
    ("overview", "01-overview", ['[data-testid="kpi-card"]', '[data-testid="overview-empty"]']),
    ("verdicts", "02-verdicts", ['[data-testid="ft-factor-chip"]']),
    ("explorer", "03-explorer", ['[data-testid="kline-chart"] canvas']),
    ("backtests", "04-backtests", ['[data-testid="bt-strategies"]']),
    ("live", "05-live", ['[data-testid="live-kpi"]', '[data-testid="live-empty"]']),
    ("jobs", "06-jobs", ['[data-testid="jobs-table"]']),
]

# 已知可忽略的噪音（favicon 浏览器自动请求, 页面没提供）
IGNORED_REQUEST_SUBSTR = ("favicon.ico",)


def open_details(page) -> None:
    """展开页面内所有 <details> 表单卡(如有), 让截图能看到表单全貌。"""
    page.evaluate(
        "document.querySelectorAll('main details')"
        ".forEach(d => { d.open = true; })"
    )


def wait_any(page, selectors: list[str], timeout_ms: int = 8000) -> str | None:
    """等待任一锚点出现, 返回命中的选择器; 全部超时返回 None。"""
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        for sel in selectors:
            if page.query_selector(sel) is not None:
                return sel
        time.sleep(0.2)
    return None


def run_smoke(base: str, out_dir: Path, deep: bool) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    report: dict = {"base": base, "tabs": {}, "console_errors": [],
                    "page_errors": [], "failed_requests": [], "deep": None}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport=VIEWPORT)

        page.on("console", lambda m: report["console_errors"].append(
            {"type": m.type, "text": m.text})
            if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: report["page_errors"].append(str(e)))
        page.on("response", lambda r: report["failed_requests"].append(
            {"url": r.url, "status": r.status})
            if r.status >= 400 and not any(s in r.url for s in IGNORED_REQUEST_SUBSTR)
            else None)
        page.on("requestfailed", lambda r: report["failed_requests"].append(
            {"url": r.url, "status": "FAILED", "error": r.failure})
            if not any(s in r.url for s in IGNORED_REQUEST_SUBSTR) else None)

        page.goto(f"{base}/ui/", wait_until="domcontentloaded")
        page.wait_for_selector('[data-testid="app-shell"]', timeout=10_000)
        time.sleep(1.5)  # 首屏数据加载

        for tab, fname, anchors in TABS:
            page.click(f'[data-testid="nav-{tab}"]')
            page.wait_for_selector(f'[data-testid="page-{tab}"]', timeout=8_000)

            if tab == "explorer":
                # 不自动加载 — 主动填一个库内标的并点加载, 等 ECharts canvas
                page.fill('[data-testid="explorer-symbol-input"] input', "000021.SZ")
                page.click('[data-testid="explorer-load"]')

            hit = wait_any(page, anchors)
            open_details(page)
            time.sleep(1.2 if tab != "explorer" else 2.0)  # 数据/图表渲染余量

            path = out_dir / f"{fname}.png"
            page.screenshot(path=str(path), full_page=True)
            report["tabs"][tab] = {
                "screenshot": str(path), "anchor_hit": hit,
                "ok": hit is not None,
            }
            print(f"[{tab}] anchor={'OK:' + hit if hit else 'MISS'} -> {path}")

        if deep:
            report["deep"] = run_deep(page, out_dir)

        browser.close()

    # ---- 汇总 ----
    all_ok = (all(t["ok"] for t in report["tabs"].values())
              and not report["console_errors"] and not report["page_errors"]
              and (report["deep"] is None or report["deep"]["ok"]))
    report["verdict"] = "PASS" if all_ok else "FAIL"
    report_path = out_dir / "smoke_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"\n==== 冒烟结论: {report['verdict']} ====")
    print(f"console 错误 {len(report['console_errors'])} 条, "
          f"页面异常 {len(report['page_errors'])} 条, "
          f"失败请求 {len(report['failed_requests'])} 条")
    print(f"报告: {report_path}")
    return 0 if all_ok else 1


def run_deep(page, out_dir: Path) -> dict:
    """交互冒烟: 在回测页真提交一个小回测, 等任务卡走到终态。"""
    page.click('[data-testid="nav-backtests"]')
    page.wait_for_selector('[data-testid="page-backtests"]', timeout=8_000)
    open_details(page)
    # dual_ma 默认勾选; 用默认日期区间; 填单标的成 chip(bt-symbols-input 是普通 input, 非 NInput)
    page.fill('[data-testid="bt-symbols-input"]', "000021.SZ")
    page.press('[data-testid="bt-symbols-input"]', "Enter")  # 整码即时成 chip; Enter 兜底取候选
    page.wait_for_selector('[data-testid="bt-chip"]', timeout=5_000)
    page.click('[data-testid="bt-submit"]')

    card = page.wait_for_selector('[data-testid="job-card"]', timeout=10_000)
    time.sleep(3)  # 等首轮日志轮询
    page.screenshot(path=str(out_dir / "07-job-running.png"), full_page=True)

    status = "timeout"
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        cls = card.query_selector(".badge").get_attribute("class") or ""
        st = cls.replace("badge", "").strip()
        if st in ("succeeded", "failed", "canceled"):
            status = st
            break
        time.sleep(2)

    time.sleep(1)
    page.screenshot(path=str(out_dir / "08-job-done.png"), full_page=True)
    print(f"[deep] 回测任务终态: {status}")
    return {"ok": status == "succeeded", "final_status": status,
            "screenshots": ["07-job-running.png", "08-job-done.png"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="驾驶舱 UI 冒烟 + 截图")
    parser.add_argument("--base", default=os.environ.get("UI_BASE", "http://127.0.0.1:8501"),
                        help="服务根(不含 /ui/); 迁移期可指 Vite dev server 如 http://127.0.0.1:5173")
    parser.add_argument("--out", default="data/ui_screenshots")
    parser.add_argument("--deep", action="store_true",
                        help="附加交互冒烟: 真提交一个小回测并等待完成")
    args = parser.parse_args()
    sys.exit(run_smoke(args.base, Path(args.out), args.deep))


if __name__ == "__main__":
    main()
