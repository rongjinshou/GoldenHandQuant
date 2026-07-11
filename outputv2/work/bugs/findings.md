# ShopHub 设计-实现一致性 — 已验证发现索引（findings.md）

> **本文件在本作品里的定位：背景/溯源资料，不是执行入口。** 实际执行路径是
> `INSTRUCTION.md` → `work/bugs/README.md`（批次表）→ 19 个按批次组织的详细卡片文件
> （`S1-quick-wins.md`、`S2-events.md`、各模块 `.md`、`S3-audit.md`、`S4-config.md`）——那 19
> 份文件里的每条卡片都是**自包含**的（文件/现状/期望/改法/验收/勿犯全齐），执行 agent 不需要
> 也不应该回来读本文件。保留本文件是因为它的「尽调后明确放弃」「已识别但未实施」两节，以及
> 末尾的验证历史记录，包含 19 份卡片文件里没有逐字复制的推理过程，供人工审阅溯源用。

本文件是离线审查阶段产出的**人可审查发现索引**。12 个模块审查 agent 逐模块比对
`design-docs/`（冻结验收基准）+ `README.md`（冻结 REST 契约）与 `code/`（唯一待修对象），
每一条发现整理为 **症状 → 设计依据 → 修复** 三要素。

- **验证状态**：下表所有条目均已在作者侧实修，并通过 `mvn -f code/pom.xml test` +
  `mvn -f test-cases/pom.xml test`（公开黑盒 24 例）验证——修复后的目标代码已直接写进
  19 份卡片文件的「改法」里，本文件只保留发现本身。
- **规模**：第一轮（模块级 97 项 + 跨模块集成 8 项 = 105 项）+ 第二轮深审（§7，28 项）+ 第三轮深审（§8，模块内 11 项 + 跨领域 9 项 = 20 项），合计 **153 项**。
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

全系统联调阶段，在 12 个模块单独修复合并后、
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
| **加固** orderNo 同毫秒碰撞 | `generateOrderNo()` 原用 `currentTimeMillis()%10000` 生成序列号，同一毫秒内创建的多笔订单（批量下单）会产生相同 orderNo，违反其唯一约束。 | 改用单调递增计数器 `orderSequence.incrementAndGet()%10000`；所有单笔/批量下单都经同一 `OrderService` bean，计数器共享、无碰撞。 |

---

## 第二轮深审新发现与修复（§7）

第一轮交付并稳定通过 24/24 后，针对**隐藏用例可能触达、但公开 24 例未覆盖**的深层设计契约，
派出 5 个独立只读审计 agent（支付/退款/发票/结算、促销/积分、物流/库存/订单、横切面契约、
用户/商品/购物车/评价），每个 agent 先与本文件（第一轮 105 项）逐条比对去重，只报告
「新发现」或「已记录但复核后判定修复不完整」的项，避免重复劳动。汇总约 55 条（含跨报告重复）后，
按 **definite + 低回归风险** 标准裁决，逐批实施、每批之后重跑 24 例黑盒确认无回归。

### 已修复（28 项）

