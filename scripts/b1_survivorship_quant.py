"""B1 生存者偏差量化(真实数据) — 2021+ 退市股的终局跌幅 = F01 因生存者偏差躲掉的损失。

QMT mini 无退市股、Tushare 无 token、akshare SZ 近年退市缺失、退市股历史 market_cap 不可直取
→ 干净的点对点全回填不可得(强行做=不完整/近似的"修正", 会误导)。故改为用 akshare 能可靠拿到的
SH 2021+ 退市股(87 只)真实价格轨迹, 量化偏差量级 + 方向, 回答 B1 真正目的:偏差是否推翻结论。
用法: $WIN_PYTHON scripts/b1_survivorship_quant.py
"""

import akshare as ak
import pandas as pd

WINDOW_START = pd.Timestamp("2021-01-01")


def main() -> None:
    sh = ak.stock_info_sh_delist()
    sh["susp"] = pd.to_datetime(sh["暂停上市日期"], errors="coerce")
    inwin = sh[sh["susp"] >= WINDOW_START].copy()
    print(f"SH 2021+ 退市股: {len(inwin)} 只 (akshare; SZ 近年退市缺失, 故为下界)")

    term_rets, dds, last_closes, n_ok = [], [], [], 0
    for _, row in inwin.iterrows():
        code = str(row["公司代码"]).zfill(6)
        try:
            df = ak.stock_zh_a_hist(
                symbol=code, period="daily",
                start_date="20200101", end_date="20260611", adjust="qfq",
            )
            if df is None or df.empty or len(df) < 30:
                continue
            c = df["收盘"].astype(float).to_numpy()
            last = c[-1]
            tail = c[-250:] if len(c) >= 250 else c        # 近 ~1 年
            term_ret = last / tail[0] - 1                    # 退市前约 1 年累计收益
            peak = max(c)
            dd = last / peak - 1                             # 峰值→终局回撤
            term_rets.append(term_ret)
            dds.append(dd)
            last_closes.append(last)
            n_ok += 1
        except Exception:
            continue

    if not term_rets:
        print("无可用轨迹(网络/接口)。")
        return
    s_ret = pd.Series(term_rets)
    s_dd = pd.Series(dds)
    print(f"\n取到轨迹: {n_ok} 只")
    print(f"退市前约1年累计收益: 中位 {s_ret.median():.1%} | 均值 {s_ret.mean():.1%} | "
          f"<-50% 占 {(s_ret < -0.5).mean():.0%} | <-80% 占 {(s_ret < -0.8).mean():.0%}")
    print(f"峰值→终局回撤: 中位 {s_dd.median():.1%} | 均值 {s_dd.mean():.1%}")
    print(f"终局收盘价: 中位 ¥{pd.Series(last_closes).median():.2f} (退市股普遍沦为低价微盘)")
    print("\n含义: 这些是 F01(最小市值)正应'命中'的标的; 它们退市前暴跌后被移出宇宙 →")
    print("survivor-only 回测吃不到这些损失 → F01 绝对收益被高估(此为 SH-only 下界)。")


if __name__ == "__main__":
    main()
