# 批三·增强（P7-P9）完成记录

- 完成日期：2026-07-10
- 分支：`feat/frontend-ux-overhaul`
- 方式：5 路并行 subagent（按页面独占文件）→ 中央集成

## 集成验收（全绿）

| 检查 | 结果 |
|---|---|
| `npm run typecheck` | 0 error |
| `npm run test` | **439 passed / 42 files** |
| `npm run lint` | 0 error / 21 warning（`any`，测试文件） |
| `npm run build` | ✓ built |
| `check_frontend_fresh` | OK |
| `ui_smoke` | **PASS — 0 / 0 / 0** |
| 读图 | Live「已停用」中译确认；六页无回归 |

## 交付

- **P7 URL 深链**：回测轮 `?run=`、判决轮 `?run=`、行情标的 `?symbols=` 均双向幂等同步（`router.replace` 不污染历史，值比较刹车结构性防死循环，各带纯逻辑模块 run-selection.ts / run-deeplink.ts / deep-link.ts + 单测）。刷新/前进后退可恢复选中，研究结果可深链分享。叠加对比 `?overlay=` 按计划延后（次级功能）。
- **P8 内容 i18n**：
  - Verdicts 5 个孤儿 glossary 词条全部接线（oos_ic/oos_ir/ls_oos → OOS 格，score → grade 徽章，verdict_badge → 逐关判定小节），零改 glossary.ts。
  - Live 审计动作/执行状态/委托方向/启用停用中译（labels.ts，对齐后端 auto_trade_app.py 权威枚举）；Jobs 类型中译（jobTypeLabel，对齐后端 submit 调用点）；`mode`(dry_run/live) 刻意保留（已是双语术语）。
  - 回测/判决日期显年（`slice(5,16)`→含年，跨年可分辨）。
  - Live 收益率精度统一 2 位（returnPct 单一口径，持仓盈亏 1→2 位）。
- **P9 响应式 + 字体**：顶栏窄屏 flex-wrap 兜底（nav 换行不溢出）；`.table-scroll` 全局工具类；CJK 字体栈补 Microsoft YaHei/PingFang SC（未装思源不裸退默认宋，**零 webfont 体积**）。

## 范围调整（已在计划记录）

- **自托管中文 webfont 未打进 bundle**：@fontsource CJK 会给已入库 static/ 灌数十 MB，改为强化系统 CJK 回退。真正 fonttools 子集化 webfont 另立专项。

## 并行编排

5 路 subagent 同工作树、按页面独占文件，零冲突集成（typecheck 一次过、439 测试全绿）。跨流在途 TDD 红态（run-naming/CyclesTable/run-deeplink）均在各自流收尾后自然转绿，集成门全绿。

## 附：一条挂起的非前端发现（未处理，待用户定夺）

批二某 subagent 越界只读排查 market.duckdb 后报告：行情特征线在 **2025-11-25→12-22** 集体 NULL（return/volatility/ma/rsi 等滚动特征冷启动，疑似某次增量重算缺 200 天预热历史，之后 fetch_meta 标记已履约致 `data refresh` 跳过而固化）。**这是后端/数据问题，非本轮前端范围，且非用户交办**。未执行任何 DB 写操作（需授权 + 停 dashboard 写占用）。排查脚本在 scratchpad（只读）。**挂起，待用户决定是否单独立项修复。**
