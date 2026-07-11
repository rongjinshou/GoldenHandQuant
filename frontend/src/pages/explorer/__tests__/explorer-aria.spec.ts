import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

/* Explorer 流无障碍/反馈的模板契约防线(设计 §8 S5/S6/S8, 任务 1-5):
 * 联想 combobox 键盘 aria、图表 role=img、特征在途/失败反馈、加载骨架等属性直接落在 .vue 模板上,
 * 挂载真实 Explorer(含 ECharts/naive/NPopover)在 jsdom 下代价高且脆; 这里按"读文件断言关键属性存在"
 * 守住不回归(纯逻辑另在 suggest-nav.spec.ts / chart-options.spec.ts 覆盖)。 */

function read(rel: string): string {
  return readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8')
}

const explorer = read('../../Explorer.vue')
const featurePanel = read('../FeaturePanel.vue')

describe('Explorer.vue 标的联想 combobox 键盘 aria(任务 1 / §8 S8)', () => {
  it('input 挂 combobox 语义与联动 aria', () => {
    expect(explorer).toContain('role="combobox"')
    expect(explorer).toContain('aria-autocomplete="list"')
    expect(explorer).toContain('aria-expanded')
    expect(explorer).toContain('aria-controls')
    expect(explorer).toContain('aria-activedescendant')
  })

  it('候选列表 listbox/option + aria-selected(高亮读共享 chips.activeIndex, 单一真相源)', () => {
    expect(explorer).toContain('role="listbox"')
    expect(explorer).toContain('role="option"')
    expect(explorer).toContain('aria-selected')
    expect(explorer).toContain('chips.activeIndex')
  })

  it('键盘 ↑↓/Enter/Esc 接线到共享 composable(不自持第二套高亮状态)', () => {
    expect(explorer).toContain('ArrowDown')
    expect(explorer).toContain('ArrowUp')
    expect(explorer).toContain('Escape')
    expect(explorer).toContain('chips.onArrowDown()')
    expect(explorer).toContain('chips.onArrowUp()')
    expect(explorer).toContain('chips.onEscape()')
    expect(explorer).toContain('chips.onEnter()')
  })

  it('点外收起: 监听 document pointerdown + 容器 ref → chips.onEscape', () => {
    expect(explorer).toContain('onDocPointerDown')
    expect(explorer).toContain('chipsBoxRef')
    expect(explorer).toMatch(/onDocPointerDown[\s\S]*?chips\.onEscape\(\)/)
  })

  it('chips 校验错误 role=alert(§8 S6)', () => {
    expect(explorer).toMatch(/sym-err[\s\S]*?role="alert"/)
  })
})

describe('Explorer.vue 图表替代文本与加载态(任务 3/5 / §8 S5)', () => {
  it('K 线容器 role=img + 动态 aria-label', () => {
    expect(explorer).toContain('role="img"')
    expect(explorer).toContain(':aria-label="klineAriaLabel"')
  })

  it('加载期给骨架而非空态文案', () => {
    expect(explorer).toContain('chart-skeleton')
    expect(explorer).toMatch(/v-if="loadingData"/)
  })
})

describe('Explorer.vue 特征在途反馈接线(任务 2)', () => {
  it('向呈现框透传 fetching / fetch-error', () => {
    expect(explorer).toContain(':fetching="panelFetching"')
    expect(explorer).toContain(':fetch-error="featureError"')
  })

  it('refetch 失败落到 featureError 而非顶部 error banner', () => {
    expect(explorer).toContain('featureError.value = (e as Error).message')
    // 顶部 error banner 只在整体 loadAll 失败时用; refetch 不再写 error.value = message
    expect(explorer).not.toMatch(/if \(myFeatureGen !== featureFetchGen\) return[\s\S]{0,80}error\.value = \(e as Error\)/)
  })
})

