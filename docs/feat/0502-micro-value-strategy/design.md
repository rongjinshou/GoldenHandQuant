# 微盘价值质量增强策略 — 架构设计文档

## 概述

基于 QuantFlow DDD 架构，开发一套完全适配 A 股日频环境的"基本面过滤 + 极小市值轮动增强"量化策略。策略以防守为先（剔除劣质资产、规避系统风险），以极端下沉市值为攻（捕获流动性溢价），并在极其苛刻的摩擦成本假设下验证有效性。

## 架构决策记录 (ADR)

| # | 决策点 | 选择 | 依据 |
|---|--------|------|------|
| 1 | 策略接口 | 新建 `CrossSectionalStrategy` 基类 | 截面策略与现有时序策略语义不同，分而治之 |
| 2 | 风控架构 | 三分层：SystemRiskGate + RiskChain + RiskSignalGenerator | 盘前/盘中/盘后不同生命周期，各司其职 |
| 3 | 基本面数据 | `FundamentalSnapshot` 值对象 + `FundamentalRegistry` 索引 | 与 Bar 解耦，各自独立获取和索引 |
| 4 | 过滤逻辑 | Domain 层纯函数 + Infra 层数据供给 | Domain 纯净可测试，Infra 管 I/O |
| 5 | 回测循环 | 双模式：时序路径 + 截面路径 | 不影响现有 DualMaStrategy |
| 6 | Sizer 接口 | 新增 `calculate_targets()` 批量方法 | 截面策略产出批量信号，需要批量调仓计算 |
| 7 | 财务数据源 | Tushare 基础接口（daily_basic, stock_basic, fina_indicator） | 免费即可获取，覆盖需求 |
| 8 | 订单执行顺序 | SELL 优先，BUY 在后 | A 股 T+1，先释放资金再建仓 |

---

## 第 1 段：数据层

### 新增值对象

**FundamentalSnapshot** — `src/domain/market/value_objects/fundamental_snapshot.py`

```python
@dataclass(slots=True, kw_only=True)
class FundamentalSnapshot:
    symbol: str
    date: datetime
    name: str
    list_date: datetime
    market_cap: float
    roe_ttm: float | None
    ocf_ttm: float | None
```

**StockSnapshot** — `src/domain/market/value_objects/stock_snapshot.py`

```python
@dataclass(slots=True, kw_only=True)
class StockSnapshot:
    symbol: str; date: datetime
    open: float; high: float; low: float; close: float; volume: float
    name: str; list_date: datetime
    market_cap: float
    roe_ttm: float | None; ocf_ttm: float | None
```

### FundamentalRegistry

`src/domain/market/services/fundamental_registry.py` — 双索引内存结构：
- `dict[symbol, dict[date, FundamentalSnapshot]]` — 按标的查询
- `dict[date, list[FundamentalSnapshot]]` — 按日期批量获取（O(1)）

索引键使用 `ann_date`（公告日期）而非 `end_date`（报告期），杜绝未来函数。

### 数据获取

| 接口 (Domain) | 实现 (Infrastructure) | Tushare API | 获取字段 |
|---------------|----------------------|-------------|----------|
| `IFundamentalFetcher` | `TushareFundamentalFetcher` | `stock_basic` | name, list_date |
| | | `daily_basic` | total_mv |
| | | `fina_indicator` | roe, ocf |
| | 提供 `fetch_by_range(start_date, end_date)` | 批量预加载，回测启动时一次性拉取 | |
| `(IHistoryDataFetcher)` | `TushareHistoryDataFetcher` (扩展) | `daily` | pre_close |
| — | `TushareIndexFetcher` | `index_daily` | CSI1000 日线 |

### FeaturePipeline 扩展

新增 `build_cross_section(date, bars, registry) -> list[StockSnapshot]` 方法，将当日 Bar 与 FundamentalRegistry 合并为截面快照列表。

### 文件变更

| 操作 | 文件 |
|------|------|
| 新增 | `src/domain/market/value_objects/fundamental_snapshot.py` |
| 新增 | `src/domain/market/value_objects/stock_snapshot.py` |
| 新增 | `src/domain/market/services/fundamental_registry.py` |
| 新增 | `src/domain/market/interfaces/gateways/fundamental_fetcher.py` |
| 新增 | `src/infrastructure/gateway/tushare_fundamental_fetcher.py` |
| 新增 | `src/infrastructure/gateway/tushare_index_fetcher.py` |
| 修改 | `src/infrastructure/ml_engine/feature_pipeline.py` |
| 修改 | `src/infrastructure/gateway/tushare_history_data.py` — 映射 pre_close |

