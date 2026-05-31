# 实盘监控面板 设计文档

> **目标:** 实盘运行后，实时监控持仓、收益、风险。随时打开看当前持仓、今日盈亏、策略表现。
> **定位:** Phase 2 子项目 2.2（系统路线图），半自动交易的配套监控能力。

## 1. 背景与动机

项目当前状态：
- 半自动交易 CLI 已可用（`live_trade.py`），能扫描信号、确认下单
- QMT 交易网关可获取账户资产（`get_asset`）和持仓（`get_positions`）
- QMT 行情网关可获取实时 K 线（`get_market_data_ex`）
- 风控模块有仓位限制、回撤熔断、硬止损等策略
- 回测框架有完整的绩效评估（夏普、索提诺、胜率、盈亏比）

**缺失：** 下单之后没有"回头看"的能力。不知道持仓盈亏多少、今天赚了还是亏了、风险敞口多大。

**目标：** 一个 CLI 监控面板，运行后持续刷新，一屏看到所有关键信息。

## 2. 核心流程

```
用户运行命令
    |
    v
连接 QMT（复用 QmtTradeGateway）
    |
    v
[定时循环] ─────────────────────────────────────────┐
    |                                                |
    v                                                |
获取账户资产（get_asset）                             |
获取持仓列表（get_positions）                         |
获取实时行情（get_market_data_ex，批量）              |
    |                                                |
    v                                                |
计算持仓盈亏（实时价 vs 成本价）                      |
计算今日盈亏（总资产 vs 昨日快照）                     |
计算风险指标（仓位、集中度）                          |
触发告警检查                                          |
    |                                                |
    v                                                |
渲染 rich 面板（Live 模式，定时刷新）                  |
    |                                                |
    v                                                |
等待下一次刷新间隔（默认 3 秒）  ─────────────────────┘
    |
    v
用户按 Ctrl+C 退出
```

## 3. 面板布局设计

使用 `rich` 库的 `Live` 模式实现终端实时刷新，布局分为四个区域：

```
┌──────────────────────────────────────────────────────────────────┐
│  GoldenHandQuant 实盘监控                          14:30:15      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [Panel 1] 账户概览                                              │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐       │
│  │  总资产   │  可用资金  │  持仓市值  │  今日盈亏  │  盈亏率   │       │
│  │1,023,456 │  500,000  │  523,456  │  +3,456   │  +0.34%  │       │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘       │
│                                                                  │
│  [Panel 2] 持仓明细                                              │
│  ┌────────┬──────┬───────┬───────┬───────┬────────┬───────┐     │
│  │  标的   │ 数量  │ 成本价 │ 现价   │ 市值   │  盈亏   │ 盈亏%  │     │
│  ├────────┼──────┼───────┼───────┼───────┼────────┼───────┤     │
│  │600000SH│  500 │ 12.50 │ 13.10 │ 6,550 │  +300  │ +4.8% │     │
│  │000001SZ│  300 │ 15.30 │ 15.10 │ 4,530 │   -60  │ -1.3% │     │
│  └────────┴──────┴───────┴───────┴───────┴────────┴───────┘     │
│                                                                  │
│  [Panel 3] 风险指标                                              │
│  ┌──────────┬────────────┬──────────┬──────────┐                 │
│  │ 总仓位%  │  最大集中度  │ 持仓数量  │  当日回撤  │                 │
│  │  52.3%   │  6.4%      │    2     │  -0.12%  │                 │
│  └──────────┴────────────┴──────────┴──────────┘                 │
│                                                                  │
│  [Panel 4] 告警                                                  │
│  (无告警时隐藏此区域)                                             │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│ 刷新: 3s  |  按 Ctrl+C 退出  |  最后更新: 14:30:15              │
└──────────────────────────────────────────────────────────────────┘
```

### 3.1 Panel 1: 账户概览

