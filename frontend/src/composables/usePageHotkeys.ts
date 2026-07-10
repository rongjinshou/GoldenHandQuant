import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

import { NAV_ITEMS } from '@/router'

/** 守卫判定所需的最小事件形状(结构类型): 单测可直接构造普通对象, KeyboardEvent 天然满足。 */
export interface HotkeyEventLike {
  ctrlKey: boolean
  metaKey: boolean
  altKey: boolean
  shiftKey: boolean
  isComposing: boolean
  target: EventTarget | null
}

/** 输入场景选择器: 自身或祖先命中即视为"正在输入", 快捷键让路(覆盖 naive-ui 包壳 input 等嵌套结构)。 */
const INPUT_CONTEXT_SELECTOR = 'input,textarea,select,[contenteditable="true"]'

function inInputContext(node: EventTarget | Element | null): boolean {
  // window/document/null 等非 Element 没有 closest → 视为非输入场景
  if (!node || typeof (node as Element).closest !== 'function') return false
  return (node as Element).closest(INPUT_CONTEXT_SELECTOR) !== null
}

/** 快捷键守卫(纯函数, R2-D): 全部命中才放行 ——
 * ① 无任何修饰键(ctrl/meta/alt/shift, 避免劫持 Ctrl+1 切浏览器页签类系统习惯);
 * ② 非输入法合成中(isComposing, 拼音敲数字选字不切页);
 * ③ 事件目标与 activeElement 均不在输入场景(双保险: 事件可能从 window 派发, target 不一定是焦点元素)。
 * activeElement 由调用方显式传入(通常为 document.activeElement), 保持本函数纯。 */
export function shouldHandleHotkey(e: HotkeyEventLike, activeElement: Element | null = null): boolean {
  if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) return false
  if (e.isComposing) return false
  if (inInputContext(e.target)) return false
  if (inInputContext(activeElement)) return false
  return true
}

/** 键名 → 页签下标(纯函数): '1'→0 … '6'→5, 其余(含 '0'/'7'/多字符/空串)→ null。
 * 主键盘与小键盘(NumLock 开)的 e.key 均为 '1'..'6', 按 key 判定即天然覆盖 Digit/Numpad 两路。 */
export function hotkeyIndex(key: string): number | null {
  return /^[1-6]$/.test(key) ? Number(key) - 1 : null
}

/** R2-D 专家效率: 数字键 1-6 直达六页签(可发现性挂在 nav-link 的 title 上)。
 * onMounted 挂 window keydown / onUnmounted 卸, 不残留监听; 不 preventDefault(数字键无默认行为可抢)。 */
export function usePageHotkeys(): void {
  const router = useRouter()

  function onKeydown(e: KeyboardEvent): void {
    const index = hotkeyIndex(e.key)
    if (index === null || index >= NAV_ITEMS.length) return
    if (!shouldHandleHotkey(e, document.activeElement)) return
    void router.push({ name: NAV_ITEMS[index].name })
  }

  onMounted(() => window.addEventListener('keydown', onKeydown))
  onUnmounted(() => window.removeEventListener('keydown', onKeydown))
}
