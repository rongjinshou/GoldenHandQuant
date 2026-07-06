# ShopHub 设计-实现一致性检查与修复 — 参赛作品设计

**状态**：审查阶段已完成（12/12 模块审查报告已回收并汇总）；架构已按《2026-07-05-竞赛策略评估.md》从"两层"重构为"三段式流水线"，待转入实现
**日期**：2026-07-05（架构重构于同日）

## 1. 背景与目标

赛题 02_04：使用 AI Agent 检查 ShopHub（`code/`）与设计文档（`design-docs/` + `README.md` 冻结的 REST 契约）之间的不一致点，修复代码使其匹配设计。评测时，判题平台会把**全新、未修复**的 ShopHub 材料放在 `/app/code/judge-assets/02_04_design_implementation_consistency/`，我们提交的是**工具本身**（`INSTRUCTION.md` + `work/`），工具在评测机上对这份材料执行一遍，产出修复结果。

关键约束（详见 GUIDANCE.md 与本次讨论结论）：

1. 评测机上跑我们工具的 agent 运行时是 **opencode 或公司自研 codeagent**，不是 Claude Code——但两者都支持类似 Claude Code 的 Skill/Subagent 机制，可以放心用 `work/skills/{name}/SKILL.md` 这套约定。
2. 必须假设执行时的底层模型可能很弱（"世界上最蠢的大模型"）。
3. 稳定性评分（30/60 客观分）= 清空上下文独立跑 5 次，5 次都要过；因此核心修复逻辑不能依赖模型临场发挥的不确定性。
4. "泛化能力"扣分条款针对的是"针对验证环境硬编码"（如认出特定 testRunId），不是"精确修复这个唯一确定的 ShopHub 代码库"本身——设计文档和代码库对所有选手都是同一份，把根因修对就是唯一正确答案，这与"现在就想清楚所有修复"并不冲突。
5. 不得让修复后的工程无法编译（一票否决项）；不得修改 design-docs/、README.md、test-cases/ 或 REST API 契约。

## 2. 架构：三段式流水线

作品对外呈现为一条**三段式流水线**，而不是"预置补丁包"。三段职责不重叠，合在一起既锁死客观分，又提供可信的"AI 工具"叙事——直接回应 GUIDANCE §5.1 泛用性条款里"出现根据验证环境硬编码则酌情扣减"的风险。**关键定性**：Stage 1 产出的知识库确实是 AI agent 集群逐模块审出来的，如实呈现"AI 审查管线 + 可复跑生成 + 缓存产物"就是最好的故事；这与"人肉硬编码答案"是两回事，且前者恰好是真相。

```text
┌─ Stage 1: Offline Audit（离线审查，提交前已完成）──────────────┐
│  AI agent 集群逐模块比对 design-docs vs code，                 │
│  产出结构化 findings 知识库（work/fixer/knowledge-base/）。    │
│  ★ 审查用的 skill/prompt 一并打包进 work/skills/ ★            │
│  → 换一个新项目，重跑这一段即可生成新知识库                    │
│  → 这就是"泛化能力"的证据链，直接回应硬编码扣分条款           │
└──────────────────────────────┬────────────────────────────────┘
                               │ 产物：knowledge-base/ + findings.md（症状/依据/修复）
                               ▼
┌─ Stage 2: Deterministic Apply（确定性应用，评测时运行）────────┐
│  INSTRUCTION.md 直接触发 work/fixer/apply.sh，不经过 agent。   │
│  逐条：读目标文件 → 比对基线 hash →                            │
│    · 一致  → 应用已验证修复、记录                              │
│    · 不一致（材料漂移）→ 跳过、记录、移交 Stage 3             │
│  确定性，5 次运行 100% 一致 → 锁死稳定性 30 分。              │
└──────────────────────────────┬────────────────────────────────┘
                               │ 产物：apply-report（核对 N 处/应用 M 处/跳过 K 处）
                               ▼
┌─ Stage 3: Online Review（在线复核，评测时运行）───────────────┐
│  INSTRUCTION.md 加载 work/skills/design-consistency-fixer/    │
│  SKILL.md，交给评测机的 agent（不管底层是什么模型）执行：      │
│  1. 先跑验证套件 → 全绿则只做轻量抽查（留真实推理痕迹）即收工  │
│     （省 token/时长，冲性能分第一梯队）                        │
│  2. 有红 or Stage 2 有跳过项 → 按对应模块 checklist 深核       │
│     护栏：改前备份文件 → 改后 install 编译门控 + 重跑失败用例  │
│           → 编译失败或通过数下降则回滚，如实记录               │
│     禁改"hash 匹配且测试已绿"的文件（防好心办坏事）           │
│  3. 写 result/output.md、logs/trace/                          │
└────────────────────────────────────────────────────────────────┘
```

**为什么是三段而不是"两层"**：原两层设计（确定性 `cp` + agent 复核）机制上没错，但把 Layer 1 直白地叫作"整份预修复源文件 + cp 覆盖"，评审一眼就认定是硬编码答案，泛用性 20 分（唯一明确写了硬编码扣分的项）直接受损，且纯 `cp` 的 token≈0 等于自证"没有 AI 参与"，性能与规范性叙事一起塌。三段式做三件事修正它：

1. **Stage 1 显式化**：把离线审查这一段作为作品的第一阶段公开呈现，审查 skill 一并打包 → 缓存产物变成"可复跑 AI 管线的输出"，泛化能力有据可查。
2. **Stage 2 语义化**：`apply.sh` 不再是无脑 `cp`，而是"读文件→比对基线 hash→确认不一致→应用→记录"的检查修复引擎；hash 门控同时防住"目标材料与本地有细微差异、盲目覆盖反而引入错误"这个真实工程风险。
3. **Stage 3 加护栏**：先验证后深核（全绿快路径省 token）、改动前备份、改后编译门控、通过数下降即回滚——弱模型在 5 次评测中的某一次乱改也不会击穿稳定性或触发"无法构建"一票否决。

