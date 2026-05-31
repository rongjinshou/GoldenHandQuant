# Phase 2.5: 信号审核界面 — 设计文档

**文档版本**: v1.0
**创建日期**: 2026-05-31
**文档类型**: 详细设计 / 技术方案
**状态**: 草案

---

## 一、需求概述

### 1.1 阶段目标

**在现有半自动 CLI 基础上，升级为功能完善的信号审核界面。支持丰富信息展示、批量操作、审核记录持久化，以及截面策略信号。**

### 1.2 用户故事

> 作为量化投资者，我希望在每天开盘前快速审核策略信号，看到每个信号的风险评分和置信度，
> 能一键批准或批量拒绝，并保留完整的审核记录供复盘。

### 1.3 与现有 live_trade.py 的关系

**重构而非重写。** `live_trade.py` 保留为入口文件，内部逻辑拆分到独立模块：

| 现状 | 目标 |
|------|------|
| `live_trade.py` 一个文件 223 行，信号展示 + 确认 + 下单一锅端 | 拆分为入口 + 审核界面 + 审核记录三个模块 |
| 只支持 bar 类型策略 | 同时支持截面策略 |
| 无审核记录 | JSON 持久化审核记录 |
| 逐条确认，无批量操作 | 支持全部批准/全部拒绝 |
| 信号卡片仅 8 列 | 增加风险评分、ML 置信度、历史信号追踪 |

---

## 二、现有代码分析

### 2.1 核心文件

| 文件 | 职责 | 关键类/函数 |
|------|------|------------|
| `src/interfaces/cli/live_trade.py` | CLI 入口 + 交互逻辑 | `main()`, `print_signal_table()`, `confirm_single()` |
| `src/application/live_signal_service.py` | 信号扫描 + 下单编排 | `LiveSignalService`, `SignalDisplay`, `OrderResult` |
| `src/domain/strategy/value_objects/signal.py` | 信号领域实体 | `Signal` (symbol, direction, confidence_score, reason) |
| `src/domain/strategy/services/cross_sectional_strategy.py` | 截面策略基类 | `CrossSectionalStrategy.generate_cross_sectional_signals()` |
| `src/application/order_service.py` | 风控 + 下单 | `OrderService.place_order()` |

### 2.2 现有流程

```
main() -> load config -> connect QMT -> LiveSignalService.scan()
       -> print_signal_table() -> input choice -> confirm_single() (逐条)
       -> place_confirmed_orders() -> print_order_results()
```

### 2.3 现有瓶颈

1. **截面策略阻断**：`live_trade.py:139` 检测到 `cross_section` 直接 `sys.exit(0)`，`LiveSignalService._scan_cross_sectional()` 返回空列表。
2. **无审核记录**：信号审核后即丢失，无法复盘历史决策。
3. **交互简陋**：纯文本表格，无 Rich 美化，无批量操作。

---

## 三、新增数据结构

### 3.1 SignalReviewRecord 值对象

```python
# src/domain/strategy/value_objects/signal_review_record.py

@dataclass(slots=True, kw_only=True)
class SignalReviewRecord:
    """信号审核记录 — 一次审核决策的持久化快照。"""

    record_id: str               # UUID
    signal: Signal               # 原始信号
    action: ReviewAction         # APPROVED / REJECTED / SKIPPED
    reviewed_at: datetime        # 审核时间
    reviewer_note: str = ""      # 审核备注
    order_id: str = ""           # 下单后回填（仅 APPROVED）
    suggested_price: float = 0.0
    suggested_volume: int = 0
    risk_score: float = 0.0      # 风险评分 (0.0-1.0，越高越危险)
    ml_confidence: float = 0.0   # ML 模型置信度（若可用）
    signal_age_hours: float = 0.0 # 信号存活时间
```

### 3.2 ReviewAction 枚举

```python
# src/domain/strategy/value_objects/review_action.py

class ReviewAction(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"
```

### 3.3 EnhancedSignalDisplay