| 指标 | 计算方式 | 数据来源 |
|------|---------|---------|
| 总资产 | `asset.total_asset` | `IAccountGateway.get_asset()` |
| 可用资金 | `asset.available_cash` | 同上 |
| 持仓市值 | `sum(pos.volume * current_price)` | 持仓 + 实时行情 |
| 今日盈亏 | `total_asset - yesterday_snapshot.total_asset` | 快照文件 |
| 今日盈亏率 | `今日盈亏 / yesterday_snapshot.total_asset` | 计算 |

### 3.2 Panel 2: 持仓明细

| 指标 | 计算方式 |
|------|---------|
| 标的 | `position.ticker` |
| 数量 | `position.total_volume` |
| 成本价 | `position.average_cost` |
| 现价 | 实时行情 `bar.close` |
| 市值 | `volume * current_price` |
| 浮动盈亏 | `(current_price - average_cost) * volume` |
| 盈亏率 | `(current_price - average_cost) / average_cost` |

### 3.3 Panel 3: 风险指标

| 指标 | 计算方式 | 说明 |
|------|---------|------|
| 总仓位 | `market_value / total_asset` | 持仓市值占总资产比例 |
| 最大集中度 | `max(单只市值) / total_asset` | 单只标的最大占比 |
| 持仓数量 | `len(positions)` | 持有标的数量 |
| 当日回撤 | 基于快照计算 | 今日最高点到当前的回撤 |

### 3.4 Panel 4: 告警区

触发条件时显示红色告警条，详见第 6 节。

## 4. 数据获取设计

### 4.1 复用现有组件

| 组件 | 用途 | 来源 |
|------|------|------|
| `QmtTradeGateway` | 获取资产、持仓 | `src/infrastructure/gateway/qmt_trade.py` |
| `QmtMarketGateway` | 获取实时行情 | `src/infrastructure/gateway/qmt_market.py` |
| `IAccountGateway` | 接口协议 | `src/domain/account/interfaces/gateways/` |
| `IMarketGateway` | 接口协议 | `src/domain/market/interfaces/gateways/` |

### 4.2 实时行情获取策略

`QmtMarketGateway.get_recent_bars()` 已支持批量获取，但目前是单标的调用。监控面板需要为所有持仓标的批量获取最新价：

```python
# 批量获取所有持仓标的的最新行情
symbols = [pos.ticker for pos in positions]
prices: dict[str, float] = {}
for symbol in symbols:
    bars = market_gateway.get_recent_bars(symbol, Timeframe.DAY_1, limit=1)
    if bars:
        prices[symbol] = bars[-1].close
```

**优化方向（后续迭代）：** `xtdata.get_market_data_ex()` 本身支持 `stock_list` 批量传入，可直接获取所有标的的一次行情，减少调用次数。第一版先用逐个调用，保持与现有接口一致。

### 4.3 今日盈亏数据源

今日盈亏需要"昨日总资产"作为基准。两种方案：

**方案 A（推荐）：快照文件**
- 每日收盘后自动保存快照到 `data/snapshots/{date}.json`
- 监控面板读取最近一个快照作为基准
- 复用 `DailySnapshot` 值对象

**方案 B：QMT 历史查询**
- 通过 QMT 接口查询历史资产（如果支持）
- 依赖外部接口，不如本地快照可靠

第一版采用方案 A，快照保存逻辑在日终结算时自动触发。

## 5. 领域模型设计

### 5.1 新增值对象：`MonitorSnapshot`

位置：`src/domain/account/value_objects/monitor_snapshot.py`

```python
@dataclass(slots=True, kw_only=True)
class MonitorSnapshot:
    """监控面板快照 — 聚合账户、持仓、风险的实时状态。"""
    timestamp: datetime
    asset: Asset
    positions: list[PositionDetail]
    risk_metrics: RiskMetrics
    alerts: list[Alert]
```

### 5.2 新增值对象：`PositionDetail`

位置：`src/domain/account/value_objects/position_detail.py`

