"""Smoke test for factor-test CLI wiring."""

import argparse
from unittest.mock import MagicMock, patch

from src.interfaces.cli.commands.factor_test import run_factor_test


class TestFactorTestCLI:
    @patch("src.application.factor_test_app.FactorTestAppService")
    def test_run_factor_test_calls_service(self, mock_service_cls):
        """Verify CLI command creates service and calls run_batch."""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.prepare_snapshots.return_value = ({}, {}, {})
        mock_service.run_batch.return_value = []

        args = argparse.Namespace(
            factors="F01,F02",
            start_date="2021-01-01",
            end_date="2025-12-31",
            split_date=None,
            num_layers=5,
            output=None,
            config="nonexistent.yaml",
        )

        run_factor_test(args)

        mock_service.prepare_snapshots.assert_called_once()
        mock_service.run_batch.assert_called_once()
