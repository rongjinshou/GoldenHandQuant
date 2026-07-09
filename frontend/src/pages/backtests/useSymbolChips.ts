import { ref, type Ref } from 'vue'

import { fetchJSON } from '@/api/fetch'
import type { SymbolHit } from '@/api/types'

/* 标的 chips + 联想 — 旧 backtests.js initSymbolChips 语义对等(设计 DD-9):
 * - 完整代码(联想点选/手输完成) → 即时成 chip, 并清在途防抖(防旧候选填回)
 * - 粘贴含分隔符 / 末尾敲分隔符 → 拆分(编辑残留非法串时逐键重拆会跳光标, 收窄触发条件)
 * - 联想 200ms 防抖, 过期响应丢弃, 失败静默; Enter 取候选需候选确属当前输入
 * - Backspace 空输入框回删末 chip; 非法 token 留在输入框可修正 */

export const SYMBOL_RE = /^\d{6}\.(SH|SZ|BJ)$/

const SEP_RE = /[\s,，;；]+/
const HAS_SEP_RE = /[,，;；\s]/
const ENDS_SEP_RE = /[,，;；\s]$/

/* 文本 → 合法/非法 token(大写化, 分隔符切分); 纯函数供 Vitest 直测 */
export function splitSymbolTokens(text: string): { ok: string[]; bad: string[] } {
  const tokens = text
    .split(SEP_RE)
    .map((t) => t.trim().toUpperCase())
    .filter(Boolean)
  const ok: string[] = []
  const bad: string[] = []
  for (const t of tokens) {
    if (SYMBOL_RE.test(t)) ok.push(t)
    else bad.push(t)
  }
  return { ok, bad }
}

export interface UseSymbolChipsReturn {
  symbols: Ref<string[]>
  input: Ref<string>
  suggestions: Ref<SymbolHit[]>
  /* 当前 ↑↓ 键盘高亮的候选下标; -1 = 无高亮(aria-activedescendant 空) */
  activeIndex: Ref<number>
  err: Ref<string>
  commitText: (text: string) => string[]
  remove: (sym: string) => void
  pickSuggestion: (hit: SymbolHit) => void
  onInput: (e: Event) => void
  onEnter: () => void
  onBackspace: () => void
  onArrowDown: () => void
  onArrowUp: () => void
  onEscape: () => void
  clearPending: () => void
}

