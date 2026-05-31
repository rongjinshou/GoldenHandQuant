# 统一投研 CLI — 实现计划

**文档版本**: v1.0
**创建日期**: 2026-05-31
**关联设计**: `2026-05-31-unified-research-cli-design.md`
**状态**: 待开始

---

## Task 概览

| # | Task | 依赖 | 预估文件数 |
|---|------|------|-----------|
| 1 | 创建子命令目录和 `__init__.py` | 无 | 1 |
| 2 | 实现 `strategy_matcher.py`（关键词匹配） | 无 | 1 |
| 3 | 实现 `commands/backtest.py`（包装回测） | Task 1 | 1 |
| 4 | 实现 `commands/live.py`（包装半自动交易） | Task 1 | 1 |
| 5 | 实现 `commands/research.py`（自然语言投研） | Task 2, 3 | 1 |
| 6 | 实现 `quant.py` 统一入口 + pyproject.toml 注册 | Task 2-5 | 2 |
| 7 | 实现 `commands/compare.py` 和 `commands/factor_test.py` | Task 1 | 2 |
| 8 | 端到端验证 + 补充测试 | Task 1-7 | 2 |

---

## Task 1: 创建子命令目录

**文件**:
- `src/interfaces/cli/commands/__init__.py`（新建，空文件）

**验证标准**:
- 目录存在，`__init__.py` 可被 import
- `python -c "from src.interfaces.cli.commands import __init__"` 不报错

---

## Task 2: 实现关键词匹配模块

**文件**:
- `src/interfaces/cli/strategy_matcher.py`（新建）

**实现内容**:
- `KEYWORD_MAP` 字典：关键词 → 策略注册名
- `match_strategy(idea: str) -> str | None` 函数
- `format_available_strategies() -> str` 辅助函数（格式化可用策略列表）

**验证标准**:
- `match_strategy("微盘价值")` 返回 `"micro_value"`
- `match_strategy("多因子选股")` 返回 `"multi_factor"`
- `match_strategy("双均线金叉")` 返回 `"dual_ma"`
- `match_strategy("未知想法xyz")` 返回 `None`
- `ruff check src/interfaces/cli/strategy_matcher.py` 无错误

---

## Task 3: 实现 `commands/backtest.py`

**文件**:
- `src/interfaces/cli/commands/backtest.py`（新建）

**实现内容**:
- `run_backtest(args: argparse.Namespace) -> None` 函数
- 参数：`--strategy`（必填）、`--config`、`--start-date`、`--end-date`、`--plot`
- 加载 YAML 配置（`load_backtest_config`），CLI 参数覆盖 YAML 值
- 调用 `BacktestAppService.run_backtest()`（与 `run_backtest.py` 相同的服务）
- 输出 `BacktestReport` 终端摘要

**核心逻辑**（从 `run_backtest.py` 提取，不复制）:
- 导入并调用 `BacktestAppService`、`MockMarketGateway`、`MockTradeGateway` 等
- 处理 `cross_section` 策略的 `FundamentalRegistry` 初始化
- 处理 `bar` 策略的简单模式

**验证标准**:
- `quant backtest --strategy dual_ma --config resources/backtest.yaml` 可正常执行
- 输出包含 `Total Return`、`Annualized Return`、`Max Drawdown` 等指标
- `ruff check src/interfaces/cli/commands/backtest.py` 无错误

---

## Task 4: 实现 `commands/live.py`

**文件**:
- `src/interfaces/cli/commands/live.py`（新建）

**实现内容**:
- `run_live(args: argparse.Namespace) -> None` 函数
- 参数：`--strategy`、`--symbols`、`--config`（默认 `resources/trading.yaml`）
- 直接调用 `live_trade.py` 的 `main()` 逻辑，或提取其核心为可复用函数

**实现策略**: 由于 `live_trade.py` 的 `main()` 已经是完整的交互式流程（信号扫描 → 用户确认 → 下单），最简方案是提取其参数解析后的核心逻辑为独立函数，`commands/live.py` 负责参数转换后调用。

**验证标准**:
- `quant live --strategy dual_ma --symbols 600000.SH` 参数解析正确
- 不连接 QMT 时应有明确的错误提示
- `ruff check src/interfaces/cli/commands/live.py` 无错误

---

## Task 5: 实现 `commands/research.py`

**文件**:
- `src/interfaces/cli/commands/research.py`（新建）

