"""向量化因子测试编排器 — 与对象式 FactorTestRunner 等价, 消费列式 FactorPanel。

求值/IC/分层/衰减全程向量化(无 StockSnapshot 物化、无逐日 AST walk); IR 计算、
评分复用对象式同一实现(ICCalculator.calculate_ir / FactorScorer), 保证报告逐位一致。
"""

from src.domain.strategy.factor_test.lexer import tokenize
from src.domain.strategy.factor_test.panel import FactorPanel
from src.domain.strategy.factor_test.parser import FactorExpressionParser
from src.domain.strategy.factor_test.report import (
    FactorTestReport,
    ScoredFactorTestReport,
)
from src.domain.strategy.factor_test.scorer import FactorScorer
from src.domain.strategy.factor_test.vectorized_evaluator import VectorizedEvaluator
from src.infrastructure.factor_test.ic_calculator import ICCalculator
from src.infrastructure.factor_test.vectorized_series import VectorizedSeriesBuilder


class VectorizedRunner:
    """列式因子测试编排器。run 签名与产物对齐 FactorTestRunner.run(以 panel 替三 dict)。"""

    def __init__(self) -> None:
        self._parser = FactorExpressionParser()
        self._evaluator = VectorizedEvaluator()
        self._ic_calculator = ICCalculator()  # 仅复用纯函数 calculate_ir
        self._series = VectorizedSeriesBuilder()
        self._scorer = FactorScorer()

    def run(
        self,
        expression_str: str,
        panel: FactorPanel,
        test_period: tuple[str, str] = ("", ""),
        num_layers: int = 5,
        rebalance_days: int = 1,
        objective: str = "long_short",
        cost_rate: float = 0.003,
    ) -> ScoredFactorTestReport:
        expression = self._parser.parse(tokenize(expression_str))

        # 因子值: 整张面板一次性向量化求值(IC/分层/衰减共用)
        factor_series = self._evaluator.evaluate(expression, panel.df)

        # IC/IR
        ic_series = self._series.ic_series(panel, factor_series)
        ic_values = [ic for _, ic in ic_series]
        ic_mean, ic_std, ir = self._ic_calculator.calculate_ir(ic_values)
        ic_positive_rate = (
            sum(1 for v in ic_values if v > 0) / len(ic_values) if ic_values else 0.0
        )

        # 分层回测
        layer_result = self._series.layer_series(
            panel, factor_series, num_layers, cost_rate, rebalance_days
        )

        # 因子衰减
        decay_periods, decay_ics = self._series.decay_ics(panel, factor_series)

        # 截面股票数均值 (与对象式同口径: 总行数 // 日期数)
        df = panel.df
        n_dates = int(df["date"].nunique()) if not df.empty else 0
        avg_count = len(df) // n_dates if n_dates else 0

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

        score, grade, reasons = self._scorer.score(report, objective=objective)
        return ScoredFactorTestReport(
            report=report, score=score, grade=grade, grade_reasons=reasons
        )
