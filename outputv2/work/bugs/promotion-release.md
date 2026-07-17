# B05b · promotion-release — 券/秒杀释放与 order 侧取消接线（自 promotion.md 拆出的独立批次）

本文件是批次 **B05b**，含 3 张卡：PROMO-14（券释放）、PROMO-15（秒杀名额释放）、PROMO-16
（order 侧取消路径接线，内嵌 ORD-A17/ORD-A21 完整卡）。原属 B05（promotion.md），为控制单批
subagent 上下文体量而拆出——卡片编号与内容不变，其他文件对 PROMO-14/15/16 的引用仍然有效。

**执行前提（务必读完再动手）：**

1. 按 `work/bugs/README.md` 批次表，本文件在 **B05（promotion.md）之后**执行。**B05b 依赖 B05**：
   本批的释放逻辑建立在 B05 已落地的核销与购买留痕之上（PROMO-13 的 `markUsed(couponId, orderId,
   userId)` 写入券的 orderId、PROMO-8 的 `SeckillPurchaseRecord` 购买记录）——若 B05 被跳过，
   本批整体顺延，与 B05 一起在补救循环重开。
2. 本批涉及的 `OrderCancelService.java` / `OrderTimeoutService.java` 已被 **B03/B04（order.md）**
   改过：卡片「现状」以未修复基线为准、仅用于定位，真正改动以锚点文本（方法名/固定字符串）为准。
3. 三张卡**一次性全部改完后才 verify**——PROMO-16 调用 PROMO-14/15 新增的 `releaseForOrder`，
   只落一半必编译失败、黑盒 0/24。
4. 测试文件同步（`CouponServiceTest`/`SeckillServiceTest`/`OrderCancelServiceTest`/
   `OrderTimeoutServiceTest`）不计分但参与 test-compile，漏改则 `install` 失败。

---

### PROMO-14 | 订单取消后优惠券从不回退，USED 状态被已取消订单永久占用

- 风险: low · 置信度: definite
- **文件**:
  1. `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/repository/UserCouponRepository.java`
  2. `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/service/CouponService.java`
  3. （同步测试）`code/ecommerce-promotion/src/test/java/com/ecommerce/promotion/service/CouponServiceTest.java`
- **现状**: 基线 `UserCoupon` 实体本来就有消费记账字段（基线第 32-33 行
  `@Column(name = "used_order_id") private Long usedOrderId;` 与 `usedAt`）；PROMO-4/PROMO-13
  落地后，下单成功会经 `CouponService.markUsed(userCouponId, orderId, userId)` 把券置为
  `CouponStatus.USED` 并记录 `usedOrderId`。但**全仓库没有任何反向路径**（基线与 PROMO-1..13
  落地后都一样）：订单取消后（用户直接取消 CREATED/PAYING 单，或 PAID 单商家审核通过），券永远停在
  `USED`，`GET /api/v1/promotions/coupons/my` 里再也不可用——用户什么都没买成，券却被烧掉了。
  `UserCouponRepository`（基线 36 行，仅 `findByUserId`/`findByUserIdAndCouponCode`/
  `findByUserIdAndStatus`/`countByUserIdAndCouponTemplateId` 四个方法）也没有任何按
  `usedOrderId` 反查的入口。
- **期望**: 订单取消成功后，该订单核销的优惠券应回到可用状态（`USED` → `AVAILABLE`，清除
  `usedOrderId`/`usedAt`）。设计文档没有逐字写"退券"条款，最接近的一致性原则依据：
  design-docs/08 §6（取消规则表——CREATED 行"用户可直接取消，**释放库存**"：取消必须归还订单
  占用的资源，券与库存同理；PAID 行"审核通过后按退款流程处理"）；design-docs/10 §2（优惠券校验
  顺序第 6 条"是否已使用"——`USED` 的语义是"已被真实成交订单消费"，被已取消订单占住的 `USED`
  是伪状态，会让校验第 6 条给出错误答案）。来源：`findings.md`「已识别但因时间/风险预算未实施」
  条目"优惠券/秒杀名额在订单取消后从未释放（需要 promotion 侧新增 release 方法 + order 侧接线）"
  ——本卡即其中优惠券侧的 promotion 落地；秒杀侧见 PROMO-15，order 侧接线见 `order.md` ORD-A17
  （**与本卡同批应用**）。
