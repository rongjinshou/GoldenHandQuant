# 行情页（Explorer.vue）多标的叠加改造 — 设计与决策记录

> 状态: **已实现**（2026-07-05）。三项需求（去时间选择器/多标的叠加对比/特征曲线可增呈现框）
> 均已落地，pytest 无涉（纯前端改动），vitest 188 例全绿，typecheck/lint/build/
> check_frontend_fresh 全绿，`frontend/scripts/shot.py explorer` 实测双主题截图+浏览器
> console/pageerror 监听零报错。起因: 用户提出"行情界面做些优化和额外功能：1.取消时间，
> 按当前不填的时间 2.支持叠加，多个股票叠加 3.特征曲线支持新增一个呈现框，勾选框内嵌到
> 呈现框中"（2026-07-05）。

## 1. 决策

| # | 决策 | 理由 |
|---|------|------|
| D1 | 移除起止日期选择器，永远吃后端 `_default_range` 的"未填"默认区间（近一年至今） | 后端该默认逻辑早已存在，零改动；去掉一步手动选择，新手更少一个要理解的控件 |
| D2 | 标的输入改为复用 `useSymbolChips()` 的 chip 输入；K 线区按标的数分支：1 只=蜡烛+成交量（逐字零回归），2+ 只=单 pane"涨跌幅对比"折线图（各标的以自身区间内首个可用收盘价为基准 0%） | 蜡烛图本质是单标的可视化，多标的叠加只有"归一化后比涨跌幅"才有意义；这是同花顺/雪球等同类工具的标准做法 |
| D3 | 特征曲线区从"一条共享勾选框+一张图"改造成可重复"新增呈现框"，每框自带内嵌勾选框，共享同一份按标的缓存的特征数据（拉取时按全部呈现框已勾选特征的并集去重请求，避免重复拉取） | 用户明确要求"呈现框"可增、勾选框内嵌其中；共享缓存避免同一特征在多个框各自重复发请求 |
| D4 | 标的配色：`symbolColor(palette, index) = palette.series[index % 6]`，下标取自"已加载标的"；同一标的在 K 线对比图与特征图两处颜色一致，但删除较早的标的会使其后标的颜色整体重排（不做跨删除的持久化颜色分配） | 6 色循环已覆盖绝大多数实际对比场景（2-4 只标的）；持久化分配需要额外的槽位回收设计，复杂度增量与其解决的"纯视觉重排"问题不成比例 |
| D5 | 特征呈现框内，同一标的下不同特征用 `lineStyle.type`（solid/dashed/dotted，按 `FEATURE_META` 声明顺序固定映射）区分，颜色仍按标的走 | "颜色管标的、虚实线管特征"两个视觉通道各司其职，比纯撞色方案对色弱用户更友好，也让同一标的能跨 K 线图/特征图用颜色追踪 |
| D6 | 呈现框/标的 chip 的删除均不做二次确认弹窗 | 参照 `BacktestForm.vue` 现状 `chips.remove()` 零确认的先例：这类状态是纯前端可逆状态，几秒内重新键入/勾选即可恢复，不销毁任何服务端持久化数据，不同于 `Backtests.vue`/`Verdicts.vue` 里"删一整轮跑批结果"需要 `NPopconfirm` 二次确认的场景 |
| D7 | 后端 `research.py`/`market_data_store.py` 零改动 | `bars`/`features` 端点本就是单标的路径参数，前端对每个标的各发一次请求、`Promise.all` 并行等齐即可（沿用改动前 `loadAll()` 已有的并行模式，只是从 1 个标的扩展到 N 个） |

## 2. 实现范围（文件）

- `frontend/src/pages/explorer/chart-options.ts`（新）：纯函数层 —— `FEATURE_META`/`featureLabel`/`DEFAULT_FEATURES`（从 `Explorer.vue` 原样迁移，标签文案不变）、`symbolColor`、`featureLineDash`、`buildUnionDates`/`alignByDate`（日期并集对齐工具）、`buildKlineOption`、`buildFeaturePanelOption`。零 Vue 依赖，vitest 直测（24 例）。
- `frontend/src/pages/explorer/FeaturePanel.vue`（新）：单个"呈现框"组件，纯 props 受控（`symbols`/`featuresBySymbol`/`modelValue`/`removable`/`panelIndex`），emit `update:modelValue`/`remove`；内嵌 13 项特征勾选框 + 自己的折线图；首个呈现框固定 `data-testid="feature-chart"`（兼容 `scripts/ui_smoke.py`/`frontend/scripts/shot.py`），其余按位置编号 `feature-chart-N`。组件挂载测试 7 例（`@vue/test-utils`，`VChart` 按其内部 `name` 字段 `Echarts` 而非本地 import 别名 `VChart` 打桩，否则会真实挂载 vue-echarts 在 jsdom 里因缺 canvas backend 报错）。
- `frontend/src/pages/Explorer.vue`（重写）：页面本体 —— `useSymbolChips()` 接管标的 chip 输入；`loadedSymbols`（已加载标的快照）与图表实际读取的"当前标的"解耦于 chip 输入框的实时数组（避免"改 chip 还没点加载，图表就抢先跳到多标的分支"）；`featureFetchGen` 世代计数器统一守护"加载"首拉与勾选驱动的自动重拉，防止乱序响应互相覆盖；`panels` 数组管理呈现框的增删。

