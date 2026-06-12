"""compare_strategies 参数解析测试（不跑回测）。"""

from src.interfaces.cli.compare_strategies import parse_args


class TestParseArgs:
    def test_initial_capital_flag(self) -> None:
        args = parse_args(["--strategies", "dual_ma", "--initial-capital", "200000"])
        assert args.initial_capital == 200000.0

    def test_initial_capital_default_none(self) -> None:
        args = parse_args(["--strategies", "dual_ma"])
        assert args.initial_capital is None

    def test_single_strategy_accepted(self) -> None:
        args = parse_args(["--strategies", "dual_ma"])
        assert args.strategies == "dual_ma"