- **改法**:
  1. **`UserCouponRepository.java`** 末尾（`countByUserIdAndCouponTemplateId` 之后）加一个反查方法：
     ```java
     /**
      * Find all coupons in a given status that were consumed by a given order,
      * used to give coupons back when that order is cancelled.
      */
     List<UserCoupon> findByStatusAndUsedOrderId(CouponStatus status, Long usedOrderId);
     ```
     （`List`/`CouponStatus` 的 import 基线已有，不用加。）
  2. **`CouponService.java`** 在 `markUsed(...)` 方法之后、私有 `generateCouponCode()` 之前，新增
     `markUsed` 的逆操作：
     ```java
     /**
      * Give back every coupon consumed by a cancelled order: each USED coupon
      * whose {@code usedOrderId} matches becomes AVAILABLE again, with the
      * consumption bookkeeping ({@code usedOrderId}/{@code usedAt}) cleared.
      * The inverse of {@link #markUsed}, called by the order module on the
      * successful-cancellation paths.
      *
      * <p>Deliberately a no-op for orders that consumed no coupon, and never
      * throws in normal operation — a release failure must not block the
      * cancellation itself. Whether the coupon is still inside its validity
      * window is not re-checked here: the validator enforces the template
      * window again at next use.
      */
     @Transactional
     public void releaseForOrder(Long orderId) {
         if (orderId == null) {
             return;
         }
         for (UserCoupon userCoupon
                 : userCouponRepository.findByStatusAndUsedOrderId(CouponStatus.USED, orderId)) {
             userCoupon.setStatus(CouponStatus.AVAILABLE);
             userCoupon.setUsedOrderId(null);
             userCoupon.setUsedAt(null);
             userCouponRepository.save(userCoupon);
         }
     }
     ```
     注意方法体里**没有任何 `orElseThrow`/主动抛异常**——"这个订单没用过券"就是合法的空遍历，
     这是设计出来的"永不抛错"语义（原因见「勿犯」）。
  3. **`CouponServiceTest.java`** 在 `MarkUsed` 嵌套类之后追加一组新用例（沿用同文件
     `userCouponCaptor` 捕获器）：
     ```java
     @Nested
     @DisplayName("releaseForOrder")
     class ReleaseForOrder {

         private final Long orderId = 900L;
         private UserCoupon usedCoupon;

         @BeforeEach
         void setUp() {
             usedCoupon = new UserCoupon();
             usedCoupon.setId(55L);
             usedCoupon.setUserId(42L);
             usedCoupon.setCouponTemplateId(1L);
             usedCoupon.setCouponCode("CPN-USED");
             usedCoupon.setStatus(CouponStatus.USED);
             usedCoupon.setUsedOrderId(orderId);
             usedCoupon.setUsedAt(LocalDateTime.of(2026, 1, 1, 12, 0));
         }

         @Test
         @DisplayName("releaseForOrder: puts the order's USED coupons back to AVAILABLE and clears usage bookkeeping")
         void testReleaseForOrder_restoresCoupon() {
             when(userCouponRepository.findByStatusAndUsedOrderId(CouponStatus.USED, orderId))
                     .thenReturn(java.util.List.of(usedCoupon));
             when(userCouponRepository.save(any(UserCoupon.class)))
                     .thenAnswer(invocation -> invocation.getArgument(0));

             couponService.releaseForOrder(orderId);

             verify(userCouponRepository).save(userCouponCaptor.capture());
             UserCoupon saved = userCouponCaptor.getValue();
             assertThat(saved.getStatus()).isEqualTo(CouponStatus.AVAILABLE);
             assertThat(saved.getUsedOrderId()).isNull();
             assertThat(saved.getUsedAt()).isNull();
         }

         @Test
         @DisplayName("releaseForOrder: is a no-op for an order that consumed no coupon")
         void testReleaseForOrder_noCoupons_noop() {
             when(userCouponRepository.findByStatusAndUsedOrderId(CouponStatus.USED, orderId))
                     .thenReturn(java.util.List.of());

             couponService.releaseForOrder(orderId);

             verify(userCouponRepository, never()).save(any(UserCoupon.class));
         }

         @Test
         @DisplayName("releaseForOrder: is a no-op for a null orderId")
         void testReleaseForOrder_nullOrderId_noop() {
             couponService.releaseForOrder(null);

             verify(userCouponRepository, never()).save(any(UserCoupon.class));
         }
     }
     ```
