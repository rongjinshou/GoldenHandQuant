"""
获取 QMT 账户信息并组装 Hermes 投研团队任务。

使用方式:
    python -m src.interfaces.cli.fetch_account
    python -m src.interfaces.cli.fetch_account --output task.md
    python -m src.interfaces.cli.fetch_account --json
"""

import argparse
import sys
from datetime import datetime

from src.infrastructure.config.settings import load_trading_config

from .cli_utils import (
    cancel_timeout,
    check_qmt_connection,
    output_error,
    output_success,
    setup_timeout,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="获取 QMT 账户信息并组装投研任务")
    parser.add_argument(
        "--config", "-c", type=str, default="resources/trading.yaml",
        help="配置文件路径",
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="输出文件路径（默认输出到终端）",
    )
    parser.add_argument(
        "--json", "-j", action="store_true", default=False,
        help="输出 JSON 格式（供 Agent 调用）",
    )
    return parser.parse_args()


def connect_qmt(config_path: str):
    """连接 QMT 并返回 trade_gw。"""
    settings = load_trading_config(config_path)
    qmt = settings.qmt

    from src.infrastructure.gateway.qmt_trade import QmtTradeGateway

    trade_gw = QmtTradeGateway(
        path=qmt.userdata_path,
        session_id=qmt.session_id,
        account_id=qmt.account_id,
        account_type=qmt.account_type,
    )
    return trade_gw, settings


def fetch_account_info(trade_gw) -> dict:
    """获取账户资金和持仓信息。"""
    asset = trade_gw.get_asset()
    positions = trade_gw.get_positions()

    market_value = sum(pos.total_volume * pos.average_cost for pos in positions) if positions else 0.0

    account_info = {
        "account_id": trade_gw.account_id,
        "total_asset": asset.total_asset if asset else 0,
        "available_cash": asset.available_cash if asset else 0,
        "frozen_cash": asset.frozen_cash if asset else 0,
        "market_value": market_value,
        "positions": [],
    }

    for pos in positions:
        account_info["positions"].append({
            "ticker": pos.ticker,
            "total_volume": pos.total_volume,
            "available_volume": pos.available_volume,
            "average_cost": pos.average_cost,
        })

    return account_info


def assemble_task(account_info: dict, settings) -> str:
    """组装 Hermes 投研团队任务。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    today = datetime.now().strftime("%Y-%m-%d")

    # 持仓标的列表
    position_tickers = [p["ticker"] for p in account_info["positions"]]
    # 配置中的关注标的
    config_tickers = settings.live_trade.symbols if hasattr(settings, "live_trade") else []
    # 合并去重
    all_tickers = list(dict.fromkeys(position_tickers + config_tickers))

    task = f"""# 投研任务：{today} 每日投研分析

**任务发起时间**: {now}
**任务来源**: GoldenHandQuant QMT 账户

---

## 一、当前账户状态

### 资金概况
| 项目 | 金额 (¥) |
|------|---------|
| 总资产 | {account_info['total_asset']:,.2f} |
| 可用资金 | {account_info['available_cash']:,.2f} |
| 冻结资金 | {account_info['frozen_cash']:,.2f} |

### 当前持仓
"""

    if account_info["positions"]:
        task += "| 标的 | 持仓数量 | 可用数量 | 成本价 |\n"
        task += "|------|---------|---------|--------|\n"
        for pos in account_info["positions"]:
            task += (f"| {pos['ticker']} | {pos['total_volume']} "
                     f"| {pos['available_volume']} | {pos['average_cost']:.2f} |\n")
    else:
        task += "当前无持仓。\n"

    task += f"""
### 关注标的
{', '.join(all_tickers) if all_tickers else '无'}

---

## 二、投研任务要求

请 secretary 协调团队，对以下标的进行全面投研分析：

### 分析标的
"""

    if all_tickers:
        for ticker in all_tickers:
            task += f"- `{ticker}`\n"
    else:
        task += "- 请根据当前市场热点，选择 3-5 个值得关注的标的\n"

    task += f"""
### 分析流程（按 v2.0 工作流执行）

**第一阶段：数据采集（并行）**
- quant-scout: 采集今日行情、新闻、资金流向、龙虎榜数据
- quant-repo-scout: （可选）相关开源量化项目

**第二阶段：投资大师分析**
- quant-analyst (巴菲特): 对每个标的进行价值分析，计算内在价值

**第三阶段：政策分析（并行）**
- macro-policy-analyst (索罗斯): 今日宏观政策研判
- industry-policy-analyst (林园): 相关产业政策解读

**第四阶段：多空辩论**
- bull-researcher (费雪): 构建看多论据
- bear-researcher (伯里): 构建看空论据

**第五阶段：风险评估（三方辩论）**
- risk-aggressive (木木姐): 高收益视角
- risk-conservative (塔勒布): 风险控制视角
- risk-neutral (芒格): 平衡视角

**第六阶段：最终决策**
- portfolio-manager (达里奥): 综合所有意见，给出最终决策

**第七阶段：汇报**
- secretary: 整理所有报告，汇报给用户

### 输出要求

每个标的的最终决策必须包含：
- 评级：Buy / Overweight / Hold / Underweight / Sell
- 目标价位：¥人民币
- 建议仓位：百分比
- 止损价位：¥人民币
- 持有周期

---

## 三、特别关注

1. **持仓标的**：对当前持仓的标的，重点评估是否需要调仓
2. **可用资金**：当前可用资金 ¥{account_info['available_cash']:,.2f}，评估是否有新的买入机会
3. **风险控制**：单只标的仓位不超过总资产的 20%

---

*本任务由 GoldenHandQuant QMT 账户自动获取数据生成*
"""

    return task


def main() -> None:
    args = parse_args()

    if args.json:
        setup_timeout()
        try:
            if not check_qmt_connection():
                output_error("QMT 客户端未连接，请先启动 MiniQMT")
                sys.exit(1)

            print("正在连接 QMT...", file=sys.stderr)
            trade_gw, _settings = connect_qmt(args.config)

            print("正在获取账户信息...", file=sys.stderr)
            account_info = fetch_account_info(trade_gw)
            output_success(account_info)
        except TimeoutError:
            output_error("请求超时 (30s)")
            sys.exit(1)
        except Exception as e:
            output_error(str(e))
            sys.exit(1)
        finally:
            cancel_timeout()
    else:
        print("正在连接 QMT...", file=sys.stderr)
        try:
            trade_gw, settings = connect_qmt(args.config)
        except Exception as e:
            print(f"QMT 连接失败: {e}", file=sys.stderr)
            sys.exit(1)

        print("正在获取账户信息...", file=sys.stderr)
        account_info = fetch_account_info(trade_gw)

        print("正在组装投研任务...", file=sys.stderr)
        task = assemble_task(account_info, settings)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(task)
            print(f"任务已保存到: {args.output}", file=sys.stderr)
        else:
            print(task)


if __name__ == "__main__":
    main()
