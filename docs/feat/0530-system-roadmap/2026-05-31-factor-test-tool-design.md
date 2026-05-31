# 因子快速测试工具 设计文档

> **目标:** 10 分钟验证一个新因子是否有效。用户输入因子表达式（如 `revenue_growth / pe_ratio`），系统自动计算因子值、执行分层回测、生成有效性报告（IC/IR/分层收益/单调性/因子衰减）并给出 0-100 综合评分。
> **核心价值:** 将因子验证从"写策略+跑回测+手动分析"的数小时流程压缩到一条命令。

## 1. 背景与动机

当前验证一个新因子需要：
1. 在 `src/domain/strategy/factors/` 中新建因子类
2. 配置 `MultiFactorStrategy` 参数
3. 跑完整回测
4. 手动分析回测报告判断因子是否有效

这个流程耗时长、重复劳动多。因子快速测试工具将整个流程自动化：用户只需写一个表达式，系统完成剩下所有工作。

**设计原则：**
- 表达式求值在 domain 层（纯 Python，无第三方依赖）
- 统计计算（IC/IR）在 infrastructure 层（可使用 numpy/pandas）
- 复用现有 30 个因子的 `Factor.compute()` 作为表达式的叶子节点
- 复用现有 `BacktestAppService` 驱动分层回测
- 输出结构化报告，便于后续比较和存档

## 2. 架构概览

```
用户输入: "earnings_growth / pe_ratio"
         │
         ▼
┌─────────────────────────┐
│  FactorExpressionParser  │  Domain 层：纯 Python 解析器
│  字符串 → AST → 求值器   │  输出: dict[str, float] (每只股票的因子值)
└────────────┬────────────┘
             │
    ┌────────┴────────┐
    ▼                 ▼
┌──────────┐   ┌──────────────┐
│ IC/IR    │   │ 分层回测      │  Infrastructure 层
│ 计算     │   │ (N 组分层)    │  使用 numpy/pandas
└────┬─────┘   └──────┬───────┘
     │                │
     ▼                ▼
┌─────────────────────────────┐
│     FactorTestReport         │  Domain 层值对象
│  IC/IR/分层收益/单调性/衰减   │  纯数据结构
│  综合评分 (0-100)             │
└─────────────────────────────┘
```

## 3. 核心组件

### 3.1 因子表达式语言

#### 语法定义

```bnf
expression  → term (('+' | '-') term)*
term        → factor_expr (('*' | '/') factor_expr)*
factor_expr → '(' expression ')'
            | FUNC_NAME '(' expression ')'
            | FACTOR_NAME
            | NUMBER

FACTOR_NAME → [a-z][a-z0-9_]*     (对应 StockSnapshot 字段名或已注册因子名)
FUNC_NAME   → 'abs' | 'log' | 'sign' | 'max' | 'min' | 'rank' | 'zscore'
NUMBER      → [0-9]+('.'[0-9]+)?
```

#### 支持的运算符

| 运算符 | 语义 | 示例 |
|--------|------|------|
| `+` | 逐元素加 | `roa + gross_margin` |
| `-` | 逐元素减 | `close - ma_20` |
| `*` | 逐元素乘 | `earnings_growth * roe_ttm` |
| `/` | 逐元素除（除零保护） | `revenue_growth / pe_ratio` |
| `abs()` | 绝对值 | `abs(return_5d)` |
| `log()` | 自然对数（正数保护） | `log(market_cap)` |
| `sign()` | 符号函数 (-1/0/1) | `sign(macd_hist)` |
| `rank()` | 截面百分位排名 [0,1] | `rank(earnings_growth)` |
| `zscore()` | 截面 Z 标准化 | `zscore(pe_ratio)` |

#### 可用的因子名称

所有 `StockSnapshot` 的 `float` 字段均可直接引用，包括：

- **价量字段:** `close`, `open`, `high`, `low`, `volume`, `prev_close`
- **基本面字段:** `pe_ratio`, `pb_ratio`, `roe_ttm`, `ocf_ttm`, `market_cap`, `roa_ttm`, `gross_margin`, `net_margin`, `asset_turnover`, `current_ratio`, `debt_to_equity`, `pcf_ratio`, `ps_ratio`, `dividend_yield`, `earnings_growth`, `revenue_growth`
- **技术指标字段:** `return_5d`, `return_20d`, `return_60d`, `volatility_20d`, `volatility_60d`, `turnover_rate`, `avg_turnover_20d`, `rsi_14`, `macd`, `macd_signal`, `ma_5`, `ma_20`, `ma_60`, `high_20d`, `low_20d`, `atr_14`, `skewness_20d`, `illiquidity_20d`, `obv_slope_20d`

