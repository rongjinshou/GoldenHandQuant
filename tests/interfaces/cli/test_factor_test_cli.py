"""Smoke test for factor-test CLI wiring。

默认 DB 快路径走列式向量化引擎(prepare_panel + run_batch_panel, B8);
--no-store 回退对象路径(prepare_snapshots + run_batch)。
"""

import argparse
from unittest.mock import MagicMock, patch

from src.interfaces.cli.commands.factor_test import run_factor_test


def _args(**overrides) -> argparse.Namespace:
    base = dict(
        factors="F01", start_date="2021-01-01", end_date="2025-12-31",
        split_date=None, num_layers=5, rebalance_days=1, output=None,
        config="nonexistent.yaml",
    )
    base.update(overrides)
    return argparse.Namespace(**base)


class TestFactorTestCLI:
    @patch("src.application.factor_test_app.FactorTestAppService")
    def test_db_path_calls_vectorized(self, mock_service_cls):
        """默认(DB)路径调用 prepare_panel + run_batch_panel(列式向量化)。"""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.run_batch_panel.return_value = []

        run_factor_test(_args(factors="F01,F02"))

        mock_service.prepare_panel.assert_called_once()
        mock_service.run_batch_panel.assert_called_once()
        mock_service.prepare_snapshots.assert_not_called()
        mock_service.run_batch.assert_not_called()

    @patch("src.application.factor_test_app.FactorTestAppService")
    def test_no_store_calls_object_path(self, mock_service_cls):
        """--no-store 回退对象路径 prepare_snapshots + run_batch。"""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.prepare_snapshots.return_value = ({}, {}, {})
        mock_service.run_batch.return_value = []

        run_factor_test(_args(no_store=True))

        mock_service.prepare_snapshots.assert_called_once()
        mock_service.run_batch.assert_called_once()
        mock_service.run_batch_panel.assert_not_called()

    @patch("src.application.factor_test_app.FactorTestAppService")
    def test_passes_rebalance_days(self, mock_service_cls):
        """--rebalance-days 应透传给 run_batch_panel。"""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.run_batch_panel.return_value = []

        run_factor_test(_args(rebalance_days=5))

        assert mock_service.run_batch_panel.call_args.kwargs["rebalance_days"] == 5

    @patch("src.application.factor_test_app.FactorTestAppService")
    def test_passes_objective_and_cost_rate(self, mock_service_cls):
        """--objective/--cost-rate 应透传给 run_batch_panel。"""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.run_batch_panel.return_value = []

        run_factor_test(_args(
            end_date="2026-06-11", split_date="2024-06-30", rebalance_days=5,
            objective="long_only", cost_rate=0.005,
        ))

        assert mock_service.run_batch_panel.call_args.kwargs["objective"] == "long_only"
        assert mock_service.run_batch_panel.call_args.kwargs["cost_rate"] == 0.005