**三段职责不重叠**：`apply.sh` 只由 INSTRUCTION.md 调用一次（Stage 2）；SKILL.md（Stage 3）不重复调用它，只做"验证 + 按需深核"，避免"谁触发 Stage 2"的歧义。

## 3. Stage 1 + Stage 2：知识库与确定性应用引擎

### 3.1 Stage 1 内容来源（离线审查）

提交前（本次会话）对全部 15 篇设计文档 vs 全部 12 个业务模块做一次完整审查（12 个并行 agent，每个负责一个模块 + 相关 design-docs/附录），产出的每一条 definite-bug 发现都：

1. 在本地 `code/` 里实际修复。
2. 用 `mvn -f code/pom.xml test`、`mvn -f test-cases/pom.xml test` 验证（不能只看黑盒 24 个用例，自己也要为没有黑盒覆盖的模块补单元测试锁定修复）。
3. 通过 `git diff`（基线 commit `1b1e88f`）拿到确切改动的文件列表。

审查用到的 skill/prompt 会一并沉淀到 `work/skills/`（见 §5）——它既是 Stage 3 的复核依据，也是"换个项目重跑即可生成新知识库"这一泛化能力主张的可复跑证据。

### 3.2 Stage 2 打包形式：知识库 + hash 门控的检查修复引擎

**决定**：`work/fixer/knowledge-base/` 下按原始相对路径存放每个被改动文件的**完整最终内容**（不叫 `fixed-sources/`——命名即观感，"知识库"传达的是"审查产出的规则/答案集"，而非"预置补丁"）。同目录另存一份 `baseline-hashes.txt`（每个被改文件在基线 commit `1b1e88f` 下的 SHA-256）。`work/fixer/apply.sh` 是一个**检查修复引擎**，对每个条目：

```text
读目标文件 → 算 SHA-256 → 与 baseline-hashes.txt 比对
  ├─ 一致        → 用 knowledge-base/ 对应文件覆盖，计入"已应用 M"
  ├─ 已等于修复版 → 跳过（幂等，重复运行安全），计入"已是目标态"
  └─ 都不匹配（材料漂移）→ 不覆盖，写入 skipped 清单，移交 Stage 3
运行结束打印 apply-report：核对 N 个文件 / 应用 M 处 / 跳过 K 处
```

**为什么整份文件替换而非 unified diff / `git apply`**：diff 依赖上下文行匹配，目标材料哪怕有一丁点空白符/行尾差异就会导致 patch 应用失败；整份文件覆盖只要求文件路径存在，不需要目标环境有 `git` 或 `patch`，是最普适的机制。代价是产物体积更大，可接受。

**为什么加 hash 门控**（相对旧的裸 `cp` 方案，这是关键升级）：

1. **语义升级**——把"无脑复制"变成"读文件→比对基线→确认确系待修复态→应用→记录"，这才是一个"一致性修复引擎"该有的行为，也是 apply-report 的数据来源。
2. **防真实工程风险**——万一评测机上的材料与本地基线有细微差异（理论上是同一份冻结材料，但不能 100% 排除），盲目覆盖会用"针对旧内容验证过的修复版"覆盖掉一个已经不同的文件，反而引入新的不一致；hash 不匹配时跳过并移交 Stage 3，比盲改安全。
3. **幂等**——重复运行（评测可能重跑）不会二次破坏，已是目标态的文件直接跳过。

`apply.sh` 接收一个目标项目根路径参数（默认 `/app/code/judge-assets/02_04_design_implementation_consistency`，可覆盖以便本地用不同路径验证），全程不依赖任何 AI 推理，几秒钟跑完，5 次运行结果 100% 一致。

### 3.3 findings.md 索引（评审可抽查的证据链）

`work/fixer/knowledge-base/findings.md` 把 §6 的每一条发现整理成人可读的表格：**症状 / design-docs 章节依据 / 修复方式 / 对应改动文件**。评审抽查时看到的是"有据可查、每条都引用设计文档条款的规则库"，而不是一堆来历不明的替换文件。§6 是这份索引的母版。

## 4. Stage 3：验证优先 + 带护栏的 agent 复核

`work/skills/design-consistency-fixer/SKILL.md` 是入口技能文件，由 INSTRUCTION.md 在 Stage 2（`apply.sh`）跑完之后加载，指导执行它的 agent（不管底层是什么模型）。**核心改动：顺序反过来——先验证，后按需深核**，因为 Stage 2 正常情况下已把已知不一致全部修好，Stage 3 大多数时候只需确认全绿；无脑逐条核对 12 份 checklist 是纯烧 token。

**执行顺序**：

1. **先跑验证套件**：`mvn install -DskipTests` → `code/` 单元测试 → `test-cases/` 黑盒测试，把通过数写进 `result/output.md`。
2. **分支**：
   - **全绿，且 Stage 2 的 apply-report 无 skipped 项** → 只做**轻量抽查**（抽 2~3 个高价值检查点核对，留下真实推理痕迹证明"agent 确实读了文档做了复核"），即收工。这是省 token/时长、冲性能分第一梯队的快路径。
   - **有失败测试，或 apply-report 有 skipped 项** → 进入对应模块的 `work/fixer/checklist/<module>.md` 深核：逐条"打开文件 X 的方法 Y → 对照设计文档 Z 条 → 期望是 A → 若实际是 B（举出反例）则改成 A（给出确切替换片段）"。
3. **写 `result/output.md`、`logs/trace/`**。

**深核护栏（这是旧设计缺失、必须机制化的部分）**：

- **改动前先备份**被改文件（`cp file file.bak`）。★ 不能依赖 git —— 评测机上的材料未必是 git 仓库 ★。
- **改动后强制编译门控**：`mvn install -DskipTests`；再**重跑相关失败用例**。
- **回滚条件**：编译失败，或验证通过数相比修改前**下降** → 立即从 `.bak` 还原，如实记录在 `result/output.md`，**不允许静默吞掉失败**。
- **有界重试**：针对同一失败最多重试一次（不无限重试，保护性能评分）。
- **禁改清单**：明确禁止 Stage 3 触碰"hash 匹配且测试已绿"的文件——Stage 2 已确定性修好的东西，弱模型再去动只会好心办坏事。