| # | 症状 | 位置 | 置信度 | 设计依据 | 修复 |
|---|------|------|--------|----------|------|
| 1 | 两份并存 `SecurityFilterChain`（user 模块 + app 模块），均无 `@Order`/`securityMatcher`，谁生效取决于 Spring bean 注册顺序——脆弱，任何依赖/classpath 变化都可能静默反转生效方 | `ecommerce-user/config/SecurityConfig.java`、`ecommerce-app/SecurityConfig.java` | definite | 02（app-bootstrap 统一持有安全配置） | 尽调确认 user 模块的 `BCryptPasswordEncoder` bean 被 `UserRegisterService`/`UserAuthService` 按具体类型直接注入（不可删），窄修复：只删 user 模块的 `SecurityFilterChain` bean + `@EnableWebSecurity`，保留其 encoder bean；user 模块 4 个 `@WebMvcTest` 改用新建的纯测试态 `TestSecurityConfig` |
| 2 | 缺失/伪造 JWT 访问受保护接口返回 Spring Security 默认 403 + 非契约错误体（跳过 `GlobalExceptionHandler`），而非 README 要求的 401 + `{code,message,traceId,details}` | 全仓无 `AuthenticationEntryPoint`/`AccessDeniedHandler` | definite（已用仓库自带 `SecurityConfigTest` 实测复现） | README §7（UNAUTHORIZED=401≠FORBIDDEN=403）、附录A §1 | 新增 `RestAuthenticationEntryPoint`（401+ApiError）、`RestAccessDeniedHandler`（403+ApiError），接入 app SecurityConfig 的 `exceptionHandling(...)` |
| 3 | `PaymentService.queryOrderDirectly` 用 `JdbcTemplate` 直接查 `orders` 表，绕过 `OrderQueryService`，违反模块边界 | `PaymentService.java` | definite | 09§1"支付服务通过OrderQueryService查询...不得直接查询订单表" | 改调用 `orderQueryService.getPayableOrder(orderId)`；移除 JdbcTemplate 依赖 |
| 4 | 订单状态冲突（重复支付、非可支付状态）用 400+`ORDER_STATUS_INVALID`（非冻结码），应为 409+`ORDER_STATUS_CONFLICT` | `OrderQueryServiceImpl.getPayableOrder`、`PaymentValidator` | definite | README §7 `ORDER_STATUS_CONFLICT`/409 | 改抛 `ConflictException("ORDER_STATUS_CONFLICT",...)` |
| 5 | 已 SUCCESS 又收到 FAILED 回调用 400+`BusinessException`，应为 409 | `PaymentCallbackService.processFailedCallback` | likely | 03§2（状态冲突=409） | 改 `ConflictException` |
| 6 | 支付/回调的 `paidAmount` 直接存客户端原始精度，未经 `MonetaryUtil.roundToCent` | `PaymentService.pay`、`PaymentCallbackService.processSuccessCallback` | likely | 03§1（入库两位小数） | 补 `MonetaryUtil.roundToCent` |
| 7 | README 冻结码 `REFUND_WAITING_WAREHOUSE_ACCEPT`（409）全仓库从未被抛出 | `RefundService.reviewRefund` | definite（两个独立 agent 各自复核确认） | README §7 | 对已在 `WAITING_WAREHOUSE_ACCEPT` 的退款再次审核，改抛该码 |
| 8 | 退款审核、仓库验收无审计日志 | `RefundService.reviewRefund`/`warehouseAccept` | definite | 03§6（7类必须审计操作） | 接入 `AuditLogService.record` |
| 9 | 退款完成通知渠道用 EMAIL，应为 IN_APP | `RefundService.sendRefundNotification` | definite | 15§2（退款状态→IN_APP） | 改 `NotificationChannel.IN_APP` |
| 10 | 发票金额（`invoiceAmount`）未经 `MonetaryUtil.roundToCent`（`taxAmount` 有做，唯独本体漏了） | `InvoiceService.generateInvoice` | likely | 03§1 | 补舍入 |
| 11 | 发票开具无审计日志 | `InvoiceService.generateInvoice` | definite | 03§6 | 接入 `AuditLogService` |
| 12 | 结算批次生成无审计日志 | `SettlementBatchService.generateBatch` | definite | 03§6 | 新增 `operatorId` 参数 + 接入 `AuditLogService`；`AdminSettlementController` 从 SecurityContext 提取 |
| 13 | 支付成功通知渠道用 EMAIL，应为 SMS | `PaymentSucceededNotificationListener` | definite | 15§2（支付成功→SMS） | 改 `NotificationChannel.SMS` |
| 14 | 创建订单请求体 `addressId`（附录A 必填字段）被完全忽略，恒用默认地址 | `OrderService.createOrder` | definite | 附录A §6 | `UserQueryService` 新增 `getAddressById(userId, addressId)`（校验归属），`OrderService` 改按请求值查询 |
| 15 | `calculateDiscounts` 用 `catch(Exception e)` 吞掉全部异常，真实的优惠券业务失败（`COUPON_EXPIRED` 等 README 冻结码）被静默降级为"零折扣、下单照常成功" | `OrderService.calculateDiscounts` | definite | README §7（这些码必须可达） | 收窄为 `catch(BusinessException e){throw e;}` + `catch(Exception e){降级}` 两层 |
| 16 | `order.max-items`（附录B 默认 30）从未被强制校验；仓库里唯一的上限校验（`OrderValidationUtils`，常量还错写成100）是从未调用的死代码 | `OrderPreconditionChecker` | definite | 附录B | 接入 `RuntimeConfigRegistry.getInt("order.max-items", 30)` 做真实校验 |
| 17 | `order.expire-minutes` 硬编码 `plusMinutes(60)`，不读配置，运行时配置覆盖对下单流程无效果 | `OrderService.createOrder` | definite | 附录B | 接入 `RuntimeConfigRegistry` |
| 18 | `RefundCompletedEvent` 全仓库零监听者，退款完成后订单状态永不变化；该事件类仍留在 `payment.event` 包（未迁移到 common），导致 order 模块（依赖方向决定它不能反向依赖 payment）根本无法引用它写监听器 | 全仓 | definite（grep 实锤 + 两个独立 agent 复核） | 02§5（"更新售后状态"） | 事件类迁移到 `common.event`（仿照其余4个已迁移事件）；新增 order 模块 `RefundCompletedEventListener`，DELIVERED→REFUNDING→REFUNDED（状态机只定义了这条路径，非DELIVERED状态收到退款完成则记录日志并跳过，不臆造未定义的迁移） |
| 19 | `OrderCreatedEvent` 监听器只打日志，注释自认"In production this would...send notification"，从未真正发通知 | `OrderEventListener.onOrderCreated` | likely | 15§2（订单状态→IN_APP） | 接入 `LocalNotificationService` |
| 20 | 创建订单、支付回调两个接口无 `@RateLimit`（4类限流要求中缺2个） | `OrderController.createOrder`、`PaymentController.callback` | definite | 03§4（订单20/分钟/用户，回调20/分钟/paymentNo） | 加注解；订单侧用新增的 `Authentication` 方法参数按用户限流（非IP——黑盒测试全部从同一主机发起，IP维度会误伤同进程内的其他测试方法） |
| 21 | 库存不足统一抛 `INSUFFICIENT_STOCK`，应为 README 冻结码 `INVENTORY_NOT_ENOUGH`（3处：库存预占、手工出库、购物车校验） | `InventoryReservationServiceImpl`、`InventoryService`、`CartValidationService` | definite | README §7 | 改字符串（同步改 4 处测试断言） |
| 22 | `listAvailableWarehouses` 未按仓库 `priority` 降序排序，与其自身在 `InventoryQueryService` 接口上的 javadoc 承诺自相矛盾 | `InventoryService.listAvailableWarehouses` | likely | 06§4（隐含的分配优先级） | 注入 `WarehouseRepository`，按 `priority` 降序排序 |
| 23 | 非本人追评（`appendReview`）抛 `BusinessException("FORBIDDEN")`→400，code 与 HTTP 状态自相矛盾（应 403） | `ReviewService.appendReview` | definite | 03§2（`AuthorizationException`=401/403） | 改 `AuthorizationException.forbidden(...)` |
| 24 | 重复评价提交、重复审核（对非 PENDING_REVIEW 状态再次审核）用 400，应为 409 | `ReviewService.createReview`、`ReviewModerationService.approve/reject` | likely | 03§2（重复提交=状态冲突=409） | 改 `ConflictException` |
| 25 | `sensitive_words` 表永远为空（无播种数据、无管理接口），敏感词过滤算法本身正确（第一轮已修）但因表恒空而永不触发 | 全仓无播种逻辑 | definite | 13§3（敏感词过滤是强制步骤） | 新增 `SensitiveWordSeeder`（启动时若表为空则播种默认词表） |
| 26 | 商品搜索关键词只匹配 SPU/SKU 名称，未匹配 SPU `description`（"卖点"） | `ProductSearchService.resolveKeywordSpuIds` | likely（对应第一轮 product#9，suspicious，复核后确认应补齐） | 05§4（"商品名称、卖点模糊匹配"） | 新增 `ProductSpuRepository.findByDescriptionContainingIgnoreCase`，并入关键词匹配 |
| 27 | 积分抵扣只估算（`estimateRedeemPoints`）从未真正扣减（`redeemPoints` 命令全仓零调用，含未接线的死代码平行实现），同一批积分可在任意多笔订单重复"抵扣" | `OrderService.createOrder` | definite（独立判断：连从未接线的平行实现`OrderPricingService`/`LoyaltyIntegrationService`里也只做估算，说明"扣减"这一半功能从未被写过，不是接错线） | 附录A §6（`pointsDeductionAmount` 字段） | 订单持久化后调用 `loyaltyCommandService.redeemPoints`（与优惠券/秒杀"仅在持久化成功后消费"同一模式） |
| 28 | `InventoryReservationService.release()` 只处理 `RESERVED` 状态预占；已支付订单（预占早已转为 `DEDUCTED`）走商家审核通过取消时，`release()` 找不到 `RESERVED` 记录、静默 no-op，`onHandStock` 永久性短少（货从未发出） | `InventoryReservationServiceImpl.release` | likely | 06§3（取消需释放库存）+ 08§6 | `release()` 增加对 `DEDUCTED` 记录的处理：归还 `onHandStock`，置 `RELEASED` |

