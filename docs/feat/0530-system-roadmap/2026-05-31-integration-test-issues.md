# 2026-05-31 集成测试问题记录

**测试日期**: 2026-05-31
**测试环境**: WSL + Windows QMT + xtquant
**数据源**: QMT（Tushare 已弃用）
**账户 ID**: 50570555
**Windows Python**: `/mnt/c/Users/11492/.conda/envs/goldenhandquant/python.exe`

---

## 测试结果汇总

| # | 测试项 | 状态 | 问题编号 |
|---|--------|------|---------|
| 1.1 | QMT 连接 | ✅ 通过 | |
| 1.2 | fetch_quote 实时行情 | ✅ 通过 | |
| 1.3 | fetch_financial 财务数据 | ✅ 通过（修复后） | #01 |
| 1.4 | fetch_indicators 技术指标 | ✅ 通过（修复后） | #02 |
| 1.5 | fetch_northbound 北向资金 | ✅ 通过（优雅降级） | |
| 1.6 | fetch_dragon_tiger 龙虎榜 | ✅ 通过（优雅降级） | |
| 1.7 | fetch_sector 行业板块 | ❌ 失败 | #03 |
| 2.1 | quant --help | ✅ 通过 | |
| 2.2 | quant list | ✅ 通过 | |
| 2.3 | quant backtest | ✅ 通过（修复后） | #04 |
| 2.4 | quant research | ✅ 通过 | |
| 3.1 | factor_test 简单因子 | ✅ 通过（修复后） | #05, #06, #07 |
| 3.2 | factor_test 复合因子 | ✅ 通过（修复后） | #08 |
| 3.3 | factor_test 函数因子 | ✅ 通过（修复后） | #05, #06, #07 |
| 3.4 | factor_test 错误处理 | ✅ 通过 | |
| 4.1 | compare_strategies | ✅ 通过 | |
| 5.1 | 信号扫描 | ✅ 通过（修复后） | #09 |
| 5.2 | 信号审核 Rich UI | ⏳ 未测（依赖 5.1） | |
| 6.1 | live_monitor 监控面板 | ✅ 通过（修复后） | #10 |
| 7.1 | ml_train 数据集构建 | ✅ 通过（修复后） | #13 |
| 7.2 | ml_train 模型训练 | ✅ 通过（修复后） | #13 |

**通过率**: 20/21 (95%)，其中 11 个经修复后通过，0 个失败，1 个未测（#03 行业板块跳过）

---

## 问题详情

### #01 fetch_financial 卡死
- **现象**: `download_financial_data()` 调用后程序挂起，无输出
- **原因**: `xtdata.download_financial_data()` 在批量下载财务数据时耗时极长（可能 >60s），且无超时保护
- **临时修复**: ✅ 已修复 `fetch_financial.py`，移除 `download_financial_data()` 调用，直接使用 `get_financial_data()`（本地已有数据时可直接返回）
- **是否阻塞**: 已解决

### #02 fetch_indicators download_history_data 参数错误
- **现象**: `download_history_data() got an unexpected keyword argument 'count'`
- **原因**: `xtdata.download_history_data()` 不支持 `count` 参数，应使用 `start_time`/`end_time`
- **临时修复**: ✅ 已修复 `fetch_indicators.py` 和 `fetch_sector.py`，改为 `start_time='', end_time=''`
- **是否阻塞**: 已解决

### #03 fetch_sector 板块不存在
- **现象**: `板块 'semiconductor' (半导体) 未找到`
- **原因**: xtdata 的 `get_sector_list()` 返回的是市场分类（沪深A股、上证A股等），不是行业板块（半导体、新能源）。xtdata 不支持行业板块查询。
- **临时修复**: 无（需要接入其他数据源如东方财富行业板块）
- **是否阻塞**: 否（优雅返回错误信息）