```python
@dataclass(slots=True, kw_only=True)
class PositionDetail:
    """持仓明细 — 包含实时盈亏计算。"""
    ticker: str
    total_volume: int
    available_volume: int
    average_cost: float
    current_price: float
    market_value: float       # volume * current_price
    unrealized_pnl: float     # (current_price - average_cost) * volume
    pnl_ratio: float          # (current_price - average_cost) / average_cost
```

### 5.3 新增值对象：`RiskMetrics`

位置：`src/domain/risk/value_objects/risk_metrics.py`

```python
@dataclass(slots=True, kw_only=True)
class RiskMetrics:
    """风险指标快照。"""
    total_position_ratio: float    # 总仓位 = market_value / total_asset
    max_concentration: float       # 最大集中度 = max(单只市值) / total_asset
    position_count: int            # 持仓标的数量
    today_drawdown: float          # 当日回撤
```

### 5.4 新增值对象：`Alert`

位置：`src/domain/risk/value_objects/alert.py`

```python
@dataclass(slots=True, kw_only=True)
class Alert:
    """告警信息。"""
    level: str          # "WARNING" | "CRITICAL"
    category: str       # "LOSS" | "CONCENTRATION" | "POSITION"
    message: str
    value: float
    threshold: float
```

## 6. 告警规则引擎

### 6.1 设计原则

- 规则定义在 domain 层，与通知机制解耦
- 复用现有 `BaseRiskPolicy` 的 check 模式，但告警不拦截只通知
- 规则可配置（阈值通过配置文件传入）

### 6.2 告警规则

| 规则 | 触发条件 | 级别 | 说明 |
|------|---------|------|------|
| 单日亏损 | `today_pnl / yesterday_asset < -threshold` | CRITICAL | 默认阈值 -3% |
| 单只亏损 | `pos.unrealized_pnl_ratio < -threshold` | WARNING | 默认阈值 -5% |
| 仓位过高 | `total_position_ratio > threshold` | WARNING | 默认阈值 80% |
| 集中度过高 | `max_concentration > threshold` | WARNING | 默认阈值 30% |
| 仓位过低 | `total_position_ratio < threshold` | WARNING | 默认阈值 10%（空仓信号） |

### 6.3 告警规则引擎

位置：`src/domain/risk/services/alert_engine.py`

```python
class AlertEngine:
    """告警规则引擎 — 检查监控快照并生成告警。"""

    def __init__(self, rules: list[AlertRule] | None = None) -> None:
        self._rules = rules or _default_rules()

    def check(self, snapshot: MonitorSnapshot) -> list[Alert]:
        alerts: list[Alert] = []
        for rule in self._rules:
            alert = rule.evaluate(snapshot)
            if alert:
                alerts.append(alert)
        return alerts
```

每个 `AlertRule` 是一个 Protocol：

```python
class AlertRule(Protocol):
    def evaluate(self, snapshot: MonitorSnapshot) -> Alert | None: ...
```

内置规则：
- `DailyLossRule` — 单日亏损告警
- `StockLossRule` — 单只亏损告警
- `PositionRatioRule` — 仓位过高/过低告警
- `ConcentrationRule` — 集中度过高告警

### 6.4 通知机制

第一版仅在终端面板中显示告警。后续可扩展：

| 通知渠道 | 优先级 | 说明 |
|---------|--------|------|
| 终端面板 | P0（本次实现） | 告警条显示在面板中 |
| 日志文件 | P0（本次实现） | 告警写入日志 |
| 企业微信/钉钉 | P2（后续） | Webhook 推送 |
| 邮件 | P3（后续） | SMTP 发送 |

通知接口设计（预留扩展）：

```python
class INotifier(Protocol):
    """通知器接口。"""
    def notify(self, alert: Alert) -> None: ...

class TerminalNotifier:
    """终端通知（第一版实现）。"""
    def notify(self, alert: Alert) -> None:
        # 在 rich 面板中显示
        ...

class LogNotifier:
    """日志通知。"""
    def notify(self, alert: Alert) -> None:
        logger.warning(f"[{alert.level}] {alert.category}: {alert.message}")
```

