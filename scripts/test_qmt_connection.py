"""QMT 连接测试脚本 - 验证 xtquant/xtdata 基础连接和数据获取。"""

import sys
import time

MINI_QMT_PATH = r"C:\QMT\userdata_mini"
TEST_STOCK = "000001.SZ"


def test_step(step_name: str):
    """装饰器工厂，打印测试步骤。"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            print(f"\n{'='*60}")
            print(f"  Step: {step_name}")
            print(f"{'='*60}")
            try:
                result = func(*args, **kwargs)
                print(f"  ✅ {step_name} - 成功")
                return result
            except Exception as e:
                print(f"  ❌ {step_name} - 失败: {e}")
                return None
        return wrapper
    return decorator


@test_step("1. xtdata 连接")
def test_xtdata_connect():
    from xtquant import xtdata
    # 直接使用 get_instrument_detail 验证连接（xtdata 会自动连接本地服务）
    time.sleep(1)
    instruments = xtdata.get_instrument_detail(TEST_STOCK)
    if instruments:
        print(f"    获取到 {TEST_STOCK} 合约信息: {instruments.get('InstrumentName', 'N/A')}")
        return True
    else:
        raise RuntimeError("无法获取合约信息")


@test_step("2. 获取实时行情 (get_full_tick)")
def test_realtime_quote():
    from xtquant import xtdata
    tick = xtdata.get_full_tick([TEST_STOCK])
    if tick and TEST_STOCK in tick:
        data = tick[TEST_STOCK]
        print(f"    {TEST_STOCK} 最新价: {data.get('lastPrice', 'N/A')}")
        return True
    else:
        raise RuntimeError("无法获取实时行情")


@test_step("3. 获取历史K线 (get_market_data_ex)")
def test_history_kline():
    from xtquant import xtdata
    kline = xtdata.get_market_data_ex(
        field_list=["open", "high", "low", "close", "volume"],
        stock_list=[TEST_STOCK],
        period="1d",
        start_time="20260101",
        end_time="20260531",
        dividend_type="front",
    )
    if kline and TEST_STOCK in kline:
        df = kline[TEST_STOCK]
        print(f"    获取到 {len(df)} 根日K线")
        if len(df) > 0:
            print(f"    最新: {df.index[-1]} close={df['close'].iloc[-1]}")
        return True
    else:
        raise RuntimeError("无法获取历史K线")


@test_step("4. XtQuantTrader 登录 + 账户查询")
def test_trader_login():
    from xtquant import xttrader, xttype
    trader = xttrader.XtQuantTrader(MINI_QMT_PATH, session=1)
    trader.start()
    connect_result = trader.connect()
    if connect_result != 0:
        raise RuntimeError(f"Trader 连接失败, code={connect_result}")

    ACCOUNT_ID = "50570555"
    account = xttype.StockAccount(ACCOUNT_ID, "STOCK")

    # 查询资产
    asset = trader.query_stock_asset(account)
    if asset:
        print(f"    总资产: {asset.total_asset:.2f}")
        print(f"    可用资金: {asset.cash:.2f}")
    else:
        print("    ⚠️ 未获取到资产信息（可能未登录或账户不匹配）")

    # 查询持仓
    positions = trader.query_stock_positions(account)
    if positions:
        print(f"    持仓数量: {len(positions)}")
        for p in positions[:3]:
            print(f"      {p.stock_code}: {p.volume}股")
    else:
        print("    当前无持仓")

    trader.stop()
    return True


def main():
    print("=" * 60)
    print("  QMT 连接测试")
    print(f"  Mini QMT 路径: {MINI_QMT_PATH}")
    print(f"  测试标的: {TEST_STOCK}")
    print("=" * 60)

    results = {}
    steps = [
        ("xtdata_connect", test_xtdata_connect),
        ("realtime_quote", test_realtime_quote),
        ("history_kline", test_history_kline),
        ("trader_login", test_trader_login),
    ]

    for name, func in steps:
        result = func()
        results[name] = result is not None
        if result is None:
            print(f"\n⚠️  {name} 失败，后续步骤可能受影响")

    print("\n" + "=" * 60)
    print("  测试结果汇总")
    print("=" * 60)
    all_pass = True
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {name}")
        if not passed:
            all_pass = False

    print(f"\n  总结: {'全部通过 ✅' if all_pass else '存在失败 ❌'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
