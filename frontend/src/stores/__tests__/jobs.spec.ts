import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { activeJobCount, useJobsStore } from '@/stores/jobs'

async function flush() {
  for (let i = 0; i < 6; i++) await Promise.resolve()
}

function stubFetch(body: unknown) {
  const f = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  })
  vi.stubGlobal('fetch', f)
  return f
}

const listOf = (...statuses: string[]) => ({
  jobs: statuses.map((status, i) => ({ job_id: `j${i}`, status })),
  active: statuses.some((s) => s === 'queued' || s === 'running'),
})

describe('activeJobCount(纯函数)', () => {
  it('统计 queued + running', () => {
    expect(
      activeJobCount([
        { status: 'queued' },
        { status: 'running' },
        { status: 'succeeded' },
        { status: 'failed' },
        { status: 'canceled' },
      ]),
    ).toBe(2)
  })
  it('空列表为 0', () => {
    expect(activeJobCount([])).toBe(0)
  })
})

describe('useJobsStore 全局轮询', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })
  afterEach(() => {
    useJobsStore().stopGlobalPolling()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('startGlobalPolling 拉取 /api/jobs 并回填 activeCount', async () => {
    const f = stubFetch(listOf('queued', 'running', 'succeeded'))
    const s = useJobsStore()
    s.startGlobalPolling()
    await flush()
    expect(f).toHaveBeenCalledWith('/api/jobs?limit=100', expect.anything())
    expect(s.activeCount).toBe(2)
  })

  it('去重: 某页最近已 setActive 回填则跳过自身请求', async () => {
    const f = stubFetch(listOf('queued'))
    const s = useJobsStore()
    s.setActive(3) // 模拟任务页刚回填
    s.startGlobalPolling()
    await flush()
    expect(f).not.toHaveBeenCalled() // 命中去重窗口 → 不重复请求
    expect(s.activeCount).toBe(3) // 保留页面回填的计数
  })

  it('幂等: 重复 startGlobalPolling 只建一个轮询', async () => {
    const f = stubFetch(listOf('running'))
    const s = useJobsStore()
    s.startGlobalPolling()
    s.startGlobalPolling()
    await flush()
    expect(f).toHaveBeenCalledTimes(1) // 第二次 start 被幂等吞掉
  })

  it('setActive 直接置数(fetch 层 503 文案消费之)', () => {
    const s = useJobsStore()
    s.setActive(5)
    expect(s.activeCount).toBe(5)
  })
})