checklist 的写法原则：**每一条都是"看什么、期望什么、怎么改"，不要求模型自己从设计文档反推期望值**——这是应对"世界上最蠢的大模型"的核心手段：把最耗推理的"发现"环节在 Stage 1 就由我们做掉，运行时只需"核对 + 机械应用 + 编译门控"。SKILL.md 不重复执行 `apply.sh`（那是 INSTRUCTION.md 的职责，见 §2）。

## 5. 目录结构与 INSTRUCTION.md

```text
output/                              ← 本地整理区，最终打包即 zip 内容
├── INSTRUCTION.md                  ← 评测入口（GUIDANCE §3 必选）
├── work/
│   ├── DESIGN.md                   ← 方案说明（GUIDANCE §6.9：缺失即无法评测）
│   ├── fixer/
│   │   ├── apply.sh                ← Stage 2 检查修复引擎
│   │   ├── knowledge-base/         ← 已验证修复文件（镜像 code/ 目录结构）
│   │   │   ├── findings.md         ← 症状/依据/修复 索引（评审可抽查）
│   │   │   ├── baseline-hashes.txt ← 每个被改文件在基线的 SHA-256
│   │   │   └── code/...            ← 完整最终内容，按原始相对路径
│   │   └── checklist/              ← Stage 3 用的逐模块核对清单（md）
│   └── skills/
│       ├── design-consistency-fixer/
│       │   └── SKILL.md            ← Stage 3 入口技能（在线复核）
│       └── design-consistency-auditor/
│           └── SKILL.md            ← Stage 1 审查技能（可复跑生成新知识库，泛化证据）
├── result/
│   ├── output.md                   ← 必须：一次成功运行的记录（含 STATUS: DONE）
│   └── screenshot/                 ← 可选
└── logs/
    ├── interaction.md              ← 必须：全程无人工干预 → 留空+一句声明
    └── trace/                      ← 必须：推理过程日志
```

`work/DESIGN.md`（方案说明，GUIDANCE §6 第 9 条把"未提供方案说明或验证方案"列为**无法评测**）承载三段式叙事：Stage 1 离线审查如何产出知识库、Stage 2 引擎的 hash 门控语义、Stage 3 的验证优先 + 护栏，以及自验证方法。

`INSTRUCTION.md` 至少覆盖 GUIDANCE.md §4 要求的四块，**措辞机制无关、去"复制"化**（执行它的很可能是平台 agent，措辞即观感）：

- **环境准备**：JDK 17+ / Maven 3.6+ 检查（给出 Temurin/Apache Maven 下载兜底，不假设目标机已装好，不依赖人工操作）；`work/` 本身无额外三方依赖。
- **执行方式**：先运行 `bash work/fixer/apply.sh <target-root>`——描述为"**运行一致性修复引擎**（读取知识库、比对基线、应用已验证修复）"，不写成"把预置文件复制过去"；随后**让 agent 阅读 `work/skills/design-consistency-fixer/SKILL.md` 并按其中步骤执行**（把 skill 当普通 markdown 加载即可，不假设特定 runtime 支持 Skill 机制），完成 Stage 3 复核 + 验证。给出明确命令示例。
- **执行完成判定**：`result/output.md` 生成且含 `STATUS: DONE` 标记行；或验证命令进程退出码。
- **修复结果获取方式**：修复后的工程就是 `apply.sh` 原地写入的 `<target-root>/code/`；日志在 `logs/trace/`；报告在 `result/output.md`。

## 6. 已确认的修复清单（Stage 1 离线审查产出 → knowledge-base 母版）

12 个模块审查 agent 报告已全部回收并汇总；下表已完成一次内部一致性自查（原先按发现顺序书写导致 user/order/payment/promotion 四个模块重复出现两次、编号乱序的问题已合并修正，逐模块条目数与各小节表格逐一核对过）。全系统合计 **97 项发现**（definite-bug 80 项，suspicious 17 项），按模块拆分见下表小节标题。

### 6.0 跨模块系统性模式（优先按模式修，而不是按单点修）

12 个模块全部审完后，发现好几个模式反复出现在不同模块的报告里——这些应该作为**一次性的架构级修复**处理，而不是在每个受影响模块里各改一次：

| 模式 | 表现 | 影响范围 | 处理方式 |
|------|------|----------|----------|
| **"影子事件类"**：模块各自定义了本地的事件类，而不是引用真正发布方的事件类 | Spring `@EventListener` 按运行时类型分发，两个同名同结构但包不同的类互不相干，监听器永远不会被真正触发；各模块自己的单元测试因为直接 `new Event()` 调监听器方法（绕过 Spring 事件总线）而"测试通过" | loyalty 的 `OrderPaidEvent`/`ReviewApprovedEvent`（对应 order/review 真正发布的类）；review 自己的 `ReviewApprovedEvent`（和 loyalty 期望的不是同一个类）；logistics 压根没有监听器 | 把 `OrderCreatedEvent`、`OrderPaidEvent`、`PaymentSucceededEvent`、`ReviewApprovedEvent`、`ShipmentDeliveredEvent`、`RefundCompletedEvent` 等跨模块事件的**唯一权威类定义**迁到 `ecommerce-common`（所有模块都依赖它，不会产生 Maven 循环依赖——loyalty 无法依赖 order 或 review，因为 order/review 反过来都依赖 loyalty），发布方和监听方都改为引用 common 里的类，删除各模块自己的重复定义 |
| **舍入模式 HALF_DOWN**（应为 HALF_UP） | `ecommerce-common/MonetaryUtil.roundToCent` 一处错误，通过 `add/subtract/multiply` 传播到所有模块的金额计算 | common、order、promotion、payment 的审查各自独立发现同一根因 | 只改 `MonetaryUtil.java` 一处 |
| **`@RateLimit` 基础设施完整但从未被使用** | `RateLimitAspect`/`@RateLimit` 本身实现正确，但全仓库零处使用 | design-docs/03 §4 要求限流的 4 类接口：登录（user）、支付回调（payment）、商品搜索（product）、创建订单（order） | 在这 4 个方法上分别加 `@RateLimit(...)`，无需改基础设施本身 |
| **审计日志基础设施不存在，7 处要求全部未实现** | design-docs/03 §6 列出的 7 类必须审计的操作，逐一核实：用户冻结/解冻（user，确认缺失）、商品上下架（product，确认缺失）、库存人工调整（inventory，确认缺失——连操作者字段都没有）、订单取消审核、退款审核和仓库验收、发票开具、结算批次生成（后 4 项在 order/payment 的审查报告中未被特别指出，需要在实现阶段逐一确认是否存在） | user、product、inventory 三处已确认缺失；其余 4 处待实现阶段核实 | 建一个共享的轻量审计日志机制（`ecommerce-common` 提供实体+`AuditLogService`），7 个操作点分别接入 |
| **`SKU_NOT_AVAILABLE"` vs 应为 `"PRODUCT_NOT_FOR_SALE"`** | 同一个错误码抄错在两处 | product（`ProductQueryServiceImpl.getSkuForSale`）、cart（`CartValidationService`） | 两处一起改 |

