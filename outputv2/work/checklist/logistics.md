# checklist: ecommerce-logistics

依据：`design-docs/11-物流服务设计.md`、附录 C/D。相关黑盒：PUB-107、PUB-014。

## 发货单状态机（严格 CREATED → PICKING → LABEL_PRINTED → OUTBOUND）

- [ ] 发货单创建后初始状态是 `CREATED`（**不是** `OUTBOUND`，不跳过拣货/打面单）。（PUB-107）
- [ ] `pick()` 校验前置为 `CREATED`，**不允许**从 `OUTBOUND` 倒退回 `PICKING`。
- [ ] `printLabel()` 有前置状态校验（须 `PICKING`）。
- [ ] `outbound()` 前置必须是 `LABEL_PRINTED`。
- [ ] `pick(id, pickerId)` 对 `pickerId` 判空，不因 `null.toString()` 抛 NPE（与 printLabel/outbound 一致）。

## 事件（附录 D §4）

- [ ] 存在监听 common `OrderPaidEvent` 的监听器**自动创建发货单**（基线无任何 `@EventListener`）；监听器方法用 `@Transactional(REQUIRES_NEW)`，后置动作在全新事务内提交（`AFTER_COMMIT` 阶段无存活事务，否则发货单从不落库）。
- [ ] 跨模块同名监听器 bean 显式限定名（如 `@Component("logisticsOrderPaidEventListener")`），避免与 loyalty 的同名监听器冲突（`ConflictingBeanDefinitionException`）。
- [ ] `ShipmentDeliveredEvent` 存在，签收时发布（供 order 推进订单到 DELIVERED）。

## 回调 / 运费

- [ ] 物流回调**真实实现**：按 `trackingNo` 查发货单、按 `trackingNo+eventTime+status` 幂等去重、验签、真正更新状态（**不是**空实现）。
- [ ] 运费模板有 30 分钟缓存；运费计算解析 `provinceRules`/`weightRules` 参与计算（**不是**只用固定 `defaultFreight`）。
