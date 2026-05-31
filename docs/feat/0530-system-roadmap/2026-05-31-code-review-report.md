# GoldenHandQuant Phase 1-4 代码评审报告

**评审日期**: 2026-05-31
**评审范围**: Phase 1-4 全部 13 个子项目的实现代码（~180 个文件，~35,000 行新增代码）
**评审团队**: 6 个专业评审 agent 并行审查
**评审维度**: 架构 DDD 合规性、代码质量与规范、测试质量、安全与风控、ML 引擎质量、集成与依赖分析

---

## 评审总览

| 维度 | 严重 | 中等 | 轻微 | 结论 |
|------|------|------|------|------|
| 架构 DDD 合规性 | 2 | 5 | 6 | ⚠️ 需修复 |
| 代码质量与规范 | 0 | 4 | 6 | ✅ 通过 |
| 测试质量 | 1 | 4 | 5 | ⚠️ 需修复 |
| 安全与风控 | 3 | 4 | 3 | 🔴 需修复 |
| ML 引擎质量 | 5 | 8 | 6 | 🔴 需修复 |
| 集成与依赖 | 2 | 5 | 3 | ⚠️ 需修复 |
| **合计（去重）** | **7** | **15** | **19** | **⚠️ 需修复后再合并** |

---

## 🔴 必须修复的严重问题（7 个）

### CRITICAL-1: Tushare API Token 硬编码在版本控制中
- **发现者**: 安全评审、集成评审
- **位置**: `resources/backtest.yaml:57`、`resources/backtest_multi_factor.yaml:48`
- **问题**: Tushare token `bd02c391...` 以明文形式硬编码在 YAML 配置文件中，且被 git 追踪。任何有仓库读权限的人均可获取。
- **修复**: 使用环境变量 `${TUSHARE_TOKEN}`，在 `settings.py` 中通过 `os.environ.get()` 读取。将配置文件加入 `.gitignore`，从 git 历史中清除已泄露的 token。

### CRITICAL-2: Domain 层 import numpy（Domain 红线违反）
- **发现者**: 架构评审、集成评审
- **位置**: `src/domain/strategy/services/strategies/ml_return_prediction_strategy.py:9`
- **问题**: `import numpy as np` 出现在 `src/domain/` 下，`_InferenceEngine` Protocol 签名使用 `np.ndarray`，`_extract_features` 调用 `np.array()`。
- **修复**: Protocol 参数改为 `dict[str, list[float]]`，`_extract_features` 用 `list[float]` 替代 `np.array()`。numpy 转换移至 infrastructure 层。

### CRITICAL-3: Domain registry 反向依赖 infrastructure
- **发现者**: 架构评审
- **位置**: `src/domain/strategy/registry.py:157,236-237`
- **问题**: domain 层通过延迟 import 引用了 `FactorRepository`、`InferenceEngine`、`ModelLoader`，违反依赖方向。
- **修复**: 在 domain 层定义 Protocol 接口，由 application 层注入具体实现。

### CRITICAL-4: 训练管道缺少 Purging Gap（数据泄露）
- **发现者**: ML 评审
- **位置**: `src/infrastructure/ml_engine/training_pipeline.py:239-251`
- **问题**: `walk_forward_train` 中 train/val/test 窗口紧邻，无 gap。训练集末尾标签用到验证集时间段的价格数据，造成未来信息泄露。
- **修复**: 在 train_end 和 val_start 之间加入至少 `forward_days` 天的 embargo 窗口。

### CRITICAL-5: 前瞻收益标签错误
- **发现者**: ML 评审
- **位置**: `src/infrastructure/ml_engine/factor_miner.py:141-150`、`training_pipeline.py:108-112`
- **问题**: 用 `return_5d`（回溯收益）代替前瞻收益作为标签，模型学习的是错误的目标函数。
- **修复**: 使用 `P(t+forward_days) / P(t) - 1` 计算真正的前瞻收益。

### CRITICAL-6: 训练/推理特征不匹配
- **发现者**: ML 评审
- **位置**: `trainer.py` vs `ml_return_prediction_strategy.py`
- **问题**: trainer 自动检测 DataFrame 数值列（含组合特征），策略层用 22 个基础字段。维度和含义完全不同，预测结果无意义。
- **修复**: 训练时将特征列列表保存到 metadata，推理时严格校验。策略层复用训练时的特征工程管道。

### CRITICAL-7: Web Dashboard SSE/GET 端点无认证
- **发现者**: 安全评审
- **位置**: `src/infrastructure/web/dashboard.py:167-186`
- **问题**: `/api/events`、`/api/status`、`/api/stats`、`/api/health` 四个端点完全没有认证检查。任何能访问端口的人可实时监控交易活动。
- **修复**: 所有端点添加 Bearer token 认证。

---

## 🟡 建议修复的中等问题（15 个，去重后）

### 架构类
1. **frozen dataclass 使用 `datetime.now()` 默认值** — 4 个值对象中 `datetime.now()` 只求值一次，应用 `field(default_factory=datetime.now)`
2. **6 个值对象缺少 `frozen=True`** — NotificationMessage、AnomalyEvent、RiskMetrics、ExecutionRecord 等，破坏值语义
3. **接口混用 ABC 和 Protocol** — portfolio/risk 用 ABC，notification/trade 用 Protocol，应统一为 Protocol
4. **`FactorTestReport` 被 `object.__setattr__` 绕过 frozen** — 应重构构建流程