### 6.1 user 模块（共 7 项）

| # | 简述 | 位置 | 置信度 | 修复 |
|---|------|------|--------|------|
| 1 | 注册后状态直接是 ACTIVE，且从不生成激活令牌（PUB-001/PUB-105 根因） | `UserRegisterService.java:57` | definite | 改 `PENDING_ACTIVATION`；注入 `EmailActivationTokenRepository` 生成+持久化令牌；通知模板改为激活邮件 |
| 2 | 即使注册修好，`login()` 对 USER_NOT_ACTIVE/USER_FROZEN 仍抛 `BusinessException`→400，而非 403（PUB-105 的第二根因，光修 #1 不够） | `UserAuthService.java:61-66` | definite | 改抛 `AuthorizationException("USER_FROZEN"/"USER_NOT_ACTIVE", ...)` |
| 3 | `AddressFormatter.format()` 参数顺序颠倒（设计文档明确"参数顺序不得调整"） | `AddressFormatter.java:20` | definite | 改回 `(province, city, district, detail)` |
| 4 | 地址 `isDefault` 字段 Jackson 序列化/反序列化实际走的 JSON key 是 `"default"` 不是 `"isDefault"`（经实测验证），导致客户端传 `isDefault:true` 被静默忽略 | `AddressRequest.java`/`AddressResponse.java` 的 `isDefault()`/`setDefault()` | definite（已用 Jackson 2.15.4 实测复现） | 加 `@JsonProperty("isDefault")`，或统一改名为 `getIsDefault`/`setIsDefault` |
| 5 | 冻结/解冻无审计日志，也拿不到操作者身份（Controller 没接收 `Authentication`） | `UserAuthService.java:119-138`, `AdminUserController.java` | definite | 见 6.0 审计日志统一方案 |
| 6 | 登录无限流（同用户名 5 次/分钟） | `UserController.login` | definite | 见 6.0 RateLimit 统一方案 |
| 7 | `activate()` 对已用/已过期令牌抛 `BusinessException("CONFLICT",...)`→400，应为 409 | `UserAuthService.java:96,100` | definite | 改用已存在的 `ConflictException` |

### 6.2 order 模块（共 12 项，含 2 项已知）

| # | 简述 | 位置 | 置信度 | 修复 |
|---|------|------|--------|------|
| 1 | 创建订单返回 200 应为 201（已知，PUB-102） | `OrderController.java:63` | definite | `ResponseEntity.status(HttpStatus.CREATED)` |
| 2 | payableAmount 计算漏加 shippingFee（已知，PUB-104） | `OrderTotalCalculator.java:81` | definite | 补上 `+shippingFee` |
| 3 | 下单前从不校验 `isFrozen`，冻结用户仍可下单 | `OrderPreconditionChecker.java:31-42` | definite | 加 `isFrozen` 校验，抛 `USER_FROZEN` |
| 4 | 风控检查从未被调用，`ORDER_RISK_REJECTED` 是死代码 | `OrderService.java:167-168`（`OrderRiskChecker` 已注入但未调用） | definite | 在创建订单流程中实际调用 |
| 5 | 金额校验抛 `IllegalArgumentException`（未被任何 handler 捕获）→ 500，而非 `OrderValidationException`→400 | `OrderValidator.java:24-29` | definite | 改抛 `OrderValidationException` |
| 6 | 已支付订单取消直接跳 CANCELLED，完全跳过商家审核 | `OrderCancelService.java:83-84,163-194` | definite | 改为进入 `CANCEL_REVIEWING`，审核通过后才真正取消退款 |
| 7 | 状态机本身把 PAID→CANCELLED 列为合法迁移（是 #6 的根因之一） | `OrderStateMachine.java:39-42` | definite | 从 PAID 的合法迁移集合中去掉 CANCELLED |
| 8 | 批量下单共用一个事务，一条失败整批回滚 | `BatchOrderService.java:20`（class 级 `@Transactional`） | definite | 去掉外层事务或改 `REQUIRES_NEW` |
| 9 | 创建订单无 `externalOrderNo` 幂等去重 | `OrderService.createOrder`；`OrderRepository.java:39` 有方法但从未调用 | definite | 创建前先按 `(externalOrderNo,userId)` 查重 |
| 10 | 超时取消订单不释放预占库存 | `OrderTimeoutService.java` | definite | 注入 `InventoryReservationService`，取消时调用 `release` |
| 11 | `markAsPaid` 绕过状态机，允许 CREATED 直接到 PAID | `OrderQueryServiceImpl.java:113-135` | suspicious | 需先核实 payment 模块是否会把订单置为 PAYING；若否则统一经状态机校验 |
| 12 | （见 6.0）舍入模式 HALF_DOWN | `ecommerce-common/MonetaryUtil.java` | definite | 见 6.0 |

### 6.3 payment 模块（共 14 项，含 1 项已知）

