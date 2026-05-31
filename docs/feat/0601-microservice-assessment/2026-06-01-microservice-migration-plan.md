# GoldenHandQuant 微服务迁移计划

> **版本**: v1.0 | **创建日期**: 2026-06-01 | **文档类型**: 迁移计划 (Migration Plan)

## 1. 迁移策略总览

### 1.1 核心原则

1. **渐进式迁移 (Strangler Fig Pattern)** — 新旧实现并存，逐步替换，不进行大爆炸式重构
2. **接口先行** — 利用现有 Protocol 接口，新增远程实现，保持调用方代码不变
3. **可回滚** — 每个阶段都可通过配置切换回本地实现
4. **回测先行** — 从对延迟不敏感的回测场景开始验证，再扩展到实盘

### 1.2 迁移范围

```
Phase 0: 基础设施准备（不改变业务逻辑）
   ↓
Phase 1: 策略服务化（回测场景验证）
   ↓
Phase 2: 行情数据服务化
   ↓
Phase 3: 风控规则引擎服务化
   ↓
Phase 4: 交易服务化（按需，仅在多券商需求时）
```

---

## 2. 阶段划分

### 2.1 Phase 0: 基础设施准备 (1-2 个月)

**目标**: 搭建微服务基础设施，不改变任何业务逻辑

#### 2.1.1 容器化

- 为现有单体应用创建 `Dockerfile`
- 编写 `docker-compose.yml`，定义服务编排
- 确保容器内回测结果与本地一致

#### 2.1.2 服务通信框架

- 定义统一的 Proto IDL 文件目录结构: `proto/`
- 实现基础 gRPC 服务框架（健康检查、优雅关闭、错误处理）
- 实现消息队列基础封装（连接管理、重试机制、死信队列）

#### 2.1.3 可观测性

- 集成 OpenTelemetry SDK（tracing + metrics）
- 统一日志格式为结构化 JSON
- 搭建 Prometheus + Grafana 监控栈
- 搭建 ELK 日志收集栈

#### 2.1.4 配置管理

- 将 `resources/trading.yaml` 和 `resources/backtest.yaml` 外部化
- 实现环境变量 + 配置文件的统一加载
- 支持远程配置热更新（初期可用文件 watch）

**验收标准**:
- [ ] 单体应用可 Docker 化运行
- [ ] gRPC 基础框架可用（echo 服务验证）
- [ ] Prometheus 采集基础指标
- [ ] 日志输出为结构化 JSON

---

### 2.2 Phase 1: 策略服务化 (2-3 个月)

**目标**: 将策略计算从回测主循环中解耦，支持远程策略执行

这是最关键的阶段，因为策略计算是当前系统的主要 CPU 瓶颈。

#### 2.2.1 Proto 定义

```protobuf
// proto/strategy/v1/strategy_service.proto
syntax = "proto3";
package goldenhandquant.strategy.v1;

service StrategyService {
  // 时序策略信号生成
  rpc GenerateBarSignals(GenerateBarSignalsRequest)
      returns (GenerateBarSignalsResponse);

  // 截面策略信号生成
  rpc GenerateCrossSectionalSignals(GenerateCrossSectionalSignalsRequest)
      returns (GenerateCrossSectionalSignalsResponse);

  // 因子计算
  rpc ComputeFactors(ComputeFactorsRequest)
      returns (ComputeFactorsResponse);

  // 健康检查
  rpc HealthCheck(HealthCheckRequest) returns (HealthCheckResponse);
}

message BarSignal {
  string symbol = 1;
  string direction = 2;  // BUY / SELL
  float confidence_score = 3;
  string strategy_name = 4;
}

message GenerateBarSignalsRequest {
  repeated string symbols = 1;
  string timeframe = 2;
  int32 lookback_count = 3;
  string strategy_name = 4;
  map<string, bytes> market_data = 5;  // 序列化的 Bar 数据
}

message GenerateBarSignalsResponse {
  repeated BarSignal signals = 1;
  map<string, float> current_prices = 2;
}
```

