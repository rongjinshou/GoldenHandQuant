"""开发期快照: 截 dev server 双主题图供读图自查 (用法: $WIN_PYTHON frontend/scripts/shot.py [route])"""
import sys

from playwright.sync_api import sync_playwright

route = sys.argv[1] if len(sys.argv) > 1 else ''
base = 'http://127.0.0.1:5173/ui/'

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900})

    # window.__console_errors 全仓库(含 index.html/main.ts)搜不到一处写入 —— 恒为 [], 不是真信号。
    # 另挂一路 Playwright 原生 console/pageerror 监听全程收集, 末尾在原有那行之外多打一行真实结果。
    console_msgs: list[tuple[str, str]] = []
    page.on('console', lambda msg: console_msgs.append((msg.type, msg.text)))
    page.on('pageerror', lambda exc: console_msgs.append(('pageerror', str(exc))))

    def snapshot_themes(name: str) -> None:
        """dark/light 各截一张 full-page 图(真实切换路径: 点 theme-toggle, 走 store 响应式)。
        抽成函数供同一 route 内多个"状态"分别截图(如 explorer 单标的 vs 多标的叠加),
        文件名前缀用 name, 不与其他状态互相覆盖。"""
        for theme in ('dark', 'light'):
            current = page.evaluate('() => document.documentElement.dataset.theme')
            if current != theme:
                page.click('[data-testid="theme-toggle"]')
            page.wait_for_timeout(400)
            out = f'data/ui_dev_shots/{name}_{theme}.png'
            page.screenshot(path=out, full_page=True)
            print(f'saved {out}')

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
    snapshot_themes(route or 'root')

    if route == 'explorer':
        # 多标的叠加覆盖(设计 docs/feat/0705-explorer-multi-symbol): 复用上面已加载的 000021.SZ,
        # 再加一个标的触发 K 线区"涨跌幅对比"折线图分支(buildKlineOption 2+ 标的分支);
        # 新增第二个呈现框(data-testid="explorer-add-panel")并勾选与首框不同的特征,
        # 验证呈现框互相独立渲染。存独立文件名前缀 explorer_multi, 不覆盖上面 explorer_*.png。
        #
        # 2026-07-05 修复记录: 曾经从"已加载单标的"状态再加第二个标的点加载会触发
        # `xAxis "0" not found` 等 console 报错并使 Explorer 组件失去响应(根因: vue-echarts
        # 默认 merge 语义下, 1 标的分支[双 grid/数组 xAxis]与 2+ 标的分支[单 grid/对象 xAxis]
        # 形状不同, 已有 ECharts 实例合并不到旧组件引用)。已在 Explorer.vue/FeaturePanel.vue
        # 的 VChart 上固定 update-options={notMerge:true} 修复, 这条正是回归覆盖该路径的用例。
        # 仍保留 query_selector 判空 + try/except, 不让脚本因未来回归而崩溃、仍能截到图。
        page.fill('[data-testid="explorer-symbol-input"] input', '600519.SH')
        page.click('[data-testid="explorer-load"]')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(1500)  # K 线区同一 canvas 元素重绘(蜡烛→对比折线), 等重绘而非等新节点出现

        page.click('[data-testid="explorer-add-panel"]')
        page.wait_for_timeout(300)
        if page.query_selector('[data-testid="feature-chart-1"]') is None:
            print('  [explorer] 警告: 新增呈现框未生效(见下方 console errors —— 若复现说明多标的切换报错回归了)')
        else:
            # 第二个呈现框固定 testid="feature-chart-1"(FeaturePanel.vue 按位置编号, 首框恒为 feature-chart)
            for feat in ('RSI(14)', 'MACD'):
                page.click(f'[data-testid="feature-chart-1"] .n-checkbox:has-text("{feat}")')
                page.wait_for_timeout(500)  # 给上一次勾选触发的 refetch 留结算时间, 避免连续快速勾选导致请求乱序
            try:
                page.wait_for_selector('[data-testid="feature-chart-1"] canvas', timeout=8000)
            except Exception:
                print('  [explorer] 警告: feature-chart-1 未渲染出 canvas')
        page.wait_for_timeout(800)
        page.mouse.move(0, 0)  # 移开悬停, 避免 GlossaryTip 提示条截图时挡图
        page.wait_for_timeout(200)

        snapshot_themes('explorer_multi')

    errors = page.evaluate('() => window.__console_errors || []')
    print('console errors:', errors)
    real_errors = [f'{t}: {m}' for t, m in console_msgs if t != 'debug']
    print('console errors (playwright console/pageerror 实测; 上一行 window.__console_errors 无写入点不可信):', real_errors)
    browser.close()