## 7. 应用层服务设计

### 7.1 `MonitorService`

位置：`src/application/monitor_service.py`

```python
class MonitorService:
    """实盘监控编排服务。

    流程: 获取数据 → 计算盈亏 → 计算风险 → 触发告警 → 产出 MonitorSnapshot。
    """

    def __init__(
        self,
        account_gateway: IAccountGateway,
        market_gateway: IMarketGateway,
        alert_engine: AlertEngine,
        yesterday_asset: float = 0.0,
    ) -> None:
        ...

    def take_snapshot(self) -> MonitorSnapshot:
        """获取一次完整的监控快照。"""
        # 1. 获取资产和持仓
        # 2. 批量获取实时行情
        # 3. 计算持仓明细（盈亏）
        # 4. 计算风险指标
        # 5. 运行告警检查
        # 6. 组装 MonitorSnapshot
        ...
```

## 8. CLI 入口设计

### 8.1 命令行接口

```bash
# 基本用法（使用 trading.yaml 配置）
python -m src.interfaces.cli.live_monitor

# 指定刷新间隔
python -m src.interfaces.cli.live_monitor --interval 5

# 指定昨日资产（不读快照文件）
python -m src.interfaces.cli.live_monitor --yesterday-asset 1000000

# 禁用告警
python -m src.interfaces.cli.live_monitor --no-alert

# 指定配置文件
python -m src.interfaces.cli.live_monitor --config resources/trading.yaml
```

### 8.2 rich 面板实现

使用 `rich.live.Live` 实现定时刷新：

```python
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table

def build_dashboard(snapshot: MonitorSnapshot) -> Layout:
    """构建监控面板布局。"""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )
    layout["body"].split_row(
        Layout(name="main", ratio=3),
        Layout(name="side", ratio=1),
    )
    layout["main"].split_column(
        Layout(name="overview", size=7),
        Layout(name="positions"),
    )
    layout["side"].split_column(
        Layout(name="risk", size=7),
        Layout(name="alerts"),
    )
    # 填充各区域内容...
    return layout

def main() -> None:
    # 初始化 QMT 连接
    # 初始化 MonitorService
    with Live(build_dashboard(initial_snapshot), refresh_per_second=1) as live:
        while True:
            snapshot = monitor_service.take_snapshot()
            live.update(build_dashboard(snapshot))
            time.sleep(interval)
```

### 8.3 色彩方案

| 元素 | 颜色 | 说明 |
|------|------|------|
| 盈利金额 | 绿色 | `+3,456` |
| 亏损金额 | 红色 | `-60` |
| 平盘 | 白色 | `0` |
| CRITICAL 告警 | 红色背景 | 高亮醒目 |
| WARNING 告警 | 黄色 | 注意 |
| 表头 | 青色 | 与现有 CLI 一致 |

## 9. 快照持久化

### 9.1 快照存储

位置：`data/snapshots/{YYYY-MM-DD}.json`

```json
{
    "date": "2026-05-31",
    "total_asset": 1023456.78,
    "available_cash": 500000.00,
    "market_value": 523456.78,
    "positions": [
        {
            "ticker": "600000.SH",
            "volume": 500,
            "average_cost": 12.50,
            "close_price": 13.10
        }
    ]
}
```

### 9.2 快照保存时机

- **自动保存：** 日终结算时（复用 `DailySettlementService` 的流程）
- **手动保存：** 监控面板退出时（Ctrl+C 触发）

## 10. 配置扩展

在 `resources/trading.yaml` 中新增 `monitor` 配置节：

