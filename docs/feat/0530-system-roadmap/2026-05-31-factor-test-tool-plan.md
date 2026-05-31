# 因子快速测试工具 实现计划

> **设计文档:** `2026-05-31-factor-test-tool-design.md`
> **预估工时:** ~8 小时 | **新增文件:** 14 个源码 + 8 个测试 | **修改文件:** 0

---

## 任务总览

| Phase | Task | 描述 | 依赖 | 预估 |
|-------|------|------|------|------|
| 1 | T1 | Domain 层：AST 节点 + 词法分析器 | 无 | 1h |
| 1 | T2 | Domain 层：递归下降解析器 | T1 | 1.5h |
| 2 | T3 | Domain 层：表达式求值器 | T2 | 1h |
| 2 | T4 | Domain 层：因子名映射 | 无 | 0.5h |
| 3 | T5 | Domain 层：FactorTestReport + Scorer | T3 | 1h |
| 4 | T6 | Infrastructure 层：IC/IR 计算引擎 | T3 | 1h |
| 4 | T7 | Infrastructure 层：分层回测引擎 | T3 | 1h |
| 5 | T8 | Infrastructure 层：因子衰减分析 | T6 | 0.5h |
| 5 | T9 | Infrastructure 层：TestRunner 编排器 | T5+T6+T7+T8 | 1h |
| 6 | T10 | Interface 层：CLI 入口 | T9 | 0.5h |
| 6 | T11 | 端到端集成测试 | T10 | 0.5h |

---

## T1: Domain 层 — AST 节点 + 词法分析器

**目标:** 定义表达式 AST 节点类型和词法分析器。

**新增文件:**
- `src/domain/strategy/factor_test/__init__.py`
- `src/domain/strategy/factor_test/expressions.py`
- `src/domain/strategy/factor_test/lexer.py`

**内容:**

`expressions.py` — 4 个 AST 节点：
```python
@dataclass(frozen=True, slots=True, kw_only=True)
class LiteralExpr:
    value: float

@dataclass(frozen=True, slots=True, kw_only=True)
class FactorRefExpr:
    field_name: str

@dataclass(frozen=True, slots=True, kw_only=True)
class BinOpExpr:
    op: str  # '+', '-', '*', '/'
    left: Expr
    right: Expr

@dataclass(frozen=True, slots=True, kw_only=True)
class UnaryFuncExpr:
    func: str  # 'abs', 'log', 'sign', 'rank', 'zscore'
    operand: Expr

type Expr = LiteralExpr | FactorRefExpr | BinOpExpr | UnaryFuncExpr
```

`lexer.py` — Token 类型 + 词法分析器：
- Token 类型：NUMBER, FACTOR_NAME, FUNC_NAME, OP(+,-,*,/), LPAREN, RPAREN, EOF
- `tokenize(expr: str) -> list[Token]`
- 处理空格跳过、数字解析（含小数点）、标识符识别

**测试文件:** `tests/domain/strategy/factor_test/test_lexer.py`
- 测试数字词法分析
- 测试标识符词法分析
- 测试运算符词法分析
- 测试完整表达式词法分析

**验证:** `python -m pytest tests/domain/strategy/factor_test/test_lexer.py -v`

---

## T2: Domain 层 — 递归下降解析器

**目标:** 将 Token 列表解析为 AST。

**新增文件:**
- `src/domain/strategy/factor_test/parser.py`

**内容:**
```python
class FactorExpressionParser:
    def parse(self, tokens: list[Token]) -> Expr
```

语法规则（运算符优先级）：
1. `expression → term (('+' | '-') term)*`
2. `term → factor_expr (('*' | '/') factor_expr)*`
3. `factor_expr → '(' expression ')' | FUNC_NAME '(' expression ')' | FACTOR_NAME | NUMBER`

**测试文件:** `tests/domain/strategy/factor_test/test_parser.py`
- 测试简单因子引用：`pe_ratio` → FactorRefExpr
- 测试二元运算：`a + b` → BinOpExpr
- 测试优先级：`a + b * c` → 正确 AST
- 测试函数调用：`rank(a)` → UnaryFuncExpr
- 测试嵌套：`rank(a + b) / c`
- 测试错误输入：空表达式、不匹配括号

**验证:** `python -m pytest tests/domain/strategy/factor_test/test_parser.py -v`

---

## T3: Domain 层 — 表达式求值器

