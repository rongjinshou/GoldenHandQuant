# GoldenHandQuant v2.0 遗留问题与需求

**日期**: 2026-05-20
**状态**: 待处理

---

## 一、首次测试发现的问题

### 问题 1：API 429 限流

**现象**：12 个 agent 同时调用 LLM API，触发 rate limit (429)

**根因**：Hermes kanban 调度器同时派发所有任务，没有并发控制

**临时解决方案**（已实施）：
- secretary 的 SOUL.md 加入分批串行执行规则
- 最多同时 2 个任务，分 6 个批次执行

**长期解决方案**：
- kanban 调度器支持 `max_concurrent_workers` 配置
- 或在 Hermes 层面实现 API 调用的队列管理

### 问题 2：Agent 使用训练数据回答

**现象**：分析角色没有调用 web_search/browser 获取实时数据，直接用模型训练数据回答

**根因**：SOUL.md 中没有强制要求先获取数据再分析

**临时解决方案**（已实施）：
- 给 6 个分析角色的 SOUL.md 加入"强制数据获取规则"
- secretary 的 SOUL.md 加入数据获取强制要求

**长期解决方案**：
- 在 Hermes 框架层面，为分析类 agent 添加"数据获取前置检查"
- 如果没有调用 web_search/browser，拒绝输出分析报告

---

## 二、需求：GoldenHandQuant CLI 脚本供 Hermes Agent 调用

### 背景

Hermes 的 agent 在执行投研任务时，需要获取 GoldenHandQuant 的实时数据（账户信息、持仓、行情等）。目前的方式是通过 web_search 搜索公开数据，但这有以下问题：

1. 数据不准确：公开数据可能延迟或不完整
2. 效率低：每次都要搜索，浪费 token
3. 无法获取私有数据：账户持仓、交易记录等无法通过搜索获取

### 需求描述

GoldenHandQuant 需要提供一组 **CLI 命令行脚本**，供 Hermes 的 agent 直接调用，获取结构化数据。

### 建议的 CLI 命令

```bash
# 1. 获取账户信息（资金、持仓）
python -m src.interfaces.cli.fetch_account

# 2. 获取单只标的的实时行情
python -m src.interfaces.cli.fetch_quote --symbol 600519.SH

# 3. 获取单只标的的财务数据
python -m src.interfaces.cli.fetch_financial --symbol 600519.SH

# 4. 获取单只标的的技术指标
python -m src.interfaces.cli.fetch_indicators --symbol 600519.SH --period 1d

# 5. 获取北向资金数据
python -m src.interfaces.cli.fetch_northbound

# 6. 获取龙虎榜数据
python -m src.interfaces.cli.fetch_dragon_tiger

# 7. 获取行业板块数据
python -m src.interfaces.cli.fetch_sector --sector semiconductor
```

### 输出格式

所有 CLI 命令输出 **JSON 格式**，便于 Hermes agent 解析：

```json
{
  "success": true,
  "data": {
    "symbol": "600519.SH",
    "price": 1850.00,
    "change_pct": 1.5,
    "volume": 12345678
  },
  "timestamp": "2026-05-20T10:30:00+08:00"
}
```

### 实现优先级

| 优先级 | 命令 | 理由 |
|--------|------|------|
| P0 | fetch_account | 已实现，投研任务必需 |
| P0 | fetch_quote | 每个分析角色都需要实时行情 |
| P1 | fetch_financial | 巴菲特分析必需 |
| P1 | fetch_indicators | 技术分析必需 |
| P2 | fetch_northbound | 量化侦察兵需要 |
| P2 | fetch_dragon_tiger | 量化侦察兵需要 |
| P3 | fetch_sector | 产业政策分析需要 |

### 技术实现要点

1. **复用 xtquant 接口**：底层调用 QMT 的 xtdata/xtquant
2. **Windows Python 执行**：xtquant 只能在 Windows Python 中运行
3. **WSL 调用方式**：通过 `/mnt/c/Users/.../python.exe -m src.interfaces.cli.xxx` 调用
4. **错误处理**：QMT 未连接时返回明确错误信息
5. **超时控制**：每个命令设置 30 秒超时

### Hermes Agent 集成方式

Hermes 的 agent 可以通过 `terminal` 工具调用这些 CLI 命令：

```
terminal(command="cd /mnt/c/Codes/GoldenHandQuant && /mnt/c/Users/11492/.conda/envs/goldenhandquant/python.exe -m src.interfaces.cli.fetch_quote --symbol 600519.SH")
```

---

## 三、后续计划

1. **短期**：完善 fetch_account 脚本，添加更多输出选项
2. **中期**：实现 fetch_quote、fetch_financial、fetch_indicators
3. **长期**：实现完整的 CLI 数据接口，支持 Hermes agent 直接调用
