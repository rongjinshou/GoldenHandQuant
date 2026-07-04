import { getCurrentScope, onScopeDispose, ref, type Ref } from 'vue'

export interface UsePollingOptions {
  intervalMs: number
  immediate?: boolean
}

export interface UsePollingReturn<T> {
  data: Ref<T | null>
  error: Ref<Error | null>
  loading: Ref<boolean>
  refresh: () => Promise<void>
  stop: () => void
}

/* 统一轮询(设计 §4.1 轮询矩阵):
 * - 首载失败置 error; 后续 tick 失败静默保留旧 data
 * - 页签隐藏暂停, 恢复立即刷一次再续
 * - 迟到响应丢弃(序号守卫, 对等旧版三处过期响应语义)
 * - effectScope/组件卸载自动停 */
export function usePolling<T>(
  fetcher: () => Promise<T>,
  opts: UsePollingOptions,
): UsePollingReturn<T> {
  const data = ref<T | null>(null) as Ref<T | null>
  const error = ref<Error | null>(null)
  const loading = ref(false)

  let timer: ReturnType<typeof setInterval> | null = null
  let seq = 0
  let stopped = false
  let hasLoadedOnce = false

  async function refresh(): Promise<void> {
    const mySeq = ++seq
    loading.value = true
    try {
      const result = await fetcher()
      if (mySeq !== seq || stopped) return // 迟到响应丢弃
      data.value = result
      error.value = null
      hasLoadedOnce = true
    } catch (e) {
      if (mySeq !== seq || stopped) return
      if (!hasLoadedOnce) {
        error.value = e instanceof Error ? e : new Error(String(e))
      }
      // tick 失败静默: 保留旧 data
    } finally {
      if (mySeq === seq) loading.value = false
    }
  }

  function startTimer(): void {
    if (timer !== null || stopped) return
    timer = setInterval(() => {
      if (document.visibilityState === 'visible') void refresh()
    }, opts.intervalMs)
  }

  function pauseTimer(): void {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
  }

  function onVisibility(): void {
    if (stopped) return
    if (document.visibilityState === 'visible') {
      void refresh() // 恢复立即刷一次
      startTimer()
    } else {
      pauseTimer()
    }
  }

  function stop(): void {
    stopped = true
    pauseTimer()
    document.removeEventListener('visibilitychange', onVisibility)
  }

  document.addEventListener('visibilitychange', onVisibility)
  if (opts.immediate !== false) void refresh()
  startTimer()

  if (getCurrentScope()) onScopeDispose(stop)

  return { data, error, loading, refresh, stop }
}