```python
# src/application/live_signal_service.py (扩展现有 SignalDisplay)

@dataclass(slots=True, kw_only=True)
class EnhancedSignalDisplay(SignalDisplay):
    """增强信号展示 — 在原有基础上增加审核相关字段。"""
    risk_score: float = 0.0
    ml_confidence: float = 0.0
    signal_age_hours: float = 0.0
    historical_win_rate: float = 0.0  # 该策略历史胜率
```

---

## 四、CLI 交互流程设计

### 4.1 Rich 表格布局

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  GoldenHandQuant 信号审核                           2026-05-31 09:15:00     │
├─────────────────────────────────────────────────────────────────────────────┤
│  策略: multi_factor  │  可用资金: ¥500,000  │  持仓: 12 只  │  信号: 5 条  │
├────┬──────────┬──────┬────────┬────────┬──────┬────────┬──────┬────────────┤
│  # │ 标的     │ 方向 │ 当前价 │ 挂单价 │ 数量 │ 资金   │ 风险 │ 置信度     │
├────┼──────────┼──────┼────────┼────────┼──────┼────────┼──────┼────────────┤
│  1 │ 600000.SH│ BUY  │ 10.50  │ 10.51  │  900 │  9,459 │ 0.2  │ 0.85      │
│  2 │ 000001.SZ│ SELL │ 15.20  │ 15.18  │  500 │  7,590 │ 0.1  │ 0.92      │
│  3 │ 601318.SH│ BUY  │ 45.80  │ 45.85  │  200 │  9,170 │ 0.4  │ 0.71      │
└────┴──────────┴──────┴────────┴────────┴──────┴────────┴──────┴────────────┘
  触发原因: 1) MACD金叉+放量  2) 破位止损  3) 因子排名前10%

  [a] 全部批准  [r] 全部拒绝  [1,3] 选择批准  [n] 添加备注  [q] 退出
  >
```

### 4.2 交互命令

| 命令 | 行为 |
|------|------|
| `1,3,5` | 批准指定序号的信号 |
| `a` | 全部批准 |
| `r` | 全部拒绝 |
| `r 2,4` | 拒绝指定序号 |
| `n 1 这只票基本面不好` | 为信号 1 添加审核备注 |
| `d 3` | 查看信号 3 的详细信息（展开卡片） |
| `q` | 退出，不执行任何操作 |
| `Enter` | 确认当前选择，进入下单流程 |

### 4.3 详细信息展开（`d` 命令）

```
┌─ 信号详情: #1 600000.SH ─────────────────────────────┐
│  策略:      dual_ma                                    │
│  方向:      BUY                                        │
│  当前价:    10.50                                      │
│  挂单价:    10.51 (+0.1% 滑点)                         │
│  数量:      900 股                                     │
│  所需资金:  ¥9,459                                     │
│  置信度:    0.85                                       │
│  风险评分:  0.2 (低)                                   │
│  历史胜率:  62.5% (近 50 次信号)                       │
│  触发原因:  MACD 金叉，5日均量放大 1.5 倍              │
│  信号时间:  2026-05-31 09:10:22                        │
│  信号年龄:  0.8 小时                                   │
└───────────────────────────────────────────────────────┘
```

---

## 五、截面策略信号支持方案

### 5.1 问题分析

截面策略（如 `multi_factor_strategy`）继承 `CrossSectionalStrategy`，其 `generate_cross_sectional_signals()` 需要 `list[StockSnapshot]` 而非 `dict[str, list[Bar]]`。当前 `LiveSignalService._scan_cross_sectional()` 直接返回空。

### 5.2 解决方案

**在 LiveSignalService 中实现真正的截面扫描，而非阻断返回。**

```
LiveSignalService.scan()
  ├─ bar 策略 -> _scan_bar() (现有逻辑不变)
  └─ cross_section 策略 -> _scan_cross_sectional() (重构)
       ├─ 1. market_gateway.get_stock_snapshots(universe) -> list[StockSnapshot]
       ├─ 2. strategy.generate_cross_sectional_signals(snapshots, positions, date)
       └─ 3. _signals_to_displays(signals, ...) (复用现有转换逻辑)
