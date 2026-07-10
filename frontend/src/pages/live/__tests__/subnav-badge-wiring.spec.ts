/* Live 子导航截断徽章接线契约 — Live.vue 以 `badgeCount(...) as unknown as number`
 * 向 SubNav(badge prop 声明 number, 组件不在本轮改动范围)传入 "500+" 字符串,
 * 依赖两条 Vue 事实: 插值只做字符串化、items 数组不做深层运行时 prop 校验。
 * 此 spec 按 Live 相同姿势挂 SubNav, 把该契约钉死(若 SubNav 日后收紧校验, 这里先红)。 */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SubNav from '@/components/SubNav.vue'

import { badgeCount } from '../logic'

const asBadge = (len: number, limit: number): number =>
  badgeCount(len, limit) as unknown as number

describe('SubNav 截断徽章接线(Live 同姿势)', () => {
  it('打满 limit 的徽章渲染为 "500+" 形态', () => {
    const w = mount(SubNav, {
      props: {
        items: [
          { key: 'cycles', label: '循环', badge: asBadge(500, 500) },
          { key: 'executions', label: '执行', badge: asBadge(1000, 1000) },
          { key: 'audit', label: '审计', badge: asBadge(1200, 500) },
        ],
        modelValue: 'cycles',
      },
    })

    expect(w.find('[data-testid="subnav-cycles"]').text()).toContain('500+')
    expect(w.find('[data-testid="subnav-executions"]').text()).toContain('1000+')
    expect(w.find('[data-testid="subnav-audit"]').text()).toContain('500+')
  })

  it('未达 limit 原样显示行数; 0 也照显(0 是真实计数非缺失)', () => {
    const w = mount(SubNav, {
      props: {
        items: [
          { key: 'cycles', label: '循环', badge: asBadge(499, 500) },
          { key: 'audit', label: '审计', badge: asBadge(0, 500) },
        ],
        modelValue: 'cycles',
      },
    })

    expect(w.find('[data-testid="subnav-cycles"]').text()).toContain('499')
    expect(w.find('[data-testid="subnav-cycles"]').text()).not.toContain('+')
    expect(w.find('[data-testid="subnav-audit"]').text()).toContain('0')
  })
})