也支持已注册因子的名称（如 `roa`, `gross_margin` 等 30 个因子），系统自动映射到对应的 `StockSnapshot` 字段。

#### 示例表达式

```
earnings_growth / pe_ratio                    # 营收增速 / PE
rank(earnings_growth) - rank(pe_ratio)        # 增长排名 - 估值排名
roa * (1 + earnings_growth)                   # ROA 加权增长
log(market_cap) * sign(return_5d)             # 市值对数 × 短期方向
abs(return_60d - return_5d) / volatility_60d  # 动量分歧度 / 波动率
```

### 3.2 解析器架构

采用**递归下降解析器**，分为三层：

```
FactorExpressionLexer   → 词法分析：字符串 → Token 列表
FactorExpressionParser  → 语法分析：Token 列表 → Expr AST
FactorExpressionEvaluator → 求值：Expr AST + snapshots → dict[str, float]
```

#### AST 节点定义（Domain 层值对象）

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class LiteralExpr:
    value: float

@dataclass(frozen=True, slots=True, kw_only=True)
class FactorRefExpr:
    field_name: str          # StockSnapshot 字段名

@dataclass(frozen=True, slots=True, kw_only=True)
class BinOpExpr:
    op: str                  # '+', '-', '*', '/'
    left: Expr
    right: Expr

@dataclass(frozen=True, slots=True, kw_only=True)
class UnaryFuncExpr:
    func: str                # 'abs', 'log', 'sign', 'rank', 'zscore'
    operand: Expr

type Expr = LiteralExpr | FactorRefExpr | BinOpExpr | UnaryFuncExpr
```

#### 求值逻辑

`rank()` 和 `zscore()` 是截面函数，需要所有股票的值才能计算。求值器在遇到这两个函数时，先递归求值子表达式得到 `dict[str, float]`，再对整个截面做排名/标准化。

普通算术运算和 `abs/log/sign` 则逐股票计算。

### 3.3 IC/IR 计算

**定义：**
- **IC (Information Coefficient):** 因子值与下一期收益率的 Spearman 秩相关系数
- **IR (Information Ratio):** IC 的均值 / IC 的标准差，衡量因子预测能力的稳定性

**计算流程：**

```
for each date t in backtest_period:
    1. 计算截面因子值: factor_values = expression.evaluate(snapshots_t)
    2. 获取下期收益率: next_returns = {s: close_{t+1}/close_t - 1 for s in symbols}
    3. 计算 Spearman 秩相关: ic_t = spearman_corr(factor_values, next_returns)

IC  = mean(ic_t for all t)
IR  = IC / std(ic_t)
IC_positive_rate = count(ic_t > 0) / count(ic_t)
```

**Spearman 秩相关实现（Domain 层，纯 Python）：**

```python
def spearman_rank_correlation(x: dict[str, float], y: dict[str, float]) -> float:
    """计算两个截面数据的 Spearman 秩相关系数。"""
    common = set(x) & set(y)
    if len(common) < 3:
        return 0.0
    # 排名 → Pearson 相关
    ...
```

### 3.4 分层回测流程

**目的:** 验证因子值高低是否能区分未来收益。

**流程：**

```
for each date t in backtest_period:
    1. 计算截面因子值
    2. 按因子值排序，将股票等分为 N 组（默认 5 组）
    3. 记录每组的等权下期收益率

结果:
    - 第 1 组（因子值最低）→ 第 N 组（因子值最高）
    - 多空收益 = 第 N 组收益 - 第 1 组收益
    - 各组累计收益曲线
```

**与现有回测系统的关系：**

分层回测不使用 `BacktestAppService`（那是策略回测，含下单/撮合/结算），而是独立的轻量计算：
- 输入：每期截面因子值 + 每期各股票收益率
- 输出：分层累计收益序列

这比策略回测快 10-100 倍，适合快速因子验证。

### 3.5 因子衰减分析

**目的:** 检验因子预测力随持有期变化的模式。

**流程：**
- 计算因子值与未来 1/5/10/20/60 日收益率的 IC
- 输出 IC 衰减曲线

```
holding_periods = [1, 5, 10, 20, 60]
for each period in holding_periods:
    ic[period] = mean(spearman_corr(factor_t, return_{t→t+period}))
