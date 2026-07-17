"""集成测试: 扫描信号 -> 审核 -> 下单 -> 记录持久化。"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.application.live_signal_service import LiveSignalService
from src.domain.account.entities.asset import Asset
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.strategy.value_objects.review_action import ReviewAction
from src.interfaces.cli.signal_review.review_store import ReviewStore
from src.interfaces.cli.signal_review.review_ui import SignalReviewUI


class _FakeQuoteFetcher:
    """有效实时报价替身(M6: place_confirmed_orders 需报价源过盘前闸)。"""

    def get_quotes(self, symbols):
        from src.domain.market.value_objects.quote import Quote
        now = datetime(2026, 6, 10, 9, 35)  # 周三盘中
        return {s: Quote(symbol=s, last=20.0, bid1=19.99, ask1=20.01,
                         prev_close=20.0, timestamp=now) for s in symbols}


def _make_bars(symbol: str, prices: list[float]) -> list[Bar]:
    bars = []
    base = datetime(2026, 1, 1) - timedelta(days=len(prices))
    for i, p in enumerate(prices):
        bars.append(Bar(
            symbol=symbol, timeframe=Timeframe.DAY_1,
            timestamp=base + timedelta(days=i),
            open=p, high=p, low=p, close=p, volume=1000,
        ))
    return bars


class TestEndToEndFlow:
    def test_scan_and_save_records(self):
        """测试扫描信号 -> 保存审核记录 -> 验证 JSON 内容。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup
            market_gw = MagicMock()
            account_gw = MagicMock()
            trade_gw = MagicMock()

            account_gw.get_asset.return_value = Asset(
                account_id="test", total_asset=1_000_000, available_cash=500_000,
            )
            account_gw.get_positions.return_value = []
            market_gw.get_recent_bars.return_value = _make_bars("600000.SH", [10]*10 + [20])
            trade_gw.place_order.return_value = "order-12345"

            service = LiveSignalService(
                market_gateway=market_gw,
                account_gateway=account_gw,
                trade_gateway=trade_gw,
                clock=lambda: datetime(2026, 6, 10, 9, 35),
            )

            store = ReviewStore(Path(tmpdir))
            ui = SignalReviewUI(service=service, store=store,
                                quote_fetcher=_FakeQuoteFetcher(),
                                max_notional=999999.0, notional_ceiling=999999.0)

            # Mock input to approve all
            with patch("builtins.input", return_value="a"):
                results = ui.run("dual_ma", ["600000.SH"])

            # Verify order was placed
            assert len(results) == 1
            assert results[0].success is True

            # Verify JSON file was created
            records = store.load_today()
            assert len(records) == 1
            assert records[0].action == ReviewAction.APPROVED
            assert records[0].signal.symbol == "600000.SH"
            assert records[0].order_id == "order-12345"

    def test_scan_empty_signals(self):
        """测试无信号场景。"""
        market_gw = MagicMock()
        account_gw = MagicMock()
        trade_gw = MagicMock()

        account_gw.get_asset.return_value = Asset(
            account_id="test", total_asset=1_000_000, available_cash=500_000,
        )
        account_gw.get_positions.return_value = []
        market_gw.get_recent_bars.return_value = []

        service = LiveSignalService(
            market_gateway=market_gw,
            account_gateway=account_gw,
            trade_gateway=trade_gw,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReviewStore(Path(tmpdir))
            ui = SignalReviewUI(service=service, store=store)
            results = ui.run("dual_ma", ["600000.SH"])
            assert results == []

    def test_reject_all_saves_records(self):
        """测试全部拒绝场景。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            market_gw = MagicMock()
            account_gw = MagicMock()
            trade_gw = MagicMock()

            account_gw.get_asset.return_value = Asset(
                account_id="test", total_asset=1_000_000, available_cash=500_000,
            )
            account_gw.get_positions.return_value = []
            market_gw.get_recent_bars.return_value = _make_bars("600000.SH", [10]*10 + [20])

            service = LiveSignalService(
                market_gateway=market_gw,
                account_gateway=account_gw,
                trade_gateway=trade_gw,
            )

            store = ReviewStore(Path(tmpdir))
            ui = SignalReviewUI(service=service, store=store)

            with patch("builtins.input", return_value="r"):
                results = ui.run("dual_ma", ["600000.SH"])

            assert results == []
            records = store.load_today()
            assert len(records) == 1
            assert records[0].action == ReviewAction.REJECTED

    def test_quit_saves_nothing(self):
        """测试退出不保存记录。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            market_gw = MagicMock()
            account_gw = MagicMock()
            trade_gw = MagicMock()

            account_gw.get_asset.return_value = Asset(
                account_id="test", total_asset=1_000_000, available_cash=500_000,
            )
            account_gw.get_positions.return_value = []
            market_gw.get_recent_bars.return_value = _make_bars("600000.SH", [10]*10 + [20])

            service = LiveSignalService(
                market_gateway=market_gw,
                account_gateway=account_gw,
                trade_gateway=trade_gw,
            )

            store = ReviewStore(Path(tmpdir))
            ui = SignalReviewUI(service=service, store=store)

            with patch("builtins.input", return_value="q"):
                results = ui.run("dual_ma", ["600000.SH"])

            assert results == []
            records = store.load_today()
            assert len(records) == 0
