import { flushPromises, mount } from '@vue/test-utils'
import { NPopconfirm } from 'naive-ui'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import type { Job, JobStatus } from '@/api/types'
import { useJobsStore } from '@/stores/jobs'

import Jobs from '../Jobs.vue'

function mkJob(id: string, status: JobStatus, extra: Partial<Job> = {}): Job {
  return {
    job_id: id,
    job_type: 'backtest',
    params: {},
    status,
    created_at: '2026-07-04T09:30:00',
    started_at: null,
    finished_at: null,
    return_code: null,
    log_path: 'x.log',
    ...extra,
  }
}

let pinia: Pinia
let listJobs: Job[]
let detailQueues: Record<string, Job[]>
let detailFail: boolean
let fetchMock: ReturnType<typeof vi.fn>
let wrapper: { unmount(): void } | null = null

function jsonResp(body: unknown) {
  return Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(''),
  })
}

/* 按 id 出队明细响应: 队列耗尽后重复最后一帧; 无脚本时默认已完成(供 JobCard done 闭环) */
function detailResp(id: string): Job {
  const q = detailQueues[id]
  if (q && q.length > 0) return q.length > 1 ? q.shift()! : q[0]
  return mkJob(id, 'succeeded', {
    started_at: '2026-07-04T09:59:00',
    finished_at: '2026-07-04T09:59:30',
    log_tail: [],
  })
}

function urls(re: RegExp): string[] {
  return fetchMock.mock.calls.map((c) => String(c[0])).filter((u) => re.test(u))
}

function bodyOf(url: string): unknown {
  const call = fetchMock.mock.calls.find((c) => String(c[0]) === url)
  if (!call) return null
  return JSON.parse((call[1] as { body: string }).body)
}

/* stub 组件(NDatePicker/NInput = true)按 data-testid 定位后发 v-model 更新事件 —
 * findComponent(string) 的类型是 WrapperLike(无 vm), 运行时实为组件包装器, 此处收窄 */
function emitStub(w: ReturnType<typeof mountJobs>, testid: string, event: string, value: unknown): void {
  const stub = w.findComponent(`[data-testid="${testid}"]`) as unknown as {
    vm: { $emit(e: string, v: unknown): void }
  }
  stub.vm.$emit(event, value)
}

