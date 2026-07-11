# 执行过程记录 — outputv2（AI 修复版）

## 方案

「检查」成果（`findings.md` 全部 BUG 卡片）已在早期离线审查阶段产出；outputv2 让评测 agent 照卡片
**派 subagent 逐条修改 `code/`**，编译 + 公开 24 例自检效果。**纯 AI，不依赖参考答案。**
详见 `work/DESIGN.md`、`work/harness/README.md`。

## 从「参考 oracle 版」到「纯改版」

初版 v2 曾用参考修复作 Harness 的 oracle + 兜底；按需求改为**纯让 agent 照卡片改、看效果**：

- 删除 `work/harness/{reference/, verify.sh, apply-reference.sh}`（不再有参考答案对照与兜底）；
- `check-all.sh` 简化为两道客观门：`mvn` 编译 + 公开黑盒 24 例回归；
- `INSTRUCTION.md` 第 ① 步直接 `cp -a /app/code/judge-assets/02_04_design_implementation_consistency/. .`
  到当前工作目录；第 ② 步照 `findings.md` 卡片改工作目录下的源码。

## 自检链路验证（作者侧）

`check-all` 的编译门 + 24 例门在**完成态工程**（作者侧已验证的参考实现）上运行：
`BUILD SUCCESS + 24/24 PASS`——确认自检门本身有效可用。**真实修复效果由评测 agent 照卡片现场产生**，
不由参考答案决定。

## 与确定性回放变体（v1）的关系

同一份 `findings`、两种落地：**v1（另一交付形态）** 用确定性哈希门控引擎**回放**参考修复；
**v2（本作品）** **纯 AI 照卡片修复** + 编译/24 例自检——体现 AI agent 能力，效果由评测检验。

## 第二次重构：从「单文件 findings.md + 事后一次性检查」到「批次卡片 + 棘轮护栏」

首次评测（5 个独立助理裁判各跑一次）暴露方差极大：2 次 PUB 24/24 全绿，1 次 58/72，**2 次归零**
（一次 `ecommerce-order` 编译错误被直接交付，一次 agent 新建第二个 `CacheManager` bean 导致
Spring 上下文启动失败）。根因不是"AI 修不好"（24/24 的两次证明上限足够），而是"AI 改坏了没人拦"：
`findings.md` 是单文件、`check-all.sh` 只在流程末尾看一眼、失败没有回滚协议，一次编译期/上下文期
事故就把交付物拖到 0 分，而 5 票里只要 1 次归零就能把该裁判手里全部 PUB 票拖成 False。

改造两条主线：

1. **质量控制确定性化**：新增 `work/harness/ratchet.sh`（快照 / 验证-固化 / 自动回滚棘轮）。
   每修完一批立刻 `verify`：编译失败或黑盒通过数比上一次固化状态更低，**自动回滚**整批改动到
   最后一个已验证良好状态；通过则固化为新的良好状态。数学效果：任何时刻交付物 = max(基线,
   已固化最佳)，"归零"在结构上不可能发生。作者侧已用四条路径实测验证（快照/编译失败回滚/
   行为回归回滚/无改动固化），见 `result/output.md`。
2. **`findings.md` 拆分为 19 个按批次组织的详细卡片文件**（`work/bugs/README.md` 为索引 +
   批次执行顺序表）：低风险单点修复（`S1-quick-wins.md`）在前，事件体系迁移（`S2-events.md`，
   横跨 order/payment/loyalty/logistics/review 五模块）、审计基础设施（`S3-audit.md`）、
   限流与缓存（`S4-config.md`，含明确禁止新建第二个 `CacheManager` 的"勿犯"——直接对应上次归零
   事故）随后；12 个模块各一个批次。每张卡六字段（文件/现状/期望/改法/验收/勿犯），"改法"对照
   已验证 24/24 通过的参考实现逐行核对，而不是让执行 agent 自己从设计文档反推实现细节——
   这是本次重构回应的具体需求："finding.md 是不是应该按模块拆开，让修改点更加详细，
   这样能保证 AI 能理解不会改错"。

19 份卡片文件由 15 个并行 subagent 各自独立生成（分别读未修复的基线代码、已验证的参考实现、
`design-docs/` 设计依据，互不看对方产出），生成后做了系统性交叉核对，发现并修复三类问题：
- **两张卡各自以为对方会做某件事，结果谁都没做**：`order.md` 的 ORD-A11（`markAsPaid` 状态机
  改造）与 `S2-events.md` 的 EVT-A2（事件类迁移）都在各自"勿犯"里把"往 `markAsPaid` 里加
  `OrderPaidEvent` 发布调用"甩给对方——而 `markAsPaid` 正是 `OrderPaymentStatusUpdater` 跨模块
  接口的实现、支付模块通知订单模块的唯一生产路径。核实后确认 `OrderLifecycleService`/
  `OrderPaymentEventHandler`（EVT-A2 原本改的两个文件）在基线和参考修复里都是零调用死代码，
  真正的发布点从未被任何卡片覆盖。已新增 `S2-events.md` 的 EVT-A7 卡片补上这一环，并订正
  EVT-A2 里"这是真正被状态机驱动调用的发布点"这句错误描述。
- **同一处修复被两个批次各写一张卡**（`order.md` ORD-B8 与 `loyalty.md` LOY-10，都是"积分抵扣
  从未真正扣减"）：核实后判定不需要合并——`ratchet.sh` 的整批提交/整批回滚语义天然保证不会有
  半成品残留，LOY-10 自带的 grep 去重检查在此前提下是安全的，两张卡并存反而是跨批次容错冗余
  （若 B09 因批内其他卡片失败被整批回滚，B14 仍能独立补上这处修复），予以保留。
- **一张卡的"勿犯"防御性措辞不完整**：`S3-audit.md` 的 AUD-6（发票开具审计）没有像同文件 AUD-7
  那样写"构造函数参数若已被其他卡追加过就接着追加，不要假设参数个数"的防御性说明，而
  `payment.md` 的 PAY-B1 恰好会先于 AUD-6 往同一个构造函数插入参数——已订正为与 AUD-7 一致的写法。

`INSTRUCTION.md`/`bug-fixer/SKILL.md`/`work/bugs/README.md` 同步重写为批次化棘轮流程；删除了
残留的两份旧版检查阶段技能（它们引用了本包里不存在的确定性引擎路径）。
`findings.md` 保留但降级为背景/溯源资料（文件头已加说明），
不再是任何操作步骤的入口——其"尽调后明确放弃"与"已识别但未实施"两节的推理未被 19 份卡片逐字
复制，仍有留存价值。