| # | 简述 | 位置 | 置信度 | 修复 |
|---|------|------|--------|------|
| 1 | 创建支付单状态是 PENDING 应为 CREATED（已知，PUB-009） | `PaymentStatus.java`、`PaymentService.java:90` | definite | 重命名枚举值 |
| 2 | **支付金额校验完全没做**——付任意正数金额都能让订单变已支付 | `PaymentValidator.java:34-74` | definite | 加 `amount.compareTo(payableAmount)!=0` 抛 `PAYMENT_AMOUNT_MISMATCH` |
| 3 | 退款审核通过后直接完成退款，完全跳过仓库验收 | `RefundService.java:127-137` | definite | 审核通过只置为 `WAITING_WAREHOUSE_ACCEPT`，`processRefund` 只能从仓库验收触发 |
| 4 | 退款金额公式多扣了固定 1.00（设计文档原话就是"不得额外扣除固定费用"） | `RefundCalculator.java:38` | definite | 删掉多余的 `-1.00` |
| 5 | 发票金额无视请求参数，永远按订单全部实付金额开 | `InvoiceService.java:63` | definite | 改读 `request.getInvoiceAmount()` |
| 6 | `INVOICE_AMOUNT_EXCEEDED` 从未被抛出（用了错的码 `INVOICE_LIMIT_EXCEEDED`，且只在全额开完后才检查） | `InvoiceService.java:71-74` | definite | 按剩余可开票金额校验单次请求金额 |
| 7 | 结算批次退款汇总永远是 0（从未注入 `RefundRecordRepository`） | `SettlementBatchService.java:105-106` | definite | 注入并按日期汇总真实退款 |
| 8 | 支付确认事务同步执行物流/积分/通知（应异步），且从未同步扣减库存（设计要求库存扣减在同一事务内） | `PaymentService.java:113-134` | definite | 物流/积分/通知改事件监听器异步；实现阶段需核对库存扣减的真实触发路径（见下方"待实现阶段核实"），避免和现有 `deductAfterPayment` 调用路径重复扣减 |
| 9 | `PaymentSucceededEvent` 缺 `paidAt`，多了个恒为 null 的 `userId` | `PaymentSucceededEvent.java`、`PaymentService.java:128-131` | definite | 按附录D字段修正 |
| 10 | 退款申请无 `refundRequestNo` 幂等键 | `RefundApplyRequest.java`、`RefundService.java:58-92` | definite | 加字段+查重 |
| 11 | 发票申请无 `invoiceRequestNo` 幂等键 | `InvoiceRequest.java`、`InvoiceService.java:50-104` | definite | 加字段+查重 |
| 12 | 支付回调对重复 FAILED 回调没有幂等保护（SUCCESS 路径是安全的） | `PaymentCallbackService.java:94-114` | suspicious | 加"已 FAILED 则直接返回"分支 |
| 13 | `PaymentStatus.REFUNDED` 应为附录C规定的 `CLOSED` | `PaymentStatus.java:7`、`RefundService.java:177` | suspicious | 需核实是否有黑盒用例断言具体字符串，若无强约束则按附录C改名 |
| 14 | `RefundStatus`/`InvoiceStatus` 命名与附录C出入较大（6 vs 5 个值，`CANCELLED` vs `VOIDED`） | `RefundStatus.java`、`InvoiceStatus.java` | suspicious | 改动范围较大，需先确认没有黑盒用例断言具体字符串再动 |

### 6.4 promotion 模块（共 10 项，含 2 项已知）

| # | 简述 | 位置 | 置信度 | 修复 |
|---|------|------|--------|------|
| 1 | DISCOUNT 类型优惠券折扣公式反了（已知，PUB-101） | `CouponService.java:84-93` | definite | 直接 `return afterDiscount`，maxDiscount 封顶分支同理 |
| 2 | 优惠叠加顺序反了：应为 满减→优惠券→会员，实际是 会员→满减→优惠券（已知，非公开用例大概率覆盖） | `PromotionCalculationService.java:46-66` | definite | 按文档顺序重排计算链 |
| 3 | 优惠券校验形同虚设：过期、门槛、商品适用性、已用状态全部未检查；`COUPON_EXPIRED` 全仓库从未被抛出 | `CouponValidator.java:32-39` | definite | 补全 6 步校验顺序 |
| 4 | 优惠券使用后从不标记为 USED，可无限次重复使用 | 全模块无任何地方设置 `CouponStatus.USED` | definite | 下单成功后调用标记方法 |
| 5 | 从不校验优惠券归属，可用他人的优惠券 | `PromotionCalculationService.java:111-139` | definite | 加 `userId` 归属校验 |
| 6 | `PromotionController` 直接调用方硬编码 `userId=1` | `PromotionController.java:115-119` | definite | 改用 `SecurityContextHolder`（和其他 Controller 一致） |
| 7 | `totalDiscount` 未按"不得大于商品金额"封顶 | `PromotionCalculationService.java:64-70` | definite | 按 clamp 后的 `finalAmount` 反推 `totalDiscount` |
| 8 | 秒杀完全没接入下单/购物车流程 | `SeckillService.java` 无任何调用方 | definite | order/cart 下单前查有效秒杀活动并调用校验 |
| 9 | 满减活动从不校验自己的起止时间窗口 | `FullReductionService.java:35-51,65-85` | suspicious | 补时间窗口校验 |
| 10 | （见 6.0）舍入模式 HALF_DOWN | `ecommerce-common/MonetaryUtil.java` | definite | 见 6.0 |

### 6.5 cart 模块（共 4 项）

