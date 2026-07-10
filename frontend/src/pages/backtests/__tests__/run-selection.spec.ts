import { describe, expect, it } from 'vitest'

import {
  overlayFromQuery,
  resolveSelection,
  selectionFromQuery,
  shouldSyncOverlayToUrl,
  shouldSyncRunToUrl,
} from '../run-selection'

/* 回测轮选中 ↔ URL ?run= / 叠加 ↔ ?overlay= 深链纯决策(设计 §12 P7 + 批三收尾) —
 * 双向 watch 靠幂等互相刹车, 杜绝 状态→写URL→读URL→改状态 死循环。纯函数各自可单测。 */

const runs = (...ids: string[]) => ids.map((run_id) => ({ run_id }))

describe('resolveSelection(载入/重载后该选哪一轮)', () => {
  it('原选中仍在 → 保留(删他轮/完成刷新不弹走当前详情), URL 不参与', () => {
    // 即便 URL 指向别轮, 只要当前选中仍有效就保留 —— 后台重载不该跳走用户正看的详情
    expect(resolveSelection(runs('A', 'B', 'C'), 'A', 'B')).toBe('B')
  })

  it('无原选中(首次载入)且 URL ?run= 命中列表 → 恢复该轮(深链/刷新/收藏)', () => {
    expect(resolveSelection(runs('A', 'B', 'C'), 'B', null)).toBe('B')
  })

  it('原选中已失效(被删) + URL 命中 → 用 URL 轮', () => {
    expect(resolveSelection(runs('A', 'B'), 'A', 'GONE')).toBe('A')
  })

  it('无原选中且无 URL → 落最新一条(倒序首条)', () => {
    expect(resolveSelection(runs('NEW', 'B', 'A'), null, null)).toBe('NEW')
  })

  it('URL ?run= 指向不存在的轮 → 忽略, 落最新', () => {
    expect(resolveSelection(runs('A', 'B'), 'ZZZ', null)).toBe('A')
  })

  it('原选中失效且 URL 也不命中 → 落最新', () => {
    expect(resolveSelection(runs('A', 'B'), 'ZZZ', 'GONE')).toBe('A')
  })

  it('空列表 → null(空态)', () => {
    expect(resolveSelection([], 'A', 'B')).toBeNull()
  })

  it('原选中优先级高于 URL: 两者都有效但不同 → 保留原选中', () => {
    expect(resolveSelection(runs('A', 'B'), 'A', 'B')).toBe('B')
  })
})

describe('selectionFromQuery(前进/后退时 ?run= 变化该切到哪轮)', () => {
  it('URL 轮有效且非当前选中 → 返回该轮(响应浏览器前进/后退)', () => {
    expect(selectionFromQuery('B', runs('A', 'B', 'C'), 'A')).toBe('B')
  })

  it('URL 轮 === 当前选中 → null(幂等, 挡住 写URL 触发的回读死循环)', () => {
    expect(selectionFromQuery('A', runs('A', 'B'), 'A')).toBeNull()
  })

  it('URL 轮不在列表 → null(不切到无效轮)', () => {
    expect(selectionFromQuery('ZZZ', runs('A', 'B'), 'A')).toBeNull()
  })

  it('?run= 缺省(undefined) → null', () => {
    expect(selectionFromQuery(undefined, runs('A', 'B'), 'A')).toBeNull()
  })

  it('?run= 为数组(重复 query 参数) → null(只认单值字符串)', () => {
    expect(selectionFromQuery(['A', 'B'], runs('A', 'B'), null)).toBeNull()
  })

  it('?run= 为 null(query 有键无值) → null', () => {
    expect(selectionFromQuery(null, runs('A', 'B'), 'A')).toBeNull()
  })
})

describe('shouldSyncRunToUrl(选中 → 是否要 replace 写回 URL)', () => {
  it('URL 与选中不同 → 需写回(true)', () => {
    expect(shouldSyncRunToUrl('A', 'B')).toBe(true)
  })

  it('URL 已是该选中值 → 不写(false, 幂等挡住 读URL 触发的回写死循环)', () => {
    expect(shouldSyncRunToUrl('B', 'B')).toBe(false)
  })

  it('URL 无 run 但已有选中 → 需写回(true)', () => {
    expect(shouldSyncRunToUrl(null, 'A')).toBe(true)
  })

  it('URL 有 run 但选中已清空(null) → 需清除(true)', () => {
    expect(shouldSyncRunToUrl('A', null)).toBe(true)
  })

  it('两者皆空 → 不写(false)', () => {
    expect(shouldSyncRunToUrl(null, null)).toBe(false)
  })
})

