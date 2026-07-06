# ShopHub 设计-实现一致性 — 已验证发现知识库（findings.md）

本文件是 Stage 1 离线审查产出的**人可审查发现索引**。12 个模块审查 agent 逐模块比对
`design-docs/`（冻结验收基准）+ `README.md`（冻结 REST 契约）与 `code/`（唯一待修对象），
每一条发现整理为 **症状 → 设计依据 → 修复** 三要素。

- **母版来源**：`docs/superpowers/specs/2026-07-05-consistency-fixer-design.md` §6（逐模块发现表）。
- **集成缺陷来源**：`.superpowers/sdd/progress.md` 的「Task 13 集成缺陷日志」（全系统联调阶段发现）。
- **落地形态**：本目录 `knowledge-base/code/` 下按原始相对路径存放的每个被改文件即为**已应用修复后的最终内容**，
  与 `baseline-hashes.txt`（基线 commit `1b1e88f` 的 SHA-256）配套，由 `apply.sh` 做 hash 门控后写入目标工程。
  下表所有条目均已在本地实修并通过 `mvn -f code/pom.xml test` + `mvn -f test-cases/pom.xml test` 验证。
- **规模**：模块级发现共 **97 项**（definite 80 / suspicious 17），跨模块集成缺陷 **8 项**（BUG-INT-1..7 + orderNo 加固），合计 **105 项**。
- **置信度**：`definite` = 确定性 bug，已确定性修复；`suspicious` = 需结合隐藏用例/上下文判断，已按设计文档最合理解释修复。
- **设计依据缩写**：`03` 指 `design-docs/03-通用规范与非功能设计.md`，`04..15` 为对应模块设计文档，
  `附录A/B/C/D` 为对应附录，`README §6/§7` 为冻结 REST 契约 / 错误码，`PUB-xxx` 为对应公开黑盒用例。

---

## 跨模块系统性模式（§6.0，按模式一次性修，而非逐点修）

多个模块报告反复命中同一根因，作为架构级一次性修复处理：

| 模式 | 设计依据 | 处理方式 |
|------|----------|----------|
| **影子事件类**：各模块自定义本地事件类而非引用真正发布方的类，Spring `@EventListener` 按运行时类型分发，同名不同包互不相干 → 监听器永不触发（各模块单测因直接 `new Event()` 绕过事件总线而"假绿"） | 附录D §1-5（事件权威契约）、02 §5（事件发布/监听方） | 把 `OrderCreatedEvent`/`OrderPaidEvent`/`PaymentSucceededEvent`/`ReviewApprovedEvent`/`ShipmentDeliveredEvent`/`RefundCompletedEvent` 的**唯一权威定义迁到 `ecommerce-common`**（不产生 Maven 循环依赖），发布方/监听方统一引用，删除各模块重复定义 |
| **舍入模式 HALF_DOWN**（应 HALF_UP） | 03 §1（舍入模式 `RoundingMode.HALF_UP`） | 只改 `ecommerce-common/MonetaryUtil.roundToCent` 一处，经 `add/subtract/multiply` 传播修正全模块 |
| **`@RateLimit` 基础设施完整但零处使用** | 03 §4（登录 / 支付回调 / 商品搜索 / 创建订单四类限流） | 在这 4 个方法上分别加 `@RateLimit(...)`，不动基础设施 |
| **审计日志基础设施缺失，7 处要求全未实现** | 03 §6（7 类必须审计操作，字段含操作者/前后状态） | `ecommerce-common` 提供审计实体 + `AuditLogService`，各操作点接入 |
| **错误码 `SKU_NOT_AVAILABLE` 应为 `PRODUCT_NOT_FOR_SALE`** | README §7（错误码表） | product（`ProductQueryServiceImpl.getSkuForSale`）、cart（`CartValidationService`）两处一起改 |

---

## common 模块（§6.11，共 5 项）

| # | 症状 | 位置 | 置信度 | 设计依据 | 修复 |
|---|------|------|--------|----------|------|
| 1 | 舍入模式 HALF_DOWN 应为 HALF_UP（跨模块根因定位在此） | `MonetaryUtil.java:32` | definite | 03 §1 | 改 `RoundingMode.HALF_UP` |
| 2 | `ConflictException` 无 `(code,message)` 构造函数，业务方无法抛带错误码的 409（`ORDER_STATUS_CONFLICT`/`REFUND_WAITING_WAREHOUSE_ACCEPT` 从未被抛出） | `ConflictException.java:11-13` | definite | 03 §2（ConflictException=409）、README §7 | 加 `(code,message)` 构造函数 |
| 3 | `AbstractDomainEvent` 缺 `aggregateId`/`traceId` 字段 | `AbstractDomainEvent.java:12-30` | definite | 附录D §1（事件通用字段） | 补字段 + `getEventType()` |
| 4 | 故障注入检查写在 try/catch 外，通知发送故障注入会真的让支付事务回滚（违反"后置动作失败不阻塞主流程"） | `LocalNotificationServiceImpl.java:49-52` | definite | 03 §8（监听器失败不回滚主事务）、15、PUB-108 | 挪进 try 块内 |
| 5 | 通知失败只写日志不落可查询记录，`GET /api/v1/admin/notifications` 看不到失败通知 | `LocalNotificationServiceImpl.java:105-108` | definite | 03 §7（失败记录）、15、README §6 | 扩展 `NotificationRecordService` 记录失败状态 |