| # | 简述 | 位置 | 置信度 | 修复 |
|---|------|------|--------|------|
| 1 | 购物车用 JPA `@Entity` 落库到真实 H2 表；已写好但从未接入的 `CartCacheManager`（Caffeine，7 天 TTL）完全没被引用 | `CartService.java`、`entity/Cart.java`、`entity/CartItem.java`、`repository/CartRepository.java`、`repository/CartItemRepository.java` | definite | 改为通过 `CartCacheManager` 读写 `CartData`/`CartItemData`，删除 JPA 实体和两个 Repository；TTL 沿用 `CartCacheConfig` 已配置的 7 天 |
| 2 | 同一 SKU 重复加入购物车是覆盖数量，不是累加 | `CartService.java:91`（`addItem`） | definite | 改为 `item.setQuantity(item.getQuantity() + request.getQuantity())`，累加后总量重新校验库存/上限 |
| 3 | 价格预估的 `discountAmount`/`pointsDeductionAmount` 硬编码为 ZERO；`pom.xml` 没有 `ecommerce-promotion` 依赖 | `CartService.java` `estimate()`（约230-238行）、`ecommerce-cart/pom.xml` | definite | 加 `ecommerce-promotion` 依赖，注入并调用 `PromotionCalculationService`，映射进 `discountAmount`/新增的 `applicableCoupons` |
| 4 | TTL 未生效（与 #1 同根因，一并解决） | 同 #1 | definite | 同 #1 |

### 6.6 product 模块（共 10 项）

| # | 简述 | 位置 | 置信度 | 修复 |
|---|------|------|--------|------|
| 1 | 库存摘要硬编码返回 999/0，从不调用 `InventoryQueryService` | `StockInfoFetcher.java:22-25` | definite | 接入真实库存查询 |
| 2 | `getSkuForSale` 抛错码 `SKU_NOT_AVAILABLE` 应为 `PRODUCT_NOT_FOR_SALE`（cart 里抄了同样的错） | `ProductQueryServiceImpl.java:60-63`；`ecommerce-cart/CartValidationService.java:47` | definite | 两处一起改 |
| 3 | 搜索默认 `onlyOnShelf=false`，未上架/草稿商品泄漏到公开列表 | `ProductSearchRequest.java:31`、`ProductSearchService.java:96-102` | definite | 默认改 `true`，或匿名端点强制只查 ON_SHELF |
| 4 | 类目过滤不含子类目 | `ProductSearchService.java:124-130` | definite | 解析类目树取后代 ID 集合再过滤 |
| 5 | 标签过滤字段完全没被读取 | `ProductSearchService.java`、`ProductSearchRequest.java:24,80-86` | definite | 接入标签过滤 |
| 6 | 分页 total 在类目/品牌过滤时算错（DB 分页后才在内存里再过滤一次） | `ProductSearchService.java:63-85` | definite | 把类目/品牌过滤下推到 DB 层 Specification |
| 7 | 商品上下架无审计日志 | `SkuService.java:78-101`、`AdminProductController.java:60-78` | definite | 见 6.0 审计日志统一方案 |
| 8 | 商品详情无 10 分钟缓存 | `ProductDetailService.java` | definite | 仿 `CartCacheConfig` 加 Caffeine 缓存 |
| 9 | 关键词搜索只匹配 SKU 名，不匹配 SPU 名/卖点 | `ProductSearchService.java:104-106` | suspicious | 至少补上 SPU 名匹配 |
| 10 | 商品搜索无限流（120次/分钟/IP） | `ProductController.java:50-55` | suspicious（系统性问题，见 6.0） | 见 6.0 RateLimit 统一方案 |

### 6.7 inventory 模块（共 7 项）

| # | 简述 | 位置 | 置信度 | 修复 |
|---|------|------|--------|------|
| 1 | `reserve()` 同时扣减 onHandStock 和增加 reservedStock（应只动 reservedStock），导致 availableStock 多扣一倍，且 release 永远无法恢复 | `InventoryReservationServiceImpl.java:58-59` | definite | 删掉多余的 `onHandStock` 扣减行 |
| 2 | 库存充足判断用 `>` 应为 `>=`，边界值误判为不足 | `InventoryService.java:75` | definite | 改 `>=` |
| 3 | 支付后扣减库存从不生成出库单 | `InventoryReservationServiceImpl.java:104-125` | definite | 补上 `OutboundOrder` 创建 |
| 4 | 库存摘要无 30 秒缓存 | `InventoryService`全类 | definite | 加 `@Cacheable`+30s TTL |
| 5 | 库存人工调整审计日志没有操作者字段 | `AdminInventoryController.java:67-74`、`StockAdjustmentService.java`、`StockAdjustment.java` | definite | 加 operator 字段并从 `Authentication` 提取 |
| 6 | `reserve()` 无并发控制，理论上可超卖 | `InventoryReservationServiceImpl.java:37-81` | suspicious | 加乐观锁 `@Version` 或悲观锁 |
| 7 | 库存预警端点在冻结的 API 契约内实际不可达（依赖一个未登记的额外接口来配置规则） | `StockWarningService.java`、`AdminInventoryController.java:86-91` | suspicious | 把默认阈值直接挂到 `inventory_stock.warning_threshold`（附录C已定义该列） |

### 6.8 logistics 模块（共 7 项，含 1 项已知）

| # | 简述 | 位置 | 置信度 | 修复 |
|---|------|------|--------|------|
| 1 | 发货单创建后直接是 OUTBOUND，跳过拣货/打面单（已知，PUB-107） | `ShipmentService.java:81` | definite | 创建时置为 `CREATED` |
| 2 | `outbound()` 不校验前置状态，任意状态都能直接出库 | `ShipmentService.java:223-229` | definite | 加"必须是 LABEL_PRINTED"前置校验 |
| 3 | `pick()` 允许从 OUTBOUND 倒退回 PICKING（像是为掩盖 #1 打的补丁），`printLabel()` 完全无状态校验 | `ShipmentService.java:138-143,181-216` | definite | 严格按 CREATED→PICKING→LABEL_PRINTED→OUTBOUND 校验 |
| 4 | 发货单从不通过事件监听器自动创建（`createShipment` 是死代码，零调用方） | 全模块无 `@EventListener` | definite | 加 `OrderPaidEvent` 监听器（结合 6.0 的事件类统一方案） |
| 5 | 物流回调完全是空实现——不查发货单、不更新状态、不做幂等、不验签 | `LogisticsCallbackService.java:33-39` | definite | 按 trackingNo 查单、幂等去重、验签、真正更新状态 |
| 6 | `ShipmentDeliveredEvent` 全仓库不存在 | — | definite | 新建该事件类，签收时发布 |
| 7 | 运费模板无 30 分钟缓存；省份/重量规则字段存了但从未被读取，运费计算只用了固定 `defaultFreight` | `FreightCalculator.java`、`FreightTemplateService.java` | definite | 加缓存；解析 `provinceRules`/`weightRules` 参与计算 |

