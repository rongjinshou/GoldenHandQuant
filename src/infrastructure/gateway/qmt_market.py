import logging
from datetime import datetime

import numpy as np

from src.domain.market.interfaces.gateways.market_gateway import IMarketGateway
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.market.value_objects.timeframe import Timeframe

from .xtquant_client import xtdata

logger = logging.getLogger(__name__)


class QmtMarketGateway(IMarketGateway):
    """QMT 行情网关实现。"""

    def get_recent_bars(self, symbol: str, timeframe: Timeframe, limit: int = 100) -> list[Bar]:
        """获取最近的 K 线数据。

        Args:
            symbol: 标的代码，如 '600000.SH'
            timeframe: 周期
            limit: 获取数量

        Returns:
            list[Bar]: K 线列表
        """
        try:
            tf_str = timeframe.value

            field_list = ["open", "high", "low", "close", "volume"]

            # 使用 get_market_data_ex（非旧版 get_market_data）
            # 返回 {stock: DataFrame(index=time, columns=fields)}
            data_map = xtdata.get_market_data_ex(
                field_list=field_list,
                stock_list=[symbol],
                period=tf_str,
                count=limit,
                dividend_type="front",
                fill_data=True,
            )

            if symbol not in data_map or data_map[symbol].empty:
                logger.warning(f"No data returned for {symbol} {timeframe}")
                return []

            df = data_map[symbol]

            # 获取不复权收盘价用于真实账本结算
            unadjusted_close_map: dict = {}
            try:
                unadj_map = xtdata.get_market_data_ex(
                    field_list=["close"],
                    stock_list=[symbol],
                    period=tf_str,
                    count=limit,
                    dividend_type="none",
                    fill_data=True,
                )
                if symbol in unadj_map and not unadj_map[symbol].empty:
                    unadj_series = unadj_map[symbol]["close"]
                    unadjusted_close_map = unadj_series.to_dict()
            except Exception:
                logger.debug("Failed to fetch unadjusted close for %s", symbol, exc_info=True)

            bars = []
            for ts, row in df.iterrows():
                dt: datetime
                if isinstance(ts, (int, float, np.integer, np.floating)):
                    dt = datetime.fromtimestamp(ts / 1000)
                elif isinstance(ts, str):
                    try:
                        dt = datetime.strptime(ts, "%Y%m%d%H%M%S")
                    except ValueError:
                        try:
                            dt = datetime.strptime(ts, "%Y%m%d")
                        except ValueError:
                            logger.warning(f"Unknown timestamp format: {ts}")
                            continue
                else:
                    logger.warning(f"Unknown timestamp type: {type(ts)}")
                    continue

                bar = Bar(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=dt,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                    unadjusted_close=float(unadjusted_close_map.get(ts, 0.0)),
                    # 前复权序列内前根 close, 与 DuckDB 历史 bars 口径自洽; 窗口首根 0.0 无碍
                    prev_close=bars[-1].close if bars else 0.0,
                )
                bars.append(bar)

            return bars

        except Exception as e:
            logger.error(f"Failed to get market data for {symbol}: {e}", exc_info=True)
            return []

    def get_stock_snapshots(self, symbols: list[str]) -> list[StockSnapshot]:
        """获取标的日频快照。

        QMT xtdata 暂无直接快照接口，返回空列表，
        由上游 FeaturePipeline 从 bar 历史计算填充。
        """
        return []

    def ensure_ready(self) -> None:
        """xtdata 服务健康探针(同 scripts/test_qmt_connection.py Step1 口径, 轻量不触发下载)。"""
        try:
            detail = xtdata.get_instrument_detail("000001.SZ")
        except Exception as e:
            raise RuntimeError(f"xtdata 行情服务探针异常: {e}") from e
        if not detail:
            raise RuntimeError(
                "xtdata 行情服务不可用(xtdatacenter 58610 未起?): "
                "诊断 $WIN_PYTHON scripts/test_qmt_connection.py; "
                "恢复: QMT 极简端确认行情面板有数据(非仅交易登录), 必要时重启重登")


