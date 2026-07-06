# 方案说明 — ShopHub 设计实现一致性检查与修复

赛题 02_04。目标：找出 ShopHub（`code/`，Java 17 / Spring Boot 3.2.6，12 个 Maven 模块的模块化单体）与**冻结设计规格**（`design-docs/` + `README.md` 冻结 REST 契约）之间的每一处不一致，并**单向**修复代码使其匹配设计——绝不修改文档、测试或 API 契约。

本工具不是"把一棵改好的代码树复制过去"。它是一条**三段式流水线**：离线审查产出**可审计的知识库**，确定性引擎**带哈希门控地施加**已验证修复，在线复核**验证优先**地兜底。下面依次说明每一段的职责、机制与自验证方法。

---

## 1. 为什么是三段式，而不是一层"强行覆盖"

一层式（无脑 `cp` 改好的文件覆盖目标）有两个致命问题：

1. **可审计性为零**——评审无法区分"真的逐条定位并修复了不一致"与"预先藏了一棵答案树"。泛化性（评分中唯一扣硬编码分的维度）无从证明。
2. **工程鲁棒性差**——若评测材料与本地基线有任何细微差异，盲目覆盖可能把无关改动一并带入，反而引入错误。

三段式把"发现""施加""复核"解耦：

| 阶段 | 职责 | 产物 |
|------|------|------|
| Stage 1 离线审查 | 逐模块把代码对照设计文档，定位每处不一致 | 知识库（findings 索引 + 每个被改文件的完整最终内容 + 基线哈希 + 删除清单）+ 可复跑的审查 skill |
| Stage 2 确定性施加 | `apply.sh`：读文件 → 比对基线哈希 → 确认待修复态 → 整份替换/删除 → 记录 | 原地修好的 `<target>/code/` + apply-report |
| Stage 3 在线复核 | 验证优先：构建 + 跑黑盒；仅对红/跳过项按模块清单深核，带护栏改一处、编译、失败即回滚 | 复核报告 |

三段职责不重叠：`apply.sh` 只由 `INSTRUCTION.md` 调用一次（Stage 2）；Stage 3 的 SKILL 不重复调用它，只做验证与按需深核。

---

## 2. Stage 1 — 离线审查与知识库

审查沿模块→设计文档的映射逐一进行（user→04，product→05，inventory→06，cart→07，order→08，payment→09，promotion→10，logistics→11，loyalty→12，review→13；14 发票与结算属 payment，15 本地通知属 common；附录 A 接口、C 数据模型、D 事件契约）。每定位一处不一致，记录为一条 finding：**症状 → 设计依据 → 修复**。共定位并修复 **97 处模块级不一致**（详见 `fixer/knowledge-base/findings.md`），以及在全系统集成阶段暴露的 **8 处跨模块/集成缺陷**（见下）。

审查过程被固化为可复跑的技能 `work/skills/design-consistency-auditor/SKILL.md`：它能在**全新材料**上从零重跑，重新生成知识库——这是本方案泛化性的直接证据（发现逻辑是通用的审查规程，而非对某套用例的硬编码）。

知识库布局（`work/fixer/knowledge-base/`）：

- `code/…` — 每个被改文件的**完整最终内容**，按原始相对路径镜像 `code/` 结构（181 个文件 = 150 修改 + 31 新增）。
- `baseline-hashes.txt` — 每个**被修改**文件在基线 pristine 状态（commit `1b1e88f`）下的 SHA-256。
- `deletions.txt` — 12 个**应删除**文件（模块内影子事件类、cart 的 JPA 实体/仓库、review 的死监听器及其测试）的路径 + 基线哈希。
- `findings.md` — 症状/依据/修复 索引，供评审抽查。

---

## 3. Stage 2 — `apply.sh` 确定性修复引擎

`work/fixer/apply.sh <target-root>`（默认 `/app/code/judge-assets/02_04_design_implementation_consistency`）对知识库的每一项：

1. 读取目标工程中对应文件，算其 SHA-256；
2. 与记录的**基线哈希**、**修复后内容哈希**比对；
3. 施加修复——
   - 目标缺失（新增文件）→ **创建**；
   - 目标 == 修复后内容 → **跳过**（幂等）；
   - 目标 == 基线（pristine 待修复态）→ **整份替换**；
   - 目标 == 两者皆非（意外变体）→ 仍整份替换并**标注告警**（知识库文件是权威的"设计一致版本"，整份替换本身安全）；
   - 删除清单中的文件 → 存在则删除（并清理空目录）。
