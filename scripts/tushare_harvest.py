"""Tushare 数据收割器 — 一次性把账号权限内的高价值数据沉淀进本地 DuckDB。

设计原则(数据诚实):
  * 收割落**独立库** data/tushare.duckdb, 不与 market.duckdb 抢写锁;
    运行时系统永不依赖代理, 数据只是本地资产。
  * 代理来源(HTTP 明文/第三方)数据先经交叉验证(见 tushare_probe 结论: daily
    成交量对 QMT 逐位匹配)方可信任; 派生进主库前再校一次。
  * fetch_log 记账 → 断点续传(中断重跑只补缺口); 超时重试(代理偶发 ReadTimeout)。

token/代理 URL 只经环境变量注入(TUSHARE_TOKEN / TUSHARE_HTTP_URL), 绝不入库入仓。

用法:
  set -a; . <env>; set +a
  python scripts/tushare_harvest.py --interface trade_cal
  python scripts/tushare_harvest.py --interface daily_basic --mode date --start 2020-01-01
  python scripts/tushare_harvest.py --interface namechange --mode symbol
"""
import argparse
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

TS_DB = "data/tushare.duckdb"
_MAX_RETRY = 4
_BACKOFF = 5.0


def _connect_tushare():
    import tushare as ts

    token = os.environ.get("TUSHARE_TOKEN")
    url = os.environ.get("TUSHARE_HTTP_URL")
    if not token:
        raise SystemExit("缺 TUSHARE_TOKEN 环境变量")
    pro = ts.pro_api(token)
    pro._DataApi__token = token
    if url:
        pro._DataApi__http_url = url  # 特殊渠道代理: 只经 env 注入
    return pro


def _call_with_retry(fn, **kw):
    last = None
    for attempt in range(_MAX_RETRY):
        try:
            return fn(**kw)
        except Exception as e:  # 代理偶发 ReadTimeout/限频
            last = e
            time.sleep(_BACKOFF * (attempt + 1))
    raise last


def _ensure_log(con):
    con.execute("""CREATE TABLE IF NOT EXISTS ts_fetch_log (
        interface VARCHAR NOT NULL, partition VARCHAR NOT NULL,
        rows INTEGER, fetched_at TIMESTAMP NOT NULL,
        PRIMARY KEY (interface, partition))""")


def _done_partitions(con, interface: str) -> set[str]:
    return {r[0] for r in con.execute(
        "SELECT partition FROM ts_fetch_log WHERE interface=?", [interface]).fetchall()}


def _sink(con, table: str, df, interface: str, partition: str) -> int:
    """df → ts_<table> 追加 + 记账, 单事务(崩溃不留半行)。"""
    n = 0 if df is None else len(df)
    con.execute("BEGIN")
    try:
        if n:
            # 列型加固: object 列显式转 string——否则首分区全 NULL 的列会被
            # 推断成非字符串型, 后续分区含字符串即整批被拒(suspend_d 实测教训)
            for col in df.columns:
                if str(df[col].dtype) == "object":
                    df[col] = df[col].astype("string")
            con.register("df_tmp", df)
            con.execute(f'CREATE TABLE IF NOT EXISTS "{table}" AS SELECT * FROM df_tmp WHERE 1=0')
            con.execute(f'INSERT INTO "{table}" SELECT * FROM df_tmp')
            con.unregister("df_tmp")
        con.execute("INSERT OR REPLACE INTO ts_fetch_log VALUES (?, ?, ?, now())",
                    [interface, partition, n])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return n


def _open_trading_days(pro, start: str, end: str) -> list[str]:
    cal = _call_with_retry(pro.trade_cal, exchange="SSE",
                           start_date=start.replace("-", ""), end_date=end.replace("-", ""))
    return sorted(str(r["cal_date"]) for _, r in cal.iterrows() if int(r["is_open"]) == 1)


def _all_symbols(pro) -> list[str]:
    """含退市(L 上市 / D 退市 / P 暂停) —— 曾用名/财务需全史。"""
    syms: list[str] = []
    for status in ("L", "D", "P"):
        try:
            df = _call_with_retry(pro.stock_basic, exchange="", list_status=status,
                                  fields="ts_code")
            syms.extend(df["ts_code"].tolist())
        except Exception as e:
            print(f"  stock_basic({status}) 失败: {e}")
    return sorted(set(syms))


def harvest(interface: str, mode: str, start: str, end: str) -> None:
    import duckdb

    pro = _connect_tushare()
    con = duckdb.connect(TS_DB)
    _ensure_log(con)
    table = f"ts_{interface}"
    done = _done_partitions(con, interface)

    if interface == "trade_cal":  # 单次
        if "ALL" in done:
            print("trade_cal 已收割, 跳过")
            return
        parts = ["ALL"]

        def fetch(p):
            return _call_with_retry(
                pro.trade_cal, exchange="SSE",
                start_date=start.replace("-", ""), end_date=end.replace("-", ""))
    elif mode == "date":
        days = _open_trading_days(pro, start, end)
        parts = [d for d in days if d not in done]

        def fetch(p):
            return _call_with_retry(getattr(pro, interface), trade_date=p)
    elif mode == "symbol":
        syms = _all_symbols(pro)
        parts = [s for s in syms if s not in done]

        def fetch(p):
            return _call_with_retry(getattr(pro, interface), ts_code=p)
    else:
        raise SystemExit(f"未知 mode: {mode}")

    total = len(parts)
    print(f"[{interface}] mode={mode} 待收割 {total} 分区 (已完成 {len(done)})", flush=True)
    t_start = time.time()
    rows_sum = 0
    for i, p in enumerate(parts, 1):
        try:
            df = fetch(p)
            n = _sink(con, table, df, interface, p)
            rows_sum += n
        except Exception as e:
            print(f"  ✗ {p}: {type(e).__name__} {str(e)[:60]} (跳过, 重跑补)", flush=True)
            continue
        if i % 50 == 0 or i == total:
            rate = i / max(time.time() - t_start, 1)
            eta = (total - i) / max(rate, 0.01)
            print(f"  {i}/{total} rows={rows_sum} {rate:.1f}/s ETA {eta/60:.0f}min", flush=True)
        time.sleep(0.05)
    con.close()
    print(f"[{interface}] 完成: {rows_sum} 行入 {TS_DB}::{table}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Tushare 数据收割器")
    ap.add_argument("--interface", required=True)
    ap.add_argument("--mode", choices=["date", "symbol", "single"], default="single")
    ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--end", default=datetime.now().strftime("%Y-%m-%d") if False else "2026-12-31")
    args = ap.parse_args()
    # end 默认取今天(避免 Date.now 依赖测试, 这里脚本运行期无妨)
    if args.end == "2026-12-31":
        args.end = date.today().isoformat() if args.interface != "trade_cal" else "2026-12-31"
    harvest(args.interface, args.mode, args.start, args.end)
    return 0


if __name__ == "__main__":
    sys.exit(main())