```

### 3.6 因子有效性评分（0-100）

**评分维度与权重：**

| 维度 | 权重 | 评分规则 |
|------|------|---------|
| IC 均值 | 30% | \|IC\| >= 0.05 → 满分，\|IC\| < 0.01 → 0 分，线性插值 |
| IR | 25% | \|IR\| >= 0.5 → 满分，\|IR\| < 0.1 → 0 分 |
| 多空年化收益 | 20% | >= 15% → 满分，< 3% → 0 分 |
| 单调性 | 15% | 各组收益严格单调 → 满分，完全无序 → 0 分 |
| IC 衰减 | 10% | 20 日 IC 保持 > 50% 的 1 日 IC → 满分 |

**评级标准：**

| 评分 | 评级 | 含义 |
|------|------|------|
| 80-100 | A | 强因子，可直接纳入策略 |
| 60-79 | B | 中等因子，建议组合使用 |
| 40-59 | C | 弱因子，仅供参考 |
| 0-39 | D | 无效因子，不建议使用 |

### 3.7 因子有效性报告

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class FactorTestReport:
    """因子测试结果报告。"""
    expression: str                    # 原始表达式
    test_period: tuple[str, str]       # 测试区间 (start_date, end_date)
    universe_count: int                # 截面股票数均值

    # IC/IR
    ic_mean: float                     # IC 均值
    ic_std: float                      # IC 标准差
    ir: float                          # IC 均值 / IC 标准差
    ic_positive_rate: float            # IC > 0 的比例
    ic_series: list[tuple[str, float]] # 每日 IC 序列 [(date, ic), ...]

    # 分层收益
    layer_count: int                   # 分层数 (默认 5)
    layer_returns: list[float]         # 各层年化收益率 (从低到高)
    long_short_return: float           # 多空年化收益 (最高层 - 最低层)
    layer_cumulative: list[list[float]] # 各层累计收益曲线

    # 单调性
    monotonicity_score: float          # 0-1，完美单调=1

    # 因子衰减
    decay_periods: list[int]           # 持有期列表 [1, 5, 10, 20, 60]
    decay_ics: list[float]             # 各持有期的 IC

    # 综合评分
    score: float                       # 0-100
    grade: str                         # A/B/C/D
    grade_reasons: list[str]           # 各维度得分说明
```

## 4. 分层设计

遵循项目 DDD 分层原则：

### Domain 层（纯 Python，无第三方依赖）

| 文件 | 职责 |
|------|------|
| `src/domain/strategy/factor_test/expressions.py` | AST 节点定义 (Expr 类型联合) |
| `src/domain/strategy/factor_test/lexer.py` | 词法分析器 |
| `src/domain/strategy/factor_test/parser.py` | 递归下降语法分析器 |
| `src/domain/strategy/factor_test/evaluator.py` | 表达式求值器 |
| `src/domain/strategy/factor_test/scorer.py` | 因子有效性评分 (0-100) |
| `src/domain/strategy/factor_test/report.py` | FactorTestReport 值对象 |

### Infrastructure 层（可使用 numpy/pandas）

| 文件 | 职责 |
|------|------|
| `src/infrastructure/factor_test/ic_calculator.py` | IC/IR 计算引擎 |
| `src/infrastructure/factor_test/layer_backtest.py` | 分层回测引擎 |
| `src/infrastructure/factor_test/decay_analyzer.py` | 因子衰减分析 |
| `src/infrastructure/factor_test/test_runner.py` | 测试编排器（串联所有组件） |

### Interface 层

| 文件 | 职责 |
|------|------|
| `src/interfaces/cli/factor_test.py` | CLI 入口 |

## 5. CLI 设计

```bash
# 基本用法
python -m src.interfaces.cli.factor_test "earnings_growth / pe_ratio" \
    --start 2023-01-01 --end 2024-12-31

# 指定分层数和 Top N
python -m src.interfaces.cli.factor_test "rank(earnings_growth) - rank(pe_ratio)" \
    --start 2023-01-01 --end 2024-12-31 --layers 10 --top-n 20

# 输出 JSON 报告
python -m src.interfaces.cli.factor_test "roa * (1 + earnings_growth)" \
    --start 2023-01-01 --end 2024-12-31 --output report.json

# 批量测试（从文件读取多个表达式）
python -m src.interfaces.cli.factor_test --batch expressions.txt \
    --start 2023-01-01 --end 2024-12-31
```

