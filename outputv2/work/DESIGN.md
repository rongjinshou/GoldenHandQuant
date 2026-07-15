# DESIGN — AI 修复方案（outputv2）

## 一句话

我们已完成「**检查**」（`work/bugs/` 全部详细 BUG 卡片，按执行批次组织）；交付让评测 AI agent
**按批次照卡片修复源码**，每批经 **棘轮护栏**（`ratchet.sh`：通过固化 / 失败自动回滚）门禁。
**纯 AI 正面解题，不依赖参考答案**——但用确定性护栏把 AI 的方差锁在批次内部。

## 核心哲学：确定性不来自答案，而来自协议

赛题是「设计实现一致性检查与修复」，赛道是 AI 竞赛。作品把能力拆三层：

- **检查层（作者侧已完成）**：12 模块逐一审查 + 全系统集成联调 + 三轮深审，150+ 项发现全部
  写成六字段卡片（文件/现状/期望/改法/验收/勿犯），按 19 个执行批次组织——公开用例受影响的
  模块在前（早修早锁分），结构性高危改动殿后。
- **修复层（评测机 AI 现场做）**：主 agent 按批次派 subagent（`bug-fixer` 规范）照卡片改
  `code/`——这是纯 AI 的部分，也是唯一必须由 AI 做的部分。
- **质量控制层（确定性脚本）**：`ratchet.sh` 把每批的结果二值化——编译过、用例通过数不回退且**没有任何此前通过的用例变红**（逐用例回归门，用例总数以运行环境实际为准）
  → 固化为新 golden；否则**自动回滚**，就当这批没发生。

数学效果：**最坏交付 = max(基线, 已固化最佳)**。AI 发挥好 → 高分；AI 发挥差 → 若干批被回滚、
其余批的成果保留;AI 崩溃 → 交付 = 最后一个 golden。「0 分交付」在结构上不可能。

## 为什么要棘轮（上一版的教训）

上一版（无护栏、修完统一看一眼）在 5 个独立评测运行中方差极大：2 次 24/24、1 次 58/72、
2 次**归零**（一次 ecommerce-order 编译错误交付、一次新建 CacheManager bean 冲突导致上下文
启动失败）。归零的两次把所有用例的投票拖垮。本版针对性改造：

1. **每批必验、失败自动回滚**——编译错误/bean 冲突/回归当场被吃掉，不可能带到交付；
2. **公开分优先 + 高危殿后**——速赢与公开用例相关的模块批先修先固化，结构性改动
   （事件/审计/缓存）押后，失败不拖累已锁定的成果；
3. **高危黑名单 + 「绝不做」清单**——把已知会炸上下文的操作（第二个 CacheManager、
   @EnableMethodSecurity、无 @Primary 消歧的裸 OrderLogisticsStatusUpdater 生产 bean 等）写成
   禁令（该端口的生产实现本身已由 B14/LOGI-11 以 @Primary 方案安全落地，禁令约束的是落地形态）；
4. **卡片详细化**——每卡六字段，改法对照已验证的最终代码写成方法级说明 + 验收断言，
   把「理解错误」的空间压到最小。

## 组件

| 组件 | 位置 | 作用 |
|---|---|---|
| BUG 卡片库 | `work/bugs/`（`README.md` 索引 + 19 批卡片文件） | 检查成果：六字段详细卡片 + 批次表 + 绝不做清单 |
| 棘轮护栏 | `work/harness/ratchet.sh` | snapshot / verify-固化 / 自动回滚（每批强制门禁） |
| 只读诊断 | `work/harness/check-all.sh` | 编译 + 全量用例，只报告不动工作树 |
| subagent 注册器 | `work/harness/install-agent.sh` | 把技能装进 OpenCode 项目级 + 全局（`~/.config/opencode/`）注册目录（幂等双保险） |
| subagent 技能 | `work/skills/bug-fixer/SKILL.md` | 单批修复规范：强制编译自检 + 高危黑名单 |
| 复核清单 | `work/checklist/<module>.md` | 逐模块强规则速查 |

## 执行流（详见 `INSTRUCTION.md`）

```
① cp -a <judge-assets>/. .                     源码 → 当前工作目录
② bash work/harness/ratchet.sh snapshot        基线检验 + golden 快照
③ for 批次 in B01..B19（work/bugs/README.md 批次表）:
       照卡片修 → bash work/harness/ratchet.sh verify
       ADVANCED/OK → 固化,下一批 | ROLLED_BACK → 重试一次 → 再败跳过
④ 最后一次 verify + status → result/output.md（STATUS: DONE）
   结果 = 当前工作目录 / code
```

## 与确定性回放变体（v1）的关系

同一份检查成果、两种落地：**v1（另一交付形态）** 用确定性哈希门控引擎**回放**已验证修复——
快、稳、可复现，但不体现 AI 解题过程；**v2（本作品）** **AI 照卡片现场修复**，用棘轮护栏保证
下界、用卡片质量抬升上界——修复代码由评测机 AI 逐字产生，无参考答案回放。

## 目录结构

```
outputv2/
├── INSTRUCTION.md                      评测入口（①cp ②snapshot ③批次循环+verify ④收尾）
├── work/
│   ├── DESIGN.md                       本文件
│   ├── bugs/                           BUG 卡片库
│   │   ├── README.md                   索引：批次表 B01–B19 / 字段说明 / 绝不做清单
│   │   ├── S1-quick-wins.md            B01 全局速赢
│   │   ├── S2-events.md                B13+B16 事件权威定义与监听器网络
│   │   ├── <module>.md × 12            B02–B12、B14–B15、B17 模块批（order/payment 内分 §A/§B）
│   │   ├── S3-audit.md                 B18 审计
│   │   └── S4-config.md                B19 限流+缓存
│   ├── harness/
│   │   ├── ratchet.sh                  棘轮护栏（快照/验证-固化/自动回滚）
│   │   ├── check-all.sh                只读诊断
│   │   ├── install-agent.sh            bug-fixer 注册为 OpenCode subagent
│   │   └── README.md
│   ├── skills/bug-fixer/SKILL.md       subagent 修复技能
│   └── checklist/<module>.md           逐模块强规则速查
├── result/output.md                    运行记录
└── logs/{interaction.md, trace/}       过程记录
```