### ML 引擎类
5. **两套训练管道并存** — trainer.py（回归+IC）vs training_pipeline.py（分类+AUC），目标不一致
6. **全局截面标准化泄露** — 测试集参与缺失值填充统计量
7. **CV 折不足时回退到训练集=测试集** — IC 指标严重虚高
8. **年化收益因子假设错误** — 标签 horizon=5 时年化因子应为 252/5 而非 252
9. **模型注册表无版本管理** — 同名模型直接覆盖，无法回滚

### 安全类
10. **Dashboard 无 CORS 和安全头** — CSRF 攻击可触发 pause/resume
11. **异常检测不阻断自动下单** — 检测到异常后仍继续执行
12. **通知失败静默吞掉异常** — 紧急告警可能永远无法送达

### 集成类
13. **4 个新 CLI 未接入 `quant` 统一入口** — auto_trade/ml_train/ml_evaluate/monitor 是独立入口
14. **`load_trading_config()` 未加载新配置段** — auto_trade/anomaly/auto_notification 配置不生效
15. **`auto_trade.py` 和 `monitor.py` 是空壳骨架** — 打印提示后退出，未实际接入

---

## 🟢 轻微问题（19 个，摘要）

- 未使用循环变量、`print` vs `logging`、`try/except/pass` 无日志
- `from __future__ import annotations` 在 Python 3.13 中非必要
- `create_app` 返回类型为 `object` 过于宽泛
- Domain 层测试使用 MagicMock（5 个文件，应替换为 Fake 实现）
- 测试中使用 `datetime.now()` 导致不确定性
- 部分测试直接访问私有属性
- 缺少 0 策略/空输入等边界测试
- `_load_data` 函数圈复杂度 19（阈值 10）
- MLModelVersion 重建逻辑重复 4 次
- `turnover_zscore` 命名误导（实际是相对偏差）
- pickle 模型存储存在安全风险
- ExecutionMonitor 内存存储无持久化

---

## ✅ 代码亮点（做得好的地方）

1. **纯 Python 实现核心算法** — CorrelationAnalyzer、PortfolioVaRCalculator、FactorExpressionEvaluator 在 domain 层使用纯 Python，严格遵守红线
2. **教科书式递归下降解析器** — parser.py 和 evaluator.py 结构清晰、职责单一
3. **StrategyPoolEntry 充血模型** — 包含状态转换、业务判断、ML 版本管理等行为方法
4. **信号管线设计简洁** — SignalPipeline 四步流水线（去重→过滤→冲突解决→转换）
5. **通知子系统 Protocol 接口隔离** — INotificationGateway + 企业微信/Telegram 实现
6. **AAA 模式测试一致性极好** — 几乎所有测试严格遵循 Arrange-Act-Assert
7. **测试命名规范** — 如 `test_candidate_cannot_pause`、`test_cooldown_state_rejects_buy_allows_sell`
8. **Fake 实现模式值得推广** — test_anomaly_detectors.py 中的 FakeTradeHistory 是范本
9. **match/case 使用规范** — evaluator.py 中 AST 节点分发正确使用
10. **自动交易默认关闭** — `enabled: False`，符合安全设计原则
11. **hmac.compare_digest 做 token 比较** — 防止时序攻击
12. **表达式解析器白名单设计** — 无 eval/exec，无注入风险
13. **依赖注入使用良好** — AutoTradingEngine、PortfolioRiskService 等通过构造函数注入
14. **778 个测试全部通过** — 无回归

---

## 修复优先级建议

### P0（立即修复，阻塞合并）
1. CRITICAL-1: Tushare token → 环境变量
2. CRITICAL-2: Domain 层 numpy import → 改为 list[float]
3. CRITICAL-5: 前瞻收益标签 → 使用真正的前瞻收益
4. CRITICAL-6: 训练/推理特征一致性 → 保存特征列到 metadata

### P1（尽快修复）
5. CRITICAL-3: registry 反向依赖 → Protocol + DI
6. CRITICAL-4: Purging Gap → 添加 embargo 窗口
7. CRITICAL-7: Dashboard 认证 → 所有端点加 Bearer token
8. 中等问题 #6-8: 统一训练管道、修复全局泄露、CV 回退

### P2（下个迭代修复）
9. 中等问题 #1-5: frozen/dataclass/Protocol 统一
10. 中等问题 #10-15: CLI 接入、配置加载、骨架实现
11. 轻微问题：按优先级逐步清理

---

## 总体评价

Phase 1-4 的实现质量**整体良好**，架构设计遵循 DDD 分层原则，代码规范一致，测试覆盖全面。13 个子项目全部实现，~555 个新测试，778 个测试全部通过。

**主要风险集中在 ML 引擎**：5 个 CRITICAL 级别的数据泄露和特征一致性问题会导致回测指标虚高、实盘预测不可靠。在这些问题修复之前，ML 引擎的训练结果不应被用于实盘交易决策。

**安全方面**需要立即处理 Tushare token 泄露和 Dashboard 认证问题。

**建议**：按 P0 → P1 → P2 优先级修复后，再考虑合并到主分支。