#### 2.2.2 实现步骤

1. **Proto 代码生成**: 使用 `grpcio-tools` 生成 Python stub
2. **策略服务端实现**: 包装现有 `BaseStrategy` 和 `CrossSectionalStrategy`
   - `src/infrastructure/grpc/strategy_service.py`
3. **策略客户端实现**: 实现 `IGrpcStrategyClient` 接口
   - `src/infrastructure/grpc/strategy_client.py`
4. **本地代理**: `LocalStrategyProxy` 实现与本地策略相同的接口
   - 根据配置选择本地执行或远程调用
5. **回测集成**: `BacktestAppService` 通过代理调用策略，无需修改核心逻辑
6. **结果验证**: 对比本地和远程执行的回测结果，确保完全一致

#### 2.2.3 关键设计决策

- **数据传输**: Bar 数据序列化为 Protobuf bytes，减少传输开销
- **连接管理**: gRPC channel 复用，支持连接池
- **超时策略**: 策略信号生成超时 30s，超时后降级为本地执行
- **负载均衡**: 初期单实例，后期可通过 Kubernetes Service 实现负载均衡

**验收标准**:
- [ ] 策略服务独立部署，可接收 gRPC 请求
- [ ] 回测结果与本地模式完全一致（逐日快照 diff = 0）
- [ ] 策略服务可水平扩展（多实例部署验证）
- [ ] 故障降级：策略服务不可用时自动回退本地执行

---

### 2.3 Phase 2: 行情数据服务化 (2-3 个月)

**目标**: 统一数据管理层，支持多数据源聚合和集中缓存

#### 2.3.1 Proto 定义

```protobuf
// proto/market/v1/market_service.proto
syntax = "proto3";
package goldenhandquant.market.v1;

service MarketService {
  rpc GetRecentBars(GetRecentBarsRequest) returns (GetRecentBarsResponse);
  rpc GetStockSnapshots(GetStockSnapshotsRequest) returns (GetStockSnapshotsResponse);
  rpc GetFundamentalData(GetFundamentalDataRequest) returns (GetFundamentalDataResponse);
  rpc DownloadHistoryData(DownloadHistoryDataRequest) returns (DownloadHistoryDataResponse);
}
```

#### 2.3.2 实现步骤

1. **数据源适配器**: 将 `QmtMarketGateway`、`TushareHistoryDataFetcher` 等封装为行情服务后端
2. **缓存层**: 引入 Redis 缓存热点数据（当日行情、最近 K 线）
3. **行情服务端**: 实现 gRPC 接口，聚合多数据源
4. **行情客户端**: 实现 `GrpcMarketGateway`，兼容 `IMarketGateway` 接口
5. **透明切换**: 通过配置选择本地或远程行情源

#### 2.3.3 缓存策略

| 数据类型 | 缓存策略 | TTL |
|----------|----------|-----|
| 当日实时行情 | 不缓存（实时获取） | - |
| 最近 K 线 (1d) | 写穿透缓存 | 交易日结束失效 |
| 历史 K 线 | 永久缓存（本地文件） | 永不过期 |
| 基本面数据 | 每日更新 | 24h |
| 停牌/退市状态 | 每日更新 | 24h |

**验收标准**:
- [ ] 行情服务独立部署，支持 gRPC 查询
- [ ] 缓存命中率 > 80%（回测场景）
- [ ] 多数据源透明切换（QMT ↔ Tushare）
- [ ] 回测结果与本地模式一致

---

### 2.4 Phase 3: 风控规则引擎服务化 (2-3 个月)

**目标**: 风控规则独立管理，支持动态更新

#### 2.4.1 设计思路

风控服务的拆分需要特殊考虑：逐单风控在交易链路上，延迟要求高。因此采用**规则引擎 + 本地代理**的混合模式：

