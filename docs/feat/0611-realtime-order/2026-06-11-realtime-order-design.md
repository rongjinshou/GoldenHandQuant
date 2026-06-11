# 实时行情订阅 + 安全下单 设计文档（v1 垂直切片）

> 状态：用户明确指令（2026-06-11 午间，开盘日）："结合 QMT 正确订阅开盘实时数据，
> 完成改系统，用系统完成一次下单（仅买一手，选股你来决定）"。
> 决策全权委托，以下决策记录可溯源可推翻。流程：brainstorming → plan → 实现。

## 1. 目标与验收

| # | 需求 | 验收 |
|---|---|---|
| R1 | 实时行情层：快照 + 订阅推送 | 开盘时段实测拿到真实 tick（last/bid1/ask1/前收） |
| R2 | 安全下单服务：买一手，全程留痕 | 实单提交 → 轮询到终态 → 审计 JSON 落盘 |
| R3 | CLI：`quant order buy --symbol X --lots 1` | 一条命令完成 预检→报价→下单→轮询→报告 |
| R4 | 选股有依据 | 用系统数据（DuckDB）查询产生，记录于运行手册 |

**明确不做（v1）**：自动策略驱动下单（Phase 3 的 auto-trade 已有骨架）、卖出/撤单 CLI
（撤单留 gateway 能力即可）、订单簿深度行情、WebSocket 推到 dashboard（future）。

## 2. 现状与缺口

已有：`QmtTradeGateway`（连接/资产/持仓/下单，限价+市价）、`Order` 状态机、
风险子域、`trading.yaml`（userdata_mini 路径）。
缺口：① 无实时行情接口与实现（现有 fetcher 都是历史日线）；② 无"单笔下单"
应用编排（auto-trade 是策略循环，过重）；③ 交易链路实测 connect rc=-1 ——
**QMT 需以极简模式登录**（行情链路正常，是交易进程未起）。

## 3. 决策记录

**D1 实时数据获取方式**：`xtdata.get_full_tick(symbols)` 做按需快照 +
`xtdata.subscribe_quote(symbol, period='tick', callback)` 做推送订阅。
下单前的参考价用"订阅首个 tick（3s 超时）→ 失败回退 get_full_tick"双保险——
订阅是题目要求验证的能力，快照是稳态兜底。备选 get_market_data_ex(period='tick')
拉当日 tick 序列被否（下单只需最新一笔）。

**D2 下单安全闸（全部硬性，按序检查，任一失败即拒单不提交）**：
1. 交易时段：工作日 9:30-11:30 / 13:00-15:00（本地时钟，午休/盘后拒绝）
2. 报价新鲜度：拿不到 tick / last<=0 / 前收<=0 → 拒（疑似停牌/退市）
3. 涨跌停带：限价必须落在 [前收×0.9, 前收×1.1] 内（主板 ±10%；v1 不下创业板/科创板/ST，见 D4）
4. 单笔金额上限：lots×100×限价 ≤ max_notional（默认 ¥1500，CLI 可调但有上限 ¥5000）
5. 资金检查：可用资金 ≥ 预估金额×1.01（含费用 buffer）

**D3 价格策略**：限价单（不用市价单——本次目的是受控验证，不抢成交），
价格 = `min(ask1, last×1.002)` 四舍五入到 0.01（ask1 缺失时用 last×1.002）。
贴着卖一挂，正常流动性下秒级成交；万一不成交挂到收盘自动失效，资金解冻，零残留。

**D4 选股约束与方法**：v1 实单只允许 沪深主板（60xxxx.SH / 000xxx.SZ，±10% 带，
排除 ST/新股）。选股查询（运行于 market.duckdb，体现"系统选股"）：
2025H2 日线上 `volatility_20d 最低 × 日均成交额最高 × 收盘价 3~8 元` 组合排序——
低波动是 P0 判决中最接近过线的因子（F04 88/A），低价控制一手资金占用，
高流动保证成交质量。预期命中国有大行类标的。

**D5 下单后跟踪**：提交后轮询 `query_stock_orders`（2s 间隔，默认 60s 超时），
打印状态流转；终态或超时后写审计 JSON 到 `data/trade_logs/<ts>-<symbol>.json`
（ticket 全参数、各闸检查值、tick 快照、order_id、状态轨迹）。超时未成交不自动撤单
（限价贴卖一，正常会成；留给用户决定），CLI 打印手动撤单提示。

**D6 分层归位**：Quote 值对象 + `IRealtimeQuoteFetcher` Protocol → domain/market；
`QmtRealtimeQuoteFetcher` → infrastructure/gateway；`OrderTicketAppService`
（纯编排，全部依赖注入）→ application；`quant order` → interfaces/cli。
单测全部打在 application 层（mock 网关/时钟/报价），五道闸逐一覆盖拒绝路径。

## 4. 组件契约

```python
# domain/market/value_objects/quote.py
@dataclass(slots=True, kw_only=True)
class Quote:
    symbol: str
    last: float          # 最新价
    bid1: float | None   # 买一
    ask1: float | None   # 卖一
    prev_close: float    # 前收 (涨跌停带基准)
    timestamp: datetime

# domain/market/interfaces/gateways/realtime_quote_fetcher.py
class IRealtimeQuoteFetcher(Protocol):
    def get_quotes(self, symbols: list[str]) -> dict[str, Quote]: ...
    def subscribe_first_tick(self, symbol: str, timeout: float = 3.0) -> Quote | None: ...

# application/order_ticket_app.py
@dataclass(slots=True, kw_only=True)
class OrderTicketResult:
    accepted: bool
    reject_reason: str | None
    order_id: str | None
    final_status: str | None      # FILLED/PARTIAL/ALIVE/REJECTED/TIMEOUT
    ticket: dict                  # 全参数+检查值 (审计用)

class OrderTicketAppService:
    def __init__(self, quote_fetcher, trade_gateway, account_gateway,
                 max_notional: float = 1500.0, clock=datetime.now) -> None
    def buy_lots(self, symbol: str, lots: int = 1,
                 poll_timeout: float = 60.0) -> OrderTicketResult
```

CLI：`quant order buy --symbol 601288.SH --lots 1 [--max-notional 1500]
[--config resources/trading.yaml] [--yes]`；不带 `--yes` 时打印 ticket 后要求
终端输入 `yes` 确认（实单防误触；本次执行由用户预先明确指令，带 `--yes` 跑）。
账号解析顺序：`QMT_ACCOUNT_ID` env → trading.yaml `qmt.account_id`（展开后非占位）
→ `query_account_infos()` 枚举（仅一个账号时直用，多个则报错要求显式指定）。

## 5. 风险与边界（实施期实测补充）

- 交易链路 connect rc=-1 当前可复现：需 QMT 以极简模式登录；行情链路独立可用
- 轮询用 query_stock_orders 按 order_id 过滤；xtorder 状态映射:
  48/49/50/51(已报/部成)→ALIVE/PARTIAL，52/56(全成)→FILLED，53/54(废单/撤单)→REJECTED/CANCELED
- 午休提交：QMT 可接受但本设计按 D2 拒绝（13:00 后再下，行为确定性优先）
- 审计 JSON 不含完整资金账号（脱敏尾 4 位之外打码）

## 6. 测试

application 层 mock 单测：五道闸逐一拒绝 + happy path 提交与状态轮询 +
价格取整 + ask1 缺失回退；CLI 冒烟由实盘执行本身覆盖（受控 1 手）。
