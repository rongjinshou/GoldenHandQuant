"""
QMT 数据探路脚本 — 侦察 xtdata 提供的真实字段结构。

使用方式:
    python -m src.interfaces.cli.explore_qmt_data

前提: 本地 QMT 客户端已登录运行 (MiniQMT 或完整版)。
"""

import os
import sys

# 确保项目根目录在 sys.path 中
sys.path.append(os.getcwd())

# --- 探测参数 ---
TEST_SYMBOLS = ["000001.SZ", "600000.SH"]
TEST_INDEX = ["000852.SH"]
ALL_SYMBOLS = TEST_SYMBOLS + TEST_INDEX
START_DATE = "20240101"
END_DATE = "20240131"


def separator(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def main():
    from src.infrastructure.gateway.xtquant_client import xtdata

    print(f"xtdata loaded: {xtdata}")
    print(f"Test symbols: {ALL_SYMBOLS}")
    print("Date range: 2024-01-01 ~ 2024-01-31")

    # ================================================================
    # 步骤 A: 日线量价数据
    # ================================================================
    separator("A. 日线量价数据 (get_market_data_ex)")

    # download_history_data 签名: (stock_code, period, start_time, end_time)
    print("[A1] Downloading history data (one by one)...")
    for sym in ALL_SYMBOLS:
        try:
            xtdata.download_history_data(
                stock_code=sym,
                period="1d",
                start_time=START_DATE,
                end_time=END_DATE,
            )
            print(f"  {sym} - OK")
        except Exception as e:
            print(f"  {sym} - error: {e}")

    print("\n[A2] get_market_data_ex with field_list=[] (all fields)...")
    data_ex = xtdata.get_market_data_ex(
        field_list=[],
        stock_list=ALL_SYMBOLS,
        period="1d",
        start_time=START_DATE,
        end_time=END_DATE,
        dividend_type="front",
        fill_data=False,
    )

    for sym in ALL_SYMBOLS:
        print(f"\n--- {sym} ---")
        if sym in data_ex and not data_ex[sym].empty:
            df = data_ex[sym]
            print(f"Type: {type(df)}")
            print(f"Columns: {list(df.columns)}")
            print(f"Index name: {df.index.name}, dtype: {df.index.dtype}")
            print(f"Shape: {df.shape}")
            print(df.head(2).to_string())
        else:
            print("  (no data returned)")

    # ================================================================
    # 步骤 B: 财务数据探索 (重点!)
    # ================================================================
    separator("B. 财务数据探索 (get_financial_data)")

    # B1: 先下载财务数据
    print("[B1] Downloading financial data...")
    for sym in ALL_SYMBOLS:
        try:
            xtdata.download_financial_data(stock_list=[sym])
            print(f"  {sym} - OK")
        except Exception as e:
            print(f"  {sym} - error: {e}")

    # B2: 不指定 table_list，获取全部表结构
    print("\n[B2] get_financial_data (no table_list filter, all tables)...")
    for sym in TEST_SYMBOLS[:1]:
        print(f"\n--- {sym} ---")
        try:
            fin_data = xtdata.get_financial_data(
                stock_list=[sym],
            )
            print(f"Return type: {type(fin_data)}")
            if isinstance(fin_data, dict):
                print(f"Top-level keys (table names): {list(fin_data.keys())}")
                for table_name, table_content in fin_data.items():
                    print(f"\n  Table: '{table_name}'")
                    print(f"    Type: {type(table_content)}")
                    if isinstance(table_content, dict):
                        # 新版 xtdata 返回 dict[stock_code -> dict[...]]
                        for stock_code, stock_data in table_content.items():
                            print(f"    Stock: {stock_code}, Type: {type(stock_data)}")
                            if isinstance(stock_data, dict):
                                keys = list(stock_data.keys())
                                print(f"    Fields ({len(keys)}): {keys}")
                                # 打印前几个字段的值样例
                                for k in keys[:10]:
                                    v = stock_data[k]
                                    print(f"      {k}: {str(v)[:200]}")
                            elif hasattr(stock_data, 'columns'):
                                print(f"    Columns: {list(stock_data.columns)}")
                                print(stock_data.head(2).to_string())
                            break  # 只看第一个 stock
                    elif hasattr(table_content, 'columns'):
                        print(f"    Columns: {list(table_content.columns)}")
                        print(table_content.head(2).to_string())
                    elif hasattr(table_content, 'keys'):
                        keys = list(table_content.keys())
                        print(f"    Keys ({len(keys)}): {keys}")
                    else:
                        print(f"    Value: {str(table_content)[:500]}")
            elif hasattr(fin_data, 'columns'):
                print(f"Columns: {list(fin_data.columns)}")
                print(fin_data.head(2).to_string())
            else:
                print(f"Value: {str(fin_data)[:1000]}")
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

    # B3: 逐表探测字段名
    print("\n[B3] get_financial_data with specific table_list...")
    table_candidates = [
        "Balance", "Income", "CashFlow", "Capital",
        "PershareIndex", "Profit", "Top10FlowHolder",
        "Top10Holder", "HolderNum", "StockIndicator",
        "BalanceSheet", "IncomeStatement", "CashFlowStatement",
    ]
    sym = TEST_SYMBOLS[0]
    for table in table_candidates:
        try:
            result = xtdata.get_financial_data(
                stock_list=[sym],
                table_list=[table],
            )
            if result and sym in result.get(table, {}):
                stock_data = result[table][sym]
                if isinstance(stock_data, dict):
                    print(f"\n  Table '{table}': {len(stock_data)} fields")
                    print(f"    Keys: {list(stock_data.keys())}")
                elif hasattr(stock_data, 'columns'):
                    print(f"\n  Table '{table}': columns={list(stock_data.columns)}")
                else:
                    print(f"\n  Table '{table}': type={type(stock_data)}")
            elif result:
                # 可能结构不同
                rkeys = list(result.keys()) if isinstance(result, dict) else type(result)
                print(f"\n  Table '{table}': result keys={rkeys}")
            else:
                print(f"  Table '{table}': empty")
        except Exception as e:
            print(f"  Table '{table}': error - {e}")

    # ================================================================
    # 步骤 C: 基本面探索
    # ================================================================
    separator("C. 基本面探索 (instrument detail)")

    print("[C1] get_instrument_detail — 全字段打印...")
    for sym in ALL_SYMBOLS:
        print(f"\n--- {sym} ---")
        try:
            detail = xtdata.get_instrument_detail(sym)
            print(f"  Type: {type(detail)}")
            if isinstance(detail, dict):
                for k, v in detail.items():
                    print(f"  {k}: {v}")
            else:
                print(f"  Value: {detail}")
        except Exception as e:
            print(f"  Error: {e}")

    # C2: iscomplete=True 看看有没有更多字段
    print("\n\n[C2] get_instrument_detail(iscomplete=True)...")
    for sym in TEST_SYMBOLS[:1]:
        print(f"\n--- {sym} ---")
        try:
            detail = xtdata.get_instrument_detail(sym, iscomplete=True)
            if isinstance(detail, dict):
                for k, v in detail.items():
                    print(f"  {k}: {v}")
            else:
                print(f"  Value: {detail}")
        except Exception as e:
            print(f"  Error: {e}")

    separator("DONE — 探测完成")


if __name__ == "__main__":
    main()