- **风控规则引擎服务**: 管理和下发风控规则配置
- **本地风控代理**: 缓存规则配置，本地执行逐单风控检查
- **组合级风控服务**: 远程执行计算密集的组合级风控（VaR、压力测试、相关性分析）

#### 2.4.2 实现步骤

1. **规则定义 DSL**: 将现有风控策略（`HardStopLossPolicy`、`DailyLossPolicy` 等）抽象为可配置的规则
2. **规则引擎服务**: gRPC 接口，管理规则 CRUD 和下发
3. **本地风控代理**: `LocalRiskProxy` 实现 `RiskChain` 接口，缓存规则并本地执行
4. **组合级风控服务**: 将 `PortfolioRiskService`、`StressTestRunner` 等独立为远程服务
5. **熔断器状态同步**: 通过消息队列同步熔断器状态到各节点

#### 2.4.3 规则配置示例

```yaml
# 风控规则配置（由规则引擎服务管理）
risk_rules:
  - name: hard_stop_loss
    type: per_order
    enabled: true
    params:
      max_loss_rate: 0.05

  - name: daily_loss_limit
    type: per_order
    enabled: true
    params:
      max_daily_loss_rate: 0.03

  - name: circuit_breaker
    type: portfolio
    enabled: true
    params:
      max_daily_loss: 0.03
      max_total_drawdown: 0.20
      cooldown_days: 1
```

**验收标准**:
- [ ] 风控规则可通过 API 动态更新
- [ ] 逐单风控延迟 < 1ms（本地代理模式）
- [ ] 组合级风控可独立扩展
- [ ] 熔断器状态跨节点同步正确

---

### 2.5 Phase 4: 交易服务化 (可选，3-4 个月)

**目标**: 多券商接入，交易服务独立部署

#### 2.5.1 前提条件

此阶段**仅在以下条件满足时**推进：
- 需要支持多个券商（非 QMT 独占）
- 需要将交易终端部署到独立机器
- 需要高可用（交易服务主备切换）

#### 2.5.2 设计要点

1. **统一交易接口**: 扩展 `ITradeGateway`，定义标准化的订单提交/查询/撤单协议
2. **券商适配器模式**: 每个券商实现一个适配器（QMT、恒生、华锐等）
3. **订单状态管理**: 引入事件溯源（Event Sourcing）管理订单状态机
4. **分布式事务**: 使用 Saga 模式处理资金冻结 → 下单 → 成交的事务链
5. **高可用**: 交易服务主备部署，状态通过事件存储同步

#### 2.5.3 风险警告

- 订单状态机的分布式一致性是最大挑战
- T+1 结算逻辑跨服务实现复杂
- 资金冻结/解冻需要严格的事务保证
- **强烈建议**: 除非有明确的多券商需求，否则保持单体交易模块

**验收标准**:
- [ ] 支持至少 2 个券商适配器
- [ ] 订单状态机分布式一致性验证通过
- [ ] 交易服务高可用切换 < 5s
- [ ] 资金数据零丢失

---

## 3. 风险评估

### 3.1 风险矩阵

| 风险 | 概率 | 影响 | 风险等级 | 缓解措施 |
|------|------|------|----------|----------|
| 网络延迟影响实盘交易 | 高 | 高 | **严重** | 逐单风控保持本地代理；实盘链路不拆分 |
| 分布式事务数据不一致 | 中 | 高 | **高** | 初期避免拆分交易服务；使用事件溯源 |
| 回测结果不可重复 | 中 | 高 | **高** | 严格版本控制；确定性序列化；结果 diff 验证 |
| 运维复杂度上升 | 高 | 中 | **高** | 从 Docker Compose 开始；渐进式引入 K8s |
| QMT SDK Windows 限制 | 高 | 中 | **高** | 行情/交易网关保持 Windows 部署；通过 gRPC 暴露接口 |
| 团队技能不足 | 中 | 中 | **中** | 培训计划；从简单场景开始；文档先行 |
| 第三方依赖升级破坏兼容 | 低 | 中 | **低** | 依赖锁定；灰度升级 |
| 网络分区导致服务不可用 | 低 | 高 | **中** | 降级策略：本地模式兜底 |

