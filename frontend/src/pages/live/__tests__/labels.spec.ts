import { describe, expect, it } from 'vitest'

import { auditActionLabel, directionLabel, enabledLabel, execStatusLabel } from '../labels'

describe('auditActionLabel', () => {
  it('七个审计动作对齐 auto_trade_app.py 的 action 码', () => {
    expect(auditActionLabel('cycle_start')).toBe('循环开始')
    expect(auditActionLabel('cycle_end')).toBe('循环结束')
    expect(auditActionLabel('place_order')).toBe('下单')
    expect(auditActionLabel('place_order_failed')).toBe('下单失败')
    expect(auditActionLabel('reject_order')).toBe('拒单')
    expect(auditActionLabel('execute_failed')).toBe('执行失败')
    expect(auditActionLabel('cancel_order')).toBe('撤单')
  })

  it('未知动作回退原码(后端新增动作前端不崩)', () => {
    expect(auditActionLabel('modify_strategy')).toBe('modify_strategy')
    expect(auditActionLabel('')).toBe('')
  })
})

describe('execStatusLabel', () => {
  it('执行状态映射对齐 STATUS_BADGE 键', () => {
    expect(execStatusLabel('FILLED')).toBe('已成交')
    expect(execStatusLabel('DRY_RUN')).toBe('纸面')
    expect(execStatusLabel('SUBMITTED')).toBe('已提交')
    expect(execStatusLabel('PARTIAL')).toBe('部分成交')
    expect(execStatusLabel('ALIVE')).toBe('挂单中')
    expect(execStatusLabel('TIMEOUT_CANCELED')).toBe('超时已撤')
    expect(execStatusLabel('TIMEOUT_UNCANCELED')).toBe('超时未撤')
    expect(execStatusLabel('CANCELED')).toBe('已撤单')
    expect(execStatusLabel('REJECTED')).toBe('已拒单')
    expect(execStatusLabel('FAILED')).toBe('失败')
  })

  it('未知状态回退原值', () => {
    expect(execStatusLabel('WHATEVER')).toBe('WHATEVER')
  })
})

describe('directionLabel', () => {
  it('BUY/SELL → 买/卖', () => {
    expect(directionLabel('BUY')).toBe('买')
    expect(directionLabel('SELL')).toBe('卖')
  })

  it('未知方向回退原值', () => {
    expect(directionLabel('HOLD')).toBe('HOLD')
  })
})

describe('enabledLabel', () => {
  it('true → 已启用; false/缺省 → 已停用', () => {
    expect(enabledLabel(true)).toBe('已启用')
    expect(enabledLabel(false)).toBe('已停用')
    expect(enabledLabel(null)).toBe('已停用')
    expect(enabledLabel(undefined)).toBe('已停用')
  })
})