- **验收**:
  - 单测：`releaseForOrder(orderId)` 对 `status=USED && usedOrderId=orderId` 的券 → 置回
    `AVAILABLE` 且 `usedOrderId`/`usedAt` 清空；订单没用过券 → 一次 `save` 都不发生；
    `releaseForOrder(null)` → 纯 no-op、不查库。
  - 端到端（ORD-A17 接线后）：领券 → 用券下单（`discountAmount>0`，`coupons/my` 显示 `USED`）→
    `POST /api/v1/orders/{orderId}/cancel` → 再查 `GET /api/v1/promotions/coupons/my`，该券状态回到
    `AVAILABLE`，且可再次用于新订单正常抵扣。
  - 公开 24 例回归全绿（本卡为纯增量，不改任何既有方法的行为）。
- **勿犯**: 本卡是纯增量（新方法+新查询），**不要**动 `markUsed`/`claim`/`calculateDiscount` 的任何
  既有逻辑。不要在 `releaseForOrder` 里"顺手"校验有效期或把 `EXPIRED` 的券也重置——只回退
  `USED && usedOrderId` 匹配的券，过没过期交给下次使用时 `CouponValidator` 用模板时间窗判断。
  最重要的一条：**保持方法体"永不抛错"（没有任何 `orElseThrow`）**——它将被 ORD-A17 在订单取消的
  共享事务里调用，`CouponService` 是 `@Transactional` 代理 bean，若这里抛出 RuntimeException，
  即使调用方 catch 住，事务也已在代理边界被标记 rollback-only，整个取消请求会在提交时 500
  （机理同 PROMO-11 的事务毒化）。

---

### PROMO-15 | 订单取消后秒杀名额从不归还（购买记录缺 orderId，无从反查）

- 风险: high · 置信度: definite
- **文件**:
  1. `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/entity/SeckillPurchaseRecord.java`（PROMO-8 新增的实体，本卡加字段）
  2. `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/repository/SeckillPurchaseRecordRepository.java`（PROMO-8 新增，本卡加方法）
  3. `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/service/SeckillService.java`（`recordPurchase` 改签名 + 新增 `releaseForOrder`）
  4. `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderService.java`（Step 10b 调用点同步实参）
  5. （同步测试）`code/ecommerce-promotion/src/test/java/com/ecommerce/promotion/service/SeckillServiceTest.java`
- **现状**: 基线 `SeckillService.recordPurchase(Long activityId)`（基线第 80-87 行）只做
  `soldQuantity+1`，连购买记录都不存在；PROMO-8 落地后 `recordPurchase(activityId, userId, quantity)`
  会累加 `soldQuantity` 并写一条 `SeckillPurchaseRecord(activityId, userId, quantity)` 供限购判断
  累加。但记录上**没有 orderId**，且全仓库没有任何释放路径：订单取消后 `soldQuantity` 不回落、
  购买记录不删除——秒杀活动库存与该用户的限购额度被已取消的订单**永久占用**：活动名额白白流失，
  取消过秒杀单的用户自己也会因 `SECKILL_LIMIT_EXCEEDED` 无法再买。
- **期望**: 订单取消成功后归还其秒杀占用：活动 `soldQuantity` 回落该单购买量、删除该单的购买记录
  （同时恢复限购余量）。一致性原则依据同 PROMO-14（design-docs/08 §6 取消释放资源），另加
  design-docs/10 §4（秒杀校验第 3 条"用户未超过限购数量"、第 4 条"秒杀库存充足"——这两条消费的
  都应是**真实有效订单**的占用量，被取消订单不应继续计入）。来源：`findings.md`「已识别但因
  时间/风险预算未实施」同一条目的秒杀侧；order 侧接线见本文件 PROMO-16 内嵌的 ORD-A17（**与本卡同批应用**）。