**目标:** 对 AST 求值，输出每只股票的因子值。

**新增文件:**
- `src/domain/strategy/factor_test/evaluator.py`

**内容:**
```python
class FactorExpressionEvaluator:
    def evaluate(self, expr: Expr, snapshots: list[StockSnapshot]) -> dict[str, float]:
        """返回 {symbol: factor_value}"""
```

关键逻辑：
- LiteralExpr → 常量广播到所有股票
- FactorRefExpr → 从 StockSnapshot 提取字段值
- BinOpExpr → 逐元素运算（除零保护：分母为 0 的股票排除）
- UnaryFuncExpr:
  - `abs/log/sign` → 逐股票计算
  - `rank/zscore` → 截面计算（需要所有股票的值）

**测试文件:** `tests/domain/strategy/factor_test/test_evaluator.py`
- 使用构造的 StockSnapshot 列表测试（不需要真实数据）
- 测试各种运算符和函数
- 测试除零保护
- 测试空截面处理

**验证:** `python -m pytest tests/domain/strategy/factor_test/test_evaluator.py -v`

---

## T4: Domain 层 — 因子名映射

**目标:** 将已注册的 30 个因子名映射到 StockSnapshot 字段名。

**新增文件:**
- `src/domain/strategy/factor_test/field_mapping.py`

**内容:**
```python
FACTOR_FIELD_MAP: dict[str, str] = {
    "roa": "roa_ttm",
    "gross_margin": "gross_margin",
    "roe": "roe_ttm",
    # ... 30 个因子的映射
}
```

**验证:** `python -c "from src.domain.strategy.factor_test.field_mapping import FACTOR_FIELD_MAP; print(len(FACTOR_FIELD_MAP))"`

---

## T5: Domain 层 — FactorTestReport + Scorer

**目标:** 定义报告值对象和综合评分器。

**新增文件:**
- `src/domain/strategy/factor_test/report.py`
- `src/domain/strategy/factor_test/scorer.py`

**内容:**

`report.py` — FactorTestReport 数据类（见设计文档 3.7 节）

`scorer.py` — 综合评分：
```python
class FactorScorer:
    def score(self, report: FactorTestReport) -> tuple[float, str, list[str]]:
        """返回 (score_0_100, grade_ABCD, reasons)"""
```

评分维度：IC 均值(30%) + IR(25%) + 多空收益(20%) + 单调性(15%) + IC 衰减(10%)

**测试文件:** `tests/domain/strategy/factor_test/test_scorer.py`
- 测试各维度评分
- 测试综合评分计算
- 测试评级正确性

**验证:** `python -m pytest tests/domain/strategy/factor_test/test_scorer.py -v`

---

## T6: Infrastructure 层 — IC/IR 计算引擎

**目标:** 计算因子值与未来收益的 Spearman 秩相关。

**新增文件:**
- `src/infrastructure/factor_test/__init__.py`
- `src/infrastructure/factor_test/ic_calculator.py`

**内容:**
```python
class ICCalculator:
    def calculate_ic_series(
        self,
        expression: Expr,
        snapshots_by_date: dict[str, list[StockSnapshot]],
        returns_by_date: dict[str, dict[str, float]],
    ) -> list[tuple[str, float]]:
        """返回 [(date, ic_value), ...]"""

    def calculate_ir(self, ic_series: list[float]) -> tuple[float, float, float]:
        """返回 (ic_mean, ic_std, ir)"""
```

使用 numpy 计算 Spearman 秩相关。

**测试文件:** `tests/infrastructure/factor_test/test_ic_calculator.py`
- 使用构造数据测试 IC 计算
- 测试已知相关性的数据验证正确性

**验证:** `python -m pytest tests/infrastructure/factor_test/test_ic_calculator.py -v`

---

## T7: Infrastructure 层 — 分层回测引擎

**目标:** 将股票按因子值分组，计算各组收益。

**新增文件:**
- `src/infrastructure/factor_test/layer_backtest.py`

**内容:**
```python
class LayerBacktester:
    def run(
        self,
        expression: Expr,
        snapshots_by_date: dict[str, list[StockSnapshot]],
        returns_by_date: dict[str, dict[str, float]],
        num_layers: int = 5,
    ) -> LayerBacktestResult:
        """返回分层回测结果"""
```

