"""驾驶舱交互截图工具 — 按步骤 DSL 操作页面后截图（Playwright, Windows python）。

ui_smoke.py 管整页冒烟; 本工具管"做几步交互后看局部效果"（hover 气泡 /
chips 输入 / 表单状态等截图验证）。

用法示例:
    $WIN_PYTHON scripts/ui_interact_shot.py \
        --do tab:backtests --do open-details --do fill:#bt-symbols-input=000021.SZ \
        --do wait:0.5 --do shot:chips.png

支持的步骤 (按顺序执行):
    tab:<name>            点页签 (overview/verdicts/explorer/backtests/live/jobs)
    open-details          展开当前页签所有 <details>
    fill:<sel>=<text>     填输入框 (触发 input 事件)
    select:<sel>=<value>  下拉框选值 (触发 change 事件)
    type:<sel>=<text>     逐字符键入 (触发联想)
    press:<sel>=<key>     对元素按键 (Enter/Backspace/...)
    click:<sel>           点击
    hover:<sel>           悬停 (配合 shot 验证 tooltip)
    wait:<sec>            等待秒数
    shot:<file>           截图 (存到 --out 目录, full_page)
"""

import argparse
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")


def run(base: str, out_dir: Path, steps: list[str]) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1680, "height": 1050})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{base}/ui/", wait_until="domcontentloaded")
        page.wait_for_selector("#meta", timeout=10_000)
        time.sleep(1.5)

        for step in steps:
            op, _, arg = step.partition(":")
            match op:
                case "tab":
                    page.click(f'.tab[data-tab="{arg}"]')
                    time.sleep(0.8)
                case "open-details":
                    page.evaluate(
                        "document.querySelectorAll('.panel.active details')"
                        ".forEach(d => { d.open = true; })")
                case "fill":
                    sel, _, text = arg.partition("=")
                    page.fill(sel, text)
                case "type":
                    sel, _, text = arg.partition("=")
                    page.type(sel, text, delay=60)
                case "press":
                    sel, _, key = arg.partition("=")
                    page.press(sel, key)
                case "click":
                    page.click(arg)
                case "select":
                    sel, _, value = arg.partition("=")
                    page.select_option(sel, value)
                case "hover":
                    page.hover(arg)
                    time.sleep(0.3)
                case "wait":
                    time.sleep(float(arg))
                case "shot":
                    path = out_dir / arg
                    page.screenshot(path=str(path), full_page=True)
                    print(f"[shot] {path}")
                case _:
                    print(f"[skip] 未知步骤: {step}")
        browser.close()

    if errors:
        print(f"页面异常 {len(errors)} 条: {errors[:3]}")
        return 1
    print("无页面异常")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="驾驶舱交互截图")
    parser.add_argument("--base", default="http://127.0.0.1:8501")
    parser.add_argument("--out", default="data/ui_screenshots")
    parser.add_argument("--do", dest="steps", action="append", required=True,
                        help="步骤, 可重复 (tab:/fill:/type:/press:/click:/hover:/wait:/shot:)")
    args = parser.parse_args()
    sys.exit(run(args.base, Path(args.out), args.steps))


if __name__ == "__main__":
    main()
