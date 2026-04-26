try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from src.domain.backtest.entities.backtest_report import BacktestReport

class BacktestPlotter:
    """回测结果可视化工具。"""

    def plot(self, report: BacktestReport, show: bool = True) -> None:
        """绘制回测报告图表。
        
        Args:
            report: 回测报告实体。
            show: 是否显示图表。
        """
        if not HAS_MATPLOTLIB:
            print("Warning: matplotlib is not installed. Cannot plot backtest results.")
            return

        if not report.dates or not report.equity_curve:
            print("Warning: No data to plot.")
            return

        # 设置绘图风格
        try:
            plt.style.use('bmh')
        except OSError:
            pass # 如果样式不可用，使用默认
        
        # 创建画布 (2行1列)
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
        
        # 1. 绘制权益曲线
        ax1.plot(report.dates, report.equity_curve, label='Total Asset', color='blue')
        ax1.set_title('Equity Curve')
        ax1.set_ylabel('Asset Value')
        ax1.grid(True)
        ax1.legend(loc='upper left')
        
        # 2. 绘制每日收益率
        ax2.bar(report.dates, report.daily_returns, label='Daily Return', color='gray', alpha=0.6)
        ax2.set_title('Daily Returns')
        ax2.set_ylabel('Return Rate')
        ax2.axhline(0, color='black', linewidth=0.8)
        ax2.grid(True)
        
        plt.tight_layout()
        
        if show:
            plt.show()
        else:
            plt.close(fig)