### 3.2 关键风险详细分析

#### 3.2.1 网络延迟风险

**现状**: 当前进程内调用延迟 < 1us
**拆分后**: gRPC 局域网调用延迟约 0.5-2ms
**影响**: 实盘交易链路（信号 → 风控 → 下单）每增加 1ms 延迟，可能错过最优成交价

**缓解方案**:
- 逐单风控通过本地代理执行（规则从远程引擎缓存，检查在本地完成）
- 交易下单保持本地 SDK 调用（QmtTradeGateway 不拆分）
- 仅将计算密集的策略生成和组合级风控远程化

#### 3.2.2 数据一致性风险

**场景**: 回测结果在本地模式和远程模式下必须完全一致

**风险点**:
- 浮点数序列化精度损失
- 数据传输顺序变化导致计算结果不同
- 时钟同步问题

**缓解方案**:
- 使用确定性序列化格式（Protobuf，而非 JSON）
- 数据传输使用 bytes 原始格式，避免中间转换
- 回测场景使用固定时间戳，不依赖实时时钟
- 每阶段回归测试：对比本地和远程模式的逐日快照

#### 3.2.3 QMT SDK Windows 限制

**现状**: xtquant 仅支持 Windows Python 环境
**影响**: 行情和交易网关无法部署到 Linux 容器

**缓解方案**:
- 行情/交易网关保持 Windows 部署，通过 gRPC 暴露接口
- 使用 Windows 容器（Windows Server Core）或独立 Windows 机器
- 长期方案：寻找替代数据源（如 Wind、聚宽等）

---

## 4. 回滚策略

### 4.1 回滚原则

1. **配置切换即可回滚** — 每个服务化阶段都通过配置开关控制，回滚只需修改配置
2. **数据不丢失** — 回滚到本地模式后，远程服务的历史数据仍可查询
3. **零停机回滚** — 通过蓝绿部署或滚动更新实现

### 4.2 各阶段回滚方案

#### Phase 1 回滚（策略服务化）

```
配置切换: strategy.mode = "local" (默认) / "remote"
回滚操作: 修改配置文件 → 重启服务
回滚时间: < 1 分钟
数据影响: 无（策略服务不持有持久化数据）
```

#### Phase 2 回滚（行情服务化）

```
配置切换: market.source = "local" (默认) / "remote"
回滚操作: 修改配置文件 → 重启服务
回滚时间: < 1 分钟
数据影响: 远程缓存数据可能不同步，回滚后需重新拉取
```

#### Phase 3 回滚（风控服务化）

```
配置切换: risk.mode = "local" (默认) / "remote"
回滚操作: 修改配置文件 → 重启服务
回滚时间: < 1 分钟
数据影响: 远程规则配置可能与本地不一致，需同步
```

#### Phase 4 回滚（交易服务化）

```
配置切换: trade.mode = "local" (默认) / "remote"
回滚操作: 
  1. 确认无进行中的订单
  2. 切换配置
  3. 重启服务
回滚时间: < 5 分钟（需等待进行中订单完成）
数据影响: 远程订单状态需同步到本地
```

### 4.3 紧急回滚流程

```
1. 检测到异常（监控告警 / 业务指标异常）
2. 决策：是否需要回滚（< 5 分钟内决策）
3. 执行回滚：
   a. 修改配置，切换回本地模式
   b. 滚动重启服务实例
   c. 验证服务恢复正常
4. 事后分析：
   a. 收集远程服务日志
   b. 分析根因
   c. 修复后重新部署
```

---

## 5. 测试策略

### 5.1 各阶段测试要求

