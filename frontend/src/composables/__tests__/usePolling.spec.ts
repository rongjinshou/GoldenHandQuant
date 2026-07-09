import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope } from 'vue'

import { computeStale, nextInterval, usePolling } from '../usePolling'

function deferred<T>() {
  let resolve!: (v: T) => void
  let reject!: (e: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

async function flush() {
  await Promise.resolve()
  await Promise.resolve()
}

describe('usePolling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('immediate 默认立即拉取一次', async () => {
    const fetcher = vi.fn().mockResolvedValue(42)
    const { data } = usePolling(fetcher, { intervalMs: 1000 })
    await flush()
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(data.value).toBe(42)
  })

  it('按间隔轮询', async () => {
    const fetcher = vi.fn().mockResolvedValue(1)
    usePolling(fetcher, { intervalMs: 1000 })
    await flush()
    await vi.advanceTimersByTimeAsync(2100)
    expect(fetcher.mock.calls.length).toBeGreaterThanOrEqual(3)
  })

  it('首载失败置 error, 后续 tick 失败静默保留旧 data', async () => {
    const fetcher = vi.fn().mockRejectedValueOnce(new Error('boom'))
    const { data, error } = usePolling(fetcher, { intervalMs: 1000 })
    await flush()
    expect(error.value?.message).toBe('boom')
    expect(data.value).toBeNull()

    fetcher.mockResolvedValueOnce(7)
    await vi.advanceTimersByTimeAsync(1000)
    expect(data.value).toBe(7)
    expect(error.value).toBeNull()

    fetcher.mockRejectedValueOnce(new Error('tick fail'))
    await vi.advanceTimersByTimeAsync(1000)
    expect(data.value).toBe(7) // 旧数据保留
    expect(error.value).toBeNull() // tick 失败静默
  })

  it('stop 后不再轮询', async () => {
    const fetcher = vi.fn().mockResolvedValue(1)
    const { stop } = usePolling(fetcher, { intervalMs: 1000 })
    await flush()
    stop()
    await vi.advanceTimersByTimeAsync(3000)
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('页签隐藏暂停, 恢复立即刷新', async () => {
    const fetcher = vi.fn().mockResolvedValue(1)
    usePolling(fetcher, { intervalMs: 1000 })
    await flush()
    expect(fetcher).toHaveBeenCalledTimes(1)

    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(3000)
    expect(fetcher).toHaveBeenCalledTimes(1) // 隐藏期零调用

    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
    document.dispatchEvent(new Event('visibilitychange'))
    await flush()
    expect(fetcher).toHaveBeenCalledTimes(2) // 恢复立即刷一次
  })

  it('迟到响应丢弃(过期守卫)', async () => {
    const slow = deferred<number>()
    const fetcher = vi.fn().mockReturnValueOnce(slow.promise).mockResolvedValueOnce(2)
    const { data, refresh } = usePolling(fetcher, { intervalMs: 60_000 })
    await flush()
    await refresh() // 第二次请求先完成
    expect(data.value).toBe(2)
    slow.resolve(1) // 第一次请求迟到
    await flush()
    expect(data.value).toBe(2) // 迟到响应被丢弃
  })

  it('effectScope 销毁自动 stop', async () => {
    const fetcher = vi.fn().mockResolvedValue(1)
    const scope = effectScope()
    scope.run(() => usePolling(fetcher, { intervalMs: 1000 }))
    await flush()
    scope.stop()
    await vi.advanceTimersByTimeAsync(3000)
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('每次拉取传入新 signal, 新拉取 abort 上一个在途请求', async () => {
    const signals: (AbortSignal | undefined)[] = []
    const slow = deferred<number>()
    const fetcher = vi.fn().mockImplementation((signal?: AbortSignal) => {
      signals.push(signal)
      return signals.length === 1 ? slow.promise : Promise.resolve(2)
    })
    const { refresh } = usePolling(fetcher, { intervalMs: 60_000 })
    await flush() // 第一次拉取: signals[0], 挂起
    await refresh() // 第二次拉取: 应 abort signals[0]
    expect(signals).toHaveLength(2)
    expect(signals[0]?.aborted).toBe(true)
    expect(signals[1]?.aborted).toBe(false)
    slow.resolve(1) // 迟到, 被序号守卫丢弃
    await flush()
  })

  it('lastSuccessAt 记录成功时刻, 超过 2×interval 未成功则 isStale=true', async () => {
    vi.setSystemTime(0)
    const fetcher = vi.fn().mockResolvedValueOnce(1).mockRejectedValue(new Error('down'))
    const { isStale, lastSuccessAt } = usePolling(fetcher, { intervalMs: 1000 })
    await flush()
    expect(lastSuccessAt.value).toBe(0)
    expect(isStale.value).toBe(false)

    // 1s 时首次 tick 失败, 尚未超 2×interval
    await vi.advanceTimersByTimeAsync(1000)
    expect(isStale.value).toBe(false)

    // 继续失败, 累计 > 2000ms → 陈旧
    await vi.advanceTimersByTimeAsync(2500)
    expect(isStale.value).toBe(true)
    expect(lastSuccessAt.value).toBe(0) // 仍是最后一次成功时刻

    // 恢复成功 → 复位
    fetcher.mockResolvedValue(9)
    await vi.advanceTimersByTimeAsync(60_000)
    expect(isStale.value).toBe(false)
  })

  it('失败退避(opt-in): 连续失败逐步拉长轮询间隔', async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error('down'))
    usePolling(fetcher, { intervalMs: 1000, backoff: true })
    await flush()
    expect(fetcher).toHaveBeenCalledTimes(1) // init 立即拉取(首载失败 → failCount=1)
    // 首次重试仍按 base=1s(init 排程早于失败计数生效)
    await vi.advanceTimersByTimeAsync(1000)
    expect(fetcher).toHaveBeenCalledTimes(2) // t=1000 重试再失败 → failCount=2 → 下次 4s 后
    await vi.advanceTimersByTimeAsync(3000)
    expect(fetcher).toHaveBeenCalledTimes(2) // t=4000 仍在退避窗口内, 无新请求
    await vi.advanceTimersByTimeAsync(1500)
    expect(fetcher).toHaveBeenCalledTimes(3) // t=5500 越过退避点(t=5000)重试
  })

  it('默认(无 backoff)失败也保持固定节奏(向后兼容 JobCard 连败计数)', async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error('x'))
    usePolling(fetcher, { intervalMs: 1000 })
    await flush()
    expect(fetcher).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(3000) // 固定 1s: t=1000/2000/3000 各一次
    expect(fetcher).toHaveBeenCalledTimes(4)
  })
})

