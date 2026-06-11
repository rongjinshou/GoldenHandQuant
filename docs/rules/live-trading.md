# 实盘自动交易规范 (Live Trading)

> 闭环 v1（2026-06-11）现行架构与安全规则。设计/决策记录：
> `docs/feat/0611-closed-loop/`（design / plan / night-review / morning-runbook）。

## 1. 自动循环脊柱

入口 `quant auto-trade`（`src/interfaces/cli/auto_trade.py`），编排核心
`AutoTradeAppService.run_cycle()`（`src/application/auto_trade_app.py`）：

```
TradingScheduler 槽位触发 (execution_times, 如 09:35/14:50)
  → LiveSignalService 扫描行情产信号
  → _select: 置信度过滤 + 当日同标的同方向去重(跨 mode) + SELL 优先 + 截断
  → 逐单: 盘前闸(见 §2) → place_order → 轮询终态(超时撤单)
  → 留痕 trading.db + 账户/持仓快照 (finally 必达)
```

- 信号源 `LiveSignalService` + `FixedRatioSizer`；**旧编排链
  `AutoTradingEngine` / `TradingOrchestrator` / `SignalPipeline` / `OrderExecutor`
  不再接线**（决策 DD-1，归档候选，债 D9）。
- `TradingScheduler` 用 `_fired_slots` 槽位集合防采样漂移漏触发/双触发；
  启动时预标记已过槽位，周末不触发。
- 单笔执行异常自隔离为该单 FAILED，不炸穿循环；循环级异常也必须留痕收口。
- 轮询终态：`FILLED / CANCELED / REJECTED / DRY_RUN`；超时（默认 30s）调
  `cancel_order`，结果标记 `TIMEOUT_CANCELED / UNCANCELED`。

## 2. 三层防线（顺序执行，任一不过即拒单）

### 第一层：六道盘前闸（domain 纯函数，ticket 与 auto 共用）

`src/domain/trade/services/pre_trade_checks.py` — `run_pre_trade_gates()`：

1. **标的白名单**: 仅沪市 `60xxxx` + 深市 `000xxx/001xxx`（002 序列暂不在 v1
   范围，扩围登记为债 D6）。
2. **交易时段**: 仅交易日连续竞价时段可下单（周末直接拒）。
3. **报价新鲜度**: 行情快照超过 `MAX_QUOTE_AGE_SECONDS=180` 秒拒单
   （超龄视为停牌/断连的陈旧快照）。
4. **价格带**: 限价必须落在前收 ±10%（`PRICE_BAND`）内；限价构造
   `build_limit_price`——买贴卖一但不超 `last×1.002`，卖贴买一但不低于 `last×0.998`。
5. **单笔金额**: ≤ `per_order_notional_cap`（配置 1500），硬顶
   `MAX_NOTIONAL_CEILING=5000` 写死在代码里。
6. **资金/持仓**: 买入校验可用资金（×`CASH_FEE_BUFFER=1.01` 费用缓冲），
   卖出校验可用持仓（允许零股清仓）。

### 第二层：预算闸（应用层 + trading.db 统计）

- 单循环最多 `max_orders_per_cycle=3` 单。
- 日累计申报金额 ≤ `daily_notional_cap=3000`；统计**跨 mode**（dry_run 与 live
  共享额度，防切换钻空），CANCELED 也占预算（保守口径）。
- 当日同标的同方向去重；循环内资金游标递减（BUY 提交后扣
  `notional × 1.01`），防同循环多单超资金。

### 第三层：当日亏损禁买

- 当日首循环先落盘前基准快照（`day_start_equity`）；
- 权益回撤 > `daily_loss_limit_ratio=2%` 时禁止新买入（卖出不受限）。

## 3. 运行模式与 live 三重确认

- **dry_run 默认**：`DryRunTradeGateway` 包装真实 QMT 网关——查询透传、下单/撤单
  模拟（订单号 `dry-<uuid>`，防重启覆盖历史），`is_dry_run=True` 标志。
- **live 真单三重确认，缺一降级 dry_run**（`resolve_mode()`）：
  1. `resources/trading.yaml` 配置 `auto_trade.mode: live`
  2. 配置 `auto_trade.enabled: true`
  3. CLI 显式 `--live`
- `AutoTradeAppService` 构造时校验 `mode` 与网关 `is_dry_run` 装配一致性，
  接错直接拒绝启动。
- **纪律红线：因子未过硬门槛（edge 未验证）前不得开启 live。**

## 4. 交易留痕（审计优先）

- 库：`data/trading.db`（SQLite WAL，`check_same_thread=False`——守护线程写库
  必需，教训见 night-review）。
- 四表：`trading_cycles` / `execution_records` / `account_snapshots` /
  `position_snapshots`（`src/infrastructure/persistence/trading_store.py`）。
- `save_execution` 按 order_id INSERT OR REPLACE；审计动作另入 `audit_logs`
  （`AuditService` + `SqliteAuditLogRepository`）。
- 消费端：驾驶舱「实盘」页（`/api/live/*` 五个只读端点，sqlite URI mode=ro）。

## 5. 配置

`resources/trading.yaml` 的 `auto_trade` 段：`enabled` / `mode` / `strategy` /
`symbols`（主板白名单内）/ `execution_times` / `min_confidence` /
`max_orders_per_cycle` / `per_order_notional_cap` / `daily_notional_cap` /
`daily_loss_limit_ratio` / `poll_timeout_seconds`。
映射 `AutoTradeSettings`（`src/infrastructure/config/settings.py`）。