### 尽调后明确放弃（2 项，风险高于收益）

| 项目 | 尽调结论 |
|---|---|
| `OrderLogisticsStatusUpdater` 生产实现（物流状态从未真正推进订单 PICKING/SHIPPED） | 冻结的 `test-cases/BlackboxHarnessConfig`（黑盒测试基类会 import）已注册一个**无限定符**的该接口 no-op bean。若在 `ecommerce-order` 生产代码新增真实实现（会被 `@ComponentScan` 扫到），会与该 no-op bean 类型冲突，在黑盒测试的 Spring 上下文启动时精确重演 BUG-INT-1（`NoUniqueBeanDefinitionException`）——不是"中风险"，是**必定复现 24 例全灭**。彻底放弃。 |
| `@EnableMethodSecurity`（激活全仓库当前休眠的 `@PreAuthorize` 注解） | 逐条核对 README §6 全部 61 个端点，URL 级 `SecurityConfig` 规则已 100% 独立覆盖，启用方法级安全**不会修复任何当前可观察的行为**，只会让此前从未生效过的 `@PreAuthorize` 注解突然生效——如果其中任何一处注解的角色写错（因为从未被执行过，没有任何验证），会静默改变现有端点的鉴权行为。零当前收益、非零风险，放弃。 |

### 已识别但因时间/风险预算未实施（供后续参考）

