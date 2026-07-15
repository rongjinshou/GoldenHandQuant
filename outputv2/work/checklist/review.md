# checklist: ecommerce-review

依据：`design-docs/13-评价服务设计.md`、附录 C/D。相关黑盒：PUB-014。

## 评价前置校验

- [ ] 提交评价前校验**购买 + 签收**：调 `OrderQueryService.verifyPurchase`，不满足抛 `REVIEW_PURCHASE_REQUIRED`（基线 `verifyPurchase` 零调用，未购买也能评价）。

## 事件（附录 D，与 loyalty 联动）

- [ ] `ReviewApprovedEvent` 只在 `approve()`（审核通过）时发布**一次**——**不是**提交评价时就发、也不是审核时再发一次（双发），被拒绝的评价不发。
- [ ] 事件载荷含 `orderId`、`productId`（附录 D 要求 4 个字段，不能只有 2 个）。
- [ ] 发的是 common `ReviewApprovedEvent`（**不是** review 本地影子类）——否则 loyalty 监听不到，评价积分从未发放。
- [ ] review 本地 `event/ReviewApprovedEvent`、死监听器 `ReviewApprovedEventListener` 及其测试已删除（残留同名 bean 会致启动冲突）。

## 敏感词

- [ ] 敏感词过滤用 `contains`/`replace`（**包含匹配**），设计明确「不得只做完全相等匹配」。
- [x] 命中敏感词的评价落库为 `REJECTED`（进入允许的终态），而不是直接抛异常丢弃请求。`[suspicious]`
  ✔ 已核实（W15-C 回勾）：`ReviewService.java:88`（`containsSensitiveWord` 判定）→ `:102-105` `sensitiveHit` 时 `setStatus(ReviewStatus.REJECTED)` + `reviewedAt` + 自动驳回 `reviewerResponse`，随后正常 `save`——请求不被抛弃。