### 输出示例

```
=== 因子测试报告 ===
表达式:   earnings_growth / pe_ratio
测试区间: 2023-01-01 ~ 2024-12-31
截面均值: 2,847 只股票

--- IC/IR ---
IC 均值:         0.0382
IC 标准差:       0.0914
IR:              0.418
IC > 0 占比:     62.3%

--- 分层收益 ---
第 1 组 (最低):  年化  3.2%
第 2 组:         年化  7.8%
第 3 组:         年化 11.5%
第 4 组:         年化 14.2%
第 5 组 (最高):  年化 18.7%
多空收益:        年化 15.5%

--- 单调性 ---
单调性得分: 0.85 / 1.00

--- 因子衰减 ---
 1 日 IC: 0.0382
 5 日 IC: 0.0341
10 日 IC: 0.0298
20 日 IC: 0.0215
60 日 IC: 0.0103

=== 综合评分: 72 / 100 (B) ===
  IC 均值 (30%):  24/30  |IC|=0.038, 高于 0.03 阈值
  IR (25%):       18/25  |IR|=0.418, 中等稳定性
  多空收益 (20%): 16/20  年化 15.5%, 表现良好
  单调性 (15%):   13/15  得分 0.85, 接近单调
  衰减 (10%):      1/10  20日IC衰减 44%, 保留不足 50%

建议: 中等因子，可作为多因子组合的组成部分。
```

## 6. 数据流

```
                     ┌──────────────────────┐
                     │ HistoryDataFetcher    │ 拉取历史行情
                     │ (已有)               │
                     └──────────┬───────────┘
                                │ bars per symbol
                                ▼
                     ┌──────────────────────┐
                     │ FeaturePipeline       │ 计算技术指标
                     │ (已有)               │
                     └──────────┬───────────┘
                                │ list[StockSnapshot] per date
                                ▼
┌──────────────┐    ┌──────────────────────┐
│ Expression   │◄───│ TestRunner           │ 编排器
│ Parser +     │    │ (新)                 │
│ Evaluator    │    │                      │
│ (新)         │    │  for each date:      │
└──────────────┘    │    1. evaluate expr   │
                    │    2. compute IC      │
                    │    3. layer backtest   │
                    └──────────┬───────────┘
                               │
                    ┌──────────┴───────────┐
                    ▼                      ▼
         ┌──────────────┐      ┌──────────────────┐
         │ IC Calculator │      │ Layer Backtest   │
         │ (新)          │      │ (新)              │
         └──────┬───────┘      └────────┬─────────┘
                │                       │
                ▼                       ▼
         ┌──────────────────────────────────┐
         │        Scorer (新)               │
         │  IC/IR + 分层 + 单调性 + 衰减     │
         │  → 0-100 评分                    │
         └──────────────┬──────────────────┘
                        │
                        ▼
              ┌──────────────────┐
              │ FactorTestReport │
              │ (新)              │
              └──────────────────┘
```

## 7. 关键设计决策

### 7.1 为什么不用 BacktestAppService 做分层回测？

`BacktestAppService` 是策略回测：建仓 → 撮合 → 结算 → 快照。分层回测只需要"因子排序 → 分组 → 计算收益"，不涉及下单撮合。用轻量计算替代，速度快 100 倍，更适合快速迭代。

### 7.2 为什么表达式求值在 Domain 层？

表达式求值是纯函数：输入 `list[StockSnapshot]`，输出 `dict[str, float]`。无副作用、无外部依赖，符合 Domain 层职责。IC/IR 计算需要跨日期的时间序列分析，涉及 numpy，放在 Infrastructure 层。

### 7.3 为什么用递归下降而不是 ast.literal_eval 或 eval()？

- `eval()` 有安全风险
- `ast.literal_eval` 不支持自定义运算符和函数
- 递归下降解析器完全可控，可扩展（未来支持条件表达式、时序算子等），且是纯 Python 标准库实现

### 7.4 因子衰减为什么需要多次回测？

