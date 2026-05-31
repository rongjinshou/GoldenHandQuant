"""因子快速测试工具 CLI 入口。

使用方式:
    python -m src.interfaces.cli.factor_test "earnings_growth / pe_ratio" \
        --start 2023-01-01 --end 2024-12-31
"""

import argparse
import json
import os
import sys
from datetime import datetime

# 确保项目根目录在 sys.path 中
sys.path.append(os.getcwd())


def _print_report(report) -> None:
    """终端格式化输出报告。"""
    print()
    print("=== 因子测试报告 ===")
    print(f"表达式:   {report.expression}")
    print(f"测试区间: {report.test_period[0]} ~ {report.test_period[1]}")
    print(f"截面均值: {report.universe_count:,} 只股票")
    print()

    print("--- IC/IR ---")
    print(f"IC 均值:         {report.ic_mean:.4f}")
    print(f"IC 标准差:       {report.ic_std:.4f}")
    print(f"IR:              {report.ir:.3f}")
    print(f"IC > 0 占比:     {report.ic_positive_rate:.1%}")
    print()

    print("--- 分层收益 ---")
    for i, ret in enumerate(report.layer_returns):
        label = f"第 {i + 1} 组"
        if i == 0:
            label += " (最低)"
        elif i == len(report.layer_returns) - 1:
            label += " (最高)"
        print(f"{label}:  年化 {ret:.1%}")
    print(f"多空收益:        年化 {report.long_short_return:.1%}")
    print()

    print("--- 单调性 ---")
    print(f"单调性得分: {report.monotonicity_score:.2f} / 1.00")
    print()

    print("--- 因子衰减 ---")
    for period, ic in zip(report.decay_periods, report.decay_ics):
        print(f"{period:>2} 日 IC: {ic:.4f}")
    print()

    grade_label = {"A": "强因子，可直接纳入策略", "B": "中等因子，建议组合使用",
                   "C": "弱因子，仅供参考", "D": "无效因子，不建议使用"}
    print(f"=== 综合评分: {report.score:.0f} / 100 ({report.grade}) ===")
    for reason in report.grade_reasons:
        print(f"  {reason}")
    print()
    print(f"建议: {grade_label.get(report.grade, '未知')}")


def _report_to_dict(report) -> dict:
    """将报告转为可序列化的字典。"""
    return {
        "expression": report.expression,
        "test_period": list(report.test_period),
        "universe_count": report.universe_count,
        "ic_mean": report.ic_mean,
        "ic_std": report.ic_std,
        "ir": report.ir,
        "ic_positive_rate": report.ic_positive_rate,
        "ic_series": [[d, ic] for d, ic in report.ic_series],
        "layer_count": report.layer_count,
        "layer_returns": report.layer_returns,
        "long_short_return": report.long_short_return,
        "monotonicity_score": report.monotonicity_score,
        "decay_periods": report.decay_periods,
        "decay_ics": report.decay_ics,
        "score": report.score,
        "grade": report.grade,
        "grade_reasons": report.grade_reasons,
    }


def main():
    parser = argparse.ArgumentParser(description="因子快速测试工具")
    parser.add_argument("expression", nargs="?", help="因子表达式")
    parser.add_argument("--start", required=True, help="起始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--layers", type=int, default=5, help="分层数 (默认 5)")
    parser.add_argument("--output", help="输出 JSON 文件路径")
    parser.add_argument("--batch", help="批量表达式文件（每行一个表达式）")

    args = parser.parse_args()

    if not args.expression and not args.batch:
        parser.error("必须提供 expression 或 --batch 参数")

    expressions: list[str] = []
    if args.batch:
        with open(args.batch) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    expressions.append(line)
    else:
        expressions.append(args.expression)

    # 加载数据
    from src.infrastructure.factor_test.test_runner import FactorTestRunner
    runner = FactorTestRunner()

    # 数据加载需要外部数据源，这里提供 mock 支持
    # 实际使用时通过 HistoryDataFetcher + FeaturePipeline 构建
    snapshots_by_date, returns_by_date, prices_by_date = _load_data(
        args.start, args.end
    )

    all_reports = []
    for expr_str in expressions:
        try:
            report = runner.run(
                expression_str=expr_str,
                snapshots_by_date=snapshots_by_date,
                returns_by_date=returns_by_date,
                prices_by_date=prices_by_date,
                test_period=(args.start, args.end),
                num_layers=args.layers,
            )
            all_reports.append(report)
            _print_report(report)
        except Exception as e:
            print(f"Error testing expression '{expr_str}': {e}")

    if args.output and all_reports:
        output_data = [_report_to_dict(r) for r in all_reports]
        if len(output_data) == 1:
            output_data = output_data[0]
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"报告已保存到: {args.output}")


