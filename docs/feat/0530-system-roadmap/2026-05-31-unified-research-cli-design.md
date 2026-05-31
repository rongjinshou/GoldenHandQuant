# 统一投研 CLI — 设计文档

**文档版本**: v1.0
**创建日期**: 2026-05-31
**文档类型**: 详细设计 / 技术方案
**状态**: 草案

---

## 一、需求概述

### 1.1 用户故事

> 作为量化研究员，我希望通过一条命令完成"选股 → 回测 → 报告"全流程，
> 而不是分别运行 `run_backtest.py`、`live_trade.py`、`compare_strategies.py` 等独立脚本。
> 输入自然语言描述（如"微盘价值"），系统自动匹配策略、执行回测、输出报告。

### 1.2 核心能力

| # | 能力 | 优先级 |
|---|------|--------|
| 1 | 统一入口 `quant`，子命令分发 | P0 |
| 2 | `quant research` — 自然语言 → 策略匹配 → 回测 → 报告 | P0 |
| 3 | `quant backtest` — 直接回测（包装现有 `run_backtest.py`） | P0 |
| 4 | `quant live` — 半自动交易（包装现有 `live_trade.py`） | P0 |
| 5 | `quant compare` — 多策略对比（包装 `compare_strategies.py`） | P1 |
| 6 | `quant factor-test` — 因子测试（包装 `factor_test.py`） | P1 |
| 7 | `quant list` — 列出所有可用策略 | P2 |

---

## 二、现有 CLI 入口分析

### 2.1 现有入口盘点

| 入口文件 | 功能 | 调用方式 | CLI 框架 |
|----------|------|---------|----------|
| `src/interfaces/cli/run_backtest.py` | 单策略回测 | `python -m src.interfaces.cli.run_backtest` | 无 argparse，硬编码配置 |
| `src/interfaces/cli/live_trade.py` | 半自动交易 | `python -m src.interfaces.cli.live_trade --strategy dual_ma` | argparse |
| `src/interfaces/cli/main.py` | QMT 直接下单测试 | `python -m src.interfaces.cli.main` | 无 argparse |
| `src/interfaces/cli/batch_download.py` | 批量下载数据 | `python -m src.interfaces.cli.batch_download` | - |
| `src/interfaces/cli/data_loader.py` | 数据加载 | `python -m src.interfaces.cli.data_loader` | - |

### 2.2 策略注册表（`src/domain/strategy/registry.py`）

当前已注册 3 个策略：

| 注册名 | 类型 | 描述 |
|--------|------|------|
| `dual_ma` | bar | DualMa 双均线策略 (MA5/MA10 金叉死叉) |
| `micro_value` | cross_section | 微盘价值质量增强策略 |
| `multi_factor` | cross_section | 多因子选股策略 (30 因子) |

### 2.3 关键约束

1. **不重写底层逻辑**：统一 CLI 仅做路由和参数转换，调用现有 `BacktestAppService`、`LiveSignalService` 等。
2. **向后兼容**：现有 `python -m src.interfaces.cli.run_backtest` 仍可用。
3. **Domain 红线不变**：`src/domain/` 禁止 import 第三方库。
4. **配置文件驱动**：默认从 `resources/*.yaml` 加载，CLI 参数可覆盖。

---

## 三、CLI 架构设计

### 3.1 命令结构

```
quant
├── research      # 自然语言 → 策略匹配 → 回测 → 报告
├── backtest      # 直接回测
├── live          # 半自动交易
├── compare       # 多策略对比
├── factor-test   # 因子测试
└── list          # 列出可用策略
```

### 3.2 统一入口文件

**文件**: `src/interfaces/cli/quant.py`

采用 `argparse` 子命令模式，与 `live_trade.py` 现有风格一致。

