import { describe, expect, it } from 'vitest'

import { applyLastRun, toggleGroup } from '../factor-selection'

const s = (...ids: string[]) => new Set(ids)

describe('toggleGroup 整组切换', () => {
  it('组内可用项已全选 → 整组清空, 组外勾选不动', () => {
    expect(toggleGroup(s('F01', 'F03'), ['F01', 'F02'], s('F02'))).toEqual(s('F03'))
  })

  it('部分勾选 → 补全该组', () => {
    expect(toggleGroup(s('F01'), ['F01', 'F02', 'F03'], s())).toEqual(s('F01', 'F02', 'F03'))
  })

  it('全未勾 → 全选, 禁用项跳过', () => {
    expect(toggleGroup(s(), ['F01', 'F02', 'F03'], s('F02'))).toEqual(s('F01', 'F03'))
  })

  it('全禁用组 → 原样返回(无可全选也无可清空)', () => {
    expect(toggleGroup(s('X'), ['F02'], s('F02'))).toEqual(s('X'))
  })

  it('空组 → 原样返回', () => {
    expect(toggleGroup(s('X'), [], s())).toEqual(s('X'))
  })

  it('清空时连组内异常残留的禁用 id 一起移除, 不误伤组外', () => {
    expect(toggleGroup(s('F01', 'F02', 'Z'), ['F01', 'F02'], s('F02'))).toEqual(s('Z'))
  })

  it('不就地修改输入集合', () => {
    const cur = s('F01')
    toggleGroup(cur, ['F01', 'F03'], s())
    expect(cur).toEqual(s('F01'))
  })
})

describe('applyLastRun 上轮同款', () => {
  it('整体替换: 现有勾选被上轮集合覆盖', () => {
    expect(applyLastRun(s('F09'), ['F01', 'F03'], s('F01', 'F03', 'F09'), s())).toEqual({
      next: s('F01', 'F03'),
      skipped: 0,
      applied: 2,
    })
  })

  it('上轮含未知(已下架)因子 → 跳过并计数', () => {
    expect(applyLastRun(s(), ['F01', 'F99'], s('F01'), s())).toEqual({
      next: s('F01'),
      skipped: 1,
      applied: 1,
    })
  })

  it('上轮含禁用因子 → 跳过并计数', () => {
    expect(applyLastRun(s(), ['F01', 'F02'], s('F01', 'F02'), s('F02'))).toEqual({
      next: s('F01'),
      skipped: 1,
      applied: 1,
    })
  })

  it('上轮因子全部不可用 → 保持现有勾选不动(applied=0)', () => {
    expect(applyLastRun(s('F05'), ['F98', 'F99'], s('F05'), s())).toEqual({
      next: s('F05'),
      skipped: 2,
      applied: 0,
    })
  })

  it('重复 id 去重后再计数', () => {
    expect(applyLastRun(s(), ['F01', 'F01', 'F99', 'F99'], s('F01'), s())).toEqual({
      next: s('F01'),
      skipped: 1,
      applied: 1,
    })
  })

  it('不就地修改输入集合', () => {
    const cur = s('F05')
    applyLastRun(cur, ['F01'], s('F01'), s())
    expect(cur).toEqual(s('F05'))
  })
})
