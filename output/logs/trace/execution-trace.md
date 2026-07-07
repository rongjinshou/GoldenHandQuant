# 执行/推理痕迹

记录本方案从审查到验证的关键过程。逐条设计依据见 `work/fixer/knowledge-base/findings.md`，方案总述见 `work/DESIGN.md`。

## 1. Stage 1 离线审查
- 沿"模块 → 设计文档"映射逐模块把 `code/` 对照 `design-docs/` + `README.md` 冻结契约审查（user→04 … review→13；14 发票结算属 payment；15 通知属 common；附录 A/C/D）。
- 每处不一致记为一条 finding（症状 → 设计依据 → 修复）。共 **97 处模块级不一致**。
- 修复按模块提交到工作分支（每模块一次干净提交，便于抽查与回溯）。

## 2. 全系统集成验证（关键）
把 12 模块合起来跑全量黑盒时，暴露 8 处只在跨模块运行才显形、单模块审查看不到的缺陷，逐一定位根因并修复：
1. 两个同名 `OrderPaidEventListener`（logistics/loyalty）→ `ConflictingBeanDefinitionException`，Spring 上下文启动失败（24 用例全 ERROR）。→ 显式模块限定 bean 名。
2. `SeckillService.validateSeckill`（`@Transactional(readOnly=true)`）对非秒杀 SKU 抛 `ResourceNotFoundException`，被下单流程吞掉，但已把共享事务标记 rollback-only → 每笔下单提交时 `UnexpectedRollbackException` 500。→ `noRollbackFor`。
3. 物流 `OrderPaidEventListener` 在 `AFTER_COMMIT` 阶段建发货单，无存活事务 → `save()` 不 flush、发货单 id 为 null、从不落库。→ 监听器加 `REQUIRES_NEW`。
4. `pick` 端点传 `null` pickerId，`ShipmentService.pick` 对其 `toString()` → NPE 500，断掉拣货→面单→出库→签收链。→ pickerId 判空。
5. 签收后无 `ShipmentDeliveredEvent` 监听 → 订单永远停在 PAID，评价被"必须购买并签收"拒（harness 的 `OrderLogisticsStatusUpdater` 是 no-op，中间态永不落订单）。→ 新增 order 模块监听器，链式校验 PAID→…→DELIVERED（仿 markAsPaid）。
6. 支付成功后库存从不扣减（`OrderPaymentEventHandler` 是死代码，真实 `markAsPaid` 不扣）。→ 新增 inventory `PaymentSucceededEvent` 监听，调幂等 `deductAfterPayment`（附录D §3）。
7. `OrderService.verifyPurchase` 按不存在的 `deliveredAt` 列排序 → REST 端点 500。→ 改按 `createdAt`。
8. `generateOrderNo` 同毫秒碰撞（批量下单两单）违反 orderNo 唯一约束。→ 单调序列硬化。

诊断方法：读 surefire 报告与应用日志堆栈，从"24 全 ERROR（上下文启动）→ 单点 500（下单）→ 连锁失败"逐层定位根因，每修一处即重跑黑盒确认。

## 3. Stage 2 引擎与端到端干跑
- 从工作分支 `git diff 基线..HEAD` 提取被改文件的完整最终内容 + 基线 SHA-256 + 删除清单，构成知识库。
- `apply.sh` 检查修复引擎：读→比对基线哈希→整份替换/新增/删除→apply-report。
- **端到端干跑**（见 `e2e-dryrun.log`）：pristine 基线 → `apply.sh` → 修复树与已验证工作树逐文件一致（fix=150/added=31/deleted=12/failed=0）→ 构建 → 黑盒 24/24 → 再跑 `apply.sh` 幂等。

## 4. 稳定性
公开黑盒 24 用例本地连续 6 次以上 `Tests run: 24, Failures: 0, Errors: 0`，无 flaky。

## 5. 平台首轮评测反馈与修正（关键迭代）

首轮提交在平台 5 个助理裁判上的结果:23/72、35/72、0/72(上下文启动失败)、2 次评分汇总超时。逐裁判取证:

- **最好的一次(35/72)公开用例失败集 = {PUB-001,009,101,102,104,105},与未修复基线的 6 个失败一一对应**——即该次测的是一行未改的原始代码,修复完全没有生效;
- 0/72 那次的"ApplicationContext 加载失败"与本地验证过的"只覆盖新增/修改、漏掉 12 个删除 → 同名监听器 bean 冲突"签名完全一致——裁判 agent 手工搬运了知识库但没有执行删除;
- 23/72 那次比基线还差——agent 自由发挥的局部修改破坏了原本通过的链路;
- 2 次超时——说明书把环境准备/构建/自测放进了流程,耗尽了评分时间预算。

**根因**:说明书写死的材料路径(GUIDANCE 示例 `/app/code/judge-assets/...`)在真实评测机上不存在(实际为 `/app/tasks/<task>/assistant_judge_N/`),引擎报错后各裁判 agent 只能即兴发挥,产生 4 种不同的失败形态。

**修正**(全部经 6 场景仿真平台布局验证):
1. 引擎自动定位材料根(CWD/脚本位置逐级向上 + 常见评测根扫描,排除知识库自身;失败时给出可执行指引);
2. 新增功能等价的 `apply.py`(纯标准库),bash 不可用时的第二通道,两引擎产物逐字节一致;
3. apply-report 落盘两份(作品侧+材料侧),确定性阶段是否发生可从评测产物直接取证;
4. INSTRUCTION 重写:必选动作只剩"运行引擎"一步(秒级、零依赖、无网络);手工兜底把 12 个删除逐一列入正文(堵死"漏删除"死法);明令禁止安装软件、禁止知识库之外的任何代码改动、不必自行构建测试(平台会测)。