```python
# src/interfaces/cli/quant.py

import argparse
import sys

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quant",
        description="GoldenHandQuant 统一投研 CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # --- research ---
    p_research = subparsers.add_parser("research", help="自然语言投研：选股→回测→报告")
    p_research.add_argument("--idea", type=str, required=True, help="投资想法描述")
    p_research.add_argument("--period", type=str, default="2020-2025", help="回测周期")
    p_research.add_argument("--config", type=str, default=None, help="配置文件路径")
    p_research.add_argument("--plot", action="store_true", help="显示图表")

    # --- backtest ---
    p_bt = subparsers.add_parser("backtest", help="直接回测")
    p_bt.add_argument("--strategy", "-s", type=str, required=True, help="策略名称")
    p_bt.add_argument("--config", type=str, default="resources/backtest.yaml", help="配置文件")
    p_bt.add_argument("--start-date", type=str, default=None, help="开始日期")
    p_bt.add_argument("--end-date", type=str, default=None, help="结束日期")
    p_bt.add_argument("--plot", action="store_true", help="显示图表")

    # --- live ---
    p_live = subparsers.add_parser("live", help="半自动交易")
    p_live.add_argument("--strategy", "-s", type=str, default=None, help="策略名称")
    p_live.add_argument("--symbols", type=str, default=None, help="标的列表")
    p_live.add_argument("--config", type=str, default="resources/trading.yaml", help="配置文件")

    # --- compare ---
    p_cmp = subparsers.add_parser("compare", help="多策略对比")
    p_cmp.add_argument("--strategies", type=str, required=True, help="逗号分隔的策略列表")
    p_cmp.add_argument("--start-date", type=str, default=None)
    p_cmp.add_argument("--end-date", type=str, default=None)
    p_cmp.add_argument("--plot", action="store_true")

    # --- factor-test ---
    p_ft = subparsers.add_parser("factor-test", help="因子测试")
    p_ft.add_argument("--factors", type=str, required=True, help="逗号分隔的因子列表")
    p_ft.add_argument("--start-date", type=str, default=None)
    p_ft.add_argument("--end-date", type=str, default=None)

    # --- list ---
    subparsers.add_parser("list", help="列出所有可用策略")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    match args.command:
        case "research":
            from src.interfaces.cli.commands.research import run_research
            run_research(args)
        case "backtest":
            from src.interfaces.cli.commands.backtest import run_backtest
            run_backtest(args)
        case "live":
            from src.interfaces.cli.commands.live import run_live
            run_live(args)
        case "compare":
            from src.interfaces.cli.commands.compare import run_compare
            run_compare(args)
        case "factor-test":
            from src.interfaces.cli.commands.factor_test import run_factor_test
            run_factor_test(args)
        case "list":
            from src.domain.strategy.registry import list_strategies
            for s in list_strategies():
                print(f"  {s.name:<20} [{s.strategy_type}] {s.description}")


if __name__ == "__main__":
    main()
```

### 3.3 调用方式

```bash
# 方式 1：模块调用
python -m src.interfaces.cli.quant research --idea "微盘价值" --period 2020-2025

# 方式 2：pyproject.toml 注册 console_scripts 后
quant research --idea "微盘价值" --period 2020-2025
quant backtest --strategy multi_factor --config resources/backtest.yaml
quant live --strategy dual_ma
quant compare --strategies micro_value,multi_factor,dual_ma --plot
quant factor-test --factors pb_value,roe
quant list
```

### 3.4 pyproject.toml 入口注册

```toml
[project.scripts]
quant = "src.interfaces.cli.quant:main"
```

---

## 四、自然语言到策略映射

### 4.1 关键词字典

**文件**: `src/interfaces/cli/strategy_matcher.py`

采用简单的关键词匹配，不引入 NLP 依赖。匹配规则：用户输入命中关键词即返回对应策略名。

```python
# 关键词 → 策略注册名
KEYWORD_MAP: dict[str, list[str]] = {
    # 微盘价值
    "micro_value": ["微盘", "小盘", "微盘价值", "小市值", "壳价值"],
    # 多因子
    "multi_factor": ["多因子", "因子", "基本面", "价值+质量", "综合选股", "量化选股"],
    # 双均线
    "dual_ma": ["双均线", "均线", "金叉", "死叉", "趋势跟踪", "dual_ma", "ma"],
}


def match_strategy(idea: str) -> str | None:
    """从自然语言描述匹配策略名。返回 None 表示无法匹配。"""
    idea_lower = idea.lower()
    for strategy_name, keywords in KEYWORD_MAP.items():
        for kw in keywords:
            if kw in idea_lower:
                return strategy_name
    return None
```