```

### 5.3 MarketGateway 接口扩展

```python
# src/domain/market/interfaces/gateways/market_gateway.py (新增方法)

class IMarketMarketGateway(Protocol):
    # ... 现有方法 ...

    def get_stock_snapshots(self, symbols: list[str]) -> list[StockSnapshot]:
        """获取全市场日频快照 — 供截面策略使用。"""
        ...
```

### 5.4 降级方案

若 `get_stock_snapshots()` 不可用（如 QMT 未连接），回退到逐 symbol 拉取 bar 数据并构造简化 StockSnapshot，确保截面策略至少能产出信号（精度降低但不阻断）。

---

## 六、审核记录持久化

### 6.1 存储格式

```json
// resources/signal_reviews/2026-05-31.json
{
  "date": "2026-05-31",
  "reviews": [
    {
      "record_id": "a1b2c3d4",
      "symbol": "600000.SH",
      "direction": "BUY",
      "strategy_name": "dual_ma",
      "action": "approved",
      "reviewed_at": "2026-05-31T09:15:30",
      "reviewer_note": "",
      "order_id": "ord-12345",
      "suggested_price": 10.51,
      "suggested_volume": 900,
      "risk_score": 0.2,
      "ml_confidence": 0.85,
      "signal_age_hours": 0.8,
      "reason": "MACD金叉+放量"
    }
  ],
  "summary": {
    "total_signals": 5,
    "approved": 3,
    "rejected": 1,
    "skipped": 1,
    "total_capital_deployed": 26219
  }
}
```

### 6.2 存储路径

- 目录：`resources/signal_reviews/`
- 命名：`{YYYY-MM-DD}.json`
- 按日自动归档

### 6.3 读取历史记录

审核界面启动时加载当日已有记录，支持追加而非覆盖。历史记录用于计算策略历史胜率。

---

## 七、模块拆分方案

### 7.1 目标文件结构

```
src/interfaces/cli/
├── live_trade.py              # 保留：入口 + 参数解析 (精简到 ~80 行)
├── signal_review/             # 新增目录
│   ├── __init__.py
│   ├── review_ui.py           # Rich 表格渲染 + 交互逻辑
│   ├── review_store.py        # 审核记录 JSON 持久化
│   └── enhanced_display.py    # 增强信号展示数据结构
```

### 7.2 职责划分

| 模块 | 职责 | 行数估计 |
|------|------|---------|
| `live_trade.py` | 参数解析、QMT 连接、调用 review_ui | ~80 行 |
| `review_ui.py` | Rich 表格、交互命令、批量操作 | ~200 行 |
| `review_store.py` | JSON 读写、历史胜率查询 | ~80 行 |
| `enhanced_display.py` | EnhancedSignalDisplay + 风险评分计算 | ~50 行 |

---

## 八、与 OrderService 的集成

### 8.1 现状

`LiveSignalService.place_confirmed_orders()` 直接构造 Order 并调用 `trade_gateway.place_order()`，绕过了 `OrderService` 的风控检查。

### 8.2 改进

审核通过的信号在下单前经过 `OrderService.place_order()`，确保风控策略生效：

```python
# review_ui.py 中下单逻辑
for display in approved_displays:
    order = _build_order(display)
    result = order_service.place_order(order)  # 走风控
    record = _build_review_record(display, result, ReviewAction.APPROVED)
    store.append(record)
```

---

## 九、风险与降级

| 风险 | 影响 | 降级方案 |
|------|------|---------|
| Rich 库未安装 | 审核界面无法渲染 | 回退到现有纯文本模式 |
| QMT 截面数据不可用 | 截面策略无法扫描 | 逐 symbol 拉 bar 构造简化快照 |
| JSON 文件损坏 | 审核记录丢失 | 启动时校验，损坏则新建空文件 |
| 信号数量过多 (>50) | 表格溢出 | 分页显示，每页 20 条 |
