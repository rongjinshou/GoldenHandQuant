import { getCurrentScope, onScopeDispose, ref, type Ref } from 'vue'

export interface UsePollingOptions {
  intervalMs: number
  immediate?: boolean
  /** 失败退避: 连续失败时轮询间隔 ×2 封顶 60s, 成功复位。
   * 默认关 —— 既有调用方(JobCard/Jobs/Live)依赖固定节奏, 保持向后兼容; 需要退避的调用方显式开启。 */
  backoff?: boolean
}

export interface UsePollingReturn<T> {
  data: Ref<T | null>
  error: Ref<Error | null>
  loading: Ref<boolean>
  /** 距上次成功已超过 2×interval → true(连接可能中断, UI 可提示"数据更新于 … · 连接中断") */
  isStale: Ref<boolean>
  /** 上次成功拉取的时间戳(Date.now()); 从未成功为 null */
  lastSuccessAt: Ref<number | null>
  refresh: () => Promise<void>
  stop: () => void
}

const BACKOFF_CAP_MS = 60_000

/** 失败退避(纯函数, 便于单测): 连续失败 failCount 次后的下次间隔, 每失败一次 ×2, 封顶 60s。
 * 成功后 failCount 归 0 即回到 base。base 本身超过封顶时以 base 为准, 不会把间隔反而缩短。 */
export function nextInterval(baseMs: number, failCount: number): number {
  const grown = baseMs * 2 ** Math.max(0, failCount)
  return Math.min(grown, Math.max(baseMs, BACKOFF_CAP_MS))
}

/** 陈旧判定(纯函数): 距上次成功已超过 2×interval 即视为陈旧。从未成功(null)不算陈旧(由 error/loading 覆盖)。 */
export function computeStale(now: number, lastSuccessAt: number | null, intervalMs: number): boolean {
  if (lastSuccessAt === null) return false
  return now - lastSuccessAt > 2 * intervalMs
}

/* 统一轮询(设计 §4.1 轮询矩阵 + §10 基础设施硬化):
 * - 首载失败置 error; 后续 tick 失败静默保留旧 data
 * - 页签隐藏暂停, 恢复立即刷一次再续
 * - 迟到响应丢弃(序号守卫, 对等旧版三处过期响应语义)
 * - 失败退避: 连续失败间隔 ×2 封顶 60s, 成功复位(nextInterval)
 * - isStale/lastSuccessAt: 陈旧感知(computeStale)
 * - 每次拉取一个 AbortController, 新拉取前 abort 上一个在途请求(signal 透传给 fetcher, 用不用由 fetcher 决定)
 * - effectScope/组件卸载自动停 */
export function usePolling<T>(
  fetcher: (signal?: AbortSignal) => Promise<T>,
  opts: UsePollingOptions,
): UsePollingReturn<T> {
  const data = ref<T | null>(null) as Ref<T | null>
  const error = ref<Error | null>(null)
  const loading = ref(false)
  const isStale = ref(false)
  const lastSuccessAt = ref<number | null>(null)

  let timer: ReturnType<typeof setTimeout> | null = null
  let seq = 0
  let stopped = false
  let hasLoadedOnce = false
  let failCount = 0
  let inflight: AbortController | null = null

  async function refresh(): Promise<void> {
    const mySeq = ++seq
    inflight?.abort() // 新拉取前取消上一个在途请求
    const controller = new AbortController()
    inflight = controller
    loading.value = true
    try {
      const result = await fetcher(controller.signal)
      if (mySeq !== seq || stopped) return // 迟到响应丢弃
      data.value = result
      error.value = null
      hasLoadedOnce = true
      failCount = 0 // 成功即复位退避
      lastSuccessAt.value = Date.now()
      isStale.value = false
    } catch (e) {
      if (mySeq !== seq || stopped) return // 迟到/被取消的失败一并丢弃(不计入退避)
      failCount += 1
      isStale.value = computeStale(Date.now(), lastSuccessAt.value, opts.intervalMs)
      if (!hasLoadedOnce) {
        error.value = e instanceof Error ? e : new Error(String(e))
      }
      // tick 失败静默: 保留旧 data
    } finally {
      if (mySeq === seq) {
        loading.value = false
        if (inflight === controller) inflight = null
      }
    }
  }

  function clearTimer(): void {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
  }

  // 自重排的 setTimeout: 开启退避时下次间隔按当前 failCount 拉长; 串行(await refresh)保证退避用的是最新失败计数
  function schedule(): void {
    if (stopped || timer !== null) return
    const delay = opts.backoff ? nextInterval(opts.intervalMs, failCount) : opts.intervalMs
    timer = setTimeout(runTick, delay)
  }

  async function runTick(): Promise<void> {
    timer = null
    if (stopped) return
    if (document.visibilityState !== 'visible') return // 暂停; onVisibility 恢复时重启
    isStale.value = computeStale(Date.now(), lastSuccessAt.value, opts.intervalMs)
    await refresh()
    if (!stopped && document.visibilityState === 'visible') schedule()
  }

  function onVisibility(): void {
    if (stopped) return
    if (document.visibilityState === 'visible') {
      void refresh() // 恢复立即刷一次
      schedule()
    } else {
      clearTimer() // 暂停
    }
  }

  function stop(): void {
    stopped = true
    clearTimer()
    inflight?.abort()
    document.removeEventListener('visibilitychange', onVisibility)
  }

  document.addEventListener('visibilitychange', onVisibility)
  if (opts.immediate !== false) void refresh()
  schedule()

  if (getCurrentScope()) onScopeDispose(stop)

  return { data, error, loading, isStale, lastSuccessAt, refresh, stop }
}
