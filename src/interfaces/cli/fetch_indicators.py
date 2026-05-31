"""获取单只标的技术指标数据。

使用方式:
    python -m src.interfaces.cli.fetch_indicators --symbol 600519.SH
    python -m src.interfaces.cli.fetch_indicators --symbol 600519.SH --period 1w --bars 200
"""

import argparse
import sys
from math import sqrt

from .cli_utils import (
    cancel_timeout,
    check_qmt_connection,
    output_error,
    output_success,
    setup_timeout,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="获取单只标的技术指标")
    parser.add_argument(
        "--symbol", "-s", type=str, required=True,
        help="标的代码，如 600519.SH",
    )
    parser.add_argument(
        "--period", "-p", type=str, default="1d",
        help="K 线周期（默认 1d，支持 1d/1w/1m）",
    )
    parser.add_argument(
        "--bars", "-b", type=int, default=120,
        help="获取 K 线数量（默认 120）",
    )
    return parser.parse_args()


# --------------- 技术指标计算（纯 Python） ---------------

def _calc_ma(closes: list[float], n: int) -> float | None:
    """简单移动平均。"""
    if len(closes) < n:
        return None
    return round(sum(closes[-n:]) / n, 4)


def _calc_rsi(closes: list[float], n: int) -> float | None:
    """相对强弱指标（Wilder 平滑）。"""
    if len(closes) < n + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    # 取最后 n 个 delta
    recent = deltas[-(n):]
    gains = [d for d in recent if d > 0]
    losses = [-d for d in recent if d < 0]
    avg_gain = sum(gains) / n if gains else 0.0
    avg_loss = sum(losses) / n if losses else 0.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 2)


def _calc_ema(values: list[float], n: int) -> list[float]:
    """计算 EMA 序列。"""
    if not values:
        return []
    k = 2.0 / (n + 1)
    ema = [values[0]]
    for v in values[1:]:
        ema.append(v * k + ema[-1] * (1 - k))
    return ema


def _calc_macd(closes: list[float]) -> tuple[float, float, float] | None:
    """MACD(12,26,9)。"""
    if len(closes) < 26:
        return None
    ema12 = _calc_ema(closes, 12)
    ema26 = _calc_ema(closes, 26)
    dif_list = [a - b for a, b in zip(ema12, ema26)]
    dea_list = _calc_ema(dif_list, 9)
    macd_hist = (dif_list[-1] - dea_list[-1]) * 2
    return round(dif_list[-1], 4), round(dea_list[-1], 4), round(macd_hist, 4)


def _calc_bollinger(closes: list[float], n: int = 20, k: float = 2.0) -> tuple[float, float, float] | None:
    """布林带。"""
    if len(closes) < n:
        return None
    window = closes[-n:]
    middle = sum(window) / n
    variance = sum((x - middle) ** 2 for x in window) / n
    std = sqrt(variance)
    upper = middle + k * std
    lower = middle - k * std
    return round(upper, 4), round(middle, 4), round(lower, 4)


def _calc_kdj(highs: list[float], lows: list[float], closes: list[float]) -> tuple[float, float, float] | None:
    """KDJ(9,3,3)。"""
    if len(closes) < 9:
        return None
    k_val, d_val = 50.0, 50.0
    for i in range(len(closes) - 9, len(closes)):
        window_high = max(highs[max(0, i - 8):i + 1])
        window_low = min(lows[max(0, i - 8):i + 1])
        diff = window_high - window_low
        rsv = ((closes[i] - window_low) / diff * 100) if diff > 0 else 50.0
        k_val = k_val * 2 / 3 + rsv / 3
        d_val = d_val * 2 / 3 + k_val / 3
    j_val = 3 * k_val - 2 * d_val
    return round(k_val, 2), round(d_val, 2), round(j_val, 2)


def _calc_atr(highs: list[float], lows: list[float], closes: list[float], n: int = 14) -> float | None:
    """平均真实波幅。"""
    if len(closes) < n + 1:
        return None
    tr_list = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_list.append(tr)
    # SMA 简单平均
    if len(tr_list) < n:
        return None
    return round(sum(tr_list[-n:]) / n, 4)


def _calc_vol_ratio(volumes: list[float], n: int = 5) -> float | None:
    """量比：当日成交量 / 过去 n 日平均成交量。"""
    if len(volumes) < n + 1:
        return None
    avg = sum(volumes[-(n + 1):-1]) / n
    if avg <= 0:
        return None
    return round(volumes[-1] / avg, 2)