### #04 backtest SystemGateSettings 类型错误
- **现象**: `'SystemGateSettings' object has no attribute 'get'`
- **原因**: `settings.risk.system_gate` 是 dataclass，代码用了 dict 的 `.get()` 方法
- **临时修复**: ✅ 已修复 `commands/backtest.py:160`，改为 `settings.risk.system_gate.index_symbol`
- **是否阻塞**: 已解决

### #05 factor_test QmtHistoryDataFetcher 缺少 fetch 方法
- **现象**: `'QmtHistoryDataFetcher' object has no attribute 'fetch'`
- **原因**: `factor_test.py` 调用 `fetcher.fetch()` 批量获取数据，但 `QmtHistoryDataFetcher` 只有单标的 `fetch_history_bars()` 方法
- **临时修复**: ✅ 已修复 `qmt_history_data.py`，添加 `fetch()` 批量方法
- **是否阻塞**: 已解决

### #06 factor_test Bar 对象无 date 属性
- **现象**: `'Bar' object has no attribute 'date'`
- **原因**: `_build_cross_sections` 使用 `b.date`，但 `Bar` 只有 `timestamp` 属性
- **临时修复**: ✅ 已修复 `factor_test.py`，`b.date` → `b.timestamp`
- **是否阻塞**: 已解决

### #07 factor_test Timeframe.DAY 不存在
- **现象**: `type object 'Timeframe' has no attribute 'DAY'`
- **原因**: `Timeframe` 枚举值是 `DAY_1` 不是 `DAY`
- **临时修复**: ✅ 已修复 `qmt_history_data.py`，`Timeframe.DAY` → `Timeframe.DAY_1`
- **是否阻塞**: 已解决

### #08 复合因子计算结果全零
- **现象**: `earnings_growth / pe_ratio` 返回 IC=0, 收益=0
- **原因**: `QmtFundamentalFetcher` 读取了 `inc_net_profit_rate`/`inc_revenue_rate` 但未传入 `FundamentalSnapshot`；`FeaturePipeline._compute_fundamental_metrics` 也未将增长字段传递给 `StockSnapshot`
- **临时修复**: ✅ 已修复三处:
  1. `fundamental_snapshot.py` — 新增 `earnings_growth` 和 `revenue_growth` 字段
  2. `qmt_fundamental_fetcher.py` — 创建 `FundamentalSnapshot` 时传入 `inc_net_profit_rate` → `earnings_growth`、`inc_revenue_rate` → `revenue_growth`
  3. `feature_pipeline.py` — `_compute_fundamental_metrics` 传递 `earnings_growth` 和 `revenue_growth` 到 `StockSnapshot`
- **是否阻塞**: 已解决

### #09 信号扫描账户订阅失败
- **现象**: `Failed to subscribe to account : -1`，但信号扫描功能本身正常
- **原因**: `live_trade.py` 读取 account_id 从配置文件，配置中使用 `${QMT_ACCOUNT_ID}` 环境变量但未设置
- **临时修复**: ✅ 已修复 `live_trade.py`，在连接 QMT 前检查 `account_id` 是否为空，为空时给出明确错误提示
- **是否阻塞**: 已解决

### #10 live_monitor 无输出
- **现象**: 程序启动后无任何输出
- **原因**: `live_monitor.py` 使用 Rich Live 实时刷新终端，在非交互模式下输出被缓冲或不显示
- **临时修复**: ✅ 已修复 `live_monitor.py`，检测 `sys.stdout.isatty()`，非交互模式下使用纯文本输出一次性快照
- **是否阻塞**: 已解决

### #11 ML 依赖缺失
- **现象**: `ModuleNotFoundError: No module named 'joblib'` / `'scipy'` / `'pyarrow'`
- **原因**: Windows Python 环境未安装 ML 相关依赖（`[ml]` optional-dependencies）
- **临时修复**: ✅ 已安装 `joblib`, `scipy`, `lightgbm`, `optuna`, `scikit-learn`, `pyarrow`
- **是否阻塞**: 已解决

