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
