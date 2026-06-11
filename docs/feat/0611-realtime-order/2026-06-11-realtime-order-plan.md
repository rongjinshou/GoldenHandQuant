# 实时行情订阅 + 安全下单 实施计划

> **For agentic workers:** superpowers:executing-plans 内联执行（用户明确指令）。
> 契约/决策见同目录 design 文档；测试用 Windows conda Python。

**Goal:** R1-R4 垂直切片——实时订阅、五道闸限价买一手、CLI、系统选股实单。

**Tech Stack:** xtdata(get_full_tick/subscribe_quote) + 既有 QmtTradeGateway + argparse。

### Task 1: domain — Quote VO + IRealtimeQuoteFetcher
- Create: `src/domain/market/value_objects/quote.py`（design §4 原样）
- Create: `src/domain/market/interfaces/gateways/realtime_quote_fetcher.py`
- [x] 纯定义无逻辑，不单测；随 Task 3 的 mock 使用即验证

### Task 2: infrastructure — QmtRealtimeQuoteFetcher
- Create: `src/infrastructure/gateway/qmt_realtime_quote.py`
- [x] `get_quotes`: `xtdata.get_full_tick(symbols)` → Quote（lastPrice/bidPrice[0]/
  askPrice[0]/lastClose/time 字段映射，缺失→None/0 过滤）
- [x] `subscribe_first_tick`: `xtdata.subscribe_quote(symbol, period='tick',
  callback)` + threading.Event 等首推（timeout 默认 3s）→ `unsubscribe_quote`
  清理 → 失败回退 get_quotes
- [x] 开盘时段实测脚本: 13:00 后对 601288.SH 订阅，打印真实 tick（验收 R1）

### Task 3: application — OrderTicketAppService + 单测
- Create: `src/application/order_ticket_app.py`（design §4 契约 + D2 五道闸 +
  D3 价格策略 + D5 轮询/审计 dict 构造；审计文件写入放 CLI 层，service 返回 ticket）
- Test: `tests/application/test_order_ticket_app.py`
- [x] 单测（mock quote/trade/account 网关 + 注入 clock）:
  非交易时段拒 / 无报价拒 / 超涨跌停带拒 / 超金额上限拒 / 资金不足拒 /
  happy path（价格=min(ask1, last*1.002) 取整、volume=lots*100、place_order 调用、
  轮询到 FILLED）/ ask1 缺失回退 last*1.002
- [x] 全绿后提交

### Task 4: CLI — quant order buy
- Create: `src/interfaces/cli/commands/order_cmd.py`
- Modify: `src/interfaces/cli/quant.py`（order 子命令: buy；--symbol/--lots/
  --max-notional/--config/--yes/--poll-timeout）
- [x] 账号解析（design §4 顺序）→ 组装 QmtRealtimeQuoteFetcher + QmtTradeGateway
  → service.buy_lots → 打印 ticket/状态轨迹 → 审计 JSON 落 data/trade_logs/
- [x] ruff + 提交

### Task 5: 选股 + 实单（验收 R2-R4）
- [x] DuckDB 选股查询（D4 条件）→ 记录结果与依据
- [x] 用户切 QMT 极简模式 → `quant order buy --symbol <选出> --lots 1 --yes`
- [x] 轮询终态 + 审计 JSON + 运行手册 `2026-06-11-first-order-runbook.md`

## Self-Review
R1→T2、R2→T3/T5、R3→T4、R4→T5；五道闸单测逐一对应 D2；无占位符；
Quote/IRealtimeQuoteFetcher/OrderTicketAppService 签名与 design §4 一致。
