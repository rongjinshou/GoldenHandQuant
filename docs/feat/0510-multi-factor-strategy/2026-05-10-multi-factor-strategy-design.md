# 多因子选股策略 设计文档

> **目标:** 实现多因子选股策略，支持因子注册、因子合成、多因子打分选股，集成到回测和半自动实盘链路。
> **因子:** 价值（PB/PE）、质量（ROE）、反转（20日涨幅）、低波动（换手率/波动率）。

## 1. 背景与动机

调研结论：A 股有效性最强的策略类型是多因子选股（夏普 1.0-1.5，年化 15-22%）。当前系统只有微盘价值（截面策略）和双均线（趋势策略），缺少通用的多因子框架。

**设计原则：**
- 因子是纯计算逻辑，无副作用
- 因子可灵活组合、权重可调
- 新增因子只需实现接口并注册
- 复用现有 CrossSectionalStrategy 框架

## 2. 架构概览

```
                    ┌─────────────────────┐
                    │  MultiFactorStrategy │ (CrossSectionalStrategy)
                    │  - factors: list     │
                    │  - weights: dict     │
                    │  - top_n: int        │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   FactorScorer       │
                    │  - percentile_rank   │
                    │  - weighted_combine  │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
     ┌────────▼───┐   ┌───────▼────┐   ┌───────▼────┐
     │ ValueFactor│   │QualityFactor│   │ReversalFactor│ ...
     │ (PB, PE)   │   │ (ROE, OCF) │   │ (20d return) │
     └────────────┘   └────────────┘   └──────────────┘
```

## 3. 核心组件

### 3.1 Factor Protocol（因子接口）

```python
class FactorProtocol(Protocol):
    name: str
    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        """计算每只股票的因子原始值。返回 {symbol: raw_value}。"""
        ...
```

因子是纯函数：输入 StockSnapshot 列表，输出每只股票的原始分数。

### 3.2 FactorScorer（因子打分器）

将原始值转换为 0-1 分数：
1. **百分位排名法**：将原始值排序，转换为百分位 [0, 1]
2. **加权合成**：各因子分数 × 权重 → 综合分数
3. **排名选股**：按综合分数排序，选 top N

### 3.3 因子实现

| 因子 | 指标 | 数据来源 | 计算逻辑 |
|------|------|---------|---------|
| 价值因子 | PB_ratio, PE_ratio | FundamentalSnapshot | 低 PB/PE → 高分（取倒数排名） |
| 质量因子 | ROE_TTM | FundamentalSnapshot | 高 ROE → 高分 |
| 反转因子 | 20日涨幅 | Bar 数据 | 涨幅小/负 → 高分（A 股反转效应） |
| 低波动因子 | 20日波动率 | Bar 数据 | 低波动 → 高分 |

### 3.4 数据扩展

**FundamentalSnapshot 新增字段：**
- `pe_ratio: float | None` — 市盈率
- `pb_ratio: float | None` — 市净率
- `total_mv: float | None` — 总市值（别名，与 market_cap 同义）

**StockSnapshot 新增字段：**
- `pe_ratio: float | None`
- `pb_ratio: float | None`
- `return_20d: float | None` — 20 日收益率（由策略从 Bar 计算）
- `volatility_20d: float | None` — 20 日波动率（由策略从 Bar 计算）
- `turnover_rate: float | None` — 换手率（由策略从 Bar 计算）

### 3.5 MultiFactorStrategy

继承 CrossSectionalStrategy，在 `generate_cross_sectional_signals` 中：
1. 从 FundamentalRegistry 获取当日全市场快照
2. 从 MarketGateway 获取各标的近 20 日 Bar 数据
3. 构建 StockSnapshot 列表，填充 bar 计算的字段
4. 对每个因子调用 compute → percentile → 加权合成
5. 按综合分数排序，选 top_n
6. 生成 BUY 信号（已有持仓不在 top_n 中的生成 SELL 信号）

## 4. 策略参数

```yaml
strategy:
  name: "multi_factor"
  params:
    top_n: 10
    weights:
      value: 0.25
      quality: 0.25
      reversal: 0.25
      low_volatility: 0.25
```

## 5. 因子注册表

复用现有 StrategyRegistry 模式，在 `src/domain/strategy/registry.py` 中注册：

```python
_register(StrategyConfig(
    name="multi_factor",
    factory=_build_multi_factor,
    strategy_type="cross_section",
    description="多因子选股策略 (价值+质量+反转+低波动)",
    default_params={"top_n": 10, "weights": {...}},
))
```

## 6. 文件结构

### 新增文件

| 文件 | 职责 |
|------|------|
| `src/domain/strategy/factors/base.py` | Factor Protocol + FactorScorer |
| `src/domain/strategy/factors/value_factor.py` | 价值因子（PB, PE） |
| `src/domain/strategy/factors/quality_factor.py` | 质量因子（ROE） |
| `src/domain/strategy/factors/reversal_factor.py` | 反转因子（20d return） |
| `src/domain/strategy/factors/low_volatility_factor.py` | 低波动因子（波动率） |
| `src/domain/strategy/services/strategies/multi_factor_strategy.py` | 多因子策略 |
| `tests/domain/strategy/factors/test_base.py` | FactorScorer 测试 |
| `tests/domain/strategy/factors/test_value_factor.py` | 价值因子测试 |
| `tests/domain/strategy/factors/test_quality_factor.py` | 质量因子测试 |
| `tests/domain/strategy/factors/test_reversal_factor.py` | 反转因子测试 |
| `tests/domain/strategy/factors/test_low_volatility_factor.py` | 低波动因子测试 |
| `tests/domain/strategy/test_multi_factor_strategy.py` | 多因子策略集成测试 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `src/domain/market/value_objects/fundamental_snapshot.py` | 新增 pe_ratio, pb_ratio 字段 |
| `src/domain/market/value_objects/stock_snapshot.py` | 新增 pe_ratio, pb_ratio, return_20d, volatility_20d, turnover_rate 字段 |
| `src/domain/strategy/registry.py` | 注册 multi_factor 策略 |
| `src/infrastructure/gateway/tushare_fundamental_fetcher.py` | 读取 pe_ttm, pb 字段 |
| `resources/backtest.yaml` | 新增 multi_factor 策略配置示例 |

## 7. 验收标准

1. 因子独立可测：每个因子单独的单元测试
2. 因子合成可测：FactorScorer 的百分位排名和加权合成
3. 策略集成可测：MultiFactorStrategy 端到端测试
4. 回测可跑：`python -m src.interfaces.cli.run_backtest` 使用 multi_factor 策略
5. 注册表可切：`--strategy multi_factor` 在 CLI 中可用
6. 全部现有测试不被破坏
7. ruff lint 通过
