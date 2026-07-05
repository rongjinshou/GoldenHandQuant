import { mount, type ComponentMountingOptions } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import DataTable from '../DataTable.vue'

/* VTU 默认 stub TransitionGroup(不渲染 tag="tbody"), 关掉以测真实 DOM 结构 */
const noStub: ComponentMountingOptions<typeof DataTable>['global'] = {
  stubs: { 'transition-group': false },
}

function rows(n: number) {
  return Array.from({ length: n }, (_, i) => ({ id: String(i), name: `row-${i}` }))
}

const columns = [
  { key: 'id', title: 'ID' },
  { key: 'name', title: '名称' },
]

describe('DataTable', () => {
  it('不超过 pageSize 时全量渲染且无展开按钮', () => {
    const w = mount(DataTable, { props: { rows: rows(10), columns, rowKey: "id" }, global: noStub })
    expect(w.findAll('tbody tr')).toHaveLength(10)
    expect(w.find('[data-testid="dt-expand"]').exists()).toBe(false)
  })

  it('超过 pageSize 截断并显示"显示全部 N 条"', () => {
    const w = mount(DataTable, { props: { rows: rows(80), columns, rowKey: "id", pageSize: 50 }, global: noStub })
    expect(w.findAll('tbody tr')).toHaveLength(50)
    const btn = w.find('[data-testid="dt-expand"]')
    expect(btn.text()).toContain('显示全部 80 条')
  })

  it('展开后重传 rows 不回折(展开态跨轮询保持), 按钮常驻切换为"收起"', async () => {
    const w = mount(DataTable, { props: { rows: rows(80), columns, rowKey: "id", pageSize: 50 }, global: noStub })
    await w.find('[data-testid="dt-expand"]').trigger('click')
    expect(w.findAll('tbody tr')).toHaveLength(80)

    await w.setProps({ rows: rows(90) }) // 模拟轮询重传
    expect(w.findAll('tbody tr')).toHaveLength(90) // 保持展开
    // confirmed-bug 回归(2026-07-05): 按钮不能因 v-if 消失——那样表格新展开的某一行
    // 会占据按钮原屏幕位置, 有被浏览器补发幽灵点击误触发 rowClick 的风险。
    const btn = w.find('[data-testid="dt-expand"]')
    expect(btn.exists()).toBe(true)
    expect(btn.text()).toContain('收起')
  })

  it('展开后再次点击"收起"恢复截断', async () => {
    const w = mount(DataTable, { props: { rows: rows(80), columns, rowKey: "id", pageSize: 50 }, global: noStub })
    await w.find('[data-testid="dt-expand"]').trigger('click')
    expect(w.findAll('tbody tr')).toHaveLength(80)
    expect(w.find('[data-testid="dt-expand"]').text()).toContain('收起')

    await w.find('[data-testid="dt-expand"]').trigger('click')
    expect(w.find('[data-testid="dt-expand"]').text()).toContain('显示全部 80 条') // 状态即时翻转
    /* 收缩的行经 tbody tr 通用 transition 规则被 TransitionGroup 判定为需等 leave
     * 过渡结束才移出 DOM(jsdom 里靠 rAF 调度, 不会被 nextTick/trigger 冲掉), 需真实
     * 等待——这是既有的入场动画机制使然, 非本次改动引入, 故轮询等待而非动组件逻辑。 */
    await vi.waitFor(() => expect(w.findAll('tbody tr')).toHaveLength(50))
  })

  it('render 函数列生效', () => {
    const w = mount(DataTable, {
      props: {
        rows: rows(2),
        columns: [{ key: 'name', title: 'N', render: (r: Record<string, unknown>) => `[${r.name}]` }],
        rowKey: 'id',
      },
    })
    expect(w.text()).toContain('[row-0]')
  })
})