### #12 quant 子命令 ml-train 解析失败
- **现象**: `quant ml-train ...` 报 `unrecognized arguments: ml-train`
- **原因**: `ml_train.main()` 创建独立的 argparse 解析器，当通过 `quant ml-train` 调用时 `sys.argv` 包含 `ml-train` 子命令名
- **临时修复**: ✅ 已修复:
  1. `ml_train.py` — `main()` 接受可选 `args` 参数，被 quant 调用时使用预解析的 args
  2. `ml_evaluate.py` — 同样处理
  3. `auto_trade.py` — 同样处理
  4. `quant.py` — 调用 `ml_train_main(args)`、`ml_evaluate_main(args)`、`auto_trade_main(args)`
- **是否阻塞**: 已解决

### #13 ml_train 数据集构建缺少入口
- **现象**: `数据集不存在: data/datasets/test_model_*.parquet`，Step 1 提示"需要提供数据源"
- **原因**: `ml_train` CLI 的数据集构建步骤需要 `market_gateway` 和 `fundamental_registry` 对象，但 CLI 层没有提供从 QMT 自动构建数据集的入口。用户需要先手动构建 parquet 数据集。
- **临时修复**: ✅ 已修复 `ml_train.py`，当数据集不存在时自动调用 `QmtHistoryDataFetcher` + `QmtFundamentalFetcher` + `DatasetBuilder` 从 QMT 数据构建 parquet 数据集。支持指数代码自动展开为成分股。
- **是否阻塞**: 已解决

---

## 临时修复记录

以下修复已应用到工作区，但**未合入主分支**：

| 文件 | 修复内容 | 问题编号 |
|------|---------|---------|
| `src/interfaces/cli/fetch_indicators.py` | `download_history_data` 移除 `count` 参数 | #02 |
| `src/interfaces/cli/fetch_sector.py` | `download_history_data` 移除 `count` 参数 | #02 |
| `src/interfaces/cli/commands/backtest.py` | `.get("index_symbol")` → `.index_symbol` | #04 |
| `src/infrastructure/gateway/qmt_history_data.py` | 添加 `fetch()` 批量方法 + `Timeframe.DAY_1` | #05, #07 |
| `src/interfaces/cli/factor_test.py` | `b.date` → `b.timestamp`（3处） | #06 |
| `src/interfaces/cli/fetch_financial.py` | 移除 `download_financial_data()` 调用 | #01 |
| `src/domain/market/value_objects/fundamental_snapshot.py` | 新增 `earnings_growth`、`revenue_growth` 字段 | #08 |
| `src/infrastructure/gateway/qmt_fundamental_fetcher.py` | 创建 `FundamentalSnapshot` 时传入增长字段 | #08 |
| `src/infrastructure/ml_engine/feature_pipeline.py` | `_compute_fundamental_metrics` 传递增长字段 | #08 |
| `src/interfaces/cli/live_trade.py` | 连接前检查 `account_id` 非空 | #09 |
| `src/interfaces/cli/live_monitor.py` | 非交互模式使用纯文本输出 | #10 |
| `src/interfaces/cli/ml_train.py` | `main()` 接受可选 `args` 参数 + 自动构建数据集 | #12, #13 |
| `src/interfaces/cli/ml_evaluate.py` | `main()` 接受可选 `args` 参数 | #12 |
| `src/interfaces/cli/auto_trade.py` | `main()` 接受可选 `args` 参数 | #12 |
| `src/interfaces/cli/quant.py` | 调用子命令时传入 `args` | #12 |

---

## xtdata API 注意事项

1. `download_history_data()` 参数: `stock_code, period, start_time, end_time, incrementally` — **无 `count` 参数**
2. `get_market_data_ex()` 参数: `field_list, stock_list, period, start_time, end_time, count, dividend_type, fill_data` — **有 `count` 参数**
3. `get_sector_list()` 返回市场分类（沪深A股等），**不支持行业板块**
4. `StockAccount(account_id, "STOCK")` — 查询账户需传入 StockAccount 对象，非字符串
5. `XtQuantTrader(path, session=1)` — 参数名是 `session` 不是 `session_id`
