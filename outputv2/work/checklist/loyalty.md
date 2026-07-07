# checklist: ecommerce-loyalty

依据：`design-docs/12-积分与会员服务设计.md`、附录 C/D。

## 会员等级

- [ ] GOLD 会员积分倍率是 `1.2`（**不是** `1.1`，即不得与 SILVER 相同）。
- [ ] 会员等级统计走 `OrderQueryService`/销售统计接口（**绝不**用 `JdbcTemplate` 直查 `orders` 表——违反 design-docs/02 §3 跨模块禁止直查表）。

## 积分发放（影子事件类是根因）

- [ ] 订单支付积分监听的是 common `OrderPaidEvent`（**不是** loyalty 本地影子 `OrderPaidEvent`）——否则支付积分真实环境下从未发放。
- [ ] 评价奖励积分监听的是 common `ReviewApprovedEvent`（**不是** loyalty 本地影子类）——否则评价积分从未发放。
- [ ] loyalty 本地 `event/OrderPaidEvent`、`event/ReviewApprovedEvent` 及其影子监听器已删除。
- [ ] 监听器 bean 显式限定名（`@Component("loyaltyOrderPaidEventListener")`），避免与 logistics 同名监听器冲突。

## 积分过期

- [ ] 积分过期是真实实现（扫描 → 扣减 → 记录），并有 `@Scheduled` 定时任务（**不是**空实现）。

## 以下为 suspicious，改前先判断是否有隐藏用例覆盖

- [ ] 积分冻结 `frozenPoints` 有实现（当前恒为 0）——需先确认冻结触发场景。`[suspicious]`
- [ ] `redeemPoints`/`earnPaymentPoints` 在下单/支付流程被调用（积分抵扣真实生效）。`[suspicious]`
- [ ] 评价奖励积分数、抵扣/赚取常量读 `RuntimeConfigRegistry`（不硬编码；默认值本身正确）。`[suspicious]`
- [ ] 年度消费统计用 `SystemClockService`（**不是** `LocalDate.now()`），测试时钟覆盖生效。`[suspicious]`
- [ ] 支付计分前先 `evaluateAndUpgrade` 刷新等级，避免用旧等级倍率。`[suspicious]`
