"""argv 构建器纯函数测试 — 不触网络不起进程。"""

import sys

import pytest
from pydantic import ValidationError

from src.interfaces.api.job_commands import (
    BacktestJobRequest,
    DataRefreshJobRequest,
    FactorTestJobRequest,
    MlEvaluateJobRequest,
    MlTrainJobRequest,
    build_backtest_argv,
    build_data_refresh_argv,
    build_factor_test_argv,
    build_ml_evaluate_argv,
    build_ml_train_argv,
)


class TestBacktest:
    def test_minimal_request_builds_compare_argv(self) -> None:
        req = BacktestJobRequest(
            strategies=["dual_ma"], start_date="2024-01-01", end_date="2024-12-31")
        argv = build_backtest_argv(req)
        assert argv[0] == sys.executable
        assert argv[1:3] == ["-m", "src.interfaces.cli.compare_strategies"]
        assert "--strategies" in argv and "dual_ma" in argv
        assert "--symbols" not in argv and "--params" not in argv

    def test_full_request(self) -> None:
        req = BacktestJobRequest(
            strategies=["dual_ma", "micro_value"],
            start_date="2024-01-01", end_date="2024-12-31",
            symbols=["000021.SZ", "600000.SH"],
            params={"micro_value": {"top_n": 5}},
            config="resources/backtest_multi_factor.yaml",
            initial_capital=200000,
        )
        argv = build_backtest_argv(req)
        i = argv.index("--strategies")
        assert argv[i + 1] == "dual_ma,micro_value"
        assert argv[argv.index("--symbols") + 1] == "000021.SZ,600000.SH"
        assert argv[argv.index("--params") + 1] == "micro_value.top_n=5"
        assert argv[argv.index("--initial-capital") + 1] == "200000.0"

    def test_unknown_strategy_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BacktestJobRequest(strategies=["nope"],
                               start_date="2024-01-01", end_date="2024-12-31")

    def test_config_outside_whitelist_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BacktestJobRequest(strategies=["dual_ma"], start_date="2024-01-01",
                               end_date="2024-12-31", config="/etc/passwd")

    def test_bad_date_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BacktestJobRequest(strategies=["dual_ma"],
                               start_date="2024/01/01", end_date="2024-12-31")


class TestFactorTest:
    def test_defaults(self) -> None:
        req = FactorTestJobRequest(factors="P0")
        argv = build_factor_test_argv(req)
        assert argv[1:4] == ["-m", "src.interfaces.cli.quant", "factor-test"]
        assert argv[argv.index("--factors") + 1] == "P0"
        assert argv[argv.index("--objective") + 1] == "long_short"
        assert "--split-date" not in argv

    def test_split_and_objective(self) -> None:
        req = FactorTestJobRequest(factors="F01,F02", split_date="2024-06-30",
                                   objective="long_only", rebalance_days=5)
        argv = build_factor_test_argv(req)
        assert argv[argv.index("--split-date") + 1] == "2024-06-30"
        assert argv[argv.index("--objective") + 1] == "long_only"
        assert argv[argv.index("--rebalance-days") + 1] == "5"

    def test_unknown_factor_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FactorTestJobRequest(factors="F99,NOPE")


class TestOthers:
    def test_data_refresh(self) -> None:
        argv = build_data_refresh_argv(
            DataRefreshJobRequest(start_date="2025-01-01", end_date="2025-06-01"))
        assert argv[1:5] == ["-m", "src.interfaces.cli.quant", "data", "refresh"]
        assert argv[argv.index("--start-date") + 1] == "2025-01-01"

    def test_ml_train(self) -> None:
        argv = build_ml_train_argv(MlTrainJobRequest(
            start_date="2021-01-01", end_date="2024-12-31", n_trials=10))
        assert argv[3] == "ml-train"
        assert argv[argv.index("--n-trials") + 1] == "10"
        assert argv[argv.index("--model-name") + 1] == "lgbm_return_5d"

    def test_ml_evaluate(self) -> None:
        argv = build_ml_evaluate_argv(MlEvaluateJobRequest(
            model_name="lgbm_return_5d", eval_start="2025-01-01", eval_end="2025-06-01"))
        assert argv[3] == "ml-evaluate"
        assert argv[argv.index("--model-name") + 1] == "lgbm_return_5d"