describe('overlayFromQuery(URL ?overlay= → 叠加选择, 区分两种 null 语义)', () => {
  // —— 「缺席=清空」: URL 没有(或给不出)单值 overlay → 叠加应清空 ——
  it('?overlay= 缺省(undefined) → null(清空叠加)', () => {
    expect(overlayFromQuery(undefined, runs('A', 'B'), 'A')).toBeNull()
  })

  it('有键无值(vue-router 给 null) → null(清空)', () => {
    expect(overlayFromQuery(null, runs('A', 'B'), 'A')).toBeNull()
  })

  it('空串值(?overlay=) → null(清空)', () => {
    expect(overlayFromQuery('', runs('A', 'B'), 'A')).toBeNull()
  })

  it('重复参数成数组 → null(只认单值字符串)', () => {
    expect(overlayFromQuery(['B', 'C'], runs('A', 'B', 'C'), 'A')).toBeNull()
  })

  // —— 「非法=忽略」: 键在但值没法用 → 状态置空; URL 原值去留由写方向静默容错决定 ——
  it('run_id 不在列表(手输错/已删轮) → null(忽略, 不采用)', () => {
    expect(overlayFromQuery('GONE', runs('A', 'B'), 'A')).toBeNull()
  })

  it('run_id 等于当前选中轮(自己叠自己) → null(忽略)', () => {
    expect(overlayFromQuery('A', runs('A', 'B'), 'A')).toBeNull()
  })

  it('空列表(runs 未载/全删) → null', () => {
    expect(overlayFromQuery('B', [], 'A')).toBeNull()
  })

  // —— 合法 → 采用 ——
  it('在列表且非当前选中 → 采用该轮(深链恢复/前进后退)', () => {
    expect(overlayFromQuery('B', runs('A', 'B', 'C'), 'A')).toBe('B')
  })

  it('当前选中为 null(空态)时列表命中即合法', () => {
    expect(overlayFromQuery('B', runs('A', 'B'), null)).toBe('B')
  })
})

describe('shouldSyncOverlayToUrl(叠加选择 → 是否写回 ?overlay=)', () => {
  it('URL 已是该值 → false(幂等刹车, 挡 读URL→回写 回环)', () => {
    expect(shouldSyncOverlayToUrl('B', 'B', runs('A', 'B'), 'A')).toBe(false)
  })

  it('两边皆空 → false', () => {
    expect(shouldSyncOverlayToUrl(null, null, runs('A', 'B'), 'A')).toBe(false)
  })

  it('选了叠加而 URL 无 → true(写入)', () => {
    expect(shouldSyncOverlayToUrl(null, 'B', runs('A', 'B'), 'A')).toBe(true)
  })

  it('换选另一轮 → true(更新)', () => {
    expect(shouldSyncOverlayToUrl('B', 'C', runs('A', 'B', 'C'), 'A')).toBe(true)
  })

  it('用户清空合法叠加(URL 值在列表且非选中) → true(摘键)', () => {
    expect(shouldSyncOverlayToUrl('B', null, runs('A', 'B'), 'A')).toBe(true)
  })

  it('置空因 URL 值不在列表 → false(静默容错: 手输错值留在地址栏, 不回写抹掉)', () => {
    expect(shouldSyncOverlayToUrl('GONE', null, runs('A', 'B'), 'A')).toBe(false)
  })

  it('置空因 URL 值等于当前选中轮 → false(静默容错, 同上)', () => {
    expect(shouldSyncOverlayToUrl('A', null, runs('A', 'B'), 'A')).toBe(false)
  })

  it('写方向不审查选择值: 用户在下拉选了当前选中轮也照写(展示由图表层拦)', () => {
    expect(shouldSyncOverlayToUrl(null, 'A', runs('A', 'B'), 'A')).toBe(true)
  })
})
