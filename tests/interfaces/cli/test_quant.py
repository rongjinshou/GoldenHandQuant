"""quant.py 统一入口测试。"""

import pytest

from src.interfaces.cli.quant import build_parser, main


class TestBuildParser:
    """build_parser 参数解析测试。"""

    def test_parser_has_all_subcommands(self) -> None:
        parser = build_parser()
        # 解析 --help 会触发 SystemExit(0)
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--help"])
        assert exc_info.value.code == 0

    def test_list_subcommand(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["list"])
        assert args.command == "list"

    def test_backtest_requires_strategy(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["backtest"])
        assert exc_info.value.code != 0

    def test_backtest_with_strategy(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["backtest", "--strategy", "dual_ma"])
        assert args.command == "backtest"
        assert args.strategy == "dual_ma"
        assert args.config == "resources/backtest.yaml"
        assert args.plot is False

    def test_backtest_short_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["backtest", "-s", "micro_value"])
        assert args.strategy == "micro_value"

    def test_research_requires_idea(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["research"])
        assert exc_info.value.code != 0

    def test_research_with_idea(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["research", "--idea", "微盘价值"])
        assert args.command == "research"
        assert args.idea == "微盘价值"
        assert args.period == "2020-2025"

    def test_live_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["live"])
        assert args.command == "live"
        assert args.strategy is None
        assert args.config == "resources/trading.yaml"

    def test_compare_requires_strategies(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["compare"])
        assert exc_info.value.code != 0

    def test_factor_test_requires_factors(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["factor-test"])
        assert exc_info.value.code != 0

    def test_no_command_shows_help(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.command is None


class TestMain:
    """main() 分发测试。"""

    def test_list_command_runs(self, capsys) -> None:
        """quant list 应输出策略列表且不报错。"""
        import sys

        sys.argv = ["quant", "list"]
        main()
        captured = capsys.readouterr()
        assert "dual_ma" in captured.out
        assert "micro_value" in captured.out
        assert "multi_factor" in captured.out