- **改法**（在 PROMO-8/PROMO-11 已落地的文件状态上继续改）：
  1. **`SeckillPurchaseRecord.java`** 在 `userId` 字段之后、`quantity` 之前插入：
     ```java
     /**
      * The order that consumed this seckill allocation. Used to give the
      * allocation back (restore activity stock and per-user limit headroom)
      * when that order is cancelled.
      */
     @Column(name = "order_id")
     private Long orderId;
     ```
     并在 getter/setter 区补 `getOrderId()`/`setOrderId(Long orderId)`（体例同相邻字段）。列可空
     （历史行没有订单信息也不影响限购累加），Hibernate `ddl-auto` 自动补列，不需要手写 schema。
  2. **`SeckillPurchaseRecordRepository.java`** 在 `findByActivityIdAndUserId` 之后加：
     ```java
     /**
      * Find all purchase records consumed by a given order, used to give the
      * seckill allocation back when that order is cancelled.
      */
     List<SeckillPurchaseRecord> findByOrderId(Long orderId);
     ```
  3. **`SeckillService.java`** 把 `recordPurchase` 的签名从
     `recordPurchase(Long activityId, Long userId, Integer quantity)` 扩成
     **`recordPurchase(Long activityId, Long userId, Integer quantity, Long orderId)`**，方法体只
     多一行 `record.setOrderId(orderId);`（加在 `record.setUserId(userId);` 之后），javadoc 补
     `@param orderId` 说明；然后在 `recordPurchase` 之后新增逆操作：
     ```java
     /**
      * Give back the seckill allocation consumed by a cancelled order: for each
      * purchase record of that order, the activity's {@code soldQuantity} is
      * restored (floored at 0) and the record itself is deleted, so both the
      * activity stock and the user's per-user-limit headroom are returned.
      * The inverse of {@link #recordPurchase}, called by the order module on
      * the successful-cancellation paths.
      *
      * <p>Deliberately a no-op for orders without seckill items, and never
      * throws in normal operation — a release failure must not block the
      * cancellation itself (a vanished activity just skips the stock
      * restoration and still removes the stale record).
      */
     @Transactional
     public void releaseForOrder(Long orderId) {
         if (orderId == null) {
             return;
         }
         for (SeckillPurchaseRecord record : purchaseRecordRepository.findByOrderId(orderId)) {
             seckillRepository.findById(record.getActivityId()).ifPresent(activity -> {
                 int sold = activity.getSoldQuantity() != null ? activity.getSoldQuantity() : 0;
                 int quantity = record.getQuantity() != null ? record.getQuantity() : 0;
                 activity.setSoldQuantity(Math.max(0, sold - quantity));
                 seckillRepository.save(activity);
             });
             purchaseRecordRepository.delete(record);
         }
     }
     ```
  4. **`OrderService.java`** Step 10b 里唯一的调用点同步加实参（`orderId` 本来就在作用域内，
     PROMO-8 接线时定义的 `final Long orderId`）：
     ```java
     for (SeckillPurchase purchase : seckillPurchases) {
         seckillService.recordPurchase(purchase.activityId, userId, purchase.quantity, orderId);
     }
     ```
  5. **`SeckillServiceTest.java`** 同步：
     - 共享测试数据区（`USER_ID` 之后）加 `private static final Long ORDER_ID = 900L;`；
     - `RecordPurchase` 嵌套类里全部 5 处 `seckillService.recordPurchase(..., ...)` 调用统一追加
       第 4 实参 `ORDER_ID`；"persists a purchase record" 用例的断言区加一行
       `assertThat(saved.getOrderId()).isEqualTo(ORDER_ID);`；
     - 追加 `@Nested @DisplayName("releaseForOrder") class ReleaseForOrder`，fixture 为
       `record = new SeckillPurchaseRecord()`（`activityId=1L, userId=USER_ID, orderId=ORDER_ID,
       quantity=2`），四个用例：
       1) `soldQuantity=5` 时 release → 活动 save 后 `soldQuantity==3` 且
          `verify(purchaseRecordRepository).delete(record)`；
       2) `soldQuantity=1`、记录 quantity=2 → 回补下限兜底，`soldQuantity==0` 不为负；
       3) `findByOrderId` 返回空 → 不 save 活动、不 delete 记录（纯 no-op）；
       4) 活动已不存在（`seckillRepository.findById` 返回空）→ 不 save 活动但**仍然
          `delete(record)`**（清掉孤儿记录，恢复限购余量）。
- **验收**:
  - 单测：上述 `RecordPurchase`（含 orderId 断言）与 `ReleaseForOrder` 四用例全绿。
  - 端到端（ORD-A17 接线后）：创建秒杀活动（库存 N、限购 1）→ 用户秒杀下单成功（`soldQuantity`
    变 1）→ `POST /api/v1/orders/{orderId}/cancel` → `soldQuantity` 回落为 0，同一用户可再次
    秒杀下单成功（限购余量已恢复）；对无秒杀条目的订单取消行为完全不变。
  - 公开 24 例回归全绿。
- **勿犯**: `recordPurchase` 改签名后**必须一次改完全部调用点**——生产代码只有 `OrderService.java`
  Step 10b 一处（改法第 4 步），测试有 `SeckillServiceTest` 5 处（改法第 5 步）；漏任何一处
  `code/ecommerce-order` 或 `ecommerce-promotion` 编译不过，`mvn install -DskipTests` 整体失败、
  黑盒 0/24（后果同 PROMO-13「勿犯」所述）。`releaseForOrder` 里活动查不到时**不要抛
  `ResourceNotFoundException`**——用 `ifPresent` 跳过库存回补、仍删除记录（永不抛错的理由同
  PROMO-14「勿犯」：取消共享事务的 rollback-only 毒化）。`soldQuantity` 回补必须
  `Math.max(0, ...)` 兜底，不许出现负库存。不要动 `validateSeckill` 上 PROMO-11 加的
  `noRollbackFor` 注解。

