# GoldenHandQuant Phase 1-4 合并代码评审报告

**评审日期**: 2026-05-31
**评审方式**: 初次 6 维度并行审查 + 二次 5 agent 深度验证
**评审范围**: Phase 1-4 全部实现代码（~300 文件，~35,000 行）

---

## P0 — 立即修复（11 个，阻塞合并）

| # | 编号 | 问题 | 维度 | 状态 |
|---|------|------|------|------|
| 1 | C-1+NEW-C1 | Tushare token + 账户 ID 硬编码在版本控制中 | 安全 | ✅ 已修复 |
| 2 | C-2 | Domain 层 numpy import（ml_return_prediction_strategy.py） | 架构 | ✅ 已修复 |
| 3 | C-5 | 前瞻收益标签错误（用 return_5d 回溯收益代替前瞻收益） | ML | ✅ 已修复 |
| 4 | C-6+NEW-C5 | 训练/推理特征不匹配 + 推理无标准化 | ML | ✅ 已修复 |
| 5 | NEW-C2 | 熔断后交易循环继续下单（AutoTradingEngine 不检查暂停状态） | 安全 | ✅ 已修复 |
| 6 | NEW-C4 | 两套训练管道产出不兼容模型（pickle vs joblib） | ML | ✅ 已修复 |
| 7 | NEW-C6 | QmtTradeGateway 方法签名不匹配 IAccountGateway Protocol | 集成 | ✅ 已修复 |
| 8 | NEW-H6 | 推理特征数组顺序与训练不一致 | ML | ✅ 已修复 |
| 9 | NEW-C3 | 20+ 个 frozen dataclass 含可变 list/dict 默认值 | 架构 | ✅ 已修复 |
| 10 | C-7 | Dashboard/API 端点无认证暴露财务信息 | 安全 | ✅ 已修复 |
| 11 | C-4 | 训练管道缺少 Purging Gap（数据泄露） | ML | ✅ 已修复 |

## P1 — 尽快修复（16 个）

| # | 编号 | 问题 | 维度 |
|---|------|------|------|
| 1 | C-3 | Registry 反向依赖 infrastructure | 架构 |
| 2 | NEW-H1 | AutoTradingEngine 共享状态无锁保护 | 安全 |
| 3 | NEW-H2 | SSE 队列无上限 OOM 风险 | 安全 |
| 4 | NEW-H4 | 暂停状态文件可被篡改 | 安全 |
| 5 | NEW-H5 | fillna(median()) 使用未来信息 | ML |
| 6 | NEW-H7 | 训练/推理 NaN 处理不一致 | ML |
| 7 | NEW-H8 | 全数据重训练无保留样本评估 | ML |
| 8 | NEW-H9 | pickle/joblib 序列化路径不一致 | ML |
| 9 | NEW-H10 | CapitalAllocationEngine 违反 DIP | 架构 |
| 10 | NEW-H11 | DailySettlementService 无测试 | 测试 |
| 11 | NEW-H14 | Application 层无集成测试 | 测试 |
| 12 | NEW-M10 | 测试折用于 early stopping | ML |
| 13 | NEW-M11 | ModelLoader 缓存不失效 | ML |
| 14 | NEW-M21 | QmtTradeGateway 吞没初始化异常 | 集成 |
| 15 | NEW-M20 | 配置默认值与实现不匹配（佣金差25%，滑点差3倍） | 集成 |
| 16 | NEW-C3b | 6 个值对象缺 frozen=True | 架构 |

## P2 — 下个迭代（24 个）

其余 MEDIUM + LOW 问题，按模块逐步清理。