因子衰减需要计算不同持有期（1/5/10/20/60 日）的 IC。每次持有期的下期收益率不同，需要独立计算。但因子值只计算一次，IC 计算部分可以复用。

## 8. 文件结构

### 新增文件

| 文件 | 层 | 职责 |
|------|------|------|
| `src/domain/strategy/factor_test/__init__.py` | domain | 包初始化 |
| `src/domain/strategy/factor_test/expressions.py` | domain | AST 节点定义 |
| `src/domain/strategy/factor_test/lexer.py` | domain | 词法分析器 |
| `src/domain/strategy/factor_test/parser.py` | domain | 递归下降解析器 |
| `src/domain/strategy/factor_test/evaluator.py` | domain | 表达式求值器 |
| `src/domain/strategy/factor_test/scorer.py` | domain | 综合评分器 |
| `src/domain/strategy/factor_test/report.py` | domain | FactorTestReport 值对象 |
| `src/domain/strategy/factor_test/field_mapping.py` | domain | 因子名→字段名映射 |
| `src/infrastructure/factor_test/__init__.py` | infra | 包初始化 |
| `src/infrastructure/factor_test/ic_calculator.py` | infra | IC/IR 计算 |
| `src/infrastructure/factor_test/layer_backtest.py` | infra | 分层回测 |
| `src/infrastructure/factor_test/decay_analyzer.py` | infra | 因子衰减分析 |
| `src/infrastructure/factor_test/test_runner.py` | infra | 测试编排器 |
| `src/interfaces/cli/factor_test.py` | interface | CLI 入口 |
| `tests/domain/strategy/factor_test/__init__.py` | test | 测试包 |
| `tests/domain/strategy/factor_test/test_lexer.py` | test | 词法分析器测试 |
| `tests/domain/strategy/factor_test/test_parser.py` | test | 解析器测试 |
| `tests/domain/strategy/factor_test/test_evaluator.py` | test | 求值器测试 |
| `tests/domain/strategy/factor_test/test_scorer.py` | test | 评分器测试 |
| `tests/infrastructure/factor_test/__init__.py` | test | 测试包 |
| `tests/infrastructure/factor_test/test_ic_calculator.py` | test | IC 计算测试 |
| `tests/infrastructure/factor_test/test_layer_backtest.py` | test | 分层回测测试 |
| `tests/infrastructure/factor_test/test_decay_analyzer.py` | test | 衰减分析测试 |
| `tests/infrastructure/factor_test/test_runner.py` | test | 编排器集成测试 |

### 不修改现有文件

本功能为纯新增，不修改任何现有文件。所有 30 个已有因子的 `compute()` 方法保持不变，新工具通过 `StockSnapshot` 字段直接读取原始值。

## 9. 依赖关系

```
Domain 层因子测试工具
  ├── 依赖: StockSnapshot (已有)
  ├── 依赖: FactorScorer.percentile_rank (已有，用于 rank() 函数)
  └── 不依赖: 任何第三方库

Infrastructure 层因子测试引擎
  ├── 依赖: Domain 层因子测试工具
  ├── 依赖: IHistoryDataFetcher (已有)
  ├── 依赖: FeaturePipeline (已有)
  ├── 依赖: FundamentalRegistry (已有)
  └── 依赖: numpy (已有项目依赖)

Interface 层 CLI
  ├── 依赖: Infrastructure 层因子测试引擎
  └── 依赖: argparse (标准库)
```

## 10. 验收标准

1. 表达式解析: `"earnings_growth / pe_ratio"` 正确解析并求值
2. 基本运算: `+`, `-`, `*`, `/` 对截面数据正确计算
3. 函数支持: `abs()`, `log()`, `sign()`, `rank()`, `zscore()` 正确工作
4. 除零保护: 分母为 0 的股票被排除，不报错
5. IC 计算: 与手工计算结果一致（精度 1e-6）
6. 分层回测: 5 组分层，各组收益可复现
7. 评分系统: 0-100 分，评级 A/B/C/D 正确
8. CLI 可用: `python -m src.interfaces.cli.factor_test "expr" --start ... --end ...` 正常运行
9. 测试覆盖: domain 层测试不使用 mock，infrastructure 层测试可 mock 数据源
10. 性能: 3000 只股票 × 500 个交易日，单因子测试 < 60 秒
11. 全部现有测试不被破坏
12. ruff lint 通过