以下均已被本轮某个 agent 明确指出，但因**改动面更大**（跨模块 DTO 变更）或**风险回报比不划算**（大特性/纯投机）暂缓，不在本次提交范围内：

- 优惠券 `markUsed` 缺归属校验、且消费的是请求里全部 couponId 而非计算阶段真正验证通过的那些（需要 `PromotionCalculateResponse` 新增字段回传已应用券，改动跨越 promotion+order 两个模块）
- 优惠券/秒杀名额在订单取消后从未释放（需要 promotion 侧新增 release 方法 + order 侧接线）
- 优惠券"适用类目"字段从未被校验（只校验了"适用商品"）
- 运费模板系统（省份/重量规则+缓存，本身逻辑已修好）从未接入真实下单流程，下单运费仍固定 8.00/199.00 阈值
- 多仓库分配优先级完整算法（`reserve()` 目前贪婪按 DB 返回顺序扣减，不看省份匹配/优先级）——本项里"排序自相矛盾"的小缺陷已单独修复（见已修复 #22），完整分配算法未做
- 物流回调对已终态（DELIVERED）的状态倒退无单调性校验——明确评估过风险：若做成"必须逐级到达"会打掉 PUB-014/107/108 依赖的跳跃式前进路径，故未做
- 订单 `DELIVERED→COMPLETED` 触发机制——design-docs 未写明触发方式（用户确认收货？超时自动？），纯投机不做
- 购物车 `pointsDeductionAmount` 恒为0（`discountAmount` 半部分第一轮已修，积分半部分未做）——需新增 cart→loyalty 模块依赖，中等风险
- `FailedEventRecord` 对 `AFTER_COMMIT` 监听器失败从未记录（只打日志）——需要改造多个既有监听器的 catch 块
- `InvoiceStatus.CANCELLED` 应为附录C 的 `VOIDED`——当前无任何写路径会产生该值，黑盒观测不到，优先级最低
- `payment.retry-times`/`cart.ttl-days` 等次要死配置未接入 `RuntimeConfigRegistry`

