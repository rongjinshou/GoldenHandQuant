# checklist: ecommerce-inventory

依据：`design-docs/06-库存服务设计.md`、附录 C/D。

## 预占 / 释放 / 扣减

- [ ] `reserve()` **只增加 `reservedStock`，不动 `onHandStock`**（否则 `availableStock` 多扣一倍，且 `release` 永远无法恢复）。
- [ ] 库存充足判断用 `>=`（**不是** `>`），边界值不误判为不足。
- [ ] 支付后扣减库存时**生成 `OutboundOrder`**（预占→扣 `onHand`+`reserved`、建出库单）。

## 支付后扣减的触发（集成，附录 D §3）

- [ ] 存在监听 common `PaymentSucceededEvent` 的监听器（`AFTER_COMMIT` + `REQUIRES_NEW`）调用幂等的 `deductAfterPayment(orderId)`——支付成功后库存**真的被扣**（基线里该扣减路径是死代码，从不执行）。

## 非功能与审计

- [ ] 库存摘要有 30 秒缓存。
- [ ] 库存人工调整的审计日志**含操作者字段**（从 `Authentication` 提取）。
- [ ] `reserve()` 有并发控制（乐观锁 `@Version` 或悲观锁），避免超卖。`[suspicious]`
- [ ] 库存预警阈值直接挂在 `inventory_stock.warning_threshold`（附录 C 已定义该列），不依赖未登记的额外配置接口。`[suspicious]`
