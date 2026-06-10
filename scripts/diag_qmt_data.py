"""QMT 数据完整性诊断（只读,不改任何东西）。

目的: 定位"回测数据不太全"的根因到底在哪一层。
用法 (Windows 侧, 项目根目录, QMT 客户端已登录):
    $WIN_PYTHON scripts/diag_qmt_data.py
把整段输出贴回来即可。
"""
import os
import sys

sys.path.append(os.getcwd())

from src.infrastructure.gateway.xtquant_client import xtdata

LONG_START = "20180101"   # 故意往前要 8 年, 看 QMT 到底能给到哪
LONG_END = "20261231"
SAMPLES = ["000001.SZ", "000788.SZ"]   # 一只大盘 + 一只缓存里只有 4 个月的


def _range(df):
    if df is None or df.empty:
        return "EMPTY"
    return f"rows={len(df)}  {df.index.min()} -> {df.index.max()}"


print("=" * 60)
print("[Layer 0] 连接")
try:
    print("  get_client:", xtdata.get_client() is not None)
except Exception as e:
    print("  连接异常:", e)

print("[Layer A1] 全市场股票数 (沪深A股)")
try:
    hs = xtdata.get_stock_list_in_sector("沪深A股")
    print(f"  沪深A股 数量 = {len(hs)}   (run_backtest 当前砍成 500)")
except Exception as e:
    print("  获取列表失败:", e)

for sym in SAMPLES:
    print("-" * 60)
    print(f"[Layer A2] {sym} 下载前(读本地库) 长区间 {LONG_START}~{LONG_END}")
    try:
        m = xtdata.get_market_data_ex(
            ["close"], [sym], period="1d",
            start_time=LONG_START, end_time=LONG_END,
            dividend_type="front", fill_data=False,
        )
        print("  BEFORE:", _range(m.get(sym)))
    except Exception as e:
        print("  读取异常:", e)

    print(f"[Layer C] {sym} 显式 download_history_data (不吞异常, 看返回)")
    try:
        r = xtdata.download_history_data(sym, period="1d", start_time=LONG_START, end_time="")
        print("  download 返回:", r)
    except Exception as e:
        print("  download 异常:", e)

    print(f"[Layer A3] {sym} 下载后(读本地库) 同一长区间")
    try:
        m2 = xtdata.get_market_data_ex(
            ["close"], [sym], period="1d",
            start_time=LONG_START, end_time=LONG_END,
            dividend_type="front", fill_data=False,
        )
        print("  AFTER: ", _range(m2.get(sym)))
    except Exception as e:
        print("  读取异常:", e)

print("=" * 60)
print("判读:")
print("  - 若 AFTER 比 BEFORE 深很多  => QMT 有数据, 只是没下全 -> 修代码 + 跑 batch_download")
print("  - 若 AFTER 仍然很浅(只有2024) => QMT Mini 数据源本身受限 -> 需换/补数据源")
print("=" * 60)
