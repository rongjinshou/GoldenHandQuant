import { describe, expect, it } from 'vitest'

import type { AccountSnapshot, LiveConfig, PositionSnapshot } from '@/api/types'

import {
  badgeCount,
  cumReturn,
  daemonBadge,
  equityAriaLabel,
  formatClockTime,
  num,
  positionRow,
  returnPct,
  sliceTime,
  statusBadge,
  ticketCells,
  wan,
} from '../logic'

function acct(total: number | null, extra: Partial<AccountSnapshot> = {}): AccountSnapshot {
  return {
    snapshot_time: '2026-07-04T09:30:00',
    mode: 'dry_run',
    total_asset: total,
    available_cash: null,
    frozen_cash: null,
    market_value: null,
    ...extra,
  }
}

function cfg(slots: string[], cyclesToday: number): LiveConfig {
  return {
    config_exists: true,
    auto_trade: {},
    today: { expected_slots: slots, cycles_today: cyclesToday },
  }
}

describe('num', () => {
  it('null/undefined → "-"', () => {
    expect(num(null)).toBe('-')
    expect(num(undefined)).toBe('-')
  })

  it('数值走千分位 toLocaleString', () => {
    expect(num(1234.5)).toBe((1234.5).toLocaleString())
    expect(num(0)).toBe((0).toLocaleString())
  })
})

describe('returnPct', () => {
  it('收益率统一 2 位小数 + 带符号', () => {
    expect(returnPct(0.1)).toBe('+10.00%')
    expect(returnPct(-0.1)).toBe('-10.00%')
    expect(returnPct(0)).toBe('+0.00%')
    expect(returnPct(0.12345)).toBe('+12.35%') // 四舍五入到 2 位
  })
})

describe('formatClockTime(R6-01 连接状态行)', () => {
  it('本地时钟 HH:mm:ss, 各段补零', () => {
    // 用本地时区构造 Date, 断言不依赖运行环境时区
    expect(formatClockTime(new Date(2026, 6, 9, 9, 5, 7).getTime())).toBe('09:05:07')
    expect(formatClockTime(new Date(2026, 6, 9, 23, 59, 59).getTime())).toBe('23:59:59')
  })

  it('午夜零点全零', () => {
    expect(formatClockTime(new Date(2026, 0, 1, 0, 0, 0).getTime())).toBe('00:00:00')
  })
})

describe('sliceTime', () => {
  it('null/undefined → 空串', () => {
    expect(sliceTime(null)).toBe('')
    expect(sliceTime(undefined)).toBe('')
  })

  it('截到秒(前 19 字)', () => {
    expect(sliceTime('2026-07-04T09:30:00.123456')).toBe('2026-07-04T09:30:00')
  })
})

describe('wan', () => {
  it('绝对值 ≥ 1 万显 x.x万', () => {
    expect(wan(12345)).toBe('1.2万')
    expect(wan(-20000)).toBe('-2.0万')
  })

  it('绝对值 < 1 万原样', () => {
    expect(wan(9999)).toBe('9999')
  })
})

describe('statusBadge', () => {
  it('已知状态映射对等旧 STATUS_BADGE', () => {
    expect(statusBadge('FILLED')).toBe('pass')
    expect(statusBadge('DRY_RUN')).toBe('info')
    expect(statusBadge('PARTIAL')).toBe('warn')
    expect(statusBadge('REJECTED')).toBe('fail')
    expect(statusBadge('TIMEOUT_UNCANCELED')).toBe('fail')
  })

  it('未知状态回退 info', () => {
    expect(statusBadge('WHATEVER')).toBe('info')
  })
})