---

## 第三轮深审新发现与修复（§8）

第二轮交付并稳定 24/24 后，针对**上一轮未深覆盖的模块**（user / product / logistics / review）与
**跨领域契约**（事件事务语义、幂等键、响应封装、配置默认值、本地通知、金额规范），再派 5 个独立只读
审计 agent，每个先与本文件 §1–§7 逐条去重，只报「新发现」或「复核后判定修复不完整」。汇总裁决后分三批
实施，每批之后重跑 24 例黑盒确认无回归。

### 模块内确定性修复（11 项）

| # | 症状 | 位置 | 置信度 | 设计依据 | 修复 |
|---|------|------|--------|----------|------|
| 1 | 订单赚积分误用**抵扣**汇率 `loyalty.redeem-rate`(100) 而非**赚取**汇率 `loyalty.points-per-yuan`(1)，积分被放大约 100 倍 | `LoyaltyPointService.calcOrderPoints` | definite | 12§2（赚取）与 12§3（抵扣）为两个不同汇率 | 新增 `earnRatePerYuan()` 读 `points-per-yuan` |
| 2 | `estimate-redeem` 抵扣金额硬编码 `/100` 且用 `DOWN` 舍入，不随 `points-per-yuan` | `LoyaltyController.estimateRedeem` | definite | 12§3 + 03§1（HALF_UP） | 新增 `pointsToAmount()` 按 `points-per-yuan` 反算、HALF_UP |
| 3 | 包装费按商品件数累加，应为按订单固定一份 | `OrderTotalCalculator.calculatePackagingFee` | definite | 附录B `order.packaging-fee` 标量 + 08§1 + 附录A 示例 | 改读 `order.packaging-fee` 固定值 |
| 4 | 免运费阈值硬编码 199.00，运行时配置覆盖无效 | `OrderTotalCalculator.calculateShippingFee` | definite | 附录B `order.free-shipping-threshold` | 接入 `RuntimeConfigRegistry` |
| 5 | 批量下单 `continueOnError=false` 时单行失败即抛异常中止整批 | `BatchOrderService.createBatch` | definite | 08§7（单笔失败不影响其他） | 删除中止分支，恒逐行续跑 |
| 6 | 订单取消的各种状态冲突抛 `BusinessException(...)/400`，应 409 | `OrderCancelService`（5 处） | definite | README §7 `ORDER_STATUS_CONFLICT`/409 | 改 `ConflictException("ORDER_STATUS_CONFLICT",...)` |
| 7 | 请求体 JSON 解析失败 / 参数类型不符 / 缺参 → 非契约错误体，应 400 `VALIDATION_FAILED` | `GlobalExceptionHandler` | definite | README §7 `VALIDATION_FAILED`/400 | 新增 `handleBadRequestParameter` 捕获 3 类 Spring 异常 |
| 8 | 退款记录 `orderId` 取自客户端请求（可伪造），应取自被退款的 `PaymentRecord` | `RefundService.applyRefund` | definite | 09§4（退款以支付单为准） | 改 `refund.setOrderId(payment.getOrderId())` |
| 9 | 退款手续费率硬编码，不读 `payment.refund-fee-rate` | `RefundCalculator.calculate` | likely | 附录B | 接入 `RuntimeConfigRegistry` |
| 10 | 发票税额两步舍入（`setScale(4)`→`roundToCent`）与 `RefundCalculator` 单步不一致，边界值可差 1 分 | `InvoiceService.generateInvoice` | likely | 14§4 + 03§1 | 改单步 `MonetaryUtil.multiply` |
| 11 | 同一 `couponId` 在一次请求里出现两次会被双重计算折扣 | `PromotionCalculationService.calculateCouponDiscount` | likely | 10§2（一券一单一次） | `couponIds.stream().distinct()` |

