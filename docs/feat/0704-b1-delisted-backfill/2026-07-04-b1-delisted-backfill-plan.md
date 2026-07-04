# B1 退市股 akshare 回填 — 实施计划（精简）

> TDD；测试 `$WIN_PYTHON -m pytest`；golden 全绿 + ruff 后按任务 commit。design 同目录。

## T1 · 宇宙多源开关（默认零变化）

- Modify `src/infrastructure/persistence/market_data_store.py`：`load_symbols(source)` → 支持 `load_symbols(sources: str | tuple[str, ...])`（str 保持兼容）。
- Modify `src/infrastructure/gateway/duckdb_fundamental_fetcher.py` 与 `duckdb_history_data.py`：确认查询是否 source 过滤；fundamental 侧支持多 source（bars 侧本就无过滤，退市股自动可读——已知前提，不改）。
- Modify `src/interfaces/cli/_backtest_wiring.py`：`build_backtest_cross_section(..., include_sources: tuple[str, ...] = ("qmt",))` 透传。
- Test：默认参数下返回与改前一致（现有测试回归）；`include_sources=("qmt","akshare")` 时宇宙并集（tmp duckdb fixture 两源各插行）。

## T2 · 回测引擎退市强平（DD-9）

- Modify `src/application/backtest_app.py`（`_settle_and_snapshot` 前）或既有日终结算服务：
  - 装配期从 market_gateway 取各 symbol 末根日期（`MockMarketGateway` 内存索引可得；新增最小接口或循环内首次缺 bar 时查）。
  - 日终：对每个持仓 `pos.total_volume>0` 且 `last_bar_date[sym] < current_date` → 以末根 close 生成强平 SELL（走 trade_gateway 正常撮合，成本/滑点照常），留痕 reason=`delisted-liquidation`。
  - 活股（末根=回测末日）永不触发 → 行为零变化。
- Test（`tests/application/test_backtest_app.py` 或新文件）：①两只股 A 活到结束、B 中途断流 → B 在断流次一交易日被强平、现金回流、A 不受影响；②纯活股宇宙 → 无强平单（回归）；③强平后组合净值连续（无僵尸市值）。

## T3 · AkshareDelistedFetcher + 回填脚本

- Create `src/infrastructure/gateway/akshare_delisted_fetcher.py`：
  - `fetch_delist_list() -> list[dict]`（symbol/name/list_date/delist_date，SH+SZ 并集，代码后缀 .SH/.SZ）
  - `fetch_daily_qfq(code) / fetch_daily_raw(code)`（东财→腾讯 fallback，返回 DataFrame 或 None）
  - 纯函数（重点单测）：`build_ttm_fundamentals(bs, pf, cf, bars_dates, ...) -> list[FundamentalSnapshot]`——REPORT_DATE+90 天生效、4 季滚动 TTM（缺季退化年报值）、roe_ttm/ocf_ttm/market_cap(raw_close×SHARE_CAPITAL)、name/list_date 填充、按 bars 日期出每日行。
- Create `scripts/backfill_delisted_akshare.py`：清单 → 逐只（0.6s 间隔+退避×3+断点续传：bars 表已有该 symbol akshare 行即跳过）→ `upsert_bars(qfq, source='akshare')` + `upsert_fundamentals` + `upsert_instruments`；防重叠校验（qmt 源有行则跳过并警告）；结束打核数报告（清单数/入库数/财报覆盖/市值口径占比 raw|tx|qfq-approx）。
- Test：TTM/as-of/市值纯函数用构造 DataFrame 单测（不打网络）；脚本 `--dry-run` 只打清单不写库。

## T4 · 敏感性矩阵复跑

- Create `scripts/b1_delisted_sensitivity.py`：复用 `mainboard_f01_gate.py` 装配套路 + `include_sources` 开关；矩阵 {qmt, qmt+akshare} × {严格 ST, 宽松 ST（monkeypatch filter_st 直通）} × {闸 ON,OFF} × {IS,OOS}；退市股入选统计（从 trades 抽 akshare 源 symbol）；输出 markdown 表。
- 注：全市场（非只主板）口径同 `b2_trend_gate_ab.py`，两套都跑（主板域是影子盘部署域、全市场是 B2 原始结论域）——先全市场（B1 原始语境），主板域一格作参考。

## T5 · 执行与收尾

1. `--dry-run` 核清单 → 正式回填（~20min，断点续传可中断重跑）→ 核数报告。
2. 双源对账抽查 20 只（东财 qfq vs 腾讯 qfq 逐日 close 相对差 <0.1%）。
3. 跑 T4 矩阵 → 报告 `2026-07-04-b1-delisted-backfill-report.md`（绝对收益折扣区间 / MDD / OOS 闸增益保留性）。
4. memory：factor-funnel-status（B1 敏感性结论）+ 修正"akshare 退市不可用"旧记忆；golden + ruff 收官。