function mountJobs() {
  const w = mount(Jobs, {
    global: {
      plugins: [pinia],
      stubs: {
        NDatePicker: true,
        NInput: true,
        NInputNumber: true,
        // props 透传 disabled 以断言提交 pending(:loading/:disabled)
        NButton: { props: ['loading', 'disabled'], template: '<button :disabled="disabled"><slot /></button>' },
        GlossaryTip: { template: '<span><slot /></span>' },
        // 取消二次确认(设计 §9): 同 Verdicts.spec 惯例 —— naive `.name` 运行时无 N 前缀,
        // 用 [Component.name] 收窄; 只保留 trigger 插槽 + 一个直发 positive-click 的确认钮。
        // 真 NPopconfirm 的确认钮在 teleport 弹层里(不在行内), stub 内联渲染故需 .stop
        // 阻止冒泡到 <tr> 的行 click(openLog), 复现真实"确认取消不触发日志钻取"。
        [NPopconfirm.name as string]: {
          emits: ['positive-click'],
          template:
            '<span class="stub-popconfirm"><slot name="trigger" /><button type="button" data-testid="job-cancel-confirm" @click.stop="$emit(\'positive-click\')">confirm</button></span>',
        },
      },
    },
  })
  wrapper = w
  return w
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-07-04T10:00:00'))
  pinia = createPinia()
  setActivePinia(pinia)
  listJobs = [
    mkJob('j1', 'running', {
      started_at: '2026-07-04T09:59:15',
      params: { strategies: ['micro_value'], start_date: '2024-01-01', end_date: '2024-06-30' },
    }),
    mkJob('j2', 'queued', { job_type: 'factor_test', params: { factors: 'P0' } }),
    mkJob('j3', 'succeeded', {
      started_at: '2026-07-04T09:00:00',
      finished_at: '2026-07-04T09:01:00',
    }),
  ]
  detailQueues = {}
  detailFail = false
  fetchMock = vi.fn().mockImplementation((input: unknown, init?: { method?: string }) => {
    const url = String(input)
    if (url.startsWith('/api/jobs?limit=')) {
      return jsonResp({ jobs: listJobs, active: true })
    }
    if (/\/api\/jobs\/[^/?]+\/cancel$/.test(url)) {
      return jsonResp({})
    }
    if (url === '/api/jobs/ml-train' || url === '/api/jobs/ml-evaluate') {
      expect(init?.method).toBe('POST')
      return jsonResp(mkJob('mlj1', 'queued'))
    }
    const detail = /\/api\/jobs\/([^/?]+)\?tail=\d+$/.exec(url)
    if (detail) {
      if (detailFail) return Promise.reject(new Error('net down'))
      return jsonResp(detailResp(detail[1]))
    }
    return Promise.reject(new Error(`unexpected url: ${url}`))
  })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('Jobs 任务列表', () => {
  it('渲染中文状态/参数摘要/创建切片/耗时, 活跃数写回 store', async () => {
    const w = mountJobs()
    await flushPromises()

    const rows = w.findAll('[data-testid="job-row"]')
    expect(rows).toHaveLength(3)
    expect(w.text()).toContain('运行中')
    expect(w.text()).toContain('排队中')
    expect(w.text()).toContain('已完成')
    expect(w.text()).toContain('micro_value · 2024-01-01~2024-06-30')
    expect(w.text()).toContain('07-04T09:30:00') // created_at.slice(5,19)
    expect(w.text()).toContain('45s') // running: now-started
    expect(w.text()).toContain('60s') // finished-started
    // 仅 queued|running 行有取消钮
    expect(w.findAll('[data-testid="job-row-cancel"]')).toHaveLength(2)
    // queued+running 计数写回 store(顶栏徽章/503 文案依赖)
    expect(useJobsStore().activeCount).toBe(2)
  })

  it('首载未返回显加载中占位, 返回后消失且不误显空态', async () => {
    const w = mountJobs()

    // fetch 尚未 resolve — listData 为 null
    expect(w.find('[data-testid="jobs-loading"]').exists()).toBe(true)
    expect(w.find('[data-testid="jobs-empty"]').exists()).toBe(false)

    await flushPromises()
    expect(w.find('[data-testid="jobs-loading"]').exists()).toBe(false)
  })

  it('空列表显空态并清零活跃数, 日志占位联动引导文案', async () => {
    listJobs = []
    const w = mountJobs()
    await flushPromises()

    expect(w.find('[data-testid="jobs-loading"]').exists()).toBe(false)
    expect(w.find('[data-testid="jobs-empty"]').exists()).toBe(true)
    expect(w.text()).toContain('暂无任务')
    expect(useJobsStore().activeCount).toBe(0)
    // 零任务时终端框不藏但文案引导(布局稳定)
    expect(w.find('[data-testid="job-log"]').text()).toBe('暂无任务，提交后此处显示实时日志')
  })

  it('取消: 二次确认后 POST cancel 并刷新列表, 不触发日志钻取', async () => {
    const w = mountJobs()
    await flushPromises()
    const listCalls = urls(/\/api\/jobs\?limit=100$/).length

    // NPopconfirm 确认钮(stub)对应首个 queued|running 行 = j1(running)
    await w.findAll('[data-testid="job-cancel-confirm"]')[0].trigger('click')
    await flushPromises()

    const cancelCall = fetchMock.mock.calls.find((c) => String(c[0]).endsWith('/j1/cancel'))
    expect(cancelCall).toBeTruthy()
    expect((cancelCall?.[1] as { method?: string }).method).toBe('POST')
    expect(urls(/\/api\/jobs\?limit=100$/).length).toBe(listCalls + 1) // finally 刷新列表
    expect(urls(/\?tail=300$/)).toHaveLength(0) // 未触发日志钻取
  })

  it('ID 单元格真 button 承载钻取, aria-expanded 随选中态', async () => {
    const w = mountJobs()
    await flushPromises()

    const drills = w.findAll('[data-testid="job-row-drill"]')
    expect(drills).toHaveLength(3)
    // 未选中时全部 aria-expanded=false
    expect(drills[0].attributes('aria-expanded')).toBe('false')

    // 键盘可达路径: 按钮点击即钻取(不依赖行鼠标 click)
    await drills[0].trigger('click')
    await flushPromises()
    expect(w.findAll('[data-testid="job-row-drill"]')[0].attributes('aria-expanded')).toBe('true')
    expect(urls(/\?tail=300$/).length).toBeGreaterThan(0)
  })

  it('取消乐观: 确认后行内立即显「取消中…」并撤下确认入口(cancel 悬挂期间)', async () => {
    // 覆盖 cancel 分支为悬挂 Promise, 以观察乐观中间态; 其余 URL 复用 beforeEach 实现
    const base = fetchMock.getMockImplementation()! as (i: unknown, init?: { method?: string }) => unknown
    fetchMock.mockImplementation((input: unknown, init?: { method?: string }) => {
      const url = String(input)
      if (/\/api\/jobs\/[^/?]+\/cancel$/.test(url)) return new Promise(() => {}) // 永不 resolve
      return base(input, init)
    })
    const w = mountJobs()
    await flushPromises()
    expect(w.find('[data-testid="job-row-canceling"]').exists()).toBe(false)

    await w.findAll('[data-testid="job-cancel-confirm"]')[0].trigger('click')
    await flushPromises()

    // j1 行乐观置「取消中…」, 该行确认入口(popconfirm)撤下 → 全表 confirm 从 2 减到 1
    expect(w.find('[data-testid="job-row-canceling"]').exists()).toBe(true)
    expect(w.findAll('[data-testid="job-cancel-confirm"]')).toHaveLength(1)
  })
})

describe('Jobs 日志钻取', () => {
  it('行点击 → tail=300 2s 轮询, 标题 jobId·状态, 终态停', async () => {
    detailQueues.j1 = [
      mkJob('j1', 'running', { started_at: '2026-07-04T09:59:15', log_tail: ['l1', 'l2'] }),
      mkJob('j1', 'succeeded', {
        started_at: '2026-07-04T09:59:15',
        finished_at: '2026-07-04T10:00:30',
        log_tail: ['l1', 'l2', 'done'],
      }),
    ]
    const w = mountJobs()
    await flushPromises()

    await w.findAll('[data-testid="job-row"]')[0].trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="job-log-title"]').text()).toBe('j1 · 运行中')
    expect(w.find('[data-testid="job-log"]').text()).toBe('l1\nl2')

    await vi.advanceTimersByTimeAsync(2000)
    await flushPromises()
    expect(w.find('[data-testid="job-log-title"]').text()).toBe('j1 · 已完成')
    expect(w.find('[data-testid="job-log"]').text()).toBe('l1\nl2\ndone')

    const n = urls(/\?tail=300$/).length
    await vi.advanceTimersByTimeAsync(6000)
    expect(urls(/\?tail=300$/).length).toBe(n) // 终态已停轮询
  })

  it('日志空输出显（无输出）', async () => {
    detailQueues.j3 = [
      mkJob('j3', 'succeeded', {
        started_at: '2026-07-04T09:00:00',
        finished_at: '2026-07-04T09:01:00',
        log_tail: [],
      }),
    ]
    const w = mountJobs()
    await flushPromises()

    await w.findAll('[data-testid="job-row"]')[2].trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="job-log"]').text()).toBe('（无输出）')
  })

  it('连续 5 次查询失败停轮询并显服务重启文案', async () => {
    detailFail = true
    const w = mountJobs()
    await flushPromises()

    await w.findAll('[data-testid="job-row"]')[0].trigger('click')
    await flushPromises() // 失败 1
    await vi.advanceTimersByTimeAsync(8000) // 失败 2..5
    await flushPromises()

    expect(w.find('[data-testid="job-log"]').text()).toBe('任务查询失败（服务可能已重启）')
    const n = urls(/\?tail=300$/).length
    expect(n).toBe(5)
    await vi.advanceTimersByTimeAsync(6000)
    expect(urls(/\?tail=300$/).length).toBe(n) // 已停
  })
})