describe('FeaturePanel.vue 反馈与图表 aria(任务 2/3/5)', () => {
  it('头部在途 spinner(role=status) + 失败提示(role=alert)', () => {
    expect(featurePanel).toContain('data-testid="feature-fetching"')
    expect(featurePanel).toContain('role="status"')
    expect(featurePanel).toContain('data-testid="feature-fetch-error"')
    expect(featurePanel).toContain('role="alert"')
  })

  it('特征图容器 role=img + 动态 aria-label', () => {
    expect(featurePanel).toContain('role="img"')
    expect(featurePanel).toContain(':aria-label="ariaLabel"')
  })

  it('在途且无缓存时给骨架', () => {
    expect(featurePanel).toContain('chart-skeleton')
    expect(featurePanel).toContain('fetching && !option')
  })

  it('接收 fetching / fetchError props', () => {
    expect(featurePanel).toContain('fetching?: boolean')
    expect(featurePanel).toContain('fetchError?: string')
  })
})

describe('Explorer.vue P7 URL 深链接线(?symbols= ↔ 标的组合)', () => {
  it('接入 vue-router 与深链纯逻辑模块', () => {
    expect(explorer).toContain("from 'vue-router'")
    expect(explorer).toContain('useRoute')
    expect(explorer).toContain('useRouter')
    expect(explorer).toContain("from './explorer/deep-link'")
    expect(explorer).toContain('parseSymbolsQuery')
    expect(explorer).toContain('symbolsToQuery')
  })

  it('写回用 router.replace(不 push, 不污染历史)', () => {
    expect(explorer).toContain('router.replace')
    expect(explorer).not.toContain('router.push')
  })

  it('watch(route.query.symbols) 支持前进后退', () => {
    expect(explorer).toMatch(/watch\(\s*\(\)\s*=>\s*route\.query\.symbols/)
  })

  it('挂载时若带 ?symbols= 则解析并自动加载', () => {
    expect(explorer).toMatch(/onMounted[\s\S]*?parseSymbolsQuery\(route\.query\.symbols\)/)
  })

  it('恢复复用现有加载逻辑(loadAll), 且有幂等门槛防死循环', () => {
    // applySymbolsFromQuery 复用 loadAll, 并以规范串相等为跳过门槛
    expect(explorer).toMatch(/applySymbolsFromQuery[\s\S]*?symbolsToQuery\(list\)\s*===\s*symbolsToQuery\(loadedSymbols\.value\)/)
    expect(explorer).toMatch(/applySymbolsFromQuery[\s\S]*?loadAll\(\)/)
    // 写回侧同样以规范串相等提前 return(不重复 replace)
    expect(explorer).toMatch(/syncQueryFromLoaded[\s\S]*?loadedQ\s*===\s*parseSymbolsQuery\(route\.query\.symbols\)\.join/)
  })
})

describe('Explorer.vue 「最近查看」组合 chips(识别>回忆, R3 组合记忆)', () => {
  it('接入 recent-symbols 纯逻辑模块(读/写/清/label 格式化)', () => {
    expect(explorer).toContain("from './explorer/recent-symbols'")
    expect(explorer).toContain('loadRecentSets')
    expect(explorer).toContain('pushRecentSet')
    expect(explorer).toContain('clearRecentSets')
    expect(explorer).toContain('formatSetLabel')
  })

  it('只在 loadAll 成功路径整组记入 —— 深链恢复/最近组合点击同走 loadAll, 一并记入', () => {
    expect(explorer).toMatch(/hasLoaded\.value = true[\s\S]{0,200}?pushRecentSet\(symbols\)/)
    // 失败分支(catch)不记入
    expect(explorer).not.toMatch(/catch[\s\S]{0,120}?pushRecentSet/)
  })

  it('最近行/清空按钮模板锚点; 记录为空整行不渲染', () => {
    expect(explorer).toContain('data-testid="explorer-recent"')
    expect(explorer).toContain('data-testid="recent-clear"')
    expect(explorer).toMatch(/v-if="recentSets\.length"/)
  })

  it('组合 chip 文案走 formatSetLabel(多标的截断「首标的 +N」), title/aria-label 带完整列表', () => {
    expect(explorer).toContain('{{ formatSetLabel(set) }}')
    expect(explorer).toMatch(/:title="[^"]*set\.join/)
    expect(explorer).toMatch(/:aria-label="[^"]*set\.join/)
  })

  it('点击 = 整组替换当前 chips 再加载(setChips 置换助手, 非并入), 与深链恢复共用置入路径', () => {
    expect(explorer).toMatch(/function pickRecentSet[\s\S]{0,240}?setChips\(set\)[\s\S]{0,120}?loadAll\(\)/)
    expect(explorer).toMatch(/applySymbolsFromQuery[\s\S]*?setChips\(list\)/)
    // 整组替换语义: 点击路径不走"并入"(commitText)
    expect(explorer).not.toMatch(/pickRecentSet[\s\S]{0,240}?commitText/)
  })

  it('加载在途时最近 chip 禁点(与"加载"按钮同口径, 保住 loadAll 无并发不变量)', () => {
    expect(explorer).toMatch(/class="recent-chip"[\s\S]{0,160}?:disabled="loadingData"/)
    expect(explorer).toMatch(/function pickRecentSet[\s\S]{0,120}?if \(loadingData\.value\) return/)
  })
})

