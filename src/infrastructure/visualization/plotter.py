try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from datetime import datetime

from src.domain.backtest.entities.backtest_report import BacktestReport


class BacktestPlotter:
    """回测结果可视化工具。"""

    def plot(self, report: BacktestReport, benchmark_data: list[float] | None = None,
             benchmark_dates: list[datetime] | None = None, show: bool = True) -> None:
        if not HAS_MATPLOTLIB:
            print("Warning: matplotlib is not installed.")
            return

        if not report.dates or not report.equity_curve:
            print("Warning: No data to plot.")
            return

        try:
            plt.style.use('bmh')
        except OSError:
            pass

        has_benchmark = benchmark_data is not None and benchmark_dates is not None
        n_panels = 3

        fig, axes = plt.subplots(n_panels, 1, figsize=(14, 12), sharex=True)
        ax1, ax2, ax3 = axes[0], axes[1], axes[2]

        # Panel 1: 净值曲线
        normalized_equity = [v / report.initial_capital for v in report.equity_curve]
        ax1.plot(report.dates, normalized_equity, label='Strategy NAV', color='blue', linewidth=0.8)
        if has_benchmark:
            normalized_benchmark = [v / benchmark_data[0] for v in benchmark_data]
            ax1.plot(benchmark_dates, normalized_benchmark, label='CSI1000', color='gray', linewidth=0.8, alpha=0.7)
        ax1.axhline(y=1.0, color='black', linestyle='--', linewidth=0.5)
        ax1.set_title(
            f'Strategy: {report.annualized_return:.2%} annual, '
            f'{report.max_drawdown:.2%} maxDD, Sharpe {report.sharpe_ratio:.2f}'
        )
        ax1.set_ylabel('NAV')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)

        # Panel 2: 每日收益率
        ax2.bar(report.dates, report.daily_returns, label='Daily Return', color='gray', alpha=0.5, width=0.8)
        ax2.axhline(0, color='black', linewidth=0.5)
        ax2.set_ylabel('Return')
        ax2.grid(True, alpha=0.3)

        # Panel 3: 回撤曲线
        drawdowns = []
        peak = report.initial_capital
        for v in report.equity_curve:
            if v > peak:
                peak = v
            dd = (peak - v) / peak if peak > 0 else 0
            drawdowns.append(-dd)
        ax3.fill_between(report.dates, drawdowns, 0, color='red', alpha=0.3, label='Drawdown')
        ax3.set_ylabel('Drawdown')
        ax3.set_xlabel('Date')
        ax3.grid(True, alpha=0.3)

        fig.autofmt_xdate()
        plt.tight_layout()

        # 打印核心指标
        print(f"Annual Return: {report.annualized_return:.2%}")
        print(f"Max Drawdown: {report.max_drawdown:.2%}")
        print(f"Sharpe Ratio: {report.sharpe_ratio:.2f}")
        print(f"Win Rate: {report.win_rate:.2%}")
        print(f"Turnover Rate: {report.turnover_rate:.2%}")
        print(f"Sortino Ratio: {report.sortino_ratio:.2f}")
        print(f"Calmar Ratio: {report.calmar_ratio:.2f}")

        if show:
            plt.show()
        else:
            plt.close(fig)
