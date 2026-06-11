"""因子测试编排器：串联所有组件，完成完整因子测试。"""

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factor_test.evaluator import FactorExpressionEvaluator
from src.domain.strategy.factor_test.lexer import tokenize
from src.domain.strategy.factor_test.parser import FactorExpressionParser
from src.domain.strategy.factor_test.report import FactorTestReport, ScoredFactorTestReport
from src.domain.strategy.factor_test.scorer import FactorScorer
from src.infrastructure.factor_test.decay_analyzer import DecayAnalyzer
from src.infrastructure.factor_test.ic_calculator import ICCalculator
from src.infrastructure.factor_test.layer_backtest import LayerBacktester


class FactorTestRunner:
    """因子测试编排器。"""

    def __init__(self) -> None:
        self._parser = FactorExpressionParser()
        self._evaluator = FactorExpressionEvaluator()
        self._ic_calculator = ICCalculator()
        self._layer_backtester = LayerBacktester()
        self._decay_analyzer = DecayAnalyzer()
        self._scorer = FactorScorer()

    def run(
        self,
        expression_str: str,
        snapshots_by_date: dict[str, list[StockSnapshot]],
        returns_by_date: dict[str, dict[str, float]],
        prices_by_date: dict[str, dict[str, float]],
        test_period: tuple[str, str] = ("", ""),
        num_layers: int = 5,
        rebalance_days: int = 1,
        objective: str = "long_short",
        cost_rate: float = 0.003,
    ) -> ScoredFactorTestReport:
        """执行完整因子测试流程。

        Args:
            expression_str: 因子表达式字符串
            snapshots_by_date: {date_str: [StockSnapshot, ...]}
            returns_by_date: {date_str: {symbol: daily_return}}
            prices_by_date: {date_str: {symbol: close_price}}
            test_period: (start_date, end_date)
            num_layers: 分层数
            rebalance_days: 分层回测调仓间隔(交易日), 1=每日

        Returns:
            ScoredFactorTestReport
        """
        # 1. 解析表达式
        tokens = tokenize(expression_str)
        expression = self._parser.parse(tokens)

        # 2. 计算 IC/IR
        ic_series = self._ic_calculator.calculate_ic_series(
            expression, snapshots_by_date, returns_by_date
        )
        ic_values = [ic for _, ic in ic_series]
        ic_mean, ic_std, ir = self._ic_calculator.calculate_ir(ic_values)
        ic_positive_rate = sum(1 for v in ic_values if v > 0) / len(ic_values) if ic_values else 0.0

        # 3. 分层回测
        layer_result = self._layer_backtester.run(
            expression, snapshots_by_date, returns_by_date, num_layers,
            cost_rate=cost_rate, rebalance_days=rebalance_days,
        )

        # 4. 因子衰减
        decay_periods, decay_ics = self._decay_analyzer.analyze(
            expression, snapshots_by_date, prices_by_date
        )

        # 5. 计算截面股票数均值
        total_count = sum(len(v) for v in snapshots_by_date.values())
        avg_count = total_count // len(snapshots_by_date) if snapshots_by_date else 0

        # 6. 构建报告（不含评分）
        report = FactorTestReport(
            expression=expression_str,
            test_period=test_period,
            universe_count=avg_count,
            ic_mean=ic_mean,
            ic_std=ic_std,
            ir=ir,
            ic_positive_rate=ic_positive_rate,
            ic_series=ic_series,
            layer_count=num_layers,
            rebalance_days=rebalance_days,
            layer_returns=layer_result.layer_returns,
            long_short_return=layer_result.long_short_return,
            layer_cumulative=layer_result.layer_cumulative,
            top_layer_return=layer_result.top_layer_return,
            benchmark_return=layer_result.benchmark_return,
            top_excess_return=layer_result.top_excess_return,
            excess_ir=layer_result.excess_ir,
            excess_positive_rate=layer_result.excess_positive_rate,
            monotonicity_score=layer_result.monotonicity_score,
            decay_periods=decay_periods,
            decay_ics=decay_ics,
        )

        # 7. 综合评分 — 一次性构建包含评分的完整报告
        score, grade, reasons = self._scorer.score(report, objective=objective)
        return ScoredFactorTestReport(
            report=report,
            score=score,
            grade=grade,
            grade_reasons=reasons,
        )