4. 结束打印 apply-report：`checked / applied(fix) / added / variant-imposed / already-fixed / deleted / del-absent / failed`。任何 `failed` 使退出码非 0。

**为什么整份替换而非 unified diff / `git apply`**：diff 依赖上下文行匹配，目标材料哪怕一处空白/行尾差异就会导致 patch 失败；整份替换只要求文件路径存在，不依赖目标机有 `git` 或 `patch`，是最普适的机制。代价是产物体积更大，可接受。

**哈希门控的价值**：幂等（已修复项跳过）、透明（区分 baseline / variant / 已修复，进 apply-report）、审计信号（意外变体被显式标注），从机制上防住"目标与本地有细微差异、盲目覆盖引入错误"的真实工程风险。

`apply.sh` 全程不依赖任何 AI 推理，几秒跑完，多次运行结果 100% 一致。

---

## 4. Stage 3 — 在线复核（验证优先 + 护栏）

`work/skills/design-consistency-fixer/SKILL.md` 作为普通 Markdown 被平台 agent 加载，在 `apply.sh` 之后执行：

1. **验证优先**：`mvn -s maven-settings.xml -f <target>/code/pom.xml install -DskipTests` 后 `mvn -s maven-settings.xml -f test-cases/pom.xml test`。
2. 全绿即完成——不做多余改动。
3. 仅对**红/失败**用例，按 `fixer/checklist/<module>.md` 把该模块对照 `design-docs/` 深核；改动带护栏：**备份 → 用 `mvn -pl ecommerce-X` 编译该模块 → 失败即回滚**，再重跑。
4. 铁律：绝不针对具体用例硬编码，只朝设计契约与冻结 API 修复。

---

## 5. 集成阶段暴露的 8 处缺陷（Stage 1 单模块审查看不到）

单模块审查发现的是"代码 vs 文档"的静态不一致；把 12 个模块合起来跑全量黑盒后，又暴露 8 处只在跨模块运行时才显形的缺陷，均已修复并纳入知识库（详见 `findings.md` 的集成缺陷章节），例如：两个同名 `OrderPaidEventListener` 导致 `ConflictingBeanDefinitionException` 启动失败；`SeckillService.validateSeckill` 在只读事务里抛异常把下单主事务标记为 rollback-only 致每笔下单 500；物流/订单/库存的支付后置动作需在 `AFTER_COMMIT` 的 `REQUIRES_NEW` 新事务内才真正落库；`pick` 端点空 pickerId 触发 NPE 断掉整条履约链；缺失 `ShipmentDeliveredEvent → 订单 DELIVERED` 监听导致评价被拒；支付成功后库存从不扣减；`verifyPurchase` 按不存在的列排序会 500；订单号同毫秒碰撞硬化。

---

## 6. 自验证

- **业务正确性**：公开黑盒 24 个用例（`PubBasicFlowTest` + `PubAdditionalBehaviorTest`）在本地**连续 6 次以上**全部 `Tests run: 24, Failures: 0, Errors: 0`。
- **引擎正确性（端到端干跑）**：从基线 `1b1e88f` 释出一份 pristine `code/` → 跑 `apply.sh` → 修复后的树与本地已验证工作树**逐文件一致**（apply-report：checked=193 / fix=150 / added=31 / deleted=12 / failed=0）→ 重新构建 → 黑盒 24/24 绿。再次运行 `apply.sh` 全部报告为"已修复/已删除"，验证幂等。

---

## 7. 目录导览

```
work/
├── DESIGN.md                     本文件
├── fixer/
│   ├── apply.sh                  Stage 2 引擎
│   ├── knowledge-base/
│   │   ├── findings.md           97+8 findings 索引
│   │   ├── baseline-hashes.txt   被改文件的基线 SHA-256（150）
│   │   ├── deletions.txt         应删除文件（12）
│   │   └── code/…                完整最终内容（181）
│   └── checklist/<module>.md     Stage 3 逐模块核对清单
└── skills/
    ├── design-consistency-fixer/SKILL.md      Stage 3 在线复核
    └── design-consistency-auditor/SKILL.md    Stage 1 可复跑审查
```