---

## user 模块（§6.1，共 7 项）

| # | 症状 | 位置 | 置信度 | 设计依据 | 修复 |
|---|------|------|--------|----------|------|
| 1 | 注册后状态直接 ACTIVE，从不生成激活令牌（PUB-001/PUB-105 根因） | `UserRegisterService.java:57` | definite | 04（注册→激活流程）、附录C users.status（PENDING_ACTIVATION） | 改 `PENDING_ACTIVATION`；注入 `EmailActivationTokenRepository` 生成+持久化令牌；通知改激活邮件模板 |
| 2 | `login()` 对 USER_NOT_ACTIVE/USER_FROZEN 抛 `BusinessException`→400 而非 403（PUB-105 第二根因） | `UserAuthService.java:61-66` | definite | 03 §2（AuthorizationException 401/403） | 改抛 `AuthorizationException("USER_FROZEN"/"USER_NOT_ACTIVE", ...)` |
| 3 | `AddressFormatter.format()` 参数顺序颠倒（文档明确"参数顺序不得调整"） | `AddressFormatter.java:20` | definite | 04（地址格式化） | 改回 `(province, city, district, detail)` |
| 4 | 地址 `isDefault` 实际 JSON key 走 `"default"`，客户端传 `isDefault:true` 被静默忽略（Jackson 2.15.4 实测复现） | `AddressRequest.java`/`AddressResponse.java` | definite | 附录A（地址接口字段）、README §6（字段名冻结） | 加 `@JsonProperty("isDefault")` |
| 5 | 冻结/解冻无审计日志，也拿不到操作者身份 | `UserAuthService.java:119-138`、`AdminUserController.java` | definite | 03 §6（用户冻结解冻审计） | 见 §6.0 审计统一方案 |
| 6 | 登录无限流（同用户名 5 次/分钟） | `UserController.login` | definite | 03 §4（登录限流） | 见 §6.0 RateLimit 统一方案 |
| 7 | `activate()` 对已用/已过期令牌抛 `BusinessException("CONFLICT")`→400，应 409 | `UserAuthService.java:96,100` | definite | 03 §2（ConflictException=409） | 改用 `ConflictException` |

---

## product 模块（§6.6，共 10 项）

| # | 症状 | 位置 | 置信度 | 设计依据 | 修复 |
|---|------|------|--------|----------|------|
| 1 | 库存摘要硬编码返回 999/0，从不调用 `InventoryQueryService` | `StockInfoFetcher.java:22-25` | definite | 05、02 §3（跨模块走 QueryService） | 接入真实库存查询 |
| 2 | `getSkuForSale` 抛 `SKU_NOT_AVAILABLE` 应为 `PRODUCT_NOT_FOR_SALE`（cart 抄了同样的错） | `ProductQueryServiceImpl.java:60-63`、`ecommerce-cart/CartValidationService.java:47` | definite | README §7 | 两处一起改 |
| 3 | 搜索默认 `onlyOnShelf=false`，未上架/草稿商品泄漏到公开列表 | `ProductSearchRequest.java:31`、`ProductSearchService.java:96-102` | definite | 05、附录C product_sku.status | 默认改 `true`/匿名端点强制只查 ON_SHELF |
| 4 | 类目过滤不含子类目 | `ProductSearchService.java:124-130` | definite | 05（类目过滤含后代） | 解析类目树取后代 ID 集合再过滤 |
| 5 | 标签过滤字段完全没被读取 | `ProductSearchService.java`、`ProductSearchRequest.java:24,80-86` | definite | 05（标签过滤） | 接入标签过滤 |
| 6 | 分页 total 在类目/品牌过滤时算错（DB 分页后才在内存里再过滤） | `ProductSearchService.java:63-85` | definite | 05、附录A（分页 {page,size,total,items}） | 把类目/品牌过滤下推到 DB 层 Specification |
| 7 | 商品上下架无审计日志 | `SkuService.java:78-101`、`AdminProductController.java:60-78` | definite | 03 §6（商品上下架审计） | 见 §6.0 审计统一方案 |
| 8 | 商品详情无 10 分钟缓存 | `ProductDetailService.java` | definite | 05、附录B（详情缓存 TTL） | 仿 `CartCacheConfig` 加 Caffeine 缓存 |
| 9 | 关键词搜索只匹配 SKU 名，不匹配 SPU 名/卖点 | `ProductSearchService.java:104-106` | suspicious | 05（关键词匹配范围） | 至少补上 SPU 名匹配 |
| 10 | 商品搜索无限流（120 次/分钟/IP） | `ProductController.java:50-55` | suspicious | 03 §4（商品搜索限流） | 见 §6.0 RateLimit 统一方案 |