def _load_data(start_date: str, end_date: str):
    """加载历史数据，构建截面快照和收益率。

    优先使用 TushareHistoryDataFetcher，不可用时尝试 QmtHistoryDataFetcher。
    """
    from src.domain.market.services.fundamental_registry import FundamentalRegistry
    from src.infrastructure.ml_engine.feature_pipeline import FeaturePipeline

    # 尝试加载配置
    try:
        from src.infrastructure.config.settings import load_backtest_config
        settings = load_backtest_config()
        history_fetcher_type = settings.data.history_fetcher
        tushare_token = settings.data.tushare.token
    except (FileNotFoundError, AttributeError):
        history_fetcher_type = "TushareHistoryDataFetcher"
        tushare_token = None

    # 初始化数据获取器
    if history_fetcher_type == "TushareHistoryDataFetcher":
        from src.infrastructure.gateway.tushare_fundamental_fetcher import TushareFundamentalFetcher
        from src.infrastructure.gateway.tushare_history_data import TushareHistoryDataFetcher
        fetcher = TushareHistoryDataFetcher(token=tushare_token)
        fund_fetcher = TushareFundamentalFetcher(token=tushare_token)
    else:
        from src.infrastructure.gateway.qmt_fundamental_fetcher import QmtFundamentalFetcher
        from src.infrastructure.gateway.qmt_history_data import QmtHistoryDataFetcher
        fetcher = QmtHistoryDataFetcher()
        fund_fetcher = QmtFundamentalFetcher()

    # 获取股票列表
    symbols: list[str] = []
    if history_fetcher_type != "TushareHistoryDataFetcher":
        try:
            from src.infrastructure.gateway.xtquant_client import xtdata as _xt
            for sector in ['沪深A股']:
                symbols.extend(_xt.get_stock_list_in_sector(sector))
            symbols = sorted(set(symbols))[:500]
        except Exception:
            pass

    if not symbols:
        symbols = ["000001.SZ", "000002.SZ", "600000.SH"]

    print(f"Loading data for {len(symbols)} symbols from {start_date} to {end_date}...")

    # 加载基本面数据
    fund_snapshots = fund_fetcher.fetch_by_range(start_date, end_date, symbols=symbols)
    registry = FundamentalRegistry()
    registry.load_snapshots(fund_snapshots)

    # 获取 bar 数据
    bars_by_symbol = fetcher.fetch(symbols=symbols, start_date=start_date, end_date=end_date)

    # 构建截面
    from src.domain.market.value_objects.bar import Bar
    dates = sorted({b.date.strftime("%Y-%m-%d") for bars in bars_by_symbol.values() for b in bars})

    snapshots_by_date: dict[str, list] = {}
    prices_by_date: dict[str, dict[str, float]] = {}

    for date_str in dates:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        bars_on_date: dict[str, Bar] = {}
        for symbol, bars in bars_by_symbol.items():
            for b in bars:
                if b.date.strftime("%Y-%m-%d") == date_str:
                    bars_on_date[symbol] = b
                    break

        if not bars_on_date:
            continue

        bar_history: dict[str, list[Bar]] = {}
        for symbol, bars in bars_by_symbol.items():
            hist = [b for b in bars if b.date.strftime("%Y-%m-%d") <= date_str]
            if hist:
                bar_history[symbol] = hist

        cross = FeaturePipeline.build_cross_section(
            date=dt, bars=bars_on_date, registry=registry, bar_history=bar_history
        )
        if cross:
            snapshots_by_date[date_str] = cross
            prices_by_date[date_str] = {s.symbol: s.close for s in cross}

    # 构建收益率
    returns_by_date: dict[str, dict[str, float]] = {}
    sorted_dates = sorted(prices_by_date.keys())
    for i in range(len(sorted_dates) - 1):
        d0, d1 = sorted_dates[i], sorted_dates[i + 1]
        p0, p1 = prices_by_date[d0], prices_by_date[d1]
        rets: dict[str, float] = {}
        for sym in p0:
            if sym in p1 and p0[sym] > 0:
                rets[sym] = p1[sym] / p0[sym] - 1
        if rets:
            returns_by_date[d0] = rets

    print(f"Data loaded: {len(snapshots_by_date)} trading days, "
          f"avg {sum(len(v) for v in snapshots_by_date.values()) // max(len(snapshots_by_date), 1)} stocks/day")

    return snapshots_by_date, returns_by_date, prices_by_date


if __name__ == "__main__":
    main()