describe('cumReturn', () => {
  it('零快照 → 占位/暂无', () => {
    expect(cumReturn([], null)).toEqual({ text: '—', tone: 'neutral', sub: '暂无权益快照' })
  })

  it('单快照 → 占位/需多次累计(无从谈累计)', () => {
    expect(cumReturn([acct(100000)], acct(100000))).toEqual({
      text: '—',
      tone: 'neutral',
      sub: '需多次快照累计',
    })
  })

  it('≥2 快照涨 → 红(up), 现值优先取最新账户快照, 起点副文案带模式', () => {
    const series = [acct(100000), acct(105000)]
    // latest 覆盖序列末值: 起点 100000, 现值 110000 → +10%; sub 标注 series 模式防跨模式误读
    expect(cumReturn(series, acct(110000))).toEqual({
      text: '+10.00%',
      tone: 'up',
      sub: `起点 ${(100000).toLocaleString()} (dry_run)`,
    })
  })

  it('≥2 快照跌 → 绿(down)', () => {
    const series = [acct(100000), acct(90000)]
    const r = cumReturn(series, null) // latest 缺失回退序列末值 90000
    expect(r.text).toBe('-10.00%')
    expect(r.tone).toBe('down')
  })

  it('起点无效(0) → 占位而非除零', () => {
    expect(cumReturn([acct(0), acct(5000)], acct(5000))).toEqual({
      text: '—',
      tone: 'neutral',
      sub: '暂无权益快照',
    })
  })
})

describe('daemonBadge', () => {
  it('无槽位 → info 未配置', () => {
    expect(daemonBadge(cfg([], 0), '10:00')).toEqual({ kind: 'info', text: '未配置槽位' })
  })

  it('尚未到任何执行时刻 → info', () => {
    expect(daemonBadge(cfg(['09:35', '13:00'], 0), '09:00')).toEqual({
      kind: 'info',
      text: '今日未到执行时刻',
    })
  })

  it('循环数覆盖到点槽位 → pass', () => {
    expect(daemonBadge(cfg(['09:35', '13:00'], 2), '14:00')).toEqual({
      kind: 'pass',
      text: '槽位已覆盖 2/2',
    })
  })

  it('到点却缺循环 → warn 守护可能未运行', () => {
    expect(daemonBadge(cfg(['09:35', '13:00'], 1), '14:00')).toEqual({
      kind: 'warn',
      text: '槽位缺口 1/2 — 守护可能未运行',
    })
  })
})

function pos(over: Partial<PositionSnapshot>): PositionSnapshot {
  return {
    snapshot_time: '2026-07-04T09:30:00',
    mode: 'dry_run',
    symbol: '000001.SZ',
    total_volume: 100,
    available_volume: 100,
    average_cost: 10,
    last_price: null,
    ...over,
  }
}

describe('positionRow', () => {
  it('有现价: 盯市市值 + 浮盈涨红(t-up)', () => {
    const v = positionRow(pos({ last_price: 11 }))
    expect(v.mktValText).toBe(num(100 * 11))
    expect(v.pnlCls).toBe('t-up')
    expect(v.pnlText).toBe(`+${num(100)} (+10.00%)`) // 收益率统一 2 位(returnPct)
    expect(v.lastText).toBe('11.000')
  })

  it('有现价: 浮亏跌绿(t-down)', () => {
    const v = positionRow(pos({ last_price: 9 }))
    expect(v.pnlCls).toBe('t-down')
    expect(v.pnlText).toBe(`${num(-100)} (-10.00%)`) // 收益率统一 2 位(returnPct)
  })

  it('现价缺失(null): 回退成本估市值且不显盈亏', () => {
    const v = positionRow(pos({ last_price: null }))
    expect(v.mktValText).toBe(num(100 * 10))
    expect(v.pnlText).toBe('-')
    expect(v.pnlCls).toBe('')
    expect(v.lastText).toBe('-')
  })

  it('现价为 0 视同缺失(回退成本)', () => {
    const v = positionRow(pos({ last_price: 0 }))
    expect(v.pnlText).toBe('-')
    expect(v.mktValText).toBe(num(100 * 10))
  })

  it('可用量缺省显 "-"', () => {
    const v = positionRow(pos({ available_volume: null }))
    expect(v.available).toBe('-')
  })
})