describe('nextInterval(退避纯函数)', () => {
  it('failCount=0 返回 base', () => {
    expect(nextInterval(1000, 0)).toBe(1000)
    expect(nextInterval(5000, 0)).toBe(5000)
  })
  it('每失败一次 ×2', () => {
    expect(nextInterval(1000, 1)).toBe(2000)
    expect(nextInterval(1000, 2)).toBe(4000)
    expect(nextInterval(1000, 3)).toBe(8000)
  })
  it('封顶 60s', () => {
    expect(nextInterval(1000, 6)).toBe(60_000) // 64000 → 封顶
    expect(nextInterval(5000, 10)).toBe(60_000)
    expect(nextInterval(30_000, 1)).toBe(60_000)
  })
  it('base 超封顶时以 base 为准(不缩短)', () => {
    expect(nextInterval(90_000, 0)).toBe(90_000)
  })
  it('负 failCount 兜底为 base', () => {
    expect(nextInterval(1000, -1)).toBe(1000)
  })
})

describe('computeStale(陈旧纯函数)', () => {
  it('从未成功(null)不算陈旧', () => {
    expect(computeStale(999_999, null, 1000)).toBe(false)
  })
  it('未超 2×interval 不陈旧', () => {
    expect(computeStale(2000, 1000, 1000)).toBe(false) // 差 1000 ≤ 2000
    expect(computeStale(3000, 1000, 1000)).toBe(false) // 差 2000 = 2×interval, 非严格大于
  })
  it('超过 2×interval 即陈旧', () => {
    expect(computeStale(3001, 1000, 1000)).toBe(true)
    expect(computeStale(11_000, 0, 5000)).toBe(true)
  })
})
