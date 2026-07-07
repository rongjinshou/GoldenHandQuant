# checklist: ecommerce-order

依据：`design-docs/08-订单服务设计.md`、附录 C/D。相关黑盒：PUB-102、PUB-104、PUB-101、PUB-108、PUB-014。

## 创建订单

- [ ] 创建订单返回 **201 Created**（`ResponseEntity.status(HttpStatus.CREATED)`，**不是** 200）。（PUB-102）
- [ ] `payableAmount` 计算**含 `shippingFee`**（应付 = 商品金额 + 运费 − 优惠）。（PUB-104）
- [ ] 下单前校验用户 `isFrozen`，冻结用户抛 `USER_FROZEN` → 403。
- [ ] 风控 `OrderRiskChecker` 在创建流程中**真的被调用**（`ORDER_RISK_REJECTED` 不是死代码）。
- [ ] 金额校验抛 `OrderValidationException` → 400（**绝不** `IllegalArgumentException` → 500）。
- [ ] 创建前按 `(externalOrderNo, userId)` **幂等去重**。

## 状态机 / 取消

- [ ] 已支付订单取消进入 `CANCEL_REVIEWING`（走商家审核，审核通过才真正取消退款）——**不是**直接跳 `CANCELLED`。
- [ ] `OrderStateMachine` 中 `PAID` 的合法迁移集合**不含 `CANCELLED`**。
- [ ] `markAsPaid` 经状态机（`CREATED → PAYING → PAID`），不绕过。
- [ ] 超时取消订单时**释放预占库存**（调 `InventoryReservationService.release`）。

## 批量下单

- [ ] 批量下单**不共用一个事务**——一条失败不整批回滚（去掉外层 `@Transactional` 或改 `REQUIRES_NEW`）。

## 集成接线（附录 D，黑盒事件链）

- [ ] 支付后置状态推进：监听 common `OrderPaidEvent`（发布方是 order，logistics/loyalty 监听）；下单成功发的是 common `OrderPaidEvent`，**不是** order 本地影子类。
- [ ] 存在 `ShipmentDeliveredEvent` 监听器（`AFTER_COMMIT`+`REQUIRES_NEW`）把订单推进 `PAID→PICKING→SHIPPED→DELIVERED`（幂等）——否则订单永停 PAID，评价被「必须购买并签收」拦截。（PUB-014）
- [ ] 接线 promotion：下单成功后 `couponService.markUsed(couponId, orderId)`；定价链调用 `SeckillService.validateSeckill(...)` + `recordPurchase(...)`。
- [ ] 探测「是否秒杀」调用 `validateSeckill` 时，良性 `ResourceNotFoundException` 不得毒化调用方事务（`@Transactional(readOnly=true, noRollbackFor=ResourceNotFoundException.class)`），否则普通下单全 500。
- [ ] `OrderService.verifyPurchase`（controller 路径）不按不存在的 `deliveredAt` 列排序（用 `createdAt`，签收由 `DELIVERED` 状态体现）。