describe('Jobs ML 表单', () => {
  it('训练提交默认载荷, JobCard 挂 ml-job-area, done 后刷列表', async () => {
    const w = mountJobs()
    await flushPromises()

    await w.find('[data-testid="ml-train-submit"]').trigger('click')
    await flushPromises()
    await flushPromises()

    expect(bodyOf('/api/jobs/ml-train')).toEqual({
      start_date: '2021-01-01',
      end_date: '2024-12-31',
      symbols: '000300.SH',
      model_name: 'lgbm_return_5d',
      n_trials: 50,
    })
    const area = w.find('[data-testid="ml-job-area"]')
    expect(area.find('[data-testid="job-card"]').exists()).toBe(true)

    // 默认明细响应=已完成 → JobCard 首 tick 即 done → 列表刷新
    await flushPromises()
    await flushPromises()
    expect(urls(/\/api\/jobs\?limit=100$/).length).toBe(2)
  })

  it('评估提交默认载荷(共用模型名输入), 评估行常驻显示所评模型', async () => {
    const w = mountJobs()
    await flushPromises()

    // 评估静默依赖首行「模型名」— 提示元素把依赖显式化
    expect(w.find('[data-testid="ml-eval-model"]').text()).toBe('评估模型：lgbm_return_5d')

    await w.find('[data-testid="ml-eval-submit"]').trigger('click')
    await flushPromises()

    expect(bodyOf('/api/jobs/ml-evaluate')).toEqual({
      model_name: 'lgbm_return_5d',
      eval_start: '2025-01-01',
      eval_end: '2025-12-31',
    })
  })

  /* R7(R6 遗留): 日期有默认但 clearable, 清空提交撞后端 pattern 422 —
   * 前端必填校验前置(纯函数矩阵在 jobs/__tests__/ml-forms.spec, 此处验组件接线) */
  it('训练起始日期清空 → 拦截: 零 ml-train 请求 + 横幅提示训练起止必填', async () => {
    const w = mountJobs()
    await flushPromises()

    // NDatePicker clearable 清空 = v-model:formatted-value 收到 null
    emitStub(w, 'ml-start', 'update:formattedValue', null)
    await nextTick()
    await w.find('[data-testid="ml-train-submit"]').trigger('click')
    await flushPromises()

    expect(urls(/\/api\/jobs\/ml-train$/)).toHaveLength(0)
    expect(w.find('[data-testid="error-banner"]').text()).toContain('训练起止日期均必填')
  })

  it('评估结束日期清空 → 拦截: 零 ml-evaluate 请求 + 横幅提示评估起止必填', async () => {
    const w = mountJobs()
    await flushPromises()

    emitStub(w, 'mle-end', 'update:formattedValue', null)
    await nextTick()
    await w.find('[data-testid="ml-eval-submit"]').trigger('click')
    await flushPromises()

    expect(urls(/\/api\/jobs\/ml-evaluate$/)).toHaveLength(0)
    expect(w.find('[data-testid="error-banner"]').text()).toContain('评估起止日期均必填')
  })

  it('模型名清空 → 训练/评估均拦截(后端 pattern 字段, 空串必 422)', async () => {
    const w = mountJobs()
    await flushPromises()

    emitStub(w, 'ml-model', 'update:value', '')
    await nextTick()

    await w.find('[data-testid="ml-train-submit"]').trigger('click')
    await flushPromises()
    expect(urls(/\/api\/jobs\/ml-train$/)).toHaveLength(0)
    expect(w.find('[data-testid="error-banner"]').text()).toContain('模型名必填')

    await w.find('[data-testid="ml-eval-submit"]').trigger('click')
    await flushPromises()
    expect(urls(/\/api\/jobs\/ml-evaluate$/)).toHaveLength(0)
    expect(w.find('[data-testid="error-banner"]').text()).toContain('模型名必填')
  })

  it('训练提交 pending: 提交期间按钮禁用防双击, 完成后复位', async () => {
    // 训练 POST 悬挂以观察 pending 中间态; 其余 URL 复用 beforeEach 实现
    const base = fetchMock.getMockImplementation()! as (i: unknown, init?: { method?: string }) => unknown
    let release: () => void = () => {}
    fetchMock.mockImplementation((input: unknown, init?: { method?: string }) => {
      const url = String(input)
      if (url === '/api/jobs/ml-train') {
        return new Promise((res) => {
          release = () =>
            res({ ok: true, status: 200, json: () => Promise.resolve(mkJob('mlj1', 'queued')), text: () => Promise.resolve('') })
        })
      }
      return base(input, init)
    })
    const w = mountJobs()
    await flushPromises()

    const btn = w.find('[data-testid="ml-train-submit"]')
    expect((btn.element as HTMLButtonElement).disabled).toBe(false)

    await btn.trigger('click')
    await flushPromises()
    expect((btn.element as HTMLButtonElement).disabled).toBe(true) // pending: 禁钮排重

    release()
    await flushPromises()
    expect((w.find('[data-testid="ml-train-submit"]').element as HTMLButtonElement).disabled).toBe(false)
  })
})

