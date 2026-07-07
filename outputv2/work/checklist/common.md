# checklist: ecommerce-common

依据：`design-docs/03-通用规范与非功能设计.md`、`15-本地通知组件设计.md`、附录 C/D。
common 的缺陷会通过金额工具/异常/事件基类传播到所有模块，优先核。

## 金额

- [ ] `MonetaryUtil.roundToCent` 用 `RoundingMode.HALF_UP`（**不是** `HALF_DOWN`），保留 2 位小数；`add/subtract/multiply` 都经它舍入。

## 异常体系

- [ ] `ConflictException` 有 `(code, message)` 构造函数 → 业务方能抛带具体码的 409（如 `ORDER_STATUS_CONFLICT`、`REFUND_WAITING_WAREHOUSE_ACCEPT`）。
- [ ] 六类异常齐全且状态码正确：BusinessException 400 / ResourceNotFoundException 404 / AuthorizationException 401·403 / ValidationException 400 / ConflictException 409 / RateLimitException 429。

## 事件基类（附录 D §1）

- [ ] `AbstractDomainEvent` 含 `aggregateId`、`traceId` 字段与 `getEventType()`（所有领域事件都要有）。
- [ ] 跨模块事件的**唯一权威类**定义在 `com.ecommerce.common.event`：`OrderCreatedEvent / OrderPaidEvent / PaymentSucceededEvent / ReviewApprovedEvent / ShipmentDeliveredEvent / RefundCompletedEvent`；各业务模块不得再有同名影子类（有则应已被删除）。

## 本地通知（design-docs/15）

- [ ] `LocalNotificationServiceImpl` 的**故障注入检查在 try 块内**——通知发送失败绝不能回滚触发它的支付事务（PUB-108 类场景：后置动作失败不阻塞主流程）。
- [ ] 通知失败写入**可查询记录**（经 `NotificationRecordService` 记失败状态），`GET /api/v1/admin/notifications` 能看到失败通知。
- [ ] 业务代码只向 `LocalNotificationService` 提交 `NotificationRequest`，**绝不直接**调用 `MockMailSender`/`MockSmsSender`。

## 审计日志基础设施（design-docs/03 §6）

- [ ] 存在共享 `AuditLogEntry` 实体 + `AuditLogService`，供 user/product/inventory 等 7 个操作点接入。
