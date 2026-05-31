from unittest.mock import MagicMock

from src.application.algo_trading_app import AlgoTradingAppService
from src.domain.trade.exceptions import TradeError
from src.domain.trade.services.algo_order_manager import AlgoOrderManager
from src.domain.trade.value_objects.algo_order_config import AlgoOrderConfig
from src.domain.trade.value_objects.algo_order_status import AlgoOrderStatus
from src.domain.trade.value_objects.algo_progress import AlgoProgress
from src.domain.trade.value_objects.order_direction import OrderDirection


def _make_config(
    algo_type: str = "twap",
    total_volume: int = 1000,
) -> AlgoOrderConfig:
    return AlgoOrderConfig(
        symbol="600000.SH",
        direction=OrderDirection.BUY,
        total_volume=total_volume,
        price_limit=10.0,
        algo_type=algo_type,
        num_slices=5,
    )


def _make_progress(algo_id: str = "algo-1", status: AlgoOrderStatus = AlgoOrderStatus.RUNNING) -> AlgoProgress:
    return AlgoProgress(
        algo_id=algo_id,
        total_volume=1000,
        filled_volume=0,
        remaining_volume=1000,
        status=status,
    )


class TestAlgoTradingAppService:
    def test_submit_algo_order_success(self):
        # Arrange
        trader = MagicMock()
        trader.execute_algo_order.return_value = _make_progress()
        service = AlgoTradingAppService(trader)
        config = _make_config()

        # Act
        progress = service.submit_algo_order(config)

        # Assert
        assert progress.status == AlgoOrderStatus.RUNNING
        trader.execute_algo_order.assert_called_once()

    def test_submit_algo_order_passes_correct_args(self):
        # Arrange
        trader = MagicMock()
        trader.execute_algo_order.return_value = _make_progress()
        service = AlgoTradingAppService(trader)
        config = _make_config(total_volume=500)

        # Act
        service.submit_algo_order(config)

        # Assert
        call_args = trader.execute_algo_order.call_args
        algo_id = call_args[0][0]
        passed_config = call_args[0][1]
        slices = call_args[0][2]
        assert algo_id  # non-empty
        assert passed_config.total_volume == 500
        assert len(slices) == 5

    def test_submit_algo_order_trader_error_raises_trade_error(self):
        # Arrange
        trader = MagicMock()
        trader.execute_algo_order.side_effect = Exception("gateway error")
        service = AlgoTradingAppService(trader)
        config = _make_config()

        # Act & Assert
        try:
            service.submit_algo_order(config)
            assert False, "Should have raised"
        except TradeError as e:
            assert "gateway error" in str(e)

    def test_cancel_algo_order_success(self):
        # Arrange
        trader = MagicMock()
        trader.cancel_algo_order.return_value = _make_progress(status=AlgoOrderStatus.CANCELED)
        manager = AlgoOrderManager()
        config = _make_config()
        algo_id, _ = manager.create_algo_order(config)
        service = AlgoTradingAppService(trader, manager)

        # Act
        progress = service.cancel_algo_order(algo_id)

        # Assert
        assert progress.status == AlgoOrderStatus.CANCELED
        trader.cancel_algo_order.assert_called_once_with(algo_id)

    def test_cancel_algo_order_trader_error_raises_trade_error(self):
        # Arrange
        trader = MagicMock()
        trader.cancel_algo_order.side_effect = Exception("cancel failed")
        manager = AlgoOrderManager()
        config = _make_config()
        algo_id, _ = manager.create_algo_order(config)
        service = AlgoTradingAppService(trader, manager)

        # Act & Assert
        try:
            service.cancel_algo_order(algo_id)
            assert False, "Should have raised"
        except TradeError as e:
            assert "cancel failed" in str(e)

    def test_get_progress_returns_manager_progress(self):
        # Arrange
        trader = MagicMock()
        manager = AlgoOrderManager()
        config = _make_config()
        algo_id, _ = manager.create_algo_order(config)
        service = AlgoTradingAppService(trader, manager)

        # Act
        progress = service.get_progress(algo_id)

        # Assert
        assert progress.algo_id == algo_id
        assert progress.total_volume == 1000

    def test_on_slice_filled_updates_progress(self):
        # Arrange
        trader = MagicMock()
        manager = AlgoOrderManager()
        config = _make_config()
        algo_id, slices = manager.create_algo_order(config)
        manager.start(algo_id)
        service = AlgoTradingAppService(trader, manager)

        # Act
        progress = service.on_slice_filled(algo_id, slices[0].slice_id, "order-1")

        # Assert
        assert progress.num_slices_filled == 1
        assert progress.filled_volume == slices[0].volume