---

## 第 2 段：策略层与过滤器

### 过滤函数（Domain 纯函数）

所有过滤器统一签名：`(list[StockSnapshot], **params) -> list[StockSnapshot]`

| 过滤器 | 文件 | 规则 |
|--------|------|------|
| `filter_st` | `filter_st.py` | 剔除 name 含 "ST" 或 "*ST" |
| `filter_new_listing` | `filter_new_listing.py` | 剔除上市不足 365 天 |
| `filter_penny_stock` | `filter_penny_stock.py` | 剔除 close < 1.5 元 |
| `filter_trading_status` | `filter_trading_status.py` | 剔除 volume==0 或一字涨跌停 |
| `filter_quality` | `filter_quality.py` | ROE > 全市场中位数 且 OCF > 0，min_universe_size 默认 30 |

### 截面策略基类

```python
class CrossSectionalStrategy(BaseStrategy, ABC):
    @abstractmethod
    def generate_cross_sectional_signals(
        self, universe: list[StockSnapshot],
        current_positions: list[Position], current_date: datetime
    ) -> list[Signal]: ...

    def generate_signals(self, market_data, current_positions):
        raise NotImplementedError("Use generate_cross_sectional_signals")
```

### MicroValueStrategy

```
generate_cross_sectional_signals():
  1. 日历熔断: month ∈ {1, 4} → return []
  2. 错峰调仓: weekday != 1 (周二) → return []
  3. 过滤链: ST → 次新 → 仙股 → 停牌 → 质量
  4. 按 market_cap 升序 → 截取 top_n (默认 9)
  5. 产出 BUY Signal 列表
```

### 文件变更

| 操作 | 文件 |
|------|------|
| 新增 | `src/domain/strategy/services/cross_sectional_strategy.py` |
| 新增 | `src/domain/strategy/services/strategies/micro_value_strategy.py` |
| 新增 | `src/domain/strategy/services/filters/filter_st.py` |
| 新增 | `src/domain/strategy/services/filters/filter_new_listing.py` |
| 新增 | `src/domain/strategy/services/filters/filter_penny_stock.py` |
| 新增 | `src/domain/strategy/services/filters/filter_trading_status.py` |
| 新增 | `src/domain/strategy/services/filters/filter_quality.py` |

---

## 第 3 段：组合构建与批量 Sizer

### 批量接口

`IPositionSizer` 新增 `calculate_targets()` 方法：

```python
def calculate_targets(
    self, signals: list[Signal], prices: dict[str, float],
    asset: Asset, positions: list[Position],
) -> list[OrderTarget]:
```

### EqualWeightSizer 批量实现

```
calculate_targets():
  1. 目标池为空 → 清仓所有持仓
  2. 计算每只目标仓位: target_value = total_asset / n
     - 持仓不足 → BUY 差额 (100 的倍数向下取整)
     - 持仓过多 → SELL 超额
  3. 不在目标池中的持仓 → SELL 全部可用量
```

### 文件变更

| 操作 | 文件 |
|------|------|
| 修改 | `src/domain/portfolio/interfaces/position_sizer.py` — 增加 `calculate_targets` |
| 修改 | `src/domain/portfolio/services/equal_weight_sizer.py` — 实现批量方法 |

---

## 第 4 段：风控三分层架构

### 架构

```
层1 (盘前): SystemRiskGate.check_gate(date) → GateResult(pass_buy, reason)
            └── CSI1000 < MA20 → pass_buy = False

层2 (盘中): RiskChain.check(order) → RiskCheckResult
            └── 逐单审核，已有组件不变

层3 (盘后): RiskSignalGenerator.evaluate(positions, bars) → list[Signal]
            ├── LimitUpBreakPolicy  → high == limit_up 且 close < limit_up → SELL
            └── HardStopLossPolicy → (close - cost) / cost < -3% → SELL
```

### 关键设计