describe('Jobs 聚合横幅(R7: dismissible/technical)', () => {
  it('首载失败: 横幅带 technical(title), ✕ 关闭后屏蔽跨失败 tick 保持, 成功 tick 复位', async () => {
    let listFail = true
    const base = fetchMock.getMockImplementation()! as (i: unknown, init?: { method?: string }) => unknown
    fetchMock.mockImplementation((input: unknown, init?: { method?: string }) => {
      const url = String(input)
      if (url.startsWith('/api/jobs?limit=')) {
        if (listFail) return Promise.reject(new Error('conn refused'))
        return jsonResp({ jobs: listJobs, active: true })
      }
      return base(input, init)
    })
    const w = mountJobs()
    await flushPromises()

    const banner = w.find('[data-testid="error-banner"]')
    expect(banner.exists()).toBe(true)
    expect(banner.text()).toContain('无法连接')
    expect(banner.attributes('title')).toContain('conn refused') // 技术串不进正文, title 悬停

    await banner.find('button[aria-label="关闭"]').trigger('click')
    expect(w.find('[data-testid="error-banner"]').exists()).toBe(false)

    // 首载成功前每个失败 tick 都换新 listError 对象 — 屏蔽须跨 tick 保持, 否则 5s 后横幅还魂
    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()
    expect(w.find('[data-testid="error-banner"]').exists()).toBe(false)

    // 下次成功 tick 自愈: listError → null 复位屏蔽, 列表照常渲染
    listFail = false
    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()
    expect(w.find('[data-testid="error-banner"]').exists()).toBe(false)
    expect(w.findAll('[data-testid="job-row"]')).toHaveLength(3)
  })

  it('操作错误(取消 500): 正文中文 lead + technical 透传, ✕ 关闭即清', async () => {
    const base = fetchMock.getMockImplementation()! as (i: unknown, init?: { method?: string }) => unknown
    fetchMock.mockImplementation((input: unknown, init?: { method?: string }) => {
      const url = String(input)
      if (/\/api\/jobs\/[^/?]+\/cancel$/.test(url)) {
        return Promise.resolve({
          ok: false,
          status: 500,
          json: () => Promise.resolve({}),
          text: () => Promise.resolve('boom'),
        })
      }
      return base(input, init)
    })
    const w = mountJobs()
    await flushPromises()

    await w.findAll('[data-testid="job-cancel-confirm"]')[0].trigger('click')
    await flushPromises()

    const banner = w.find('[data-testid="error-banner"]')
    expect(banner.exists()).toBe(true)
    expect(banner.text()).toContain('服务内部错误')
    expect(banner.attributes('title')).toContain('500')
    expect(banner.attributes('title')).toContain('boom')

    await banner.find('button[aria-label="关闭"]').trigger('click')
    expect(w.find('[data-testid="error-banner"]').exists()).toBe(false)
  })
})