export function useSymbolChips(): UseSymbolChipsReturn {
  const symbols = ref<string[]>([])
  const input = ref('')
  const suggestions = ref<SymbolHit[]>([])
  const activeIndex = ref(-1)
  const err = ref('')

  /* 候选集变动即清高亮(新候选无预选, 符合 aria-autocomplete=list 语义) */
  function resetHighlight(): void {
    activeIndex.value = -1
  }
  /* Enter 取候选时校验对应关系(旧 datalist dataset.q 等价) */
  let suggestQ = ''
  let timer: ReturnType<typeof setTimeout> | null = null

  /* 幽灵点击防护(2026-07-05 confirmed-bug): 鼠标点选联想候选后, 该候选 <li> 从 DOM 消失、
   * 新 chip 的×按钮在同一屏幕坐标插入, 浏览器对 mouseup 的坐标命中测试发生在这次 DOM 更新
   * 之后, 于是对新插入的×按钮补发一次原生 click——同一次点击手势里"选中"与"删除"背靠背
   * 触发, 表现为点联想候选后 chip 秒加秒删, 搜索选中彻底不可用(已用 Playwright 手动分离
   * mousedown/mouseup + 全局 click 监听逐层复现确认, 与 mousedown 或 click 触发本身无关)。
   * 防护: 记一个 symbol 最近被 commitText 加入的时间, remove() 短窗口(250ms)内命中同一
   * symbol 视为幽灵点击, 忽略——真实用户"加错了马上点×撤销"的手速也远不会快过这个窗口。 */
  const GHOST_CLICK_GUARD_MS = 250
  const recentlyAdded = new Map<string, number>()

  function clearPending(): void {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  /* 文本 → chips(去重追加); 返回非法 token */
  function commitText(text: string): string[] {
    const { ok, bad } = splitSymbolTokens(text)
    for (const sym of ok) {
      if (!symbols.value.includes(sym)) {
        symbols.value.push(sym)
        recentlyAdded.set(sym, Date.now())
      }
    }
    return bad
  }

  function remove(sym: string): void {
    const addedAt = recentlyAdded.get(sym)
    if (addedAt !== undefined && Date.now() - addedAt < GHOST_CLICK_GUARD_MS) return
    symbols.value = symbols.value.filter((s) => s !== sym)
  }

  function commitAndClear(text: string): void {
    commitText(text)
    input.value = ''
    suggestions.value = []
    resetHighlight()
    err.value = ''
  }

  function pickSuggestion(hit: SymbolHit): void {
    clearPending()
    commitAndClear(hit.symbol)
  }

  function onInput(e: Event): void {
    const v = input.value.trim().toUpperCase()
    // 完整代码(联想点选 / 手输完成) → 即时成 chip; 清在途防抖防旧候选填回
    if (SYMBOL_RE.test(v)) {
      clearPending()
      commitAndClear(v)
      return
    }
    // 粘贴 / 末尾敲分隔符 → 拆分(收窄触发条件, 防编辑残留串逐键重拆跳光标)
    const isPaste = (e as InputEvent).inputType === 'insertFromPaste'
    const endsSep = ENDS_SEP_RE.test(input.value)
    if ((isPaste && HAS_SEP_RE.test(input.value)) || endsSep) {
      clearPending()
      const bad = commitText(input.value)
      input.value = bad.join(',')
      suggestions.value = []
      resetHighlight()
      err.value = bad.length
        ? `已忽略非法标的: ${bad.join(', ')}（格式 6位代码.SH/SZ/BJ，可修正后回车）`
        : ''
      return
    }
    clearPending()
    const q = input.value.trim()
    if (!q) {
      suggestions.value = []
      resetHighlight()
      return
    }
    timer = setTimeout(() => {
      void (async () => {
        try {
          const sug = await fetchJSON<SymbolHit[]>(
            `/api/research/symbols?q=${encodeURIComponent(q)}`,
          )
          if (input.value.trim() !== q) return // 过期响应丢弃
          suggestQ = q
          suggestions.value = sug
          resetHighlight() // 新候选集: 高亮归零, 等待用户 ↑↓
        } catch {
          /* 联想失败静默 */
        }
      })()
    }, 200)
  }

  function onEnter(): void {
    // 键盘高亮候选优先(combobox 语义): 已 ↑↓ 选中某条 → 回车直取该条
    const active = activeIndex.value >= 0 ? suggestions.value[activeIndex.value] : undefined
    if (active) {
      clearPending()
      pickSuggestion(active)
      return
    }
    const v = input.value.trim().toUpperCase()
    if (!v) return
    clearPending()
    if (SYMBOL_RE.test(v)) {
      commitAndClear(v)
      return
    }
    // 编辑后的残留串(含分隔符) → 重新拆分
    if (HAS_SEP_RE.test(v)) {
      const bad = commitText(v)
      input.value = bad.join(',')
      err.value = bad.length ? `仍有非法标的: ${bad.join(', ')}` : ''
      return
    }
    // 名称搜索快捷路径: 仅当候选确属当前输入(防过期候选静默入列)
    const hit = suggestions.value[0]
    if (hit && suggestQ === input.value.trim()) {
      commitAndClear(hit.symbol)
      return
    }
    err.value = '格式 6位代码.SH/SZ/BJ；输名称请稍候联想加载后回车或点选'
  }

  function onBackspace(): void {
    if (!input.value && symbols.value.length) {
      symbols.value.pop()
    }
  }

  /* ↑↓ 在候选列表间移动高亮; -1(无高亮)按方向落首/末项, 到边回绕 */
  function moveHighlight(delta: number): void {
    const n = suggestions.value.length
    if (!n) return
    const cur = activeIndex.value
    activeIndex.value = cur === -1 ? (delta > 0 ? 0 : n - 1) : (cur + delta + n) % n
  }

  function onArrowDown(): void {
    moveHighlight(1)
  }

  function onArrowUp(): void {
    moveHighlight(-1)
  }

  /* Esc 关闭候选浮层(aria-expanded=false), 清高亮; 输入内容不动, 用户可继续编辑 */
  function onEscape(): void {
    clearPending()
    suggestions.value = []
    resetHighlight()
  }

  return {
    symbols,
    input,
    suggestions,
    activeIndex,
    err,
    commitText,
    remove,
    pickSuggestion,
    onInput,
    onEnter,
    onBackspace,
    onArrowDown,
    onArrowUp,
    onEscape,
    clearPending,
  }
}