**测试文件:** `tests/infrastructure/factor_test/test_layer_backtest.py`
- 测试分层正确性（各组股票数大致相等）
- 测试多空收益计算

**验证:** `python -m pytest tests/infrastructure/factor_test/test_layer_backtest.py -v`

---

## T8: Infrastructure 层 — 因子衰减分析

**目标:** 计算不同持有期的 IC 衰减曲线。

**新增文件:**
- `src/infrastructure/factor_test/decay_analyzer.py`

**内容:**
```python
class DecayAnalyzer:
    def analyze(
        self,
        expression: Expr,
        snapshots_by_date: dict[str, list[StockSnapshot]],
        prices_by_date: dict[str, dict[str, float]],
        holding_periods: list[int] = [1, 5, 10, 20, 60],
    ) -> tuple[list[int], list[float]]:
        """返回 (periods, decay_ics)"""
```

复用 ICCalculator，对每个持有期独立计算。

**测试文件:** `tests/infrastructure/factor_test/test_decay_analyzer.py`

**验证:** `python -m pytest tests/infrastructure/factor_test/test_decay_analyzer.py -v`

---

## T9: Infrastructure 层 — TestRunner 编排器

**目标:** 串联所有组件，一条命令完成完整因子测试。

**新增文件:**
- `src/infrastructure/factor_test/test_runner.py`

**内容:**
```python
class FactorTestRunner:
    def run(
        self,
        expression_str: str,
        start_date: str,
        end_date: str,
        num_layers: int = 5,
        data_source: str = "tushare",
    ) -> FactorTestReport:
        """完整因子测试流程"""
```

流程：
1. 解析表达式（Lexer → Parser → Evaluator）
2. 加载历史数据（复用现有数据源）
3. 构建截面快照（复用 FeaturePipeline.build_cross_section）
4. 计算 IC/IR
5. 执行分层回测
6. 分析因子衰减
7. 综合评分
8. 返回 FactorTestReport

**测试文件:** `tests/infrastructure/factor_test/test_runner.py`
- 集成测试：使用小规模数据端到端测试

**验证:** `python -m pytest tests/infrastructure/factor_test/test_runner.py -v`

---

## T10: Interface 层 — CLI 入口

**目标:** 提供命令行接口。

**新增文件:**
- `src/interfaces/cli/factor_test.py`

**内容:**
```python
# argparse 设计
parser = argparse.ArgumentParser(description="因子快速测试工具")
parser.add_argument("expression", help="因子表达式")
parser.add_argument("--start", required=True, help="起始日期")
parser.add_argument("--end", required=True, help="结束日期")
parser.add_argument("--layers", type=int, default=5, help="分层数")
parser.add_argument("--output", help="输出 JSON 文件路径")
parser.add_argument("--batch", help="批量表达式文件")
```

输出格式：
- 默认：rich 终端表格（IC/IR/分层收益/评分）
- `--output`：JSON 格式

**验证:**
```bash
python -m src.interfaces.cli.factor_test "earnings_growth / pe_ratio" \
    --start 2023-01-01 --end 2024-12-31
```

---

## T11: 端到端集成测试

**目标:** 验证完整流程可用。

**测试场景:**
1. 简单表达式：`pe_ratio` → 应返回有效报告
2. 复合表达式：`earnings_growth / pe_ratio` → 应返回有效报告
3. 函数表达式：`rank(roe_ttm)` → 应返回有效报告
4. 错误处理：无效表达式 → 应返回明确错误
5. 批量测试：多个表达式 → 应全部返回结果

**验证:** `python -m pytest tests/ -k "factor_test" -v`

---

## 里程碑

| 里程碑 | 包含 Tasks | 验证标准 |
|--------|-----------|---------|
| M1: 解析器完成 | T1+T2+T4 | 所有解析器测试通过 |
| M2: 求值器完成 | T3 | 截面求值正确 |
| M3: 评估框架完成 | T5+T6+T7+T8 | IC/分层/衰减计算正确 |
| M4: 端到端可用 | T9+T10+T11 | CLI 可运行完整因子测试 |

---

## 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 表达式解析边界情况多 | 中 | 充分的单元测试，从简单到复杂渐进 |
| IC 计算精度问题 | 低 | 与手工计算对比验证 |
| 大规模数据性能 | 中 | 3000 股 × 500 日目标 <60s，必要时优化 |
| 数据源不可用 | 低 | 支持 mock 数据测试 |