describe('ticketCells', () => {
  it('content 非对象 → null(内容不可读)', () => {
    expect(ticketCells(null)).toBeNull()
    expect(ticketCells('corrupt')).toBeNull()
    expect(ticketCells(42)).toBeNull()
  })

  it('买入 BUY: 方向 t-buy 红; FILLED 终态 t-pass 绿; 金额千分位', () => {
    const cells = ticketCells({
      symbol: '000001.SZ',
      direction: 'BUY',
      price: 10.5,
      volume: 100,
      notional: 1050,
      final_status: 'FILLED',
      order_id: 'X1',
      submitted_at: '2026-07-04T09:30:00.999',
    })
    expect(cells).not.toBeNull()
    const byK = Object.fromEntries((cells ?? []).map((c) => [c.k, c]))
    expect(byK['方向']).toEqual({ k: '方向', v: '买入 BUY', cls: 't-buy' })
    expect(byK['状态']).toEqual({ k: '状态', v: 'FILLED', cls: 't-pass' })
    expect(byK['金额'].v).toBe((1050).toLocaleString())
    expect(byK['提交时刻'].v).toBe('2026-07-04T09:30:00')
  })

  it('卖出 SELL → t-sell 绿; REJECTED 终态 → t-fail 红', () => {
    const cells = ticketCells({ symbol: 'X', direction: 'SELL', status: 'REJECTED' })
    const byK = Object.fromEntries((cells ?? []).map((c) => [c.k, c]))
    expect(byK['方向'].cls).toBe('t-sell')
    expect(byK['方向'].v).toBe('卖出 SELL')
    expect(byK['状态'].cls).toBe('t-fail')
  })

  it('无值字段跳过; 方向缺失回退占位 "-"; submitted_at 缺失回退 requested_at', () => {
    const cells = ticketCells({ symbol: 'X', requested_at: '2026-07-04T10:00:00Z' })
    const byK = Object.fromEntries((cells ?? []).map((c) => [c.k, c]))
    expect(byK['标的'].v).toBe('X')
    expect(byK['委托价']).toBeUndefined() // price 缺 → 跳过
    expect(byK['状态']).toBeUndefined() // status/final_status 缺 → 跳过
    expect(byK['方向'].v).toBe('-') // direction 缺 → 占位 '-'(对等旧 cell 只跳 null/undefined/'')
    expect(byK['提交时刻'].v).toBe('2026-07-04T10:00:00')
  })
})

describe('equityAriaLabel', () => {
  it('少于 2 快照(不成曲线) → 未绘制说明', () => {
    expect(equityAriaLabel([])).toBe('账户权益曲线，快照不足暂未绘制')
    expect(equityAriaLabel([acct(100000)])).toBe('账户权益曲线，快照不足暂未绘制')
  })

  it('单模式: 条数/最新总资产/区间(T 换空格)概述', () => {
    const series = [
      acct(100000, { snapshot_time: '2026-07-04T09:30:00' }),
      acct(105000, { snapshot_time: '2026-07-05T15:00:00' }),
    ]
    expect(equityAriaLabel(series)).toBe(
      `账户权益曲线，1 条：dry_run 最新总资产 ${num(105000)}；区间 2026-07-04 09:30:00 至 2026-07-05 15:00:00`,
    )
  })

  it('多模式各报最新总资产; 乱序输入按时间排序取区间与末值', () => {
    const series = [
      acct(105000, { snapshot_time: '2026-07-05T15:00:00', mode: 'dry_run' }),
      acct(100000, { snapshot_time: '2026-07-04T09:30:00', mode: 'dry_run' }),
      acct(200000, { snapshot_time: '2026-07-04T10:00:00', mode: 'live' }),
    ]
    expect(equityAriaLabel(series)).toBe(
      `账户权益曲线，2 条：dry_run 最新总资产 ${num(105000)}；live 最新总资产 ${num(200000)}；区间 2026-07-04 09:30:00 至 2026-07-05 15:00:00`,
    )
  })
})

describe('badgeCount', () => {
  it('未达截断上限: 原样显示行数', () => {
    expect(badgeCount(0, 500)).toBe('0')
    expect(badgeCount(1, 500)).toBe('1')
    expect(badgeCount(499, 500)).toBe('499')
    expect(badgeCount(999, 1000)).toBe('999')
  })

  it('打满上限: 转 "limit+" 截断形态(真实总数未知, 不冒充精确数)', () => {
    expect(badgeCount(500, 500)).toBe('500+')
    expect(badgeCount(1000, 1000)).toBe('1000+')
  })

  it('超过上限(防御后端异常多给)同样归入 "+"', () => {
    expect(badgeCount(501, 500)).toBe('500+')
    expect(badgeCount(9999, 1000)).toBe('1000+')
  })
})