### PROMO-16 | 券/秒杀释放的 order 侧接线（内嵌 ORD-A17 与 ORD-A21 完整卡，无需跨文件）

- 风险: low · 置信度: definite
- **本卡是本批的 order 侧接线**：PROMO-14/15 只提供了 promotion 侧的 `releaseForOrder(...)` 方法，
  真正让"订单取消 → 归还券与秒杀名额"生效的 order 侧接线由下面**两张完整卡**给出，
  已原样内嵌于本卡内 —— **不要去打开 `work/bugs/order.md`**（那个文件 70KB+、31 张卡，
  为这两张卡整体载入它会白白吃掉你的上下文；order.md 里这两张卡的原位只留了指向本卡的墓碑）：
  1. **`ORD-A17`**：给 `OrderCancelService` 注入两个 promotion 服务、三条取消成功路径调用
     `releasePromotions(orderId)`、同步 `OrderCancelServiceTest`；
  2. **`ORD-A21`**：同款接线的第四条路径（`OrderTimeoutService` 超时自动取消）、同步
     `OrderTimeoutServiceTest`。
  两张卡按批次表都属于 **本批（B05b）**——B03 执行 order.md 时按墓碑说明跳过它们，等的就是现在。
- **改法**: 依次逐字执行下面内嵌的 `ORD-A17`、`ORD-A21`（含各自的测试同步），与 PROMO-14/15
  同批一起 verify。
- **验收**:
  - `grep -n "releasePromotions" code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderCancelService.java`
    命中 ≥4 处（1 处方法定义 + 3 处调用点）；
  - `grep -n "releasePromotions" code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderTimeoutService.java`
    命中 ≥2 处（1 处方法定义 + 1 处调用点）。
- **勿犯**: 绝不能因为"这两张卡编号是 ORD-*"而跳过——本批的产物断言
  （artifacts.tsv B05b 的两条 `releasePromotions` 行）会核验它们，缺了整批按未完成处理。ORD-A21
  只做券/秒杀释放：积分退还是 B15 的 `loyalty.md` LOY-12（经 order.md ORD-A22 指针），本批
  loyalty 侧方法还不存在，谁在本批接线谁编译失败。

#### ORD-A17 | 订单取消成功路径只释放库存，从不归还优惠券/秒杀名额（接线卡）

- 风险: low · 置信度: definite
- **执行时机（先读这条再动手）**: 本卡调用的 `couponService.releaseForOrder(...)` /
  `seckillService.releaseForOrder(...)` 是本文件 PROMO-14/PROMO-15（批次 B05b，与本卡同批）新增的方法。
  按批次表顺序（B03 早于 B05b）执行到 order.md 时**这两个方法还不存在，先跳过本卡**，等执行 B05b 批次时
  把本卡与 PROMO-14/15 **同批一起落地、一起 verify**（若 B03 阶段就单独应用本卡，
  `ecommerce-order` 编译不过、`mvn install -DskipTests` 失败，黑盒 0/24）。本卡编号留在 §A 只因
  它改的是 order 模块文件；其产物断言在 `artifacts.tsv` 里也登记为 B05b。
- **文件**:
  1. `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderCancelService.java`
  2. （同步测试）`code/ecommerce-order/src/test/java/com/ecommerce/order/service/OrderCancelServiceTest.java`
- **现状**: 基线 `OrderCancelService` 的取消成功路径——`cancelCreatedOrder(...)`（基线第 110 行起，
  内有 `inventoryReservationService.release(order.getId())`）、`cancelPayingOrder(...)`（基线第
  143 行起）、`reviewCancel(...)` 审核通过分支（基线第 201 行起，内有
  `inventoryReservationService.release(orderId)`）——只释放**库存**，从不通知 promotion 模块归还
  券/秒杀名额；构造函数注入的 5 个协作者里没有任何 promotion 服务。ORD-A5/ORD-A7 落地后该文件的
  PAID 分支改走 `requestPaidOrderCancelReview`（只进 `CANCEL_REVIEWING`，不释放任何资源——那是
  对的，本卡不碰它）、5 处状态冲突换成了 `ConflictException`，但三条成功路径依旧没有券/名额释放。
  于是（配合 PROMO-4/8/13 的消费侧）出现单向棘轮：下单即消费券和秒杀名额，取消却永不归还。