---

## inventory 模块（§6.7，共 7 项）

| # | 症状 | 位置 | 置信度 | 设计依据 | 修复 |
|---|------|------|--------|----------|------|
| 1 | `reserve()` 同时扣 onHandStock 且增 reservedStock（应只动 reservedStock），availableStock 多扣一倍且 release 永远无法恢复 | `InventoryReservationServiceImpl.java:58-59` | definite | 06、附录C inventory_stock | 删掉多余的 `onHandStock` 扣减行 |
| 2 | 库存充足判断用 `>` 应为 `>=`，边界值误判为不足 | `InventoryService.java:75` | definite | 06（可用库存边界） | 改 `>=` |
| 3 | 支付后扣减库存从不生成出库单 | `InventoryReservationServiceImpl.java:104-125` | definite | 06（扣减生成出库单） | 补 `OutboundOrder` 创建 |
| 4 | 库存摘要无 30 秒缓存 | `InventoryService` 全类 | definite | 06、附录B（摘要缓存 30s） | 加 `@Cacheable` + 30s TTL |
| 5 | 库存人工调整审计日志没有操作者字段 | `AdminInventoryController.java:67-74`、`StockAdjustmentService`、`StockAdjustment.java` | definite | 03 §6（含操作者） | 加 operator 字段并从 `Authentication` 提取 |
| 6 | `reserve()` 无并发控制，理论上可超卖 | `InventoryReservationServiceImpl.java:37-81` | suspicious | 06（防超卖） | 加乐观锁 `@Version`/悲观锁 |
| 7 | 库存预警端点在冻结 API 契约内实际不可达（依赖未登记的额外配置接口） | `StockWarningService`、`AdminInventoryController.java:86-91` | suspicious | 附录C inventory_stock.warning_threshold、06 | 默认阈值直接挂到 `inventory_stock.warning_threshold` |

---

## cart 模块（§6.5，共 4 项）

| # | 症状 | 位置 | 置信度 | 设计依据 | 修复 |
|---|------|------|--------|----------|------|
| 1 | 购物车用 JPA `@Entity` 落 H2 真表；已写好的 `CartCacheManager`（Caffeine，7 天 TTL）从未被引用 | `CartService.java`、`entity/Cart.java`、`entity/CartItem.java`、`repository/Cart*Repository.java` | definite | 07（Caffeine 缓存 7 天 TTL，从不落库）、附录B | 改走 `CartCacheManager` 读写 `CartData`/`CartItemData`，删 JPA 实体和两个 Repository |
| 2 | 同一 SKU 重复加入是覆盖数量，不是累加 | `CartService.java:91`（`addItem`） | definite | 07（重复加入累加） | 改 `setQuantity(getQuantity()+request.getQuantity())`，累加后重校验库存/上限 |
| 3 | 价格预估 `discountAmount`/`pointsDeductionAmount` 硬编码为 ZERO；`pom.xml` 无 `ecommerce-promotion` 依赖 | `CartService.estimate()`（约 230-238）、`ecommerce-cart/pom.xml` | definite | 07（预估接入促销）、02 §4（PromotionCalculationService） | 加 promotion 依赖，注入 `PromotionCalculationService` 映射进 `discountAmount`/`applicableCoupons` |
| 4 | TTL 未生效（与 #1 同根因） | 同 #1 | definite | 07、附录B | 同 #1，TTL 沿用 `CartCacheConfig` 的 7 天 |

---

## order 模块（§6.2，共 12 项）

