# 真单 Spec 前置三件套 — 完成报告（2026-07-04）

> 三件全部落地（`7430e9e`/`3286545`/DD-2 commit），golden 全量绿。影子盘攒样本期间的真单准备就绪。

| 件 | 交付 | 验证 |
|---|---|---|
| **DD-1 分 mode 日预算/去重隔离** | `today_submitted_notional/today_traded_keys` 加必填 `mode` 参数（调用方必须显式声明，防再犯静默跨 mode）；`/budget` 端点同口径（按配置 mode 展示） | TDD：dry_run 意向不占 live 预算/不触发 live 去重、同 mode 防线回归；旧"跨 mode"测试按新裁定翻转并留痕理由 |
| **DD-3 实时 ST 闸** | `check_st_name`（None/空=不可得→放行，前缀口径同 filter_st）进七道闸，**只拦买入**（退出持仓不被自身警示阻断）；`QmtRealtimeQuoteFetcher.get_instrument_name`（`get_instrument_detail.InstrumentName`）；`_execute_guarded` 鸭子类型可选能力探测（fetcher 无此能力→放行，现有测试零改动） | TDD：四种 ST 前缀拒买、正常/None 放行、SELL 带 ST 名照过、无能力 fetcher 回归 |
| **DD-2 纸面净值** | `scripts/shadow_paper_equity.py`：只主板 F01+趋势闸回测（2026-07-04→当日，¥146k/top20/闸 ON），`run_id=SHADOW-PAPER-<日期>` 周度入库 backtest_runs → 驾驶舱回测页零 UI 改动可见；runbook §5 挂第⑤步 | 实跑入库 `SHADOW-PAPER-20260704`（上线日为周六 → 0 交易日诚实空窗，首个真实数据点 07-07 产生） |

**实时 fundamental 的裁定**（design DD-3 前半）：真单**继续 T-1 as-of 口径**——影子盘一致性验证的就是它；实时市值口径的差异是无偏小扰动且回测口径（T 收盘）反而更乐观。留档触发条件：周二比对若持续出现隔夜错位类 diff 再议。T-1 挡不住的唯一真风险（当日戴帽）已由实时 ST 闸补上。

**对真单 Spec 的意义**：切 live 当日预算不再被影子盘意向吃掉；当日戴帽股买不进；影子盘期间每周积累"理论净值 vs 未来真实净值"的对照基线。真单 Spec 本体（首单 runbook/cancel_order 实盘验证/纸面 vs 实盘漂移分析）待影子样本攒够后另立。
