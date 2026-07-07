# checklist: ecommerce-payment

依据：`design-docs/09-支付服务设计.md`、`14-发票与结算设计.md`、附录 C/D。相关黑盒：PUB-009、PUB-108。

## 支付

- [ ] 创建支付单初始状态是 `CREATED`（**不是** `PENDING`）。（PUB-009）
- [ ] **支付金额校验存在**：`amount.compareTo(payableAmount) != 0` 时抛 `PAYMENT_AMOUNT_MISMATCH`——绝不允许付任意正数就把订单置为已支付。
- [ ] 支付确认（`confirmPayment`）：金额校验 → **同一事务内扣减库存** → `OrderPaymentStatusUpdater.markAsPaid`；物流/积分/通知改为**事件监听器异步**，不在支付事务内同步执行，且其失败不回滚支付。

## 退款（含仓库验收，14）

- [ ] 退款审核通过后只置 `WAITING_WAREHOUSE_ACCEPT`；`processRefund` 只能由**仓库验收**触发，不得跳过验收直接完成退款。
- [ ] 退款金额公式**不额外扣固定 1.00**（设计原话「不得额外扣除固定费用」）。
- [ ] 退款申请有 `refundRequestNo` 幂等键并查重。

## 发票 / 结算（14）

- [ ] 发票金额读 `request.getInvoiceAmount()`（**不是**永远按订单全额开）。
- [ ] 超额开票抛 `INVOICE_AMOUNT_EXCEEDED`（**不是** `INVOICE_LIMIT_EXCEEDED`），且按**剩余可开票金额**校验本次请求。
- [ ] 发票申请有 `invoiceRequestNo` 幂等键并查重。
- [ ] 结算批次退款汇总注入 `RefundRecordRepository`，按日期汇总**真实退款**（不恒为 0）。

## 回调 / 事件（附录 D）

- [ ] 支付回调校验 `X-Payment-Signature` 头；按 `paymentNo + callbackSequence` 幂等；重复 FAILED 回调也幂等（已 FAILED 直接返回）。`[FAILED 分支为 suspicious]`
- [ ] `PaymentSucceededEvent` 含 `paidAt` 字段，去掉恒为 null 的 `userId`（按附录 D 校正）。

## 枚举命名（改前先确认无黑盒断言具体字符串）

- [ ] `PaymentStatus.REFUNDED` 应为附录 C 的 `CLOSED`。`[suspicious]`
- [ ] `RefundStatus`/`InvoiceStatus` 值集合与附录 C 对齐（如 `CANCELLED`→`VOIDED`）。`[suspicious，改动面大]`
