"""MarketDataAppService 测试 — DB 路径重验三个约定 + 只刷缺口行为。

数据构造复用 test_factor_test_app 的 stub fetcher（真实数据结构，非 MagicMock）。
"""

import pytest

from src.application import market_data_app as mda_module
from src.application.market_data_app import MarketDataAppService
from src.infrastructure.persistence.market_data_store import MarketDataStore
from tests.application.test_factor_test_app import (
    _consecutive_dates,
    _make_daily_bars,
    _make_fundamentals,
    _StubFundamentalFetcher,
    _StubHistoryFetcher,
)


@pytest.fixture
def store():
    s = MarketDataStore(":memory:")
    yield s
    s.close()


class _CountingHistoryFetcher(_StubHistoryFetcher):
    """记录每次 fetch 调用 (symbol, start, end)，验证只拉缺口。"""

    def __init__(self, bars_by_symbol):
        super().__init__(bars_by_symbol)
        self.calls: list[tuple[str, str, str]] = []

    def fetch_history_bars(self, symbol, timeframe, start_date, end_date):
        self.calls.append((symbol, start_date, end_date))
        return super().fetch_history_bars(symbol, timeframe, start_date, end_date)


def _build_service(
    closes: dict[str, float], store: MarketDataStore, symbol: str = "000001.SZ"
) -> tuple[MarketDataAppService, _CountingHistoryFetcher]:
    fetcher = _CountingHistoryFetcher({symbol: _make_daily_bars(symbol, closes)})
    fund = _StubFundamentalFetcher(_make_fundamentals(symbol, list(closes.keys())))
    return MarketDataAppService(store, fetcher, fund, source="qmt"), fetcher


class TestConventionsOnDbPath:
    """无前视 / T-1 信息 / warmup 三个约定在 DB 路径上必须与旧管道一致。"""

    def test_t_minus_1_info_and_exec_price(self, store):
        dates = _consecutive_dates("2024-01-01", 10)
        closes = {d: 10.0 + i for i, d in enumerate(dates)}
        service, _ = _build_service(closes, store)

        snaps, rets, prices = service.prepare(["000001.SZ"], "2024-01-05", "2024-01-10")

        snap = snaps["2024-01-05"][0]
        assert snap.close == closes["2024-01-04"]          # 特征 bar = T-1
        assert prices["2024-01-05"]["000001.SZ"] == closes["2024-01-05"]  # 执行价 = T
        # 收益按实现日键入, 用执行价计算
        expected = (closes["2024-01-06"] - closes["2024-01-05"]) / closes["2024-01-05"]
        assert abs(rets["2024-01-06"]["000001.SZ"] - expected) < 1e-12

    def test_future_prices_do_not_affect_past(self, store):
        dates = _consecutive_dates("2024-01-01", 30)
        closes = {d: 10.0 + i * 0.1 for i, d in enumerate(dates)}
        spiked = dict(closes)
        spiked[dates[-1]] = closes[dates[-1]] * 10

        store_b = MarketDataStore(":memory:")
        service_a, _ = _build_service(closes, store)
        service_b, _ = _build_service(spiked, store_b)
        snaps_a, rets_a, _ = service_a.prepare(["000001.SZ"], "2024-01-20", "2024-01-30")
        snaps_b, rets_b, _ = service_b.prepare(["000001.SZ"], "2024-01-20", "2024-01-30")
        store_b.close()

        last_day = dates[-1]
        for d in snaps_a:
            if d == last_day:
                continue
            a, b = snaps_a[d][0], snaps_b[d][0]
            assert a.close == b.close
            assert a.return_5d == b.return_5d
            assert a.volatility_20d == b.volatility_20d
        for d in rets_a:
            if d == last_day:
                continue
            assert rets_a[d] == rets_b[d]

    def test_warmup_first_day_features_available(self, store):
        dates = _consecutive_dates("2024-01-01", 45)
        closes = {d: 10.0 + i * 0.1 for i, d in enumerate(dates)}
        service, _ = _build_service(closes, store)

        snaps, rets, prices = service.prepare(["000001.SZ"], "2024-02-10", "2024-02-14")

        first_day = min(snaps.keys())
        assert first_day == "2024-02-10"
        snap = snaps[first_day][0]
        assert snap.return_5d is not None
        assert snap.volatility_20d is not None
        # warmup 数据只喂特征, 不进输出窗口
        for keys in (snaps.keys(), rets.keys(), prices.keys()):
            assert all("2024-02-10" <= d <= "2024-02-14" for d in keys)


class TestRefreshOnly:
    def test_second_prepare_fetches_nothing(self, store):
        dates = _consecutive_dates("2024-01-01", 30)
        closes = {d: 10.0 + i for i, d in enumerate(dates)}
        service, fetcher = _build_service(closes, store)

        service.prepare(["000001.SZ"], "2024-01-10", "2024-01-30")
        first_calls = len(fetcher.calls)
        assert first_calls >= 1

        result = service.prepare(["000001.SZ"], "2024-01-10", "2024-01-30")
        assert len(fetcher.calls) == first_calls  # 全命中, 零取数
        assert "2024-01-10" in result[0]

    def test_extending_end_fetches_only_tail_gap(self, store):
        dates = _consecutive_dates("2024-01-01", 40)
        closes = {d: 10.0 + i for i, d in enumerate(dates)}
        service, fetcher = _build_service(closes, store)

        service.prepare(["000001.SZ"], "2024-01-10", "2024-01-31")
        fetcher.calls.clear()

        service.prepare(["000001.SZ"], "2024-01-10", "2024-02-09")

        assert len(fetcher.calls) == 1
        _, gap_start, gap_end = fetcher.calls[0]
        assert gap_start == "2024-02-01"  # 只拉旧履约 end 之后的尾部
        assert gap_end == "2024-02-09"

    def test_features_not_recomputed_when_bars_unchanged(self, store, monkeypatch):
        dates = _consecutive_dates("2024-01-01", 30)
        closes = {d: 10.0 + i for i, d in enumerate(dates)}
        service, _ = _build_service(closes, store)

        compute_calls = {"n": 0}
        real_compute = mda_module.compute_features

        def counting_compute(bars_df):
            compute_calls["n"] += 1
            return real_compute(bars_df)

        monkeypatch.setattr(mda_module, "compute_features", counting_compute)

        service.prepare(["000001.SZ"], "2024-01-10", "2024-01-30")
        assert compute_calls["n"] == 1

        service.prepare(["000001.SZ"], "2024-01-10", "2024-01-30")
        assert compute_calls["n"] == 1  # bars 未变 + 特征区间命中 → 不重算