- **期望**: 每条**真正到达 `CANCELLED`** 的路径（CREATED 直接取消、PAYING 取消、CANCEL_REVIEWING
  审核通过）都调用 PROMO-14/15 的 `releaseForOrder(orderId)` 归还券与秒杀名额；释放是 best-effort
  ——失败只记日志，绝不阻断取消本身（与同方法里既有的库存释放 try/catch 模式一致；精神同
  design-docs/03 §8"监听器失败……不得回滚主事务"）。依据: design-docs/08 §6（取消规则表：取消
  须释放订单占用的资源）+ PROMO-14/15 卡「期望」引用的 10 §2/§4 条款。来源：`findings.md`
  「已识别但因时间/风险预算未实施」条目"优惠券/秒杀名额在订单取消后从未释放"的 order 侧接线。
- **改法**:
  1. 加 import（order 模块 pom 已依赖 ecommerce-promotion，`OrderService` 里早有同款注入，
     不需要动任何 pom）：
     ```java
     import com.ecommerce.promotion.service.CouponService;
     import com.ecommerce.promotion.service.SeckillService;
     ```
  2. 构造注入两个 promotion 领域服务（字段区加两个 `private final`，构造函数参数列表末尾追加
     `CouponService couponService, SeckillService seckillService` 并赋值——增量追加，别整段替换
     覆盖既有参数）。
  3. 类末尾（`reviewCancel` 之后）新增私有帮助方法，两段**独立** try/catch：
     ```java
     /**
      * Give back the coupons and the seckill allocation consumed by an order
      * once its cancellation has succeeded (mirrors the consumption side,
      * {@code OrderService} Step 10b). Both calls are best-effort: a release
      * failure is logged and swallowed — it must never block the cancellation
      * itself (design-docs/03: post-actions must not fail the main flow),
      * exactly like the inventory release above. Only invoked on paths that
      * actually reach CANCELLED — a PAID order entering CANCEL_REVIEWING keeps
      * its coupons/allocation until the review is approved.
      */
     private void releasePromotions(Long orderId) {
         try {
             couponService.releaseForOrder(orderId);
         } catch (Exception e) {
             log.warn("Failed to release coupons for cancelled order {}: {}", orderId, e.getMessage());
         }
         try {
             seckillService.releaseForOrder(orderId);
         } catch (Exception e) {
             log.warn("Failed to release seckill allocation for cancelled order {}: {}",
                     orderId, e.getMessage());
         }
     }
     ```
  4. 三个调用点（都在订单已持久化为目标状态之后）：
     - `cancelCreatedOrder(...)`：库存释放 try/catch 之后、`orderService.recordEvent(...)` 之前，加
       ```java
       // Give back coupons and seckill allocation consumed by this order
       releasePromotions(order.getId());
       ```
     - `cancelPayingOrder(...)`：`orderRepository.save(order)` 之后、`recordEvent` 之前，加（**此路径三判最易被漏，勿用"同上"略写，必须贴字面代码**）：
       ```java
       // Give back coupons and seckill allocation consumed by this order
       releasePromotions(order.getId());
       ```
     - `reviewCancel(...)` 的 `approved` 分支：库存释放 try/catch 之后、`recordEvent` 之前，加
       `releasePromotions(orderId);`（形参本来就叫 `orderId`）。
     `requestPaidOrderCancelReview` 与 `reviewCancel` 的驳回分支**不加**。
     **落地自检**：`grep -c "releasePromotions(" OrderCancelService.java` 必须 == 4（1 处方法定义
     + 3 处调用 cancelCreatedOrder/cancelPayingOrder/reviewCancel-approved）；< 4 说明漏了路径，补齐再 verify。
  5. **`OrderCancelServiceTest.java`** 同步：
     - 加 import `com.ecommerce.promotion.service.CouponService`/`SeckillService` 与
       `static org.mockito.Mockito.doThrow`；`@Mock` 字段区加
       `@Mock private CouponService couponService;`、`@Mock private SeckillService seckillService;`
       （`@InjectMocks` 构造注入自动接上，缺了这两个 mock 会注入 null）；
     - 既有 `testCancel_paidOrder_movesToCancelReviewing` 末尾加
       `verify(couponService, never()).releaseForOrder(anyLong());` 与 seckill 同款断言
       （审核前不许释放）；既有 `testReviewCancel_approve` 末尾加
       `verify(couponService).releaseForOrder(10L);`、`verify(seckillService).releaseForOrder(10L);`；
     - 新增三个用例：CREATED 取消 → 两个 `releaseForOrder(1L)` 各被调用一次；PAYING 取消（内联
       fixture，`status=PAYING`）→ 响应 `CANCELLED` 且两个 `releaseForOrder(5L)` 被调用；
       `doThrow(new RuntimeException("release boom")).when(couponService).releaseForOrder(1L)` 时
       取消 CREATED 单**仍然成功**（响应 `CANCELLED`），且 `verify(seckillService).releaseForOrder(1L)`
       （前一段失败不影响后一段）。