### 6.9 loyalty 模块（共 11 项）

| # | 简述 | 位置 | 置信度 | 修复 |
|---|------|------|--------|------|
| 1 | GOLD 会员倍率写成 1.1（和 SILVER 一样），应为 1.2 | `MemberLevel.java:11` | definite | 改 `1.2` |
| 2 | 监听的是本模块自己的 `OrderPaidEvent`，不是 order 真正发布的类——**订单支付积分在真实环境下从未发放过** | `OrderPaidEvent.java`、`OrderPaidEventListener.java` | definite | 见 6.0 事件类统一方案 |
| 3 | 同上，`ReviewApprovedEvent` 也是本模块自己的类——**评价奖励积分同样从未真正发放** | `ReviewApprovedEvent.java`、`ReviewApprovedEventListener.java` | definite | 见 6.0 |
| 4 | 积分过期是完全的空实现，也没有任何定时任务 | `PointsExpireService.java:20-22` | definite | 实现真正的过期扫描+扣减+记录，加 `@Scheduled` |
| 5 | 会员等级统计直接用 `JdbcTemplate` 查 `orders` 表原始 SQL，违反设计文档明文禁止的跨模块直接查表规则 | `OrderDataFetcher.java:27-37` | definite | 改用 `OrderQueryService`/销售统计接口 |
| 6 | 积分冻结（模块职责明确列出）完全没有任何实现 | `LoyaltyAccount.java:32-33`（`frozenPoints` 恒为 0） | suspicious | 需先确认冻结的具体触发场景（如退款中占用）再实现 |
| 7 | `LoyaltyCommandService.redeemPoints`/`earnPaymentPoints` 在 order/payment 模块里零调用——积分抵扣在真实下单流程里不生效 | 接口定义在 loyalty，缺口在 order/payment 侧 | suspicious | 需 order 创建订单时调用积分抵扣 |
| 8 | 评价奖励积分数硬编码 20，不读运行时配置覆盖 | `ReviewApprovedEventListener.java:18` | suspicious | 改读 `RuntimeConfigRegistry` |
| 9 | 抵扣/赚取相关四个常量硬编码，不支持运行时配置覆盖（当前默认值本身是对的） | `LoyaltyPointService.java:35-43` | suspicious | 改读 `RuntimeConfigRegistry` |
| 10 | 年度消费统计用 `LocalDate.now()` 而非 `SystemClockService`，测试时钟覆盖对它不生效 | `OrderDataFetcher.java:28` | suspicious | 改用 `SystemClockService` |
| 11 | 会员等级只在查询 `/member-level` 时才重新计算，支付时不刷新，可能用旧等级倍率算积分 | `OrderPaidEventListener.java:30-48` | suspicious | 支付计分前先调用 `evaluateAndUpgrade` |

### 6.10 review 模块（共 6 项）

| # | 简述 | 位置 | 置信度 | 修复 |
|---|------|------|--------|------|
| 1 | 从不校验购买+签收，`OrderQueryService.verifyPurchase` 零调用——未购买也能评价 | `ReviewService.java:59-102` | definite | 接入 `verifyPurchase`，不满足抛 `REVIEW_PURCHASE_REQUIRED` |
| 2 | 提交评价时（而非审核通过时）就发布 `ReviewApprovedEvent`，且审核通过时又发一次——双发，被拒绝的评价也会发 | `ReviewService.java:99`、`ReviewModerationService.java:63` | definite | 只在 `approve()` 里发一次 |
| 3 | 事件缺 `orderId`/`productId` 字段（附录D要求4个字段，只有2个） | `ReviewApprovedEvent.java` | definite | 补齐字段 |
| 4 | 发的是 review 模块自己的 `ReviewApprovedEvent`，不是 loyalty 期望监听的类——评价积分奖励从未真正发放（和 6.9 #3 是同一根因） | `ReviewApprovedEvent.java`/`ReviewApprovedEventListener.java` | definite | 见 6.0 |
| 5 | 敏感词过滤用完全相等匹配，不是包含匹配（设计文档明确要求"不得只做完全相等匹配"） | `SensitiveWordFilter.java:31-42,50-61` | definite | 改 `contains`/`replace` |
| 6 | 命中敏感词直接抛异常丢弃，评价从未进入 PENDING_REVIEW 或 REJECTED 这两个允许的终态之一 | `ReviewService.java:74-78,127-131` | suspicious | 若确认，改为落库为 REJECTED 而非直接拒绝请求 |

### 6.11 common 模块（共 5 项）

| # | 简述 | 位置 | 置信度 | 修复 |
|---|------|------|--------|------|
| 1 | 舍入模式 HALF_DOWN 应为 HALF_UP（见 6.0，根因定位在此） | `MonetaryUtil.java:32` | definite | 改 `RoundingMode.HALF_UP` |
| 2 | `ConflictException` 没有 `(code,message)` 构造函数，业务方无法用它抛出带具体错误码的 409（`ORDER_STATUS_CONFLICT`/`REFUND_WAITING_WAREHOUSE_ACCEPT` 全仓库从未被抛出过） | `ConflictException.java:11-13` | definite | 加 `(code,message)` 构造函数 |
| 3 | `AbstractDomainEvent` 缺 `aggregateId`/`traceId` 字段（附录D §1 要求所有事件都有） | `AbstractDomainEvent.java:12-30` | definite | 补字段+`getEventType()` |
| 4 | 故障注入检查写在 try/catch 外面，导致通知发送的故障注入会真的让支付事务回滚（违反 PUB-108 类场景的"后置动作失败不阻塞主流程"） | `LocalNotificationServiceImpl.java:49-52` | definite | 挪进 try 块内 |
| 5 | 通知失败只写日志，不写入任何可查询的记录，`GET /api/v1/admin/notifications` 看不到失败的通知 | `LocalNotificationServiceImpl.java:105-108` | definite | 扩展 `NotificationRecordService` 记录失败状态 |

