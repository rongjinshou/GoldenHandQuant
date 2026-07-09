# 批二·硬化（P4-P6）完成记录

- 完成日期：2026-07-10
- 分支：`feat/frontend-ux-overhaul`
- 方式：Wave1 地基（同步 subagent）→ Wave2 五路并行 subagent（按目录独占文件）→ 中央集成

## 集成验收（全绿）

| 检查 | 结果 |
|---|---|
| `npm run typecheck` | 0 error |
| `npm run test` | **366 passed / 36 files** |
| `npm run lint` | 0 error / 19 warning（`any`，多在既有测试文件） |
| `npm run build` | ✓ built |
| `check_frontend_fresh` | OK |
| `ui_smoke` | **PASS — console 0 / 页面异常 0 / 失败请求 0**（gates 已随重启修复） |
| 读图 | FactorCard OOS超额已翻红（行情色），品牌 GoldenHandQuant，六页无回归 |

## 交付

**Wave1 地基**：usePolling（isStale/lastSuccessAt/AbortController/退避 opt-in）；fetch 错误三段式中文化（保留 503 样板）；任务轮询 App 级全局化（回填时刻去重防双拉，修徽章别页不鲜活 + 503 文案失效）；document.title 随路由；GlossaryTip 焦点可达（1.4.13）；SubNav aria-current；KpiCard 从旧值滚；App 挂 NNotificationProvider/NMessageProvider。

**Wave2 五路**：
- **Jobs**：C1 任务行→真 button + aria-expanded；训练/评估 pending；日志近底跟随 + 回到最新；取消 NPopconfirm + 乐观；dead 重试；useNotification 完成通知 + title「✓」；状态徽章→AppBadge。
- **Live**：C2 循环行→真 button；九端点分频轮询（概览 5s / 其余 30s + 切视图补帧，请求量降 ~4×）；各表/KPI 骨架（TableSkeleton）；明细失败重展开重试；筛选降透明度反馈；权益图 role=img+aria。
- **Backtests**：C3 删除→平级双 button + focus 显形；**叠加对比 value 用 run_id 修下标错位数据误读 bug**；基准切换占位防抖；提交 pending；空态引导页内表单；symbol 联想 combobox 键盘（升级进共享 useSymbolChips）；EquityChart role=img+aria。
- **Verdicts**：**FactorCard/Modal OOS超额/多空收益统一行情色**（正=红），IC/IR/各正率/单调性转中性，PASS/FAIL + 闸门轨道保留判定色；Modal 标题 h3 + 打开聚焦修方向键；提交 pending；filter-seg aria-pressed；reload 非侵入保留选中。
- **Explorer**：联想 combobox 键盘（复用 Backtests 升级的共享 API，删自身冗余兜底）；K线/特征图 role=img+aria；加载骨架；特征在途/失败独立反馈通道。

## 全站涨跌色统一达成

回测（总收益/年化/超额）、判决（OOS超额/多空）、实盘（累计收益/持仓盈亏）——正收益一律**红**（A股行情色），质量指标（夏普/IC/IR 等）中性，PASS/FAIL 判定色。用户"全站统一 A 股行情色"决策完全落地。

## 遗留（批三或后续）

1. **闸门格/fchip 原生 title→GlossaryTip**（Verdicts task5）：未做。GlossaryTip 是词条键驱动，装不下动态因子表达式/闸门明细文本；原生 title 挂在可聚焦 button 上，WCAG 1.4.13 对 UA 原生 title 豁免，闸门明细已在焦点可达弹框完整呈现。判为可接受缺口。
2. **NSelect aria-label 落根 div**：naive-ui 非 filterable 单选触发器无内部 aria 落点，aria-label 经 attrs 落根元素（框架标准做法，axe 不判违规）。
3. **JobCard 反向 import `@/pages/jobs/ui`**：component→page 方向，受"只在 jobs/** 建新文件"约束所致，功能/类型正常。
4. **lint 19 warning**：`any`，多在既有 `chart-options.spec.ts` 等测试文件，非新增产品代码。

## 并行编排复盘

5 路 subagent 同工作树、按目录独占文件，零冲突集成（typecheck 一次过、366 测试全绿）。跨流依赖（Explorer 消费 Backtests 升级的 useSymbolChips API）由双页同构 + 18 测试覆盖兜底，集成期未爆问题。共享依赖（NotificationProvider）在派发前中央预置。
