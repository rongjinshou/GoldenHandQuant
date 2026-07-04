import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope } from 'vue'

import { usePolling } from '../usePolling'

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
})