- **验收**:
  - 单测：`OrderCancelServiceTest` 全绿，覆盖"三条成功路径都释放、CANCEL_REVIEWING 阶段不释放、
    释放失败不阻断取消"。
  - 端到端：见 PROMO-14/15 的端到端验收（券回 `AVAILABLE`、`soldQuantity` 回落）；对 PAID 单仅发起
    取消申请（进入 `CANCEL_REVIEWING`）后查券，状态仍是 `USED`；管理员审核**驳回**后券仍是 `USED`
    （订单回到 PAID，资源保留）。
  - 公开 24 例回归全绿。
- **勿犯**: 不要在 `requestPaidOrderCancelReview`（PAID→CANCEL_REVIEWING）里释放——券/名额和库存
  一样要等审核通过才归还，驳回时订单回到 PAID、资源必须原样保留（ORD-A5「勿犯」的镜像）。不要把
  `releasePromotions` 的 try/catch 去掉或把异常往外抛——释放失败只 `log.warn`，绝不能让取消接口
  500。不要把两段 try/catch 合并成一段——券释放失败不应连累秒杀释放。超时自动取消路径**不在本卡范围**（本卡只覆盖
  `OrderCancelService` 的三条路径）——`OrderTimeoutService` 的同款释放由后补的 **ORD-A21** 单独
  落卡（与本卡同批 B05b 执行，见该卡），不要在本卡里顺手改它；`OrderLifecycleService` 依旧是
  头部红线里的死服务，任何卡都不得接线。

#### ORD-A21 | 超时取消只释放库存，从不归还优惠券/秒杀名额（接线卡）

- 风险: low · 置信度: definite
- **执行时机（先读这条再动手）**: 同 ORD-A17——本卡调用的 `couponService.releaseForOrder(...)` /
  `seckillService.releaseForOrder(...)` 是本文件 PROMO-14/PROMO-15（批次 B05b，与本卡同批）新增的方法。
  按批次表顺序（B03 早于 B05b）执行到 order.md 时**这两个方法还不存在，先跳过本卡**，等执行 B05b 批次时
  经 PROMO-16 指针把本卡与 ORD-A17、PROMO-14/15 **同批一起落地、一起 verify**（若 B03 阶段就单独
  应用本卡，`ecommerce-order` 编译不过、黑盒 0/24）。本卡编号留在 §A 只因它改的是 order 模块文件；
  其产物断言在 `artifacts.tsv` 里也登记为 B05b。
- **文件**:
  1. `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderTimeoutService.java`
  2. （同步测试）`code/ecommerce-order/src/test/java/com/ecommerce/order/service/OrderTimeoutServiceTest.java`
- **现状**: ORD-A10 落地后 `OrderTimeoutService.cancelExpiredOrder(...)` 已经会
  `inventoryReservationService.release(order.getId())` 释放预占库存，但与 ORD-A17 修复前的
  `OrderCancelService` 一样从不通知 promotion 模块。超时取消是**第四条真正到达 CANCELLED 的路径**
  （前三条见 ORD-A17），漏掉它就是资源单向棘轮的最后一个缺口：用户下单占住券/秒杀名额后弃单不付，
  60 分钟后系统自动取消，库存回来了，券和名额永远回不来。
- **期望**: 超时取消与用户取消同样归还订单占用的资源。依据: design-docs/08 §5（超时"系统自动取消
  订单并释放预占库存"）+ 08 §6 取消释放资源原则 + PROMO-14/15「期望」引用的 10 §2/§4 条款（与
  ORD-A17 完全同源）。释放 best-effort：失败只记日志，绝不阻断取消本身。