**实现内容**:
- `run_research(args: argparse.Namespace) -> None` 函数
- 参数：`--idea`（必填）、`--period`（默认 `"2020-2025"`）、`--config`、`--plot`
- 调用 `match_strategy(idea)` 匹配策略
- 匹配成功：解析 period 为 start_date/end_date，调用 `commands/backtest.py` 的回测逻辑
- 匹配失败：输出可用策略列表，提示用 `--strategy` 手动指定

**period 解析规则**:
- `"2020-2025"` → `start="2020-01-01"`, `end="2025-12-31"`
- `"20200101-20251231"` → `start="2020-01-01"`, `end="2025-12-31"`
- `"3y"` → 最近 3 年（`end=今天`, `start=3年前`）

**验证标准**:
- `quant research --idea "微盘价值" --period 2020-2025` 匹配 `micro_value` 并执行回测
- `quant research --idea "未知策略" --period 2020-2025` 输出可用策略列表
- `ruff check src/interfaces/cli/commands/research.py` 无错误

---

## Task 6: 实现统一入口 `quant.py` + pyproject.toml 注册

**文件**:
- `src/interfaces/cli/quant.py`（新建）
- `pyproject.toml`（修改，添加 `[project.scripts]`）

**实现内容**:
- `build_parser() -> argparse.ArgumentParser` 函数：定义所有子命令和参数
- `main() -> None` 函数：解析参数，`match/case` 分发到对应 `commands/` 模块
- `quant list` 子命令：直接调用 `list_strategies()` 输出

**pyproject.toml 修改**:
```toml
[project.scripts]
quant = "src.interfaces.cli.quant:main"
```

**验证标准**:
- `python -m src.interfaces.cli.quant --help` 显示子命令列表
- `python -m src.interfaces.cli.quant list` 输出已注册策略
- `python -m src.interfaces.cli.quant research --help` 显示参数说明
- `ruff check src/interfaces/cli/quant.py` 无错误

---

## Task 7: 实现 `compare.py` 和 `factor_test.py`

**文件**:
- `src/interfaces/cli/commands/compare.py`（新建）
- `src/interfaces/cli/commands/factor_test.py`（新建）

**实现内容**:
- `run_compare(args)` — 参数解析后调用 `StrategyComparisonAppService`（待 Task 完成后对接）
- `run_factor_test(args)` — 参数解析后调用 `FactorTestAppService`（待实现）
- 初期可为 stub 实现（打印 "Coming soon"），待对应 AppService 就绪后填充

**验证标准**:
- `quant compare --strategies a,b` 不报错（stub 提示）
- `quant factor-test --factors pb_value` 不报错（stub 提示）
- `ruff check` 无错误

---

## Task 8: 端到端验证 + 补充测试

**文件**:
- `tests/interfaces/cli/test_quant.py`（新建）
- `tests/interfaces/cli/test_strategy_matcher.py`（新建）

**测试内容**:
- `test_strategy_matcher.py`:
  - 测试各关键词匹配正确
  - 测试无法匹配返回 None
- `test_quant.py`:
  - 测试 `build_parser()` 返回正确的 parser
  - 测试 `quant list` 子命令调用
  - 测试 `quant backtest` 参数解析

**验证标准**:
- `python -m pytest tests/interfaces/cli/ -v` 全部通过
- `ruff check src/interfaces/cli/` 无错误
- `python -m src.interfaces.cli.quant research --idea "微盘价值" --period 2020-2025` 端到端可执行
- `python -m src.interfaces.cli.quant backtest --strategy dual_ma` 端到端可执行

---

## 依赖关系图

```
Task 1 ──┬──→ Task 3 ──┬──→ Task 5 ──→ Task 6 ──→ Task 8
         │              │
         ├──→ Task 4 ──┘
         │
         └──→ Task 7

Task 2 ──┘ (独立，可并行)
```

**推荐执行顺序**: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

---

## 完成标准

- [ ] `quant list` 输出所有已注册策略
- [ ] `quant research --idea "微盘价值" --period 2020-2025` 端到端执行
- [ ] `quant backtest --strategy dual_ma` 端到端执行
- [ ] `quant live --strategy dual_ma` 参数解析正确
- [ ] `quant compare --strategies a,b` stub 不报错
- [ ] `quant factor-test --factors pb_value` stub 不报错
- [ ] 所有新文件 `ruff check` 通过
- [ ] 新增测试全部通过
- [ ] 现有 `python -m src.interfaces.cli.run_backtest` 仍可用（向后兼容）
