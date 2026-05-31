"""
QMT 批量数据下载脚本。

下载全市场日线行情 + 财务数据到本地，后续 fetcher 可直接读取缓存。

使用方式:
    python -m src.interfaces.cli.batch_download

前提: QMT 客户端已启动。可后台运行一晚上。
"""

import os
import sys
import time
from datetime import datetime
from threading import Event

sys.path.append(os.getcwd())

from src.infrastructure.gateway.xtquant_client import xtdata

# ============ 配置 ============
# 日线起始日期（越早越好，覆盖完整历史）
KLINE_START = '19901219'
# 财务数据不需要时间范围，QMT 会拉全量
# 分批大小
BATCH_SIZE = 200
# 下载间隔（秒），避免 QMT 服务过载
BATCH_INTERVAL = 2
# 日志文件
LOG_FILE = 'data/batch_download.log'


def log(msg: str) -> None:
    """打印并写入日志文件。"""
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def download_kline(symbols: list[str]) -> dict[str, bool]:
    """批量下载全市场日线数据。"""
    log(f"=== 开始下载日线数据 ({len(symbols)} 只) ===")
    log(f"起始日期: {KLINE_START}, 周期: 1d")

    results: dict[str, bool] = {}
    total = len(symbols)

    for i in range(0, total, BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        log(f"[日线] 批次 {batch_num}/{total_batches} ({len(batch)} 只)")

        for sym in batch:
            try:
                xtdata.download_history_data(
                    stock_code=sym,
                    period='1d',
                    start_time=KLINE_START,
                    end_time='',
                    incrementally=True,
                )
                results[sym] = True
            except Exception as e:
                results[sym] = False
                log(f"  FAIL: {sym} - {e}")

        done = sum(1 for v in results.values() if v)
        fail = sum(1 for v in results.values() if not v)
        log(f"  进度: {len(results)}/{total} (成功 {done}, 失败 {fail})")

        if i + BATCH_SIZE < total:
            time.sleep(BATCH_INTERVAL)

    ok = sum(1 for v in results.values() if v)
    log(f"=== 日线下载完成: {ok}/{total} 成功 ===")
    return results


def download_financial(symbols: list[str]) -> bool:
    """批量下载财务数据（异步，避免阻塞）。"""
    log(f"=== 开始下载财务数据 ({len(symbols)} 只) ===")

    done = Event()
    progress = {'finished': 0, 'total': 0}

    def callback(data):
        f = data.get('finished', 0)
        t = data.get('total', 1)
        progress['finished'] = f
        progress['total'] = t
        if f == t or data.get('finished') is True:
            done.set()

    total = len(symbols)
    for i in range(0, total, BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        log(f"[财务] 批次 {batch_num}/{total_batches} ({len(batch)} 只)")

        try:
            xtdata.download_financial_data2(stock_list=batch, callback=callback)
            if not done.wait(timeout=300):
                log(f"  WARNING: 批次 {batch_num} 超时 (5分钟)")
            else:
                log(f"  批次 {batch_num} 完成")
            done.clear()
        except Exception as e:
            log(f"  FAIL: 批次 {batch_num} - {e}")

        if i + BATCH_SIZE < total:
            time.sleep(BATCH_INTERVAL)

    log("=== 财务数据下载完成 ===")
    return True


def download_sector_data() -> None:
    """下载板块数据。"""
    log("=== 下载板块数据 ===")
    try:
        client = xtdata.get_client()
        client.down_all_sector_data()
        log("板块数据下载完成")
    except Exception as e:
        log(f"板块数据下载失败: {e}")


def main():
    start_time = time.time()
    log("=" * 60)
    log("QMT 批量数据下载开始")
    log("=" * 60)

    # 1. 获取全市场股票列表
    symbols: list[str] = []
    for sector in ['沪深A股']:
        try:
            symbols.extend(xtdata.get_stock_list_in_sector(sector))
        except Exception as e:
            log(f"获取 {sector} 列表失败: {e}")

    symbols = sorted(set(symbols))
    log(f"全市场股票数: {len(symbols)}")

    if not symbols:
        log("ERROR: 无法获取股票列表，退出")
        return

    # 2. 下载板块数据
    download_sector_data()

    # 3. 下载日线数据
    kline_results = download_kline(symbols)
    kline_ok = sum(1 for v in kline_results.values() if v)
    kline_fail = sum(1 for v in kline_results.values() if not v)

    # 4. 下载财务数据
    download_financial(symbols)

    # 5. 汇总
    elapsed = time.time() - start_time
    hours = int(elapsed // 3600)
    minutes = int((elapsed % 3600) // 60)
    seconds = int(elapsed % 60)

    log("=" * 60)
    log("下载汇总:")
    log(f"  股票总数:  {len(symbols)}")
    log(f"  日线成功:  {kline_ok}")
    log(f"  日线失败:  {kline_fail}")
    log("  财务数据:  已提交下载")
    log(f"  总耗时:    {hours}h {minutes}m {seconds}s")
    log("=" * 60)

    # 写入失败列表
    if kline_fail > 0:
        fail_file = 'data/failed_symbols.txt'
        with open(fail_file, 'w', encoding='utf-8') as f:
            for sym, ok in kline_results.items():
                if not ok:
                    f.write(sym + '\n')
        log(f"失败列表已写入: {fail_file}")


if __name__ == '__main__':
    main()