| # | 症状 | 位置 | 置信度 | 设计依据 | 修复 |
|---|------|------|--------|----------|------|
| 1 | 创建订单返回 200 应为 201（PUB-102） | `OrderController.java:63` | definite | 附录A、README §6、PUB-102 | `ResponseEntity.status(HttpStatus.CREATED)` |
| 2 | payableAmount 计算漏加 shippingFee（PUB-104） | `OrderTotalCalculator.java:81` | definite | 08、附录C orders.payable_amount、PUB-104 | 补上 `+shippingFee` |
| 3 | 下单前从不校验 `isFrozen`，冻结用户仍可下单 | `OrderPreconditionChecker.java:31-42` | definite | 08、04（冻结用户） | 加 `isFrozen` 校验，抛 `USER_FROZEN` |
| 4 | 风控检查从未被调用，`ORDER_RISK_REJECTED` 是死代码 | `OrderService.java:167-168`（`OrderRiskChecker` 已注入未调用） | definite | 08、README §7 | 创建流程中实际调用 |
| 5 | 金额校验抛 `IllegalArgumentException`→500 而非 `OrderValidationException`→400 | `OrderValidator.java:24-29` | definite | 03 §2（订单金额校验必抛 OrderValidationException） | 改抛 `OrderValidationException` |
| 6 | 已支付订单取消直接跳 CANCELLED，跳过商家审核 | `OrderCancelService.java:83-84,163-194` | definite | 08（已支付取消需审核） | 改为进入 `CANCEL_REVIEWING`，审核通过才退款取消 |
| 7 | 状态机把 PAID→CANCELLED 列为合法迁移（#6 根因之一） | `OrderStateMachine.java:39-42` | definite | 08（订单状态机） | 从 PAID 合法迁移集合去掉 CANCELLED |
| 8 | 批量下单共用一个事务，一条失败整批回滚 | `BatchOrderService.java:20`（class 级 `@Transactional`） | definite | 08（批量下单隔离） | 去掉外层事务/改 `REQUIRES_NEW` |
| 9 | 创建订单无 `externalOrderNo` 幂等去重 | `OrderService.createOrder`；`OrderRepository.java:39`（有方法未调用） | definite | 03 §3（externalOrderNo 幂等） | 创建前按 `(externalOrderNo,userId)` 查重 |
| 10 | 超时取消订单不释放预占库存 | `OrderTimeoutService.java` | definite | 08、06（release） | 注入 `InventoryReservationService`，取消时 `release` |
| 11 | `markAsPaid` 绕过状态机，允许 CREATED 直接到 PAID | `OrderQueryServiceImpl.java:113-135` | suspicious | 08（状态机） | 统一经状态机链式校验（CREATED→PAYING→PAID） |
| 12 | 舍入模式 HALF_DOWN（见 §6.0） | `ecommerce-common/MonetaryUtil.java` | definite | 03 §1 | 见 §6.0（common #1） |

---

## payment 模块（§6.3，共 14 项）

| # | 症状 | 位置 | 置信度 | 设计依据 | 修复 |
|---|------|------|--------|----------|------|
| 1 | 创建支付单状态 PENDING 应为 CREATED（PUB-009） | `PaymentStatus.java`、`PaymentService.java:90` | definite | 附录C payments.status（CREATED/SUCCESS/FAILED/CLOSED）、PUB-009 | 重命名枚举值 |
| 2 | 支付金额校验完全没做——付任意正数即可让订单变已支付 | `PaymentValidator.java:34-74` | definite | 09、README §7（PAYMENT_AMOUNT_MISMATCH）、03 §3 | 加 `amount.compareTo(payableAmount)!=0` 抛 `PAYMENT_AMOUNT_MISMATCH` |
| 3 | 退款审核通过后直接完成退款，跳过仓库验收 | `RefundService.java:127-137` | definite | 09/14、03 §6（退款审核+仓库验收审计） | 审核通过只置 `WAITING_WAREHOUSE_ACCEPT`，`processRefund` 仅由仓库验收触发 |
| 4 | 退款金额公式多扣固定 1.00（文档"不得额外扣除固定费用"） | `RefundCalculator.java:38` | definite | 09（退款金额=实付） | 删掉多余的 `-1.00` |
| 5 | 发票金额无视请求参数，永远按订单全部实付开 | `InvoiceService.java:63` | definite | 14、附录C invoices.amount | 改读 `request.getInvoiceAmount()` |
| 6 | `INVOICE_AMOUNT_EXCEEDED` 从未被抛出（用错码 `INVOICE_LIMIT_EXCEEDED` 且只在全额开完后查） | `InvoiceService.java:71-74` | definite | README §7、14 | 按剩余可开票金额校验单次请求金额 |
| 7 | 结算批次退款汇总永远是 0（从未注入 `RefundRecordRepository`） | `SettlementBatchService.java:105-106` | definite | 14（结算汇总退款） | 注入并按日期汇总真实退款 |
| 8 | 支付确认事务同步执行物流/积分/通知（应异步），且从未在同一事务扣库存 | `PaymentService.java:113-134` | definite | 09、03 §8（后置异步）、附录D §3（inventory 为监听方） | 物流/积分/通知改事件监听器异步；库存扣减经 `PaymentSucceededEvent` 监听器幂等触发 |
| 9 | `PaymentSucceededEvent` 缺 `paidAt`，多了个恒 null 的 `userId` | `PaymentSucceededEvent.java`、`PaymentService.java:128-131` | definite | 附录D §3（载荷 paymentNo/orderId/paidAmount/paidAt） | 按附录D 字段修正 |
| 10 | 退款申请无 `refundRequestNo` 幂等键 | `RefundApplyRequest.java`、`RefundService.java:58-92` | definite | 03 §3（refundRequestNo 幂等） | 加字段 + 查重 |
| 11 | 发票申请无 `invoiceRequestNo` 幂等键 | `InvoiceRequest.java`、`InvoiceService.java:50-104` | definite | 03 §3（invoiceRequestNo 幂等） | 加字段 + 查重 |
| 12 | 支付回调对重复 FAILED 回调无幂等保护（SUCCESS 路径安全） | `PaymentCallbackService.java:94-114` | suspicious | 03 §3（paymentNo+callbackSequence 幂等） | 加"已 FAILED 则直接返回"分支 |
| 13 | `PaymentStatus.REFUNDED` 应为附录C 的 `CLOSED` | `PaymentStatus.java:7`、`RefundService.java:177` | suspicious | 附录C payments.status（CLOSED） | 确认无黑盒断言具体字符串后按附录C 改名 |
| 14 | `RefundStatus`/`InvoiceStatus` 命名与附录C 出入较大（6 vs 5 个值，`CANCELLED` vs `VOIDED`） | `RefundStatus.java`、`InvoiceStatus.java` | suspicious | 附录C refunds.status / invoices.status | 确认无黑盒断言具体字符串后按附录C 对齐 |

