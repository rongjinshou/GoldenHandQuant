try:
    from rich.console import Console
    from rich.table import Table
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from src.domain.backtest.entities.comparison_report import ComparisonReport


class ComparisonRichPrinter:
    """多策略对比报告终端输出。"""

    def print(self, report: ComparisonReport) -> None:
        if HAS_RICH:
            self._print_rich(report)
        else:
            self._print_plain(report)

    def _print_rich(self, report: ComparisonReport) -> None:
        console = Console()
        names = [row.strategy_name for row in report.metric_table]

        console.print()
        console.print("=" * 70, style="bold")
        console.print("              STRATEGY COMPARISON REPORT", style="bold")
        console.print("=" * 70, style="bold")

        if report.reports:
            r0 = report.reports[0]
            console.print(
                f"Date Range: {r0.start_date.strftime('%Y-%m-%d')} to "
                f"{r0.end_date.strftime('%Y-%m-%d')} | "
                f"Capital: {r0.initial_capital:,.0f}"
            )
        console.print("=" * 70, style="bold")
        console.print()

        # 指标对比表
        table = Table(title="Performance Metrics", show_lines=True)
        table.add_column("Metric", style="bold", min_width=18)
        for name in names:
            table.add_column(name, justify="right", min_width=12)
        table.add_column("Best", justify="left", min_width=12)

        # 定义行
        metric_rows = [
            ("Total Return", "total_return", True, "{:.2%}"),
            ("Annualized", "annualized_return", True, "{:.2%}"),
            ("Max Drawdown", "max_drawdown", False, "{:.2%}"),
            ("Sharpe Ratio", "sharpe_ratio", True, "{:.2f}"),
            ("Sortino Ratio", "sortino_ratio", True, "{:.2f}"),
            ("Calmar Ratio", "calmar_ratio", True, "{:.2f}"),
            ("Win Rate", "win_rate", True, "{:.2%}"),
            ("Trade Count", "trade_count", None, "{:d}"),
            ("Turnover Rate", "turnover_rate", None, "{:.4%}"),
        ]

        for label, attr, higher_better, fmt in metric_rows:
            row_data = [label]
            values = [getattr(m, attr) for m in report.metric_table]
            for v in values:
                if attr == "trade_count":
                    row_data.append(fmt.format(int(v)))
                else:
                    row_data.append(fmt.format(v))

            if higher_better is True:
                best_val = max(values)
                best_idx = values.index(best_val)
                row_data.append(names[best_idx])
            elif higher_better is False:
                best_val = min(v for v in values if v > 0) if any(v > 0 for v in values) else 0
                best_idx = values.index(best_val) if best_val > 0 else 0
                if all(v == 0 for v in values):
                    row_data.append("-")
                else:
                    row_data.append(names[best_idx])
            else:
                row_data.append("-")

            table.add_row(*row_data)

        console.print(table)
        console.print()

        # 相关性矩阵
        if len(names) > 1:
            corr_table = Table(title="Correlation Matrix", show_lines=True)
            corr_table.add_column("", style="bold", min_width=12)
            for name in names:
                corr_table.add_column(name, justify="right", min_width=12)

            for i, name in enumerate(names):
                row = [name]
                for j in range(len(names)):
                    row.append(f"{report.correlation_matrix[i][j]:.2f}")
                corr_table.add_row(*row)

            console.print(corr_table)
            console.print()

        # 推荐组合
        combo = report.recommended_combo
        if len(combo) > 1:
            # 计算组合相关系数
            idx_a = names.index(combo[0])
            idx_b = names.index(combo[1])
            corr_val = report.correlation_matrix[idx_a][idx_b]
            sharpe_sum = sum(
                next(m.sharpe_ratio for m in report.metric_table if m.strategy_name == n)
                for n in combo
            )
            console.print(
                f"Recommended Combo: [{', '.join(combo)}] "
                f"(low correlation: {corr_val:.2f}, combined Sharpe: {sharpe_sum:.2f})",
                style="bold green",
            )
        else:
            console.print(
                f"Recommended: {combo[0]} (single best strategy, all pairs highly correlated)",
                style="bold yellow",
            )

        console.print("=" * 70, style="bold")

    def _print_plain(self, report: ComparisonReport) -> None:
        names = [row.strategy_name for row in report.metric_table]
        print()
        print("=" * 70)
        print("              STRATEGY COMPARISON REPORT")
        print("=" * 70)

        if report.reports:
            r0 = report.reports[0]
            print(f"Date Range: {r0.start_date.strftime('%Y-%m-%d')} to "
                  f"{r0.end_date.strftime('%Y-%m-%d')} | "
                  f"Capital: {r0.initial_capital:,.0f}")
        print("=" * 70)
        print()

        # 指标表
        header = f"{'Metric':<18}" + "".join(f"{n:>14}" for n in names) + "    Best"
        print(header)
        print("-" * len(header))

        metric_rows = [
            ("Total Return", "total_return", True, "{:.2%}"),
            ("Annualized", "annualized_return", True, "{:.2%}"),
            ("Max Drawdown", "max_drawdown", False, "{:.2%}"),
            ("Sharpe Ratio", "sharpe_ratio", True, "{:.2f}"),
            ("Sortino Ratio", "sortino_ratio", True, "{:.2f}"),
            ("Calmar Ratio", "calmar_ratio", True, "{:.2f}"),
            ("Win Rate", "win_rate", True, "{:.2%}"),
            ("Trade Count", "trade_count", None, "{:d}"),
            ("Turnover Rate", "turnover_rate", None, "{:.4%}"),
        ]

        for label, attr, higher_better, fmt in metric_rows:
            values = [getattr(m, attr) for m in report.metric_table]
            line = f"{label:<18}"
            for v in values:
                if attr == "trade_count":
                    line += f"{fmt.format(int(v)):>14}"
                else:
                    line += f"{fmt.format(v):>14}"

            if higher_better is True:
                best_val = max(values)
                best_idx = values.index(best_val)
                line += f"    {names[best_idx]}"
            elif higher_better is False:
                best_val = min(v for v in values if v > 0) if any(v > 0 for v in values) else 0
                if all(v == 0 for v in values):
                    line += "    -"
                else:
                    line += f"    {names[values.index(best_val)]}"
            else:
                line += "    -"
            print(line)

        print()

        # 相关性矩阵
        if len(names) > 1:
            print("Correlation Matrix:")
            header = f"{'':>12}" + "".join(f"{n:>14}" for n in names)
            print(header)
            for i, name in enumerate(names):
                row = f"{name:>12}"
                for j in range(len(names)):
                    row += f"{report.correlation_matrix[i][j]:>14.2f}"
                print(row)
            print()

        # 推荐组合
        combo = report.recommended_combo
        if len(combo) > 1:
            idx_a = names.index(combo[0])
            idx_b = names.index(combo[1])
            corr_val = report.correlation_matrix[idx_a][idx_b]
            sharpe_sum = sum(
                next(m.sharpe_ratio for m in report.metric_table if m.strategy_name == n)
                for n in combo
            )
            print(f"Recommended Combo: [{', '.join(combo)}] "
                  f"(low correlation: {corr_val:.2f}, combined Sharpe: {sharpe_sum:.2f})")
        else:
            print(f"Recommended: {combo[0]} (single best strategy)")

        print("=" * 70)