```yaml
monitor:
  refresh_interval: 3          # 刷新间隔（秒）
  yesterday_asset_file: "data/snapshots/"  # 快照目录
  alerts:
    daily_loss_threshold: 0.03       # 单日亏损告警阈值 -3%
    stock_loss_threshold: 0.05       # 单只亏损告警阈值 -5%
    position_ratio_max: 0.80         # 仓位过高告警阈值 80%
    position_ratio_min: 0.10         # 仓位过低告警阈值 10%
    concentration_max: 0.30          # 集中度过高告警阈值 30%
```

对应的 Settings 数据类：

```python
@dataclass(slots=True, kw_only=True)
class MonitorAlertSettings:
    daily_loss_threshold: float = 0.03
    stock_loss_threshold: float = 0.05
    position_ratio_max: float = 0.80
    position_ratio_min: float = 0.10
    concentration_max: float = 0.30

@dataclass(slots=True, kw_only=True)
class MonitorSettings:
    refresh_interval: int = 3
    yesterday_asset_file: str = "data/snapshots/"
    alerts: MonitorAlertSettings = field(default_factory=MonitorAlertSettings)
```

## 11. 文件结构

### 新增文件

| 文件 | 职责 |
|------|------|
| `src/domain/account/value_objects/position_detail.py` | 持仓明细值对象（含实时盈亏） |
| `src/domain/account/value_objects/monitor_snapshot.py` | 监控快照值对象 |
| `src/domain/risk/value_objects/risk_metrics.py` | 风险指标值对象 |
| `src/domain/risk/value_objects/alert.py` | 告警值对象 |
| `src/domain/risk/services/alert_engine.py` | 告警规则引擎 |
| `src/domain/risk/services/alert_rules/daily_loss_rule.py` | 单日亏损告警规则 |
| `src/domain/risk/services/alert_rules/stock_loss_rule.py` | 单只亏损告警规则 |
| `src/domain/risk/services/alert_rules/position_ratio_rule.py` | 仓位比例告警规则 |
| `src/domain/risk/services/alert_rules/concentration_rule.py` | 集中度告警规则 |
| `src/application/monitor_service.py` | 监控编排服务 |
| `src/interfaces/cli/live_monitor.py` | CLI 监控面板入口 |
| `src/infrastructure/snapshot/snapshot_store.py` | 快照持久化 |
| `tests/domain/risk/test_alert_engine.py` | 告警引擎单元测试 |
| `tests/application/test_monitor_service.py` | 监控服务单元测试 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `src/infrastructure/config/settings.py` | 新增 `MonitorSettings`、`MonitorAlertSettings` |
| `pyproject.toml` | 新增 `rich` 依赖 |
| `resources/trading.yaml` | 新增 `monitor` 配置节 |

## 12. 依赖新增

```toml
# pyproject.toml dependencies 新增
"rich>=13.0"
```

`rich` 是 Python 终端富文本渲染的事实标准库，轻量、无额外依赖，支持表格、面板、Live 刷新、颜色、进度条等。

## 13. 不做的事（YAGNI）

- **不做 Web 界面：** Phase 4 再考虑，CLI 够用
- **不做策略级盈亏归因：** 第一版只看总盈亏，不做按策略分组（因为当前只有一个策略在跑）
- **不做 Beta 计算：** 需要基准指数数据，后续迭代
- **不做自动告警通知（微信/钉钉）：** 第一版只在终端显示
- **不做盈亏曲线图：** 终端画图体验差，后续用 matplotlib 导出
- **不做交易记录回放：** 已有 QMT 客户端可看

## 14. 验收标准

1. `python -m src.interfaces.cli.live_monitor` 能运行，面板每 N 秒刷新
2. 账户概览正确显示总资产、可用资金、持仓市值、今日盈亏
3. 持仓明细正确显示每只股票的实时盈亏（盈亏为绿色，亏损为红色）
4. 风险指标正确计算总仓位、集中度
5. 单日亏损超阈值时面板显示 CRITICAL 告警
6. Ctrl+C 优雅退出，不残留进程
7. QMT 未连接时报错清晰
8. 所有新代码有单元测试
9. `ruff check` 通过
10. 现有测试不被破坏