## 3. 踩到的坑：vue-echarts 的 merge 语义在图表"形状切换"时会崩

**现象**：已用单一标的加载出蜡烛图后，再追加第二个标的点击"加载"，K 线区和特征图会冻结在旧的单标的画面上，`console` 抛出 `xAxis "0" not found` / `Cannot read properties of null (reading 'emitsOptions')` 等错误，此后包括"新增呈现框"在内的任何交互都不再生效，需要刷新整个页面才能恢复。

**根因**：`buildKlineOption`/`buildFeaturePanelOption` 的 1 标的分支返回双 pane 结构（`xAxis`/`yAxis`/`grid` 均为长度 2 的数组），2+ 标的分支返回单 pane 结构（这些字段是普通 object）。`<VChart :option="...">` 默认不传 `update-options`，vue-echarts 走 ECharts 的 `setOption` merge 语义——已存在的 ECharts 实例在收到形状迥异的新 option 时，合并出的内部状态引用不到位而抛错，且 Vue 组件一旦在响应式更新过程中抛出未捕获异常，后续任何触发该组件重渲染的动作都会在同一条已损坏的渲染路径上重放。

**修复**：给两处 `<VChart>` 都显式加 `:update-options="{ notMerge: true }"`，让每次 option 变化整份替换而非尝试合并。这是三路复核（正确性/构建健康度/视觉）里视觉复核用实测截图+`page.on('console')`/`page.on('pageerror')`真实监听抓到的，`window.__console_errors` 这个旧脚本里读的全局变量全仓库搜不到任何写入点、恒为空数组，是个假信号——已顺带在 `frontend/scripts/shot.py` 里补了一路真实监听。

**教训**：任何"同一个 `<VChart>` 会在不同数据形态下渲染出结构不同的 option"的场景（数组 pane 数 vs 单 object、series 数量剧变等），都应该显式 `notMerge: true`，不能依赖默认 merge 语义。

## 4. 已知的简化/未做事项

设计评审阶段曾提出一套更完整的健壮性方案（`loadedSymbols`/`featureFetchGen` 已采纳；以下几项评审建议但最终判断超出本次范围或性价比不足，未实现）：

- **`Promise.all` 而非 `Promise.allSettled`**：多标的批量请求中若有一个标的失败，当前仍是整批作废（与改动前单标的行为一致），未做"部分标的成功也能各自渲染"的细粒度容错。多标的场景下这意味着一个标的代码打错会连累其余标的也不显示。
- **无 `>6` 标的撞色提示 / 无笛卡尔积密度提示**：`palette.series` 只有 6 色，第 7 只标的开始会与第 1 只撞色；呈现框内"标的数×特征数"过多时也没有可读性提示。
- **`scripts/ui_smoke.py` 未扩展**：只有 `frontend/scripts/shot.py`（开发期读图自查）覆盖了多标的+新增呈现框路径；`ui_smoke.py`（带退出码的验收链闸门）仍只灌一个标的，多标的/多呈现框路径没有进自动化验收闸门。

这几项都是"用得更多才会真正疼"的边际项，不阻塞当前使用；如果后续实际使用中标的数经常超过 3-4 个，或对失败容错有实际诉求，可以再补。

## 5. 测试清单

- `chart-options.spec.ts`（24 例）：日期并集/对齐的空值与错位边界、配色与虚实线取模、K 线图 1/2+ 标的分支切换（含次新股缺首日数据的用例）、特征图笛卡尔积命名与配色。
- `FeaturePanel.spec.ts`（7 例）：勾选/取消勾选触发 `update:modelValue`、`removable=false` 隐藏删除按钮、空态文案。
- `frontend/scripts/shot.py explorer`：单标的基线（零回归）+ 追加第二标的触发对比图 + 新增呈现框勾选不同特征，双主题截图，真实 console/pageerror 监听。
