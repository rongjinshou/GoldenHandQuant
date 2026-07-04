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