### 跨领域深审修复（9 项）

| # | 症状 | 位置 | 置信度 | 设计依据 | 修复 |
|---|------|------|--------|----------|------|
| 1 | 核销 `markUsed` 不校验券归属：下单请求塞入他人 `userCouponId`，只要订单有任意折扣即可消耗他人的券（计算侧已强制归属，核销侧遗漏） | `CouponService.markUsed` | definite | 附录C `user_coupon.user_id` + 计算侧 `calculateCouponDiscount:146` 已强制归属 | `markUsed` 增 `userId` 参数，非本人券静默跳过 |
| 2 | 重复 `skuCode`/`spuCode` 创建抛 `ValidationException`/400，应 409 | `SkuService.createSku`、`SpuService.createSpu` | definite | README §7 `CONFLICT`/409「重复请求」+ User/Settlement 同类先例 | 改 `ConflictException` |
| 3 | 对 `DELETED` SKU 上/下架抛 400，应 409（状态机非法迁移） | `SkuService.onShelf/offShelf` | definite | README §7 `CONFLICT`/409「状态冲突」+ Order/Payment 范式 | 改 `ConflictException` |
| 4 | 评价 approve/reject 用 `@RequestBody`(required=true)，冻结 `ReviewFixture` 以 null body 调用 → 空体触发 400 ≠ 约定 200，整条审核→积分链路在冻结调用约定下不可用 | `AdminReviewController` | definite（冻结 fixture 为铁证） | README §6.7（200）+ 13 / 附录A 未定义请求体 | 改 `@RequestBody(required=false)` + null 兜底 |
| 5 | loyalty 的 `OrderPaid`/`ReviewApproved` 监听器用普通 `@EventListener`（与发布方同事务）：积分发放失败（故障注入）会把整个支付确认/评价审核事务**连带回滚** | `loyalty/OrderPaidEventListener`、`ReviewApprovedEventListener` | definite（Spring 参与型事务 rollback-only 语义） | 02§5 / 03§8 / 09§3（后置动作失败不得回滚主事务） | 改 `@TransactionalEventListener(AFTER_COMMIT)` + `@Transactional(REQUIRES_NEW)`，镜像已验证可用的 inventory/logistics 监听器 |
| 6 | 购物车估价用类内硬编码运费/包装费/阈值，与订单侧（已读配置）不同源：管理员覆盖阈值后 `/cart/estimate` 与 `/orders/create` 结果不一致 | `CartService.estimate` | likely | 附录B + 07§3（预估与下单同规则） | 改读 `RuntimeConfigRegistry`，与 `OrderTotalCalculator` 同源 |
| 7 | 支付回调不校验金额：回调体金额直接写入 `paidAmount` 并置 SUCCESS，被退款/发票据为权威 → 先正常 `pay()` 再用抬高金额回调即可放大退款/开票 | `PaymentCallbackService.processSuccessCallback` | definite | 09§2（支付金额须等于订单应付） | 回调校验 `amount == payment.orderAmount`，不一致抛 `PAYMENT_AMOUNT_MISMATCH` |
| 8 | 开票成功从不发通知 | `InvoiceService.generateInvoice` | definite | 15§2（发票通知 → EMAIL） | 注入 `LocalNotificationService`，开票后发 EMAIL（best-effort，失败不影响主流程） |
| 9 | 物流全流程从不发「发货提醒」 | `ShipmentService.outbound` | definite | 15§2（发货提醒 → SMS） | 出库后发 SMS（best-effort，失败不影响主流程） |

### 事件失败落库（1 项，跨 6 监听器）

