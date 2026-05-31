# 2026-05-31 集成测试计划

**测试环境**: WSL + Windows QMT + xtquant
**Windows Python**: `/mnt/c/Users/11492/.conda/envs/goldenhandquant/python.exe`
**测试目标**: 验证今日实现的 13 个子项目在真实 QMT 环境下的功能

---

## 测试顺序（按依赖关系）

### 第 1 批：基础设施验证（无依赖）

| # | 测试项 | CLI 命令 | 预期结果 |
|---|--------|---------|---------|
| 1.1 | QMT 连接 | `fetch_account --json` | 返回账户 JSON |
| 1.2 | 实时行情 | `fetch_quote -s 600519.SH --json` | 返回茅台行情 JSON |
| 1.3 | 财务数据 | `fetch_financial -s 600519.SH --json` | 返回财务数据 JSON |
| 1.4 | 技术指标 | `fetch_indicators -s 600519.SH --json` | 返回 MA/RSI/MACD JSON |
| 1.5 | 北向资金 | `fetch_northbound --json` | 返回数据或优雅降级 |
| 1.6 | 龙虎榜 | `fetch_dragon_tiger --json` | 返回数据或优雅降级 |
| 1.7 | 行业板块 | `fetch_sector -s semiconductor --json` | 返回成分股列表 |

### 第 2 批：统一 CLI 验证

| # | 测试项 | CLI 命令 | 预期结果 |
|---|--------|---------|---------|
| 2.1 | quant 帮助 | `quant --help` | 显示 6 个子命令 |
| 2.2 | 策略列表 | `quant list` | 显示 dual_ma/micro_value/multi_factor/ml_return_prediction |
| 2.3 | 回测命令 | `quant backtest --strategy dual_ma --start 2024-01-01 --end 2024-03-01` | 运行回测并输出报告 |
| 2.4 | 研究命令 | `quant research --idea "双均线" --start 2024-01-01 --end 2024-03-01` | 匹配 dual_ma 并回测 |

### 第 3 批：因子快速测试

| # | 测试项 | CLI 命令 | 预期结果 |
|---|--------|---------|---------|
| 3.1 | 简单因子 | `factor_test "pe_ratio" --start 2024-01-01 --end 2024-06-01` | 返回 IC/分层/评分 |
| 3.2 | 复合因子 | `factor_test "earnings_growth / pe_ratio" --start 2024-01-01 --end 2024-06-01` | 返回有效报告 |
| 3.3 | 函数因子 | `factor_test "rank(roe_ttm)" --start 2024-01-01 --end 2024-06-01` | 返回有效报告 |
| 3.4 | 错误处理 | `factor_test "invalid_field" --start 2024-01-01 --end 2024-06-01` | 返回明确错误 |

### 第 4 批：策略对比

| # | 测试项 | CLI 命令 | 预期结果 |
|---|--------|---------|---------|
| 4.1 | 双策略对比 | `compare_strategies --strategies dual_ma,micro_value --start-date 2024-01-01 --end-date 2024-06-01` | 返回对比报告 |

### 第 5 批：实盘信号（需 QMT 连接）

| # | 测试项 | CLI 命令 | 预期结果 |
|---|--------|---------|---------|
| 5.1 | 信号扫描 | `quant live --strategy dual_ma` | 扫描信号并展示表格 |
| 5.2 | 信号审核 | 同上，选择 rich 模式 | Rich 表格交互 |

### 第 6 批：实盘监控（需 QMT 连接）

| # | 测试项 | CLI 命令 | 预期结果 |
|---|--------|---------|---------|
| 6.1 | 监控面板 | `live_monitor` | 显示账户概览/持仓/风险/告警 |

### 第 7 批：ML 训练（需要数据）

| # | 测试项 | CLI 命令 | 预期结果 |
|---|--------|---------|---------|
| 7.1 | 数据集构建 | `ml_train build --symbol 600519.SH --start 2023-01-01 --end 2024-12-31` | 生成 parquet |
| 7.2 | 模型训练 | `ml_train train --model-name test_model` | 训练完成，保存模型 |

---

## 环境变量需求

测试前需要设置：
```bash
export QMT_ACCOUNT_ID="实际账户ID"
export TUSHARE_TOKEN="实际token"
```