- **改法**:
  1. 加 import（order 模块 pom 已依赖 ecommerce-promotion，不用动 pom）：
     ```java
     import com.ecommerce.promotion.service.CouponService;
     import com.ecommerce.promotion.service.SeckillService;
     ```
  2. 字段区加两个 `private final`（`CouponService couponService;`、`SeckillService seckillService;`），
     构造函数参数列表末尾**增量追加**同名参数并赋值——别整段替换覆盖既有参数。
  3. `cancelExpiredOrder(...)` 里，`inventoryReservationService.release(order.getId());` 之后、
     `orderService.recordEvent(...)` 之前，插入：
     ```java
     // Give back coupons and seckill allocation consumed by this order —
     // a timeout cancellation returns the order's resources exactly like a
     // user-requested cancellation (OrderCancelService) does.
     releasePromotions(order.getId());
     ```
  4. 类末尾新增私有帮助方法（与 ORD-A17 的同名方法仅 javadoc/日志文案不同，两段**独立** try/catch）：
     ```java
     /**
      * Give back the coupons and the seckill allocation consumed by an expired
      * order once its timeout cancellation has succeeded (mirrors the
      * consumption side, {@code OrderService} Step 10b, and the same helper in
      * {@code OrderCancelService}). Both calls are best-effort: a release
      * failure is logged and swallowed — it must never block the cancellation
      * itself (design-docs/03: post-actions must not fail the main flow).
      */
     private void releasePromotions(Long orderId) {
         try {
             couponService.releaseForOrder(orderId);
         } catch (Exception e) {
             log.warn("Failed to release coupons for expired order {}: {}", orderId, e.getMessage());
         }
         try {
             seckillService.releaseForOrder(orderId);
         } catch (Exception e) {
             log.warn("Failed to release seckill allocation for expired order {}: {}",
                     orderId, e.getMessage());
         }
     }
     ```
  5. **`OrderTimeoutServiceTest.java`** 同步：
     - 加 import `com.ecommerce.promotion.service.CouponService`/`SeckillService` 与
       `static org.mockito.Mockito.doThrow`；`@Mock` 字段区加
       `@Mock private CouponService couponService;`、`@Mock private SeckillService seckillService;`
       （`@InjectMocks` 构造注入自动接上；缺了这两个 mock 会注入 `null`，helper 里的 NPE 会被
       try/catch 吞掉，测试静默变弱）。
     - 新增两个用例（B15 的 LOY-12 之后会把它们扩成含积分退还断言的终态，见该卡；本批先按下面写）：
       ```java
       @Test
       @DisplayName("timeout gives back coupons and seckill allocation")
       void testCancelExpiredOrder_releasesPromotionsAndRefundsPoints() {
           orderTimeoutService.cancelExpiredOrder(expiredOrder);

           verify(couponService).releaseForOrder(1L);
           verify(seckillService).releaseForOrder(1L);
       }

       @Test
       @DisplayName("timeout release failures are swallowed and never block the cancellation")
       void testCancelExpiredOrder_releaseFailureDoesNotBlockCancel() {
           doThrow(new RuntimeException("release boom")).when(couponService).releaseForOrder(1L);

           orderTimeoutService.cancelExpiredOrder(expiredOrder);

           assertThat(expiredOrder.getStatus()).isEqualTo(OrderStatus.CANCELLED);
           verify(seckillService).releaseForOrder(1L);
           verify(orderService).recordEvent(eq(1L), eq(OrderStatus.CREATED), eq(OrderStatus.CANCELLED),
                   eq("TIMEOUT_CANCEL"), eq("SYSTEM"), anyString());
           verify(eventPublisher).publish(any(com.ecommerce.order.event.OrderCancelledEvent.class));
       }
       ```
- **验收**:
  - 单测：`OrderTimeoutServiceTest` 全绿——超时取消调用两个 `releaseForOrder(1L)`；券释放抛异常时
    取消仍完成（状态 CANCELLED、事件照记照发、秒杀释放照跑）。
  - `grep -n "releasePromotions" OrderTimeoutService.java` 命中 ≥2 处（1 定义 + 1 调用）。
  - 端到端：用券+秒杀下单后不支付，`POST /api/v1/admin/orders/timeout-cancel`（时钟拨过期后）触发
    超时取消 → 券回 `AVAILABLE`、`soldQuantity` 回落（同 PROMO-14/15 的端到端验收）。
  - 公开 24 例回归全绿。
- **勿犯**: 不要把 try/catch 去掉或把异常往外抛——`cancelExpiredOrders` 的循环虽有外层 catch，但
  释放失败若中断本方法，事件记录/发布会被跳过。不要把两段 try/catch 合并成一段——券释放失败不应
  连累秒杀释放。**只做券/秒杀释放**：积分退还的两行是 B15 `loyalty.md` LOY-12 的事（本批 loyalty
  侧 `refundPointsForOrder` 还不存在，现在接线必编译失败）。照旧不得接线 `OrderLifecycleService`
  等头部红线死服务。

---

