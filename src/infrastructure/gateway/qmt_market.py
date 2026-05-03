import logging
from datetime import datetime

import numpy as np

from src.domain.market.interfaces.gateways.market_gateway import IMarketGateway
from src.domain.market.value_objects.bar import Bar
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
                )
                bars.append(bar)

            return bars

        except Exception as e:
            logger.error(f"Failed to get market data for {symbol}: {e}", exc_info=True)
            return []