| # | 症状 | 位置 | 置信度 | 设计依据 | 修复 |
|---|------|------|--------|----------|------|
| 1 | 6 个跨模块监听器 catch 块只 `log.error` 吞异常、从不落库；`DomainEventPublisher.persistFailure` 仅对 `publish()` 的**同步**异常触发，而这些监听器均为 AFTER_COMMIT、在 `publish()` 返回后才执行，其失败永远到不了 `publish()` 的 catch → `GET /api/v1/admin/events/failures` 恒空 | `DomainEventPublisher` + inventory `PaymentSucceededInventoryListener`、logistics `OrderPaidEventListener`、loyalty `OrderPaidEventListener`/`ReviewApprovedEventListener`、order `ShipmentDeliveredEventListener`/`RefundCompletedEventListener` | definite | 03§8 item 2（监听器失败须「保存失败记录到本地事件处理表」）+ item 4（可经管理接口重放） | `DomainEventPublisher` 新增 public `recordListenerFailure`（`REQUIRES_NEW` 独立事务落 `FailedEventRecord`，标注来源监听器 + 错误，且**绝不外抛**——记录失败不得把已吞的监听器错误升级为硬错误）；6 监听器 catch 块经 `@Autowired(required=false)` 字段注入 + null 兜底上报（保留 8 个直接 `new` 构造的单测无需该协作者） |

**范围裁决（2 项明确排除）**：两个「纯发通知」监听器（order `OrderEventListener.onOrderCreated`、payment `PaymentSucceededNotificationListener`）**不纳入**——`LocalNotificationServiceImpl.send()` 内部自 catch 发送失败并经 `NotificationRecordService.recordFailure` 落库（03§7 item 4：通知组件自负「失败记录」），故这两个监听器对 `send()` 的调用永不外抛，给它们加监听器级 `FailedEventRecord` 既是死代码、又把「通知发送失败」错误归类到「事件监听失败」表。PUB-108 的 `logistics-create-shipment-failure` 路径仍返回支付 SUCCESS：失败记录写在独立 `REQUIRES_NEW` 事务，从不触及支付事务。

### 本轮明确不做（高危 / 已知弃项）

- **logistics `OrderLogisticsStatusUpdater` 生产实现**：本轮 logistics agent 再次以动态验证指出「生产入口无法独立启动」，但这正是 §7 已彻底放弃的项——冻结 `test-cases/BlackboxHarnessConfig` 注册了**无限定符**的该接口 no-op bean，加生产 bean 必与之冲突、**24 例全灭**；评分只经 harness（可用），从不独立启动生产入口，当前状态正确。
- **把库存扣减塞回支付确认事务**（跨领域 agent P1-6）：改事务边界高危，且 02§6 与 03§8 本身对「扣减是否属于确认事务」存在张力（当前经 `PaymentSucceededInventoryListener` 在 AFTER_COMMIT 扣减，happy-path 可观测行为正确），放弃。

### 已识别但未实施（供后续 / 用户裁决）

- **物流回调每次多写一条 `trackingNo=null` 冗余轨迹**（`updateStatus`→`recordTracking` 与 `LogisticsCallbackService` 手工插入重复）：中价值、中风险（改 `updateStatus` 签名）。
- 评价创建未交叉校验 `orderId` 归属（裸相等校验会误杀同商品多单评价，正确修法需 order 模块配合暴露订单明细）；product 详情缺 `skuList` / 创建接口返回 JPA 实体（附录A 未冻结创建响应体）；user 昵称登录（agent 自评低置信、反证充分）、会话过期硬编码 120、附录C 物理列名（黑盒不可观测）。

---

*验证结果：完整公开黑盒套件（`PubBasicFlowTest` PUB-001..016 + `PubAdditionalBehaviorTest` PUB-101..108，共 24 例）在清空上下文的重复独立运行下稳定 **24/24 全绿**（第一轮 6+ 次、第二/三轮每个批次提交前各 1 次，累计 17+ 次）。三轮全部改动已在作者侧通过端到端干跑验证：从未修复的原始工程出发，应用全部修复（166 处修改 + 37 处新增 + 13 处删除，零失败）→ 独立构建 → 黑盒 24/24 全绿，且修复应用过程验证过幂等（重复应用不产生任何额外改动）。各卡片「改法」里给出的目标代码即来自这份已验证的最终实现。*