| 测试类型 | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|----------|---------|---------|---------|---------|
| 单元测试 | 现有测试全部通过 | 现有测试全部通过 | 现有测试全部通过 | 现有测试全部通过 |
| 集成测试 | 本地 vs 远程结果 diff = 0 | 本地 vs 远程结果 diff = 0 | 风控规则一致性验证 | 订单状态机一致性验证 |
| 性能测试 | 远程延迟 < 50ms | 缓存命中延迟 < 5ms | 逐单风控 < 1ms | 下单延迟 < 10ms |
| 故障注入 | 策略服务宕机 → 降级本地 | 行情服务宕机 → 降级本地 | 风控服务宕机 → 降级本地 | 交易服务宕机 → 停止交易 |
| 混沌工程 | 网络延迟 / 丢包测试 | 数据不一致测试 | 规则冲突测试 | 分布式事务测试 |

### 5.2 回测结果一致性验证

```python
# 验证脚本伪代码
def verify_backtest_consistency():
    # 1. 使用本地模式运行回测
    local_report = run_backtest(mode="local")
    
    # 2. 使用远程模式运行回测（相同输入）
    remote_report = run_backtest(mode="remote")
    
    # 3. 逐日快照对比
    for local_snap, remote_snap in zip(local_report.snapshots, remote_report.snapshots):
        assert local_snap.total_asset == remote_report.total_asset
        assert local_snap.pnl == remote_snap.pnl
        assert len(local_snap.positions) == len(remote_snap.positions)
    
    # 4. 交易记录对比
    assert len(local_report.trades) == len(remote_report.trades)
    for local_trade, remote_trade in zip(local_report.trades, remote_report.trades):
        assert local_trade == remote_trade
```

---

## 6. 时间线与里程碑

```
2026 Q3 (7-9 月)
├── Phase 0: 基础设施准备
│   ├── M1: Docker 化 + gRPC 框架        (7 月)
│   ├── M2: 监控 + 日志栈搭建            (8 月)
│   └── M3: 配置管理外部化               (9 月)
│
2026 Q4 (10-12 月)
├── Phase 1: 策略服务化
│   ├── M4: Proto 定义 + 服务端实现       (10 月)
│   ├── M5: 客户端 + 代理实现             (11 月)
│   └── M6: 回测验证 + 故障注入测试       (12 月)
│
2027 Q1 (1-3 月)
├── Phase 2: 行情数据服务化
│   ├── M7: 行情服务端 + 缓存层           (1 月)
│   ├── M8: 客户端集成 + 多数据源验证     (2 月)
│   └── M9: 性能优化 + 压力测试           (3 月)
│
2027 Q2 (4-6 月)
├── Phase 3: 风控服务化
│   ├── M10: 规则引擎 + 本地代理          (4 月)
│   ├── M11: 组合级风控服务化             (5 月)
│   └── M12: 全链路集成测试               (6 月)
│
2027 Q3+ (按需)
└── Phase 4: 交易服务化（仅在多券商需求时）
    ├── M13: 统一交易接口 + 适配器模式
    ├── M14: 事件溯源 + 分布式事务
    └── M15: 高可用 + 混沌工程测试
```

---

## 7. 成本评估

### 7.1 基础设施成本

| 资源 | Phase 0-1 | Phase 2-3 | Phase 4 |
|------|-----------|-----------|---------|
| 服务器 | 1 台开发机 | 2-3 台（含 Windows） | 4-5 台 |
| Docker Registry | 共享或自建 | 自建 Harbor | 自建 Harbor |
| 监控栈 | 单节点 Prometheus + Grafana | 高可用部署 | 高可用部署 |
| 消息队列 | 单节点 RabbitMQ | 集群部署 | 集群部署 |
| 月成本估算 | ~500 元 | ~1500 元 | ~3000 元 |

### 7.2 人力成本

| 角色 | Phase 0-1 | Phase 2-3 | Phase 4 |
|------|-----------|-----------|---------|
| 后端开发 | 1 人 x 3 月 | 1 人 x 6 月 | 2 人 x 4 月 |
| DevOps | 0.5 人 x 2 月 | 0.5 人 x 3 月 | 1 人 x 3 月 |
| 测试 | 0.5 人 x 2 月 | 0.5 人 x 3 月 | 1 人 x 3 月 |