### 4.2 匹配失败处理

当关键词无法匹配时，CLI 输出可用策略列表，提示用户手动选择：

```
无法从 "xxx" 匹配到策略。可用策略：
  1. dual_ma       — DualMa 双均线策略
  2. micro_value   — 微盘价值质量增强策略
  3. multi_factor  — 多因子选股策略
请使用 --strategy 参数直接指定。
```

---

## 五、`research` 子命令流程

```
用户输入: quant research --idea "微盘价值" --period 2020-2025
                    │
                    ▼
        ┌───────────────────────┐
        │  match_strategy(idea) │  关键词匹配
        │  → "micro_value"      │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │  解析 period          │  "2020-2025" → start="2020-01-01", end="2025-12-31"
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │  加载 backtest.yaml   │  合并 CLI 参数覆盖
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │  调用 BacktestAppService.run_backtest()
        │  (复用 run_backtest.py 的完整逻辑)
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │  输出 BacktestReport  │  终端表格 + 可选图表
        └───────────────────────┘
```

核心原则：`research` 子命令是 `backtest` 子命令的语法糖，增加"自然语言 → 策略匹配"步骤，其余完全复用。

---

## 六、文件结构

```
src/interfaces/cli/
├── quant.py                    # 统一入口（argparse 子命令路由）
├── strategy_matcher.py         # 自然语言 → 策略映射
├── commands/                   # 子命令实现目录
│   ├── __init__.py
│   ├── research.py             # quant research 实现
│   ├── backtest.py             # quant backtest 实现（包装 run_backtest 逻辑）
│   ├── live.py                 # quant live 实现（包装 live_trade 逻辑）
│   ├── compare.py              # quant compare 实现（包装 compare_strategies）
│   └── factor_test.py          # quant factor-test 实现
├── run_backtest.py             # 保留，向后兼容
├── live_trade.py               # 保留，向后兼容
├── main.py                     # 保留，向后兼容
└── ...                         # 其他现有文件保留
```

---

## 七、与现有 CLI 的关系

| 维度 | 现有 CLI | 统一 CLI |
|------|---------|---------|
| 入口 | `python -m src.interfaces.cli.run_backtest` | `quant backtest --strategy ...` |
| 底层逻辑 | `BacktestAppService.run_backtest()` | 同一个，不重写 |
| 配置 | `resources/backtest.yaml` 硬编码路径 | 默认同路径，`--config` 可覆盖 |
| 向后兼容 | 保留原入口不变 | 新增入口，互不影响 |

**原则**：统一 CLI 的 `commands/` 模块直接 import 并调用现有应用层服务，不复制逻辑。

---

## 八、层职责划分

| 层 | 新增组件 | 职责 |
|----|---------|------|
| Interfaces | `quant.py` | 统一 CLI 入口，子命令路由 |
| Interfaces | `strategy_matcher.py` | 关键词字典匹配 |
| Interfaces | `commands/*.py` | 各子命令参数处理 + 调用 Application 层 |
| Application | 不变 | 现有 `BacktestAppService`、`LiveSignalService` 等 |
| Domain | 不变 | 现有 `StrategyRegistry`、`BacktestReport` 等 |

统一 CLI 仅在 Interfaces 层新增文件，不修改 Application 和 Domain 层。

---

## 九、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 关键词匹配过于简单 | 用户输入"价值投资"无法命中 | 维护关键词字典，逐步扩充；匹配失败时列出可用策略 |
| 子命令 import 路径问题 | `python -m` 与 `quant` 入口路径不一致 | 统一使用 `src.` 绝对导入 |
| 现有 CLI 参数不兼容 | `run_backtest.py` 无 argparse | `commands/backtest.py` 独立实现 argparse，内部调用同一个 `BacktestAppService` |
| 配置文件合并复杂 | CLI 参数与 YAML 配置冲突 | CLI 参数优先级高于 YAML，采用显式覆盖而非深度合并 |
