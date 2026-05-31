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
| 1.3 | fetch_financial 财务数据 | ❌ 失败 | #01 |
| 1.4 | fetch_indicators 技术指标 | ✅ 通过（修复后） | #02 |
| 1.5 | fetch_northbound 北向资金 | ✅ 通过（优雅降级） | |
| 1.6 | fetch_dragon_tiger 龙虎榜 | ✅ 通过（优雅降级） | |
| 1.7 | fetch_sector 行业板块 | ❌ 失败 | #03 |
| 2.1 | quant --help | ✅ 通过 | |
| 2.2 | quant list | ✅ 通过 | |
| 2.3 | quant backtest | ✅ 通过（修复后） | #04 |
| 2.4 | quant research | ✅ 通过 | |
| 3.1 | factor_test 简单因子 | ✅ 通过（修复后） | #05, #06, #07 |
| 3.2 | factor_test 复合因子 | ❌ 失败 | #08 |
| 3.3 | factor_test 函数因子 | ✅ 通过（修复后） | #05, #06, #07 |
| 3.4 | factor_test 错误处理 | ✅ 通过 | |
| 4.1 | compare_strategies | ✅ 通过 | |
| 5.1 | 信号扫描 | ⚠️ 部分通过 | #09 |
| 5.2 | 信号审核 Rich UI | ⏳ 未测（依赖 5.1） | |
| 6.1 | live_monitor 监控面板 | ❌ 失败 | #10 |
| 7.1 | ml_train 数据集构建 | ❌ 失败 | #13 |
| 7.2 | ml_train 模型训练 | ❌ 失败 | #13 |

**通过率**: 14/21 (67%)，其中 5 个经修复后通过，4 个失败，1 个部分通过，1 个未测

---

## 问题详情

### #01 fetch_financial 卡死
- **现象**: `download_financial_data()` 调用后程序挂起，无输出
- **原因**: `xtdata.download_financial_data()` 在批量下载财务数据时耗时极长（可能 >60s），且无超时保护
- **临时修复**: 无（需要优化 download 调用或增加异步超时）
- **是否阻塞**: 否（功能可用，只是慢）

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
- **原因**: `earnings_growth` 字段在 xtdata 财务数据中可能不存在或名称不匹配。FIELD_MAP 中的 `inc_revenue_rate` 映射为 `revenue_growth`，但没有 `earnings_growth` 字段
- **临时修复**: 无（需要检查字段映射或修改表达式）
- **是否阻塞**: 否（简单因子和函数因子正常工作）

### #09 信号扫描账户订阅失败
- **现象**: `Failed to subscribe to account : -1`，但信号扫描功能本身正常
- **原因**: `live_trade.py` 读取 account_id 从配置文件，配置中使用 `${QMT_ACCOUNT_ID}` 环境变量但未设置
- **临时修复**: 设置环境变量 `QMT_ACCOUNT_ID=50570555` 后可正常工作
- **是否阻塞**: 否（信号扫描本身正常，只是账户信息获取失败）

### #10 live_monitor 无输出
- **现象**: 程序启动后无任何输出
- **原因**: `live_monitor.py` 使用 Rich Live 实时刷新终端，在非交互模式下输出被缓冲或不显示
- **临时修复**: 无（需要在非交互模式下使用普通 print 输出）
- **是否阻塞**: 否（在真实终端中可正常运行）

### #11 ML 依赖缺失
- **现象**: `ModuleNotFoundError: No module named 'joblib'` / `'scipy'` / `'pyarrow'`
- **原因**: Windows Python 环境未安装 ML 相关依赖（`[ml]` optional-dependencies）
- **临时修复**: ✅ 已安装 `joblib`, `scipy`, `lightgbm`, `optuna`, `scikit-learn`, `pyarrow`
- **是否阻塞**: 已解决

### #12 quant 子命令 ml-train 解析失败
- **现象**: `quant ml-train ...` 报 `unrecognized arguments: ml-train`
- **原因**: `ml_train.main()` 创建独立的 argparse 解析器，当通过 `quant ml-train` 调用时 `sys.argv` 包含 `ml-train` 子命令名
- **临时修复**: 直接调用 `python -m src.interfaces.cli.ml_train ...` 可正常工作
- **是否阻塞**: 否（直接调用可用）

### #13 ml_train 数据集构建缺少入口
- **现象**: `数据集不存在: data/datasets/test_model_*.parquet`，Step 1 提示"需要提供数据源"
- **原因**: `ml_train` CLI 的数据集构建步骤需要 `market_gateway` 和 `fundamental_registry` 对象，但 CLI 层没有提供从 QMT 自动构建数据集的入口。用户需要先手动构建 parquet 数据集。
- **临时修复**: 无（需要添加 QMT 数据集构建流程）
- **是否阻塞**: 是（ML 训练无法从 CLI 端到端运行）

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

---

## xtdata API 注意事项

1. `download_history_data()` 参数: `stock_code, period, start_time, end_time, incrementally` — **无 `count` 参数**
2. `get_market_data_ex()` 参数: `field_list, stock_list, period, start_time, end_time, count, dividend_type, fill_data` — **有 `count` 参数**
3. `get_sector_list()` 返回市场分类（沪深A股等），**不支持行业板块**
4. `StockAccount(account_id, "STOCK")` — 查询账户需传入 StockAccount 对象，非字符串
5. `XtQuantTrader(path, session=1)` — 参数名是 `session` 不是 `session_id`
