"""compare_strategies 参数解析测试（不跑回测）。"""

import pytest

from src.interfaces.cli.compare_strategies import parse_args


class TestParseArgs:
    def test_initial_capital_flag(self) -> None:
        args = parse_args(["--strategies", "dual_ma", "--initial-capital", "200000"])
        assert args.initial_capital == 200000.0

    def test_initial_capital_default_none(self) -> None:
        args = parse_args(["--strategies", "dual_ma"])
        assert args.initial_capital is None

    def test_initial_capital_rejects_non_positive(self) -> None:
        for bad in ("0", "-100"):
            with pytest.raises(SystemExit):  # argparse 校验失败 exit 2
                parse_args(["--strategies", "dual_ma", "--initial-capital", bad])

    def test_single_strategy_accepted(self) -> None:
        args = parse_args(["--strategies", "dual_ma"])
        assert args.strategies == "dual_ma"