### 6.12 app 模块（共 4 项，含 1 项安全漏洞级别）

| # | 简述 | 位置 | 置信度 | 修复 |
|---|------|------|--------|------|
| 1 | **安全漏洞**：`reset-sandbox`/`bootstrap-admin` 两个接口未鉴权（`permitAll()`），且属于设计文档明确禁止暴露的 reset/bootstrap 接口——任何人可清库或自签 ADMIN token | `SystemAdminController.java:55-95`、`SecurityConfig.java:63-64` | definite | 整个删除这两个接口及其安全放行规则 |
| 2 | `verify-purchase` 文档要求 USER/ADMIN 均可访问，实际只放行 USER | `SecurityConfig.java:66`、`ecommerce-order/OrderController.java:36` | definite | 两处一起放开 ADMIN |
| 3 | 支付回调 `X-Payment-Signature` 头完全没有被读取或校验（超出 app 模块范围，根因在 payment 模块） | `ecommerce-payment/PaymentController.java:52-58`、`PaymentCallbackService.java:40-65` | definite | 加签名校验（并入 6.3 支付模块修复） |
| 4 | 事件失败没有重放端点，`FailedEventRecord.retried/retryCount` 字段存在但从未被更新 | `EventFailureAdminController.java` | suspicious | README 冻结的 9 个端点不含重放，属于可选增强，附加实现即可，不影响契约 |

## 7. 验证策略

**我们自己的验证（写作/提交前）**：

1. 对每一条修复：本地实际改代码，跑 `mvn -f code/pom.xml test`（含针对无黑盒覆盖模块新增的单元测试）+ `mvn -f test-cases/pom.xml test`（24 个黑盒用例应全部转绿），确认不引入新的编译/测试失败。
2. 用 `git diff <baseline>..HEAD -- code/` 生成最终改动文件清单 → 据此生成 `work/fixer/knowledge-base/code/`（完整最终内容）和 `baseline-hashes.txt`（每个被改文件在基线 `1b1e88f` 的 SHA-256）。
3. **端到端模拟评测（含 hash 门控验证）**：把基线 commit 的 `code/`（未修复版本）还原到一个临时目录，模拟 `judge-assets` 布局，跑一遍完整 `INSTRUCTION.md` 流程（`apply.sh` → SKILL.md 复核 → 验证套件），确认：(a) apply.sh 对每个文件 hash 都命中基线、全部应用、apply-report 的 skipped=0；(b) 从"脏"状态自动收敛到全绿；(c) 再跑一次 apply.sh 验证幂等（第二次全部"已是目标态"、skipped=0、不破坏任何文件）。
4. **Stage 3 playbook 的独立性检验**：用一个全新、不带本次分析上下文的 subagent，只给它 `SKILL.md` + checklist + 一份未修复的材料，看它能否仅凭书面材料复现同样的修复结果——直接检验"即使很蠢的模型拿到这份材料也能做对"。
5. 由于 opencode / 公司自研 codeagent 均不在本机可用，Stage 3"实际跑在目标 harness 上"这一环节无法字面意义验证；在 `result/output.md` 如实注明此限制，并说明用 Claude Code 子 agent 模拟执行 checklist 作为代理验证。
6. **平台提交作为合规 oracle**（GUIDANCE §3.2：每日最多 5 次提交，返回客观分 + 用例通过比例，不显示失败详情）：对 §6 里拿不准的 suspicious 项（尤其 6.3 #13/#14 的枚举改名），用 **A/B 提交归因**——一次只动一个变量，观察通过率变化，推断隐藏用例是否覆盖该点。这是唯一合规的隐藏用例信道，务必省着用。

**评测机上的验证（INSTRUCTION.md driven）**：`result/output.md` 记录每次运行的 apply-report（应用/跳过数）、单元测试通过数、黑盒测试通过数、以及任何 Stage 3 深核/回滚的触发情况。

## 8. 未决问题 / 风险

- Stage 3 的"复核"边界如何定义，既不能宽到变回"自由探索"（丧失稳定性优势），也不能窄到完全等价于 Stage 2（那就没有增量价值）——方案是 checklist 覆盖"已知强规则"（状态机、金额公式、状态码），留一小段"开放式"复核仅针对 README/设计文档里明确列出但本次审查未逐条验证到底的次要规则点。加上 §4 的"验证优先"分支后，正常路径（全绿）根本不触发深核，边界问题只在材料漂移/隐藏检查点出现时才需要考虑。
- 12 个模块审查 agent 中途因账号 session 限额（5:50pm Asia/Shanghai 重置）全部中断，已在限额重置后逐一恢复（resume）并全部完成，§6 的清单以恢复后的完整报告为准。
- **规模判断**（精确数字见 §6 开头）：实现阶段将优先修复全部 definite-bug；suspicious 项逐条判断是否修复并在提交材料里说明理由，不会不加区分地全部实现（例如 6.3 的 #13/#14 涉及大范围改名，需先确认没有隐藏用例断言具体字符串，避免"为改而改"引入新的不一致）。
- **实现顺序**：先做 6.0 列出的跨模块系统性修复（事件类迁移到 common、`MonetaryUtil` 舍入模式、`RateLimit` 接入、共享审计日志机制），因为多个模块的独立修复都依赖这些共享改动先落地，避免后续按模块并行实现时对 `ecommerce-common` 产生冲突。
- **6.3 #8 需要在实现阶段核实**：支付确认同步扣减库存 vs. inventory 模块审查发现的 `deductAfterPayment` 实际由 order 模块的事件处理器调用——需要先确认真实调用链，再决定是在 `PaymentService.confirmPayment()` 事务内新增同步调用，还是保留现有异步路径但确认其发生在正确的事务边界内，避免重复扣减库存。
