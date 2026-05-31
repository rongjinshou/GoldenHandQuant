try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from src.domain.backtest.entities.comparison_report import ComparisonReport


class ComparisonPlotter:
    """多策略对比可视化工具。"""

    def plot(self, report: ComparisonReport, show: bool = True, save_path: str | None = None) -> None:
        if not HAS_MATPLOTLIB:
            print("Warning: matplotlib is not installed. Skipping comparison plot.")
            return

        if not report.aligned_dates:
            print("Warning: No aligned data to plot.")
            return

        try:
            plt.style.use('bmh')
        except OSError:
            pass

        names = list(report.aligned_equity_curves.keys())
        colors = plt.cm.tab10.colors

        fig, axes = plt.subplots(4, 1, figsize=(14, 16), sharex=True)

        # Panel 1: 收益曲线叠加（归一化净值）
        ax1 = axes[0]
        for idx, name in enumerate(names):
            curve = report.aligned_equity_curves[name]
            color = colors[idx % len(colors)]
            label_suffix = " (Best)" if name == report.best_by_sharpe else ""
            ax1.plot(report.aligned_dates, curve, label=f"{name}{label_suffix}",
                     color=color, linewidth=0.8)
        ax1.axhline(y=1.0, color='black', linestyle='--', linewidth=0.5)
        ax1.set_title('Normalized Equity Curves')
        ax1.set_ylabel('NAV (initial = 1.0)')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)

        # Panel 2: 回撤曲线叠加
        ax2 = axes[1]
        for idx, name in enumerate(names):
            curve = report.aligned_equity_curves[name]
            color = colors[idx % len(colors)]
            drawdowns = []
            peak = curve[0] if curve else 1.0
            for v in curve:
                if v > peak:
                    peak = v
                dd = (peak - v) / peak if peak > 0 else 0
                drawdowns.append(-dd)
            ax2.fill_between(report.aligned_dates, drawdowns, 0,
                             color=color, alpha=0.2, label=name)
            ax2.plot(report.aligned_dates, drawdowns, color=color, linewidth=0.6)
        ax2.set_title('Drawdown')
        ax2.set_ylabel('Drawdown')
        ax2.legend(loc='lower left')
        ax2.grid(True, alpha=0.3)

        # Panel 3: 滚动夏普比率（120 日窗口）
        ax3 = axes[2]
        window = 120
        for idx, name in enumerate(names):
            r = next(rp for rp in report.reports if rp.strategy_name == name)
            color = colors[idx % len(colors)]
            if len(r.daily_returns) >= window:
                rolling_sharpe = []
                for i in range(window, len(r.daily_returns)):
                    window_rets = r.daily_returns[i - window:i]
                    mean_r = sum(window_rets) / len(window_rets)
                    var_r = sum((x - mean_r) ** 2 for x in window_rets) / (len(window_rets) - 1)
                    std_r = var_r ** 0.5 if var_r > 0 else 0.0
                    sharpe = (mean_r / std_r) * (252 ** 0.5) if std_r > 0 else 0.0
                    rolling_sharpe.append(sharpe)
                rolling_dates = r.dates[window:]
                if len(rolling_dates) > len(rolling_sharpe):
                    rolling_dates = rolling_dates[:len(rolling_sharpe)]
                ax3.plot(rolling_dates, rolling_sharpe, label=name,
                         color=color, linewidth=0.6)
        ax3.axhline(y=0, color='black', linewidth=0.5)
        ax3.set_title(f'Rolling Sharpe Ratio ({window}-day window)')
        ax3.set_ylabel('Sharpe')
        ax3.legend(loc='upper left')
        ax3.grid(True, alpha=0.3)

        # Panel 4: 相关性热力图
        ax4 = axes[3]
        n = len(names)
        if n > 1:
            corr = report.correlation_matrix
            im = ax4.imshow(corr, cmap='RdYlBu_r', vmin=-1, vmax=1, aspect='auto')
            ax4.set_xticks(range(n))
            ax4.set_yticks(range(n))
            ax4.set_xticklabels(names, rotation=45, ha='right')
            ax4.set_yticklabels(names)
            for i in range(n):
                for j in range(n):
                    ax4.text(j, i, f"{corr[i][j]:.2f}", ha='center', va='center',
                             color='black', fontsize=9)
            ax4.set_title('Correlation Matrix')
            fig.colorbar(im, ax=ax4, shrink=0.8)
        else:
            ax4.text(0.5, 0.5, "Single strategy - no correlation", ha='center', va='center')
            ax4.set_title('Correlation Matrix')

        fig.autofmt_xdate()
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Comparison chart saved to: {save_path}")

        if show:
            plt.show()
        else:
            plt.close(fig)
