import { describe, expect, it } from 'vitest'

import { resolveReloadSelection } from '../reload-selection'

const runs = (...ids: string[]) => ids.map((run_id) => ({ run_id }))

describe('判决轮重载选中决策', () => {
  it('首次加载(无原选中) → 选最新(0), 无提示', () => {
    expect(resolveReloadSelection(null, [], runs('C', 'B', 'A'))).toEqual({
      selectedIdx: 0,
      newRunId: null,
    })
  })

  it('新列表为空 → 回落 0, 无提示', () => {
    expect(resolveReloadSelection('B', ['B'], [])).toEqual({ selectedIdx: 0, newRunId: null })
  })

  it('原选中轮仍在且位置不变 → 保留其下标, 无提示', () => {
    expect(resolveReloadSelection('B', ['A', 'B', 'C'], runs('A', 'B', 'C'))).toEqual({
      selectedIdx: 1,
      newRunId: null,
    })
  })

  it('新轮插到最前把原选中轮挤下 → 保留原选中(下移), 提示新轮 run_id', () => {
    expect(resolveReloadSelection('B', ['B', 'C'], runs('NEW', 'B', 'C'))).toEqual({
      selectedIdx: 1,
      newRunId: 'NEW',
    })
  })

  it('原选中轮被删 → 回落最新(0), 无提示', () => {
    expect(resolveReloadSelection('B', ['A', 'B', 'C'], runs('A', 'C'))).toEqual({
      selectedIdx: 0,
      newRunId: null,
    })
  })

  it('原选中就是最新且仍是最新(无新轮) → 保留 0, 无提示', () => {
    expect(resolveReloadSelection('A', ['A', 'B'], runs('A', 'B'))).toEqual({
      selectedIdx: 0,
      newRunId: null,
    })
  })

  it('停在非最新但最新轮本就在旧列表(非新轮) → 保留, 不弹提示', () => {
    // 例如仅删了别的轮, 最新轮 A 一直都在
    expect(resolveReloadSelection('C', ['A', 'B', 'C', 'D'], runs('A', 'C', 'D'))).toEqual({
      selectedIdx: 1,
      newRunId: null,
    })
  })
})