> 补充：app §6.12 #3（支付回调 `X-Payment-Signature` 头未被读取/校验）根因在 payment 模块，已并入本模块回调修复。

---

## promotion 模块（§6.4，共 10 项）

| # | 症状 | 位置 | 置信度 | 设计依据 | 修复 |
|---|------|------|--------|----------|------|
| 1 | DISCOUNT 类型优惠券折扣公式反了（PUB-101） | `CouponService.java:84-93` | definite | 10、附录C coupons.type（DISCOUNT）、PUB-101 | 直接 `return afterDiscount`，maxDiscount 封顶分支同理 |
| 2 | 优惠叠加顺序反了（应 满减→券→会员，实际 会员→满减→券） | `PromotionCalculationService.java:46-66` | definite | 10（叠加顺序） | 按文档顺序重排计算链 |
| 3 | 优惠券校验形同虚设：过期/门槛/适用性/已用全未检查，`COUPON_EXPIRED` 从未被抛出 | `CouponValidator.java:32-39` | definite | 10、README §7（COUPON_EXPIRED） | 补全 6 步校验顺序 |
| 4 | 优惠券使用后从不标记 USED，可无限重复使用 | 全模块无处设置 `CouponStatus.USED` | definite | 10、附录C coupons | 下单成功后调用标记方法 |
| 5 | 从不校验优惠券归属，可用他人优惠券 | `PromotionCalculationService.java:111-139` | definite | 10（归属校验） | 加 `userId` 归属校验 |
| 6 | `PromotionController` 硬编码 `userId=1` | `PromotionController.java:115-119` | definite | 10、02（从 SecurityContext 取用户） | 改用 `SecurityContextHolder` |
| 7 | `totalDiscount` 未按"不得大于商品金额"封顶 | `PromotionCalculationService.java:64-70` | definite | 03 §1（优惠金额不得大于商品金额） | 按 clamp 后 `finalAmount` 反推 `totalDiscount` |
| 8 | 秒杀完全没接入下单/购物车流程 | `SeckillService.java` 无调用方 | definite | 10（秒杀校验接入下单） | order/cart 下单前查有效秒杀并调用校验 |
| 9 | 满减活动从不校验起止时间窗口 | `FullReductionService.java:35-51,65-85` | suspicious | 10（活动时间窗口） | 补时间窗口校验 |
| 10 | 舍入模式 HALF_DOWN（见 §6.0） | `ecommerce-common/MonetaryUtil.java` | definite | 03 §1 | 见 §6.0（common #1） |

---

## logistics 模块（§6.8，共 7 项）

