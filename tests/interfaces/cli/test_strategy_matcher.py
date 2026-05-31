"""strategy_matcher 模块测试。"""

from src.interfaces.cli.strategy_matcher import format_available_strategies, match_strategy


class TestMatchStrategy:
    """match_strategy 关键词匹配测试。"""

    def test_micro_value_keywords(self) -> None:
        assert match_strategy("微盘价值") == "micro_value"
        assert match_strategy("小盘股选股") == "micro_value"
        assert match_strategy("小市值策略") == "micro_value"
        assert match_strategy("壳价值") == "micro_value"

    def test_multi_factor_keywords(self) -> None:
        assert match_strategy("多因子选股") == "multi_factor"
        assert match_strategy("基本面分析") == "multi_factor"
        assert match_strategy("量化选股模型") == "multi_factor"

    def test_dual_ma_keywords(self) -> None:
        assert match_strategy("双均线金叉") == "dual_ma"
        assert match_strategy("均线突破") == "dual_ma"
        assert match_strategy("趋势跟踪策略") == "dual_ma"
        assert match_strategy("MA cross") == "dual_ma"

    def test_case_insensitive(self) -> None:
        assert match_strategy("DUAL_MA") == "dual_ma"
        assert match_strategy("DualMa") == "dual_ma"

    def test_no_match_returns_none(self) -> None:
        assert match_strategy("未知想法xyz") is None
        assert match_strategy("随机文本") is None
        assert match_strategy("") is None


class TestFormatAvailableStrategies:
    """format_available_strategies 测试。"""

    def test_contains_all_strategies(self) -> None:
        result = format_available_strategies()
        assert "dual_ma" in result
        assert "micro_value" in result
        assert "multi_factor" in result

    def test_non_empty(self) -> None:
        result = format_available_strategies()
        assert len(result) > 0