---

## 8. 总结

### 8.1 核心建议

1. **Phase 0 和 Phase 1 是最高优先级** — 基础设施准备 + 策略服务化，投入产出比最高
2. **Phase 2-3 按需推进** — 取决于数据管理复杂度和风控演进需求
3. **Phase 4 谨慎评估** — 仅在多券商需求明确时推进，风险最高
4. **始终保持本地模式可用** — 作为所有远程服务的降级方案

### 8.2 成功标准

- Phase 1 完成后：回测策略计算可水平扩展，ML 推理可部署到 GPU 节点
- Phase 2 完成后：数据管理统一，缓存命中率 > 80%
- Phase 3 完成后：风控规则可动态更新，无需重启服务
- 全部完成后：系统支持多策略、多账户、多券商的统一管理

### 8.3 决策检查点

| 检查点 | 决策依据 | 继续/暂停/终止 |
|--------|----------|---------------|
| Phase 0 完成 | 基础设施是否稳定 | 继续 → Phase 1 |
| Phase 1 完成 | 回测性能是否提升 > 50% | 继续 → Phase 2 |
| Phase 2 完成 | 数据管理复杂度是否降低 | 继续 → Phase 3 |
| Phase 3 完成 | 风控灵活性是否提升 | 评估 → Phase 4 |
| Phase 4 评估 | 是否有多券商需求 | 是 → 继续 / 否 → 终止 |

---

## 附录 A: 技术栈清单

| 类别 | 技术 | 版本 | 用途 |
|------|------|------|------|
| RPC | grpcio | >= 1.60 | 服务间通信 |
| Proto | protobuf | >= 4.25 | 接口定义 |
| 消息队列 | pika (RabbitMQ) | >= 1.3 | 异步事件 |
| 容器 | Docker | >= 24.0 | 应用打包 |
| 编排 | Docker Compose | >= 2.20 | 本地开发 |
| 监控 | prometheus_client | >= 0.19 | 指标采集 |
| 追踪 | opentelemetry-sdk | >= 1.20 | 链路追踪 |
| 日志 | python-json-logger | >= 2.0 | 结构化日志 |

## 附录 B: Proto 文件目录结构

```
proto/
├── market/
│   └── v1/
│       ├── market_service.proto
│       └── market_types.proto
├── strategy/
│   └── v1/
│       ├── strategy_service.proto
│       └── strategy_types.proto
├── risk/
│   └── v1/
│       ├── risk_service.proto
│       └── risk_types.proto
├── trade/
│   └── v1/
│       ├── trade_service.proto
│       └── trade_types.proto
└── common/
    └── v1/
        ├── health.proto
        └── common_types.proto
```

## 附录 C: 目录结构变更

微服务化后的建议目录结构（在现有结构基础上新增）：

```
src/
├── ... (现有结构不变)
├── infrastructure/
│   ├── ... (现有结构不变)
│   ├── grpc/                    # 新增：gRPC 服务实现
│   │   ├── server.py
│   │   ├── market_service.py
│   │   ├── strategy_service.py
│   │   ├── risk_service.py
│   │   └── trade_service.py
│   ├── grpc_client/             # 新增：gRPC 客户端
│   │   ├── market_client.py
│   │   ├── strategy_client.py
│   │   └── risk_client.py
│   └── messaging/               # 新增：消息队列
│       ├── rabbitmq_client.py
│       └── event_publisher.py
├── proto/                       # 新增：Proto 定义
│   ├── market/v1/
│   ├── strategy/v1/
│   ├── risk/v1/
│   └── common/v1/
└── deploy/                      # 新增：部署配置
    ├── docker/
    │   ├── Dockerfile
    │   └── docker-compose.yml
    ├── k8s/                     # 后期
    │   ├── deployments/
    │   └── services/
    └── monitoring/
        ├── prometheus.yml
        └── grafana/
```