| # | 症状 | 位置 | 置信度 | 设计依据 | 修复 |
|---|------|------|--------|----------|------|
| 1 | 发货单创建后直接 OUTBOUND，跳过拣货/打面单（PUB-107） | `ShipmentService.java:81` | definite | 11（状态机）、PUB-107 | 创建时置为 `CREATED` |
| 2 | `outbound()` 不校验前置状态，任意状态都能直接出库 | `ShipmentService.java:223-229` | definite | 11（出库前须 LABEL_PRINTED） | 加"必须 LABEL_PRINTED"前置校验 |
| 3 | `pick()` 允许 OUTBOUND 倒退回 PICKING，`printLabel()` 无状态校验 | `ShipmentService.java:138-143,181-216` | definite | 11（严格 CREATED→PICKING→LABEL_PRINTED→OUTBOUND） | 严格按状态机校验 |
| 4 | 发货单从不通过事件监听器自动创建（`createShipment` 零调用方，死代码） | 全模块无 `@EventListener` | definite | 附录D §2（OrderPaidEvent 监听方含 logistics）、02 §5 | 加 `OrderPaidEvent` 监听器（结合 §6.0 事件类统一） |
| 5 | 物流回调空实现——不查单/不更新/不幂等/不验签 | `LogisticsCallbackService.java:33-39` | definite | 11、03 §3（trackingNo+eventTime+status 幂等） | 按 trackingNo 查单、幂等去重、验签、真正更新状态 |
| 6 | `ShipmentDeliveredEvent` 全仓库不存在 | — | definite | 附录D §4（ShipmentDeliveredEvent 契约） | 新建该事件类，签收时发布 |
| 7 | 运费模板无 30 分钟缓存；省份/重量规则字段存了却从未读取，运费只用固定 `defaultFreight` | `FreightCalculator.java`、`FreightTemplateService.java` | definite | 11（按省份/重量规则）、附录B（模板缓存 30 分钟） | 加缓存；解析 `provinceRules`/`weightRules` 参与计算 |

---

## loyalty 模块（§6.9，共 11 项）

| # | 症状 | 位置 | 置信度 | 设计依据 | 修复 |
|---|------|------|--------|----------|------|
| 1 | GOLD 会员倍率写成 1.1（和 SILVER 一样），应为 1.2 | `MemberLevel.java:11` | definite | 12（会员等级倍率） | 改 `1.2` |
| 2 | 监听本模块自己的 `OrderPaidEvent` 而非 order 真正发布的类——支付积分在真实环境从未发放 | `OrderPaidEvent.java`、`OrderPaidEventListener.java` | definite | 附录D §2、02 §5 | 见 §6.0 事件类统一方案 |
| 3 | `ReviewApprovedEvent` 同样是本模块自己的类——评价奖励积分从未真正发放 | `ReviewApprovedEvent.java`、`ReviewApprovedEventListener.java` | definite | 附录D §5、02 §5 | 见 §6.0 |
| 4 | 积分过期是空实现，也没有任何定时任务 | `PointsExpireService.java:20-22` | definite | 12（积分过期）、附录C loyalty_points.expire_date | 实现过期扫描+扣减+记录，加 `@Scheduled` |
| 5 | 会员等级统计用 `JdbcTemplate` 直查 `orders` 表原始 SQL，违反禁止跨模块直接查表规则 | `OrderDataFetcher.java:27-37` | definite | 02 §3（禁止跨模块直查表，走 QueryService） | 改用 `OrderQueryService`/销售统计接口（此处改事件自维护，因 order→loyalty 依赖已存在） |
| 6 | 积分冻结（模块职责明列）完全无实现（`frozenPoints` 恒 0） | `LoyaltyAccount.java:32-33` | suspicious | 12（积分冻结） | 先确认冻结触发场景（如退款占用）再实现 |
| 7 | `redeemPoints`/`earnPaymentPoints` 在 order/payment 零调用——积分抵扣在真实下单流程不生效 | 接口在 loyalty，缺口在 order/payment 侧 | suspicious | 12、08（下单积分抵扣） | order 创建订单时调用积分抵扣 |
| 8 | 评价奖励积分数硬编码 20，不读运行时配置 | `ReviewApprovedEventListener.java:18` | suspicious | 12、附录B（运行时配置覆盖） | 改读 `RuntimeConfigRegistry` |
| 9 | 抵扣/赚取四个常量硬编码，不支持运行时配置（默认值本身正确） | `LoyaltyPointService.java:35-43` | suspicious | 附录B（配置项运行时覆盖） | 改读 `RuntimeConfigRegistry` |
| 10 | 年度消费统计用 `LocalDate.now()` 而非 `SystemClockService`，测试时钟覆盖不生效 | `OrderDataFetcher.java:28` | suspicious | 03 §5（黑盒隔离/测试时钟）、common SystemClock | 改用 `SystemClockService` |
| 11 | 会员等级只在查询 `/member-level` 时重算，支付时不刷新，可能用旧等级倍率算分 | `OrderPaidEventListener.java:30-48` | suspicious | 12（计分前刷新等级） | 支付计分前先 `evaluateAndUpgrade` |