describe('Jobs 列表陈旧指示(R7: 复用 StaleIndicator)', () => {
  it('成功显「数据更新于」, 断连超 2×interval 转警示且不打横幅, 恢复自愈', async () => {
    let listFail = false
    const base = fetchMock.getMockImplementation()! as (i: unknown, init?: { method?: string }) => unknown
    fetchMock.mockImplementation((input: unknown, init?: { method?: string }) => {
      const url = String(input)
      if (url.startsWith('/api/jobs?limit=')) {
        if (listFail) return Promise.reject(new Error('net down'))
        return jsonResp({ jobs: listJobs, active: true })
      }
      return base(input, init)
    })
    const w = mountJobs()
    await flushPromises()
    expect(w.find('[data-testid="live-conn-ok"]').exists()).toBe(true)
    expect(w.find('[data-testid="live-conn-ok"]').text()).toContain('数据更新于')

    // 断连: 5s/10s/15s 三个失败 tick, 15s 时距上次成功 > 2×5000 → 陈旧警示
    listFail = true
    await vi.advanceTimersByTimeAsync(15000)
    await flushPromises()
    expect(w.find('[data-testid="live-conn-stale"]').exists()).toBe(true)
    expect(w.find('[data-testid="live-conn-stale"]').text()).toContain('连接中断')
    // 首载已成功 → 后续失败 tick 不置 listError, 不打横幅(陈旧由指示行表达)
    expect(w.find('[data-testid="error-banner"]').exists()).toBe(false)

    // 恢复: 下个成功 tick 回「数据更新于」
    listFail = false
    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()
    expect(w.find('[data-testid="live-conn-ok"]').exists()).toBe(true)
    expect(w.find('[data-testid="live-conn-stale"]').exists()).toBe(false)
  })
})
