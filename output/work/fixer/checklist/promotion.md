# checklist: ecommerce-promotion

依据：`design-docs/10-促销服务设计.md`、附录 A/C。相关黑盒：PUB-101。

## 优惠券

- [ ] DISCOUNT 类型优惠券折扣公式方向正确（直接 `return afterDiscount`，`maxDiscount` 封顶分支同理）。（PUB-101 根因）
- [ ] 优惠券校验完整：过期、门槛、商品适用性、已用状态全部检查——`COUPON_EXPIRED` 能被真正抛出。
- [ ] 优惠券使用后标记为 `CouponStatus.USED`（下单成功后调用标记方法），不可无限重复使用。
- [ ] 校验优惠券**归属**（`userId`），不能用他人的优惠券。

## 优惠计算

- [ ] 叠加顺序为**满减 → 优惠券 → 会员**（不是会员→满减→优惠券）。
- [ ] `totalDiscount` 按「不得大于商品金额」封顶（按 clamp 后的 `finalAmount` 反推 `totalDiscount`）。
- [ ] `PromotionController` 用 `SecurityContextHolder` 取 `userId`（**不是**硬编码 `userId=1`）。

## 秒杀 / 满减

- [ ] 秒杀接入下单/购物车流程（下单前查有效秒杀活动并 `validateSeckill` + `recordPurchase`）。
- [ ] `validateSeckill` 对非秒杀 SKU 的 `ResourceNotFoundException` 不得毒化 order 的共享事务（`noRollbackFor`），见 order 清单。
- [ ] 满减活动校验自身起止时间窗口。`[suspicious]`

## 金额（见 common）

- [ ] 优惠计算走 `MonetaryUtil`（`HALF_UP`）。