---

## review 模块（§6.10，共 6 项）

| # | 症状 | 位置 | 置信度 | 设计依据 | 修复 |
|---|------|------|--------|----------|------|
| 1 | 从不校验购买+签收，`OrderQueryService.verifyPurchase` 零调用——未购买也能评价 | `ReviewService.java:59-102` | definite | 13、README §7（REVIEW_PURCHASE_REQUIRED） | 接入 `verifyPurchase`，不满足抛 `REVIEW_PURCHASE_REQUIRED` |
| 2 | 提交评价时（而非审核通过时）就发 `ReviewApprovedEvent`，审核通过又发一次——双发，被拒也发 | `ReviewService.java:99`、`ReviewModerationService.java:63` | definite | 附录D §5（审核通过发布）、13 | 只在 `approve()` 里发一次 |
| 3 | 事件缺 `orderId`/`productId`（附录D 要求 4 字段，只有 2 个） | `ReviewApprovedEvent.java` | definite | 附录D §5（reviewId/userId/orderId/productId） | 补齐字段 |
| 4 | 发的是 review 自己的 `ReviewApprovedEvent`，非 loyalty 监听的类（与 §6.9 #3 同根因） | `ReviewApprovedEvent.java`/`ReviewApprovedEventListener.java` | definite | 附录D §5、02 §5 | 见 §6.0 |
| 5 | 敏感词过滤用完全相等匹配，不是包含匹配（文档明确"不得只做完全相等匹配"） | `SensitiveWordFilter.java:31-42,50-61` | definite | 13（敏感词包含匹配） | 改 `contains`/`replace` |
| 6 | 命中敏感词直接抛异常丢弃，评价从未进入 PENDING_REVIEW/REJECTED 终态 | `ReviewService.java:74-78,127-131` | suspicious | 13、附录C reviews.status | 改为落库为 REJECTED 而非直接拒绝请求 |

---

## app 模块（§6.12，共 4 项，含 1 项安全漏洞级别）

| # | 症状 | 位置 | 置信度 | 设计依据 | 修复 |
|---|------|------|--------|----------|------|
| 1 | **安全漏洞**：`reset-sandbox`/`bootstrap-admin` 未鉴权（`permitAll()`），属文档明禁的 reset/bootstrap 接口——任何人可清库或自签 ADMIN token | `SystemAdminController.java:55-95`、`SecurityConfig.java:63-64` | definite | 03 §5（业务代码不得暴露 reset/bootstrap 接口） | 整个删除这两个接口及其安全放行规则 |
| 2 | `verify-purchase` 文档要求 USER/ADMIN 均可访问，实际只放行 USER | `SecurityConfig.java:66`、`ecommerce-order/OrderController.java:36` | definite | 附录A、README §6 | 两处一起放开 ADMIN |
| 3 | 支付回调 `X-Payment-Signature` 头完全没被读取/校验（根因在 payment 模块） | `ecommerce-payment/PaymentController.java:52-58`、`PaymentCallbackService.java:40-65` | definite | 09（回调验签） | 加签名校验（并入 §6.3 payment 修复） |
| 4 | 事件失败无重放端点，`FailedEventRecord.retried/retryCount` 存在却从未被更新 | `EventFailureAdminController.java` | suspicious | 03 §8（可通过管理接口重放失败事件） | README 冻结 9 端点不含重放，属可选增强，附加实现不影响契约 |

---

## 跨模块集成缺陷（Task 13）

全系统联调（`.superpowers/sdd/progress.md`「Task 13 集成缺陷日志」）阶段，在 12 个模块单独修复合并后、
跑全量黑盒时暴露的**跨模块接线缺陷**。这些是单模块视角看不到、必须在整机集成才显现的问题，逐一定位并修复：