- **层3 产出的是 Signal**，与策略信号类型相同，Sizer 无需区分来源
- **层1 只禁 BUY**，SELL 信号（止损/破板）畅行无阻 → "只出不进"逃命模式
- **涨停价计算**依赖 Bar 新增的 `prev_close` 字段，不能用 open 近似

### Bar 修改

`prev_close: float = 0.0` — 来自 Tushare `pre_close` 字段

### 文件变更

| 操作 | 文件 |
|------|------|
| 新增 | `src/domain/risk/services/system_risk_gate.py` |
| 新增 | `src/domain/risk/services/risk_signal_generator.py` |
| 新增 | `src/domain/risk/services/base_risk_signal_policy.py` |
| 新增 | `src/domain/risk/services/risk_policies/limit_up_break_policy.py` |
| 新增 | `src/domain/risk/services/risk_policies/hard_stop_loss_policy.py` |
| 修改 | `src/domain/market/value_objects/bar.py` — 增加 prev_close |

---

## 第 5 段：回测主循环与可视化

### 截面策略交易日循环

```
for each trading day:
  [01] build_cross_section(bars, registry) → universe
  [02] SystemRiskGate.check_gate(date) → gate_result
  [03] strategy.generate_cross_sectional_signals(universe, ...) → signals
  [04] RiskSignalGenerator.evaluate(positions, bars) → risk_signals
  [05] all_signals = signals + risk_signals
  [06] if not gate_result.pass_buy: 过滤 BUY 信号
  [07] sizer.calculate_targets(all_signals, prices, asset, positions) → targets
  [08] targets.sort(SELL first, BUY second)  # 先释放资金
  [09] for target in targets:
         Order → RiskChain.check → place_order
  [10] DailySettlement
  [11] record_snapshot
```

### 路由逻辑

BacktestAppService 通过 `isinstance(strategy, CrossSectionalStrategy)` 自动分发到 `_run_cross_sectional_strategy()`，DualMaStrategy 继续走原有的 `_run_single_strategy()`。

### 可视化增强

- Panel 1: 策略净值曲线 + 中证1000 基准曲线（双轴叠加）
- Panel 2: 每日收益率分布
- Panel 3: 回撤曲线
- BacktestReport 新增 `turnover_rate` 属性（日均换手率）

### 配置文件

```yaml
backtest:
  benchmark: "000852.SH"
  symbols:
    index: "000852.SH"

strategy:
  name: "MicroValueStrategy"
  top_n: 9

position_sizing:
  type: "EqualWeightSizer"

risk:
  system_gate:
    index_symbol: "000852.SH"
    ma_period: 20
  stop_loss:
    max_loss_ratio: 0.03
  policies:
    - "limit_up_break"
    - "hard_stop_loss"

costs:
  commission_rate: 0.0002
  tax_rate: 0.001
  min_commission: 5.0
  slippage: 0.003
```

### 文件变更

| 操作 | 文件 |
|------|------|
| 修改 | `src/application/backtest_app.py` — 增加截面循环 + 路由逻辑 |
| 修改 | `src/infrastructure/visualization/plotter.py` — 基准曲线 + 回撤面板 |
| 修改 | `resources/backtest.yaml` — 完整策略配置 |

---

## 变更总结

| 层级 | 新文件 | 修改文件 |
|------|--------|----------|
| Domain — Market | 3 (FundamentalSnapshot, StockSnapshot, FundamentalRegistry) | 1 (Bar) |
| Domain — Market (接口) | 1 (IFundamentalFetcher) | 0 |
| Domain — Strategy | 2 (CrossSectionalStrategy, MicroValueStrategy) | 0 |
| Domain — Strategy/Filters | 5 (ST, 次新, 仙股, 停牌, 质量) | 0 |
| Domain — Portfolio | 0 | 2 (IPositionSizer, EqualWeightSizer) |
| Domain — Risk | 5 (Gate, Generator, BasePolicy ×3) | 0 |
| Infrastructure — Gateway | 3 (TushareFundamental, TushareIndex, TushareHistory 扩展) | 0 |
| Infrastructure — ML | 1 (FeaturePipeline 扩展) | 0 |
| Infrastructure — Visualization | 0 | 1 (Plotter) |
| Application | 0 | 1 (BacktestAppService) |
| Config | 0 | 1 (backtest.yaml) |
| **合计** | **20** | **6** |
