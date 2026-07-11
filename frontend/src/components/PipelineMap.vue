<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { fetchJSON } from '@/api/fetch'
import type { BacktestRun, LiveOverview, OverviewData, VerdictRun } from '@/api/types'

/* 研究流水线地图(设计 docs/feat/0705-research-narrative §3.A) — 总览页 hero。
 * 业务事实: 数据资产→因子判决→策略回测→实盘 是本系统唯一的业务主线, 四页签正好是四环。
 * 节点①数据资产复用父级已拉的 overview prop(不重复请求); ②③④各自独立拉取,
 * 各自 try/catch — 任一端点失败该节点显 "—" 不阻塞其余(设计 D4: 不加聚合端点)。 */

const props = defineProps<{ overview: OverviewData | null }>()
const router = useRouter()

const verdictLatest = ref<VerdictRun | null>(null)
const backtestCount = ref<number | null>(null)
const liveOv = ref<LiveOverview | null>(null)

async function loadVerdicts(): Promise<void> {
  try {
    const data = await fetchJSON<{ runs: VerdictRun[] }>('/api/research/verdicts')
    verdictLatest.value = data.runs[0] ?? null
  } catch {
    verdictLatest.value = null
  }
}

async function loadBacktests(): Promise<void> {
  try {
    const data = await fetchJSON<{ runs: BacktestRun[] }>('/api/research/backtests')
    backtestCount.value = data.runs.length
  } catch {
    backtestCount.value = null
  }
}

async function loadLive(): Promise<void> {
  try {
    liveOv.value = await fetchJSON<LiveOverview>('/api/live/overview')
  } catch {
    liveOv.value = null
  }
}

void loadVerdicts()
void loadBacktests()
void loadLive()

/* 行数缩至"万"档, 与 KPI 卡量级一致(646万行 而非 6,462,707) */
function toWan(n: number | undefined): string {
  if (n === undefined) return '—'
  return n >= 10000 ? `${Math.round(n / 10000)}万行` : `${n}行`
}

const dataMetric = computed(() => toWan(props.overview?.tables.bars?.rows))

const verdictMetric = computed(() => {
  const run = verdictLatest.value
  if (!run) return '—'
  const total = run.factors.length
  const passed = run.factors.filter((f) => f.passed).length
  return `${passed}/${total} 过闸`
})

const backtestMetric = computed(() =>
  backtestCount.value === null ? '—' : `${backtestCount.value} 轮回测`,
)

const liveMode = computed(() => liveOv.value?.latest_account?.mode ?? null)
const liveMetric = computed(() => liveMode.value ?? '—')
const liveDesc = computed(() => {
  if (liveMode.value === 'live') return '真实资金执行中'
  if (liveMode.value === 'dry_run') return '纸面前向验证中'
  return '尚无实盘留痕'
})

interface Node {
  key: string
  index: string
  name: string
  metric: string
  desc: string
  route: 'verdicts' | 'backtests' | 'live' | null
}

const nodes = computed<Node[]>(() => [
  {
    key: 'data',
    index: '①',
    name: '数据资产',
    metric: dataMetric.value,
    desc: '行情与因子原料',
    route: null, // 自身页, 点击滚到下方 KPI
  },
  {
    key: 'verdicts',
    index: '②',
    name: '因子判决',
    metric: verdictMetric.value,
    desc: '谁的因子有预测力',
    route: 'verdicts',
  },
  {
    key: 'backtests',
    index: '③',
    name: '策略回测',
    metric: backtestMetric.value,
    desc: '能否转化为收益',
    route: 'backtests',
  },
  {
    key: 'live',
    index: '④',
    name: '实盘',
    metric: liveMetric.value,
    desc: liveDesc.value,
    route: 'live',
  },
])

// 流向微标: 节点间箭头下方的一句"数据怎么流"
const flows = ['特征喂检验', '过闸组策略', '策略上纸面']

function onNodeClick(node: Node): void {
  if (node.route) {
    void router.push({ name: node.route })
    return
  }
  document.querySelector('[data-testid="kpi-card"]')?.scrollIntoView({
    behavior: 'smooth',
    block: 'start',
  })
}
</script>

<template>
  <div class="pmap" data-testid="pipeline-map">
    <template v-for="(node, i) in nodes" :key="node.key">
      <button
        type="button"
        class="pmap-node card card--hoverable"
        :class="{ active: node.key === 'data' }"
        :data-testid="`pipeline-node-${node.key}`"
        @click="onNodeClick(node)"
      >
        <span class="pmap-top">
          <span class="pmap-index">{{ node.index }}</span>
          <span class="pmap-name">{{ node.name }}</span>
        </span>
        <span class="pmap-metric num">{{ node.metric }}</span>
        <span class="pmap-desc">{{ node.desc }}</span>
      </button>
      <span v-if="i < nodes.length - 1" class="pmap-arrow" aria-hidden="true">
        <span class="pmap-arrow-glyph">→</span>
        <span class="pmap-arrow-label">{{ flows[i] }}</span>
      </span>
    </template>
  </div>
</template>

<style scoped>
/* flex 行: 节点/箭头交替; 节点等分伸展, 箭头固定窄宽 — 窄屏箭头隐藏后节点自动 wrap 成 2x2 */
.pmap {
  align-items: stretch;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: var(--gap-lg);
}

.pmap-node {
  border-radius: var(--radius);
  color: inherit; /* button UA 不继承 color(R5 教训) */
  cursor: pointer;
  display: flex;
  flex: 1 1 150px;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  text-align: left;
}

.pmap-node.active {
  box-shadow: inset 2px 0 0 var(--accent);
}

.pmap-top {
  align-items: baseline;
  display: flex;
  gap: 6px;
}

.pmap-index {
  color: var(--accent-strong, var(--accent)); /* 文字级 accent(F-04 同款): light 压 bg-2 2.74 → 5.14:1 */
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 700;
}

.pmap-name {
  color: var(--text);
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 600;
}

.pmap-metric {
  color: var(--text);
  font-size: 20px;
  font-weight: 600;
  line-height: 1.15;
}

.pmap-desc {
  color: var(--text-3);
  font-size: 11.5px;
}

/* 箭头列: 窄屏隐藏(节点 flex-wrap 后箭头会孤立错位), 宽屏才有空间讲"数据怎么流" */
.pmap-arrow {
  display: none;
}

@media (min-width: 860px) {
  .pmap-arrow {
    align-items: center;
    color: var(--text-3);
    display: flex;
    flex: 0 0 auto;
    flex-direction: column;
    gap: 2px;
    justify-content: center;
    width: 64px;
  }

  .pmap-arrow-glyph {
    color: var(--accent);
    font-size: 15px;
  }

  .pmap-arrow-label {
    font-size: 10.5px;
    text-align: center;
    white-space: nowrap;
  }
}
</style>
