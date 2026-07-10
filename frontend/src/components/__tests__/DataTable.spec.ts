import { mount, type ComponentMountingOptions } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import DataTable, { compareRows, sortRows, type Column } from '../DataTable.vue'

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

  it('默认 clickable=false: 点击行不 emit rowClick, 无 row-clickable 类', async () => {
    const w = mount(DataTable, { props: { rows: rows(3), columns, rowKey: 'id' }, global: noStub })
    expect(w.find('tbody tr.row-clickable').exists()).toBe(false)
    await w.find('tbody tr').trigger('click')
    expect(w.emitted('rowClick')).toBeUndefined()
  })

  it('clickable=true: 点击行 emit rowClick 且带 row-clickable 类', async () => {
    const w = mount(DataTable, { props: { rows: rows(3), columns, rowKey: 'id', clickable: true }, global: noStub })
    expect(w.find('tbody tr.row-clickable').exists()).toBe(true)
    await w.find('tbody tr').trigger('click')
    expect(w.emitted('rowClick')).toHaveLength(1)
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

/* ── 列排序纯函数(sortRows/compareRows) — 与组件解耦可单测 ── */
describe('sortRows/compareRows', () => {
  const base = () => [
    { id: 'a', v: 2 },
    { id: 'b', v: 10 },
    { id: 'c', v: null },
    { id: 'd', v: 1 },
  ]

  it('数值按数值序而非字典序', () => {
    expect(sortRows(base(), 'v', 'asc').map((r) => r.id)).toEqual(['d', 'a', 'b', 'c'])
    expect(sortRows(base(), 'v', 'desc').map((r) => r.id)).toEqual(['b', 'a', 'd', 'c'])
  })

  it('null/undefined 升降序均恒排末尾', () => {
    const withUndef = [{ id: 'x' }, { id: 'y', v: 3 }]
    expect(sortRows(withUndef, 'v', 'asc').map((r) => r.id)).toEqual(['y', 'x'])
    expect(sortRows(withUndef, 'v', 'desc').map((r) => r.id)).toEqual(['y', 'x'])
    expect(sortRows(base(), 'v', 'asc').map((r) => r.id)).toContain('c')
  })

  it('非数值按 String localeCompare', () => {
    const strs = [
      { id: '1', s: 'bb' },
      { id: '2', s: 'aa' },
      { id: '3', s: 'cc' },
    ]
    expect(sortRows(strs, 's', 'asc').map((r) => r.s)).toEqual(['aa', 'bb', 'cc'])
    expect(sortRows(strs, 's', 'desc').map((r) => r.s)).toEqual(['cc', 'bb', 'aa'])
  })

  it('不变异输入数组, 相等键保持原相对顺序(稳定)', () => {
    const input = [
      { id: 'a', v: 1 },
      { id: 'b', v: 1 },
      { id: 'c', v: 0 },
      { id: 'd', v: 1 },
    ]
    const out = sortRows(input, 'v', 'asc')
    expect(input.map((r) => r.id)).toEqual(['a', 'b', 'c', 'd']) // 原数组未动
    expect(out.map((r) => r.id)).toEqual(['c', 'a', 'b', 'd']) // 相等键稳定
  })

  it('混合类型/NaN 不抛异常且返回良定义数值', () => {
    expect(() => sortRows([{ v: NaN }, { v: 1 }, { v: NaN }], 'v', 'desc')).not.toThrow()
    expect(compareRows({ v: NaN }, { v: NaN }, 'v', 'asc')).toBe(0)
    expect(compareRows({ v: 1 }, { v: 'x' }, 'v', 'asc')).toBeTypeOf('number')
  })
})

/* ── 列排序组件交互(sortable 列表头真按钮, 循环 无序→降→升→无序) ── */
describe('DataTable 列排序', () => {
  const sortColumns: Column[] = [
    { key: 'id', title: 'ID' },
    { key: 'pnl', title: '盈亏', sortable: true },
    { key: 'name', title: '名称', sortable: true },
  ]
  const pnlRows = (): Record<string, unknown>[] => [
    { id: 'a', pnl: 5, name: 'bb' },
    { id: 'b', pnl: null, name: 'dd' },
    { id: 'c', pnl: -2, name: 'aa' },
    { id: 'd', pnl: 30, name: 'cc' },
  ]
  const mountSortable = (rows = pnlRows()) =>
    mount(DataTable, { props: { rows, columns: sortColumns, rowKey: 'id' }, global: noStub })
  const idOrder = (w: ReturnType<typeof mountSortable>) =>
    w.findAll('tbody tr td:first-child').map((td) => td.text())

  it('点击表头循环 降序→升序→无序, th 挂 aria-sort, null 恒末尾', async () => {
    const w = mountSortable()
    const th = () => w.findAll('th')[1]
    const btn = w.find('[data-testid="dt-sort-pnl"]')
    expect(th().attributes('aria-sort')).toBeUndefined()

    await btn.trigger('click') // 第一击: 降序
    expect(idOrder(w)).toEqual(['d', 'a', 'c', 'b']) // null(b) 沉底
    expect(th().attributes('aria-sort')).toBe('descending')
    expect(th().text()).toContain('▾')

    await btn.trigger('click') // 第二击: 升序
    expect(idOrder(w)).toEqual(['c', 'a', 'd', 'b']) // null 仍沉底
    expect(th().attributes('aria-sort')).toBe('ascending')
    expect(th().text()).toContain('▴')

    await btn.trigger('click') // 第三击: 回无序=原始顺序
    expect(idOrder(w)).toEqual(['a', 'b', 'c', 'd'])
    expect(th().attributes('aria-sort')).toBeUndefined()
  })

  it('同一时刻仅一列有序: 切列即从降序重新开始', async () => {
    const w = mountSortable()
    await w.find('[data-testid="dt-sort-pnl"]').trigger('click')
    await w.find('[data-testid="dt-sort-name"]').trigger('click')
    const ths = w.findAll('th')
    expect(ths[1].attributes('aria-sort')).toBeUndefined() // 原排序列让位
    expect(ths[2].attributes('aria-sort')).toBe('descending') // 新列从降序起步
    expect(idOrder(w)).toEqual(['b', 'd', 'a', 'c']) // name 降序: dd,cc,bb,aa
  })

  it('排序不变异 props.rows(父级数组原顺序保持)', async () => {
    const data = pnlRows()
    const w = mount(DataTable, {
      props: { rows: data, columns: sortColumns, rowKey: 'id' },
      global: noStub,
    })
    await w.find('[data-testid="dt-sort-pnl"]').trigger('click')
    expect(data.map((r) => r.id)).toEqual(['a', 'b', 'c', 'd'])
  })

  it('排序态跨 rows 重传保持(与展开态同哲学)', async () => {
    const w = mountSortable()
    await w.find('[data-testid="dt-sort-pnl"]').trigger('click')
    await w.setProps({
      rows: [
        { id: 'x', pnl: 1, name: 'x' },
        { id: 'y', pnl: 9, name: 'y' },
      ],
    }) // 模拟轮询重传
    // 被替换的旧行按既有 leave 过渡机制延迟移出 DOM(同"收起"用例), 真实等待后断言
    await vi.waitFor(() => expect(idOrder(w)).toEqual(['y', 'x'])) // 新数据仍按降序呈现
    expect(w.findAll('th')[1].attributes('aria-sort')).toBe('descending')
  })

  it('排序发生在截断之前: 首屏即全局极值, 分页/展开钮不受影响', async () => {
    const many = Array.from({ length: 60 }, (_, i) => ({ id: String(i), pnl: i, name: `n${i}` }))
    const w = mount(DataTable, {
      props: { rows: many, columns: sortColumns, rowKey: 'id', pageSize: 50 },
      global: noStub,
    })
    await w.find('[data-testid="dt-sort-pnl"]').trigger('click')
    // 排序使可见集合换血(0-9 出 50-59 进), 出场行按既有 leave 过渡机制延迟移出
    await vi.waitFor(() => expect(w.findAll('tbody tr')).toHaveLength(50)) // 截断照旧
    expect(idOrder(w)[0]).toBe('59') // 原第 51+ 行的最大值升到首行
    expect(w.find('[data-testid="dt-expand"]').text()).toContain('显示全部 60 条')
  })

  it('非 sortable 列不渲染按钮; sortable 列是真 button; th 均保 scope="col"', () => {
    const w = mountSortable()
    const ths = w.findAll('th')
    expect(w.find('[data-testid="dt-sort-id"]').exists()).toBe(false)
    expect(ths[0].find('button').exists()).toBe(false)
    expect(ths[1].find('button[type="button"]').exists()).toBe(true) // 键盘可达
    for (const t of ths) expect(t.attributes('scope')).toBe('col')
  })
})
