import logging
import sys
from datetime import datetime
from pathlib import Path

import numpy as np


def _import_xtdata():
    """动态导入 xtquant.xtdata，支持多路径 fallback。

    优先级:
    1. 已安装的 xtquant 包 (pip install xtquant)
    2. PYTHONPATH 中的 xtquant
    3. 项目根目录 libs/xtquant/
    """
    try:
        import xtquant.xtdata as xtdata
        return xtdata
    except ImportError:
        pass

    project_root = Path(__file__).resolve().parent.parent.parent.parent
    sdk_dir = project_root / "libs" / "xtquant"
    if sdk_dir.exists():
        sys.path.insert(0, str(sdk_dir.parent))
        try:
            import xtquant.xtdata as xtdata
            return xtdata
        except ImportError:
            pass

    raise ImportError(
        "xtquant SDK not found. Install via: pip install xtquant "
        "or set PYTHONPATH to your QMT userdata_mini directory."
    )


xtdata = _import_xtdata()

from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.market.interfaces.gateways.market_gateway import IMarketGateway

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
            # 转换 timeframe 为 xtquant 格式字符串
            # Timeframe 枚举值本身就是字符串 ("1d", "1m" 等)，可能需要适配
            # 假设 Timeframe 定义的值与 xtquant 兼容
            tf_str = timeframe.value

            # 确保数据已下载 (可选，根据需求，这里假设数据已订阅或下载)
            # xtdata.download_history_data(symbol, period=tf_str, count=limit)

            field_list = ["time", "open", "high", "low", "close", "volume"]
            # 调用 xtdata 获取数据
            # 注意：默认拉取前复权数据
            # xtdata.get_market_data 返回 {field: DataFrame}
            # DataFrame index 为 stock_list, columns 为 time_list
            data = xtdata.get_market_data(
                field_list=field_list,
                stock_list=[symbol],
                period=tf_str,
                count=limit,
                dividend_type="front",
                fill_data=True,
            )


            if not data:
                logger.warning(f"No data returned for {symbol} {timeframe}")
                return []

            # 检查是否有数据
            first_field = list(data.keys())[0]
            if data[first_field].empty:
                logger.warning(f"Empty data for {symbol} {timeframe}")
                return []

            # 获取时间列 (columns)
            times = data[first_field].columns.tolist()

            # 提取该标的的数据 Series
            # 注意: 如果 symbol 不在 index 中会报错，但在 stock_list=[symbol] 且返回非空时应该存在
            if symbol not in data[first_field].index:
                logger.warning(f"Symbol {symbol} not found in returned data")
                return []

            opens = data["open"].loc[symbol]
            highs = data["high"].loc[symbol]
            lows = data["low"].loc[symbol]
            closes = data["close"].loc[symbol]
            volumes = data["volume"].loc[symbol]

            # time 字段通常返回毫秒时间戳
            timestamps = data["time"].loc[symbol]

            bars = []
            for t in times:
                ts = timestamps[t]
                dt: datetime
                # QMT 时间戳通常是毫秒级 int
                # 有时可能是字符串格式，需根据实际情况处理，这里假设是 int
                if isinstance(ts, (int, float, np.integer, np.floating)):
                    dt = datetime.fromtimestamp(ts / 1000)
                elif isinstance(ts, str):
                    # 如果是字符串，尝试解析 'YYYYMMDDHHMMSS' 等格式
                    # 这里暂略，假设是标准毫秒时间戳
                    # 也可以尝试用 pd.to_datetime
                    try:
                        dt = datetime.strptime(ts, "%Y%m%d%H%M%S")
                    except ValueError:
                        # 尝试纯日期
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
                    open=float(opens[t]),
                    high=float(highs[t]),
                    low=float(lows[t]),
                    close=float(closes[t]),
                    volume=float(volumes[t]),
                )
                bars.append(bar)

            return bars

        except Exception as e:
            logger.error(f"Failed to get market data for {symbol}: {e}", exc_info=True)
            return []


