"""开发期快照: 截 dev server 双主题图供读图自查 (用法: $WIN_PYTHON frontend/scripts/shot.py [route])"""
import sys

from playwright.sync_api import sync_playwright

route = sys.argv[1] if len(sys.argv) > 1 else ''
base = 'http://127.0.0.1:5173/ui/'

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    page.goto(f'{base}#/{route}')
    page.wait_for_load_state('networkidle')
    if route == 'explorer':
        page.fill('[data-testid="explorer-symbol-input"] input', '000021.SZ')
        page.click('[data-testid="explorer-load"]')
        page.wait_for_selector('[data-testid="kline-chart"] canvas', timeout=15_000)
        page.wait_for_timeout(1500)
    if route == 'backtests':
        # 逐行点击直到出现净值曲线(首行 shadow-paper 单日无曲线, 找有曲线的多日轮次)
        rows = page.query_selector_all('[data-testid="bt-run-row"]')
        drawn = False
        for row in rows[:12]:
            row.click()
            try:
                page.wait_for_selector('[data-testid="bt-chart"] canvas', timeout=4000)
                drawn = True
                break
            except Exception:
                continue
        if not drawn:
            print('  [backtests] 前 12 行均无净值曲线')
        page.wait_for_timeout(1500)
    for theme in ('dark', 'light'):
        current = page.evaluate('() => document.documentElement.dataset.theme')
        if current != theme:
            page.click('[data-testid="theme-toggle"]')  # 真实切换路径, 走 store 响应式
        page.wait_for_timeout(400)
        out = f'data/ui_dev_shots/{route or "root"}_{theme}.png'
        page.screenshot(path=out, full_page=True)
        print(f'saved {out}')
    errors = page.evaluate('() => window.__console_errors || []')
    print('console errors:', errors)
    browser.close()