describe('Explorer 缩放联动(R2-B): K 线与特征图同组 connect', () => {
  it('Explorer.vue 从 echarts/core 引入 connect, 并在挂载时对共享组调用一次', () => {
    expect(explorer).toMatch(/import \{ connect, use \} from 'echarts\/core'/)
    expect(explorer).toMatch(/onMounted\(\(\) => connect\(EXPLORER_CHART_GROUP\)\)/)
  })

  it('K 线 VChart 绑定共享 group(vue-echarts group prop), 常量取自 chart-options 单一真相源', () => {
    expect(explorer).toContain(':group="EXPLORER_CHART_GROUP"')
    expect(explorer).toMatch(/EXPLORER_CHART_GROUP,[\s\S]*?\} from '\.\/explorer\/chart-options'/)
  })

  it('特征呈现框 VChart 绑定同一共享 group —— 页内 K 线↔特征(含多呈现框)同步缩放', () => {
    expect(featurePanel).toContain(':group="EXPLORER_CHART_GROUP"')
    expect(featurePanel).toMatch(/EXPLORER_CHART_GROUP,[\s\S]*?\} from '\.\/chart-options'/)
  })

  it('呈现框只挂组名不自调 connect(由 Explorer 统一调一次, 防止职责双写)', () => {
    expect(featurePanel).not.toMatch(/connect\(EXPLORER_CHART_GROUP\)/)
    expect(featurePanel).not.toMatch(/import \{[^}]*\bconnect\b[^}]*\} from 'echarts\/core'/)
  })
})

describe('FeaturePanel.vue 特征勾选分组(Miller 分块, 易用性迭代任务 2)', () => {
  it('按 FEATURE_GROUPS 分组渲染: 组容器 role=group + aria-label, 组标签小字', () => {
    expect(featurePanel).toContain('FEATURE_GROUPS')
    expect(featurePanel).toContain('role="group"')
    expect(featurePanel).toContain('group-label')
    // 组标签用 --text-3 小字(任务 2 视觉要求)
    expect(featurePanel).toMatch(/\.group-label[\s\S]*?color: var\(--text-3\)/)
  })

  it('GlossaryTip 悬停释义保留(逐特征)', () => {
    expect(featurePanel).toMatch(/FEATURE_GROUPS[\s\S]*?GlossaryTip :term="fm\.name"/)
  })
})

describe('FeaturePanel.vue 复选框不嵌套交互元素(WCAG 4.1.2, 6σ R5 F-05)', () => {
  it('NCheckbox label 内不得出现 GlossaryTip 触发器(tabindex=0 role=button 嵌进复选框)', () => {
    expect(featurePanel).not.toMatch(/<NCheckbox[^]*?GlossaryTip[^]*?<\/NCheckbox>/)
  })

  it('释义触发器为复选框的相邻兄弟: </NCheckbox> 后紧跟 GlossaryTip', () => {
    expect(featurePanel).toMatch(/<\/NCheckbox>\s*<GlossaryTip :term="fm\.name"/)
  })
})