def fetch_indicators(symbol: str, period: str = "1d", bars: int = 120) -> dict:
    """获取标的技术指标。"""
    from src.infrastructure.gateway.xtquant_client import xtdata

    # 下载历史数据
    xtdata.download_history_data(stock_code=symbol, period=period, start_time='', end_time='')

    data = xtdata.get_market_data_ex(
        field_list=['open', 'high', 'low', 'close', 'volume'],
        stock_list=[symbol],
        period=period,
        count=bars,
        dividend_type='front',
        fill_data=False,
    )
    if symbol not in data or data[symbol].empty:
        raise ValueError(f"无法获取 {symbol} 的 K 线数据")

    df = data[symbol].sort_index()
    closes = [float(v) for v in df['close'].tolist()]
    highs = [float(v) for v in df['high'].tolist()]
    lows = [float(v) for v in df['low'].tolist()]
    volumes = [float(v) for v in df['volume'].tolist()]

    if len(closes) < 5:
        raise ValueError(f"K 线数据不足（仅 {len(closes)} 根），无法计算指标")

    # 计算指标
    ma5 = _calc_ma(closes, 5)
    ma10 = _calc_ma(closes, 10)
    ma20 = _calc_ma(closes, 20)
    ma60 = _calc_ma(closes, 60)
    rsi6 = _calc_rsi(closes, 6)
    rsi14 = _calc_rsi(closes, 14)
    macd_result = _calc_macd(closes)
    boll_result = _calc_bollinger(closes)
    kdj_result = _calc_kdj(highs, lows, closes)
    atr14 = _calc_atr(highs, lows, closes)
    vol_ratio = _calc_vol_ratio(volumes)

    indicators: dict = {}
    if ma5 is not None:
        indicators["ma5"] = ma5
    if ma10 is not None:
        indicators["ma10"] = ma10
    if ma20 is not None:
        indicators["ma20"] = ma20
    if ma60 is not None:
        indicators["ma60"] = ma60
    if rsi6 is not None:
        indicators["rsi_6"] = rsi6
    if rsi14 is not None:
        indicators["rsi_14"] = rsi14
    if macd_result:
        indicators["macd"] = macd_result[0]
        indicators["macd_signal"] = macd_result[1]
        indicators["macd_hist"] = macd_result[2]
    if boll_result:
        indicators["boll_upper"] = boll_result[0]
        indicators["boll_middle"] = boll_result[1]
        indicators["boll_lower"] = boll_result[2]
    if kdj_result:
        indicators["kdj_k"] = kdj_result[0]
        indicators["kdj_d"] = kdj_result[1]
        indicators["kdj_j"] = kdj_result[2]
    if atr14 is not None:
        indicators["atr_14"] = atr14
    if vol_ratio is not None:
        indicators["vol_ratio"] = vol_ratio

    # 最近 K 线
    recent_bars = []
    for i in range(max(0, len(df) - 5), len(df)):
        row = df.iloc[i]
        ts = df.index[i]
        date_str = str(ts)
        if len(date_str) == 8:
            date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        recent_bars.append({
            "date": date_str,
            "open": round(float(row["open"]), 3),
            "high": round(float(row["high"]), 3),
            "low": round(float(row["low"]), 3),
            "close": round(float(row["close"]), 3),
            "volume": int(row["volume"]),
        })

    latest_date = str(df.index[-1])
    if len(latest_date) == 8:
        latest_date = f"{latest_date[:4]}-{latest_date[4:6]}-{latest_date[6:]}"

    return {
        "symbol": symbol,
        "period": period,
        "latest_date": latest_date,
        "indicators": indicators,
        "recent_bars": recent_bars,
    }


def main() -> None:
    args = parse_args()
    setup_timeout()
    try:
        if not check_qmt_connection():
            output_error("QMT 客户端未连接，请先启动 MiniQMT")
            sys.exit(1)

        print(f"正在获取 {args.symbol} 技术指标...", file=sys.stderr)
        data = fetch_indicators(args.symbol, args.period, args.bars)
        output_success(data)
    except TimeoutError:
        output_error("请求超时 (30s)")
        sys.exit(1)
    except Exception as e:
        output_error(str(e))
        sys.exit(1)
    finally:
        cancel_timeout()


if __name__ == "__main__":
    main()