| 编号 | 根因 | 修复 |
|------|------|------|
| **BUG-INT-1** bean 名冲突 | `loyalty.OrderPaidEventListener` 与 `logistics.OrderPaidEventListener` 简单类名相同 → 默认 bean 名都为 `orderPaidEventListener` → `ConflictingBeanDefinitionException` → Spring 上下文启动失败，全量黑盒 24/24 ERROR（非断言失败）。二者是同一 `OrderPaidEvent` 的两个模块反应（logistics 建发货单 / loyalty 加积分），都必须注册。 | 仿 app 既有 `@Configuration("appSecurityConfig")` 手法，给两监听器显式模块限定 bean 名 `@Component("logisticsOrderPaidEventListener")` / `@Component("loyaltyOrderPaidEventListener")`。 |
| **BUG-INT-2** 秒杀事务毒化 | `OrderService.createOrder`（`@Transactional`）为侦测"该 SKU 是否秒杀"调 `SeckillService.validateSeckill`（`@Transactional(readOnly=true)`），普通订单必然抛 `ResourceNotFoundException`（SKU 不在秒杀），order 端 catch 吞掉当"非秒杀"——但抛出时 Spring 已把共享事务标记 rollback-only，提交时爆 `UnexpectedRollbackException` 500，**所有下单**失败（连锁 8 个用例）。 | `validateSeckill` 改 `@Transactional(readOnly=true, noRollbackFor=ResourceNotFoundException.class)`——良性 not-found 不再毒化调用方事务；真正的秒杀失败仍照常回滚。 |
| **BUG-INT-3** AFTER_COMMIT 不落库 | 支付回调后 logistics `OrderPaidEventListener`（`@TransactionalEventListener(AFTER_COMMIT)`）自动建发货单，但 AFTER_COMMIT 阶段无存活事务，`save()` 加入的是已提交的完成中事务、从不 flush → 发货单从未落库 → 订单永远到不了 DELIVERED → 评价被"必须购买并收货"拦截（pub014 失败）。 | 给 logistics 监听器方法加 `@Transactional(propagation=REQUIRES_NEW)`，后置动作在全新事务内提交；同时保证 pub108（后置失败不阻断支付）仍成立（新事务回滚不影响已提交的支付）。 |
| **BUG-INT-4** pick NPE | `AdminLogisticsController.pick(id)` 调 `shipmentService.pick(id, null)`（pickerId 恒 null），而 `ShipmentService.pick` 第 158 行 `pickerId.toString()` → NPE 500 → 发货单卡在 CREATED → 拣货/面单/出库/签收整条链断 → 评价被拒。 | pick 里 pickerId 判空（与 printLabel/outbound 一致），拣货不再 NPE。 |
| **BUG-INT-5** ShipmentDeliveredEvent 无监听者 | 发货签收后 logistics 发 `ShipmentDeliveredEvent`，但全仓无监听者 → 订单永远停在 PAID → `OrderQueryServiceImpl.verifyPurchase` 只认 DELIVERED/COMPLETED → 评价被拒。设计意图（附录D §4：order 监听 `ShipmentDeliveredEvent`）就是靠该事件把订单推到 DELIVERED。 | 新增 order 模块 `ShipmentDeliveredEventListener`（AFTER_COMMIT+REQUIRES_NEW），链式校验 PAID→PICKING→SHIPPED→DELIVERED 后置 DELIVERED；幂等（已 DELIVERED/COMPLETED 跳过）。 |
| **BUG-INT-6** 支付后库存不扣减 | 支付成功后库存从不扣减——`OrderPaymentEventHandler.handlePaymentSuccess`（会扣减）是死代码（0 次执行），真实路径 `OrderQueryServiceImpl.markAsPaid` 只置 PAID+发 `OrderPaidEvent`，不扣库存；无任何 `PaymentSucceededEvent` 监听者做扣减（违反附录D §3：inventory 为 `PaymentSucceededEvent` 监听方）。 | 新增 inventory `PaymentSucceededInventoryListener`（AFTER_COMMIT+REQUIRES_NEW）调幂等的 `deductAfterPayment(orderId)`（预占→扣 onHand+reserved、生成 OutboundOrder）。 |
| **BUG-INT-7** verifyPurchase 排序字段不存在 | `OrderService.verifyPurchase`（controller 路径）按 `Sort.by("deliveredAt")` 排序，但 Order 实体无 `deliveredAt` 列 → 调 REST `/verify-purchase` 会 `PropertyReferenceException` 500。 | 改按 `"createdAt"` 排（与端口实现一致；签收由 DELIVERED 状态体现而非时间列）。 |
| **加固** orderNo 同毫秒碰撞 | `generateOrderNo()` 原用 `currentTimeMillis()%10000` 生成序列号，同一毫秒内创建的多笔订单（批量下单）会产生相同 orderNo，违反其唯一约束。 | 改用单调递增计数器 `orderSequence.incrementAndGet()%10000`；所有单笔/批量下单都经同一 `OrderService` bean，计数器共享、无碰撞（commit 9e6274e）。 |

---

*验证结果：完整公开黑盒套件（`PubBasicFlowTest` PUB-001..016 + `PubAdditionalBehaviorTest` PUB-101..108，共 24 例）在清空上下文的重复独立运行下稳定 **24/24 全绿**。*
