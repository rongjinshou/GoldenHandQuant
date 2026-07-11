# B05 · promotion — 优惠计算 / 秒杀 / 券核销

本卡片文件覆盖 `findings.md` 中 promotion 模块（§6.4，10 项）全部条目，加上三张跨领域/深审卡：
`BUG-INT-2`（秒杀事务毒化，高危）、第三轮深审·模块内 #11（重复 couponId 双重计算）、
第三轮深审·跨领域 #1（`markUsed` 缺归属校验）。共 **13 张卡**，编号 PROMO-1 … PROMO-13。

**执行前提（务必读完再动手）：**

1. 按 `work/bugs/README.md` 的批次表，本文件是 **B05**，在 **B03/B04（`order.md`，订单核心/订单定价）之后**执行。
   这意味着当你改到本文件里涉及 `code/ecommerce-order/.../OrderService.java` 的卡片
   （PROMO-4 / PROMO-8 / PROMO-11 / PROMO-13）时，该文件大概率**已经被 order.md 的卡片改过**
   （新增了 Step 0 幂等去重、Step 1 冻结校验、Step 4 风控调用、按 `addressId` 查地址等）。
   **本文件给出的「现状」代码片段和行号以未修复的原始代码为准，仅用于定位逻辑、不保证
   逐字节吻合当前文件**——真正改动请以下方给出的**锚点文本**（方法名/变量名/固定字符串）为准，
   而不是行号。行号只作定位参考。
2. 本文件内部的卡片**按编号顺序（PROMO-1→PROMO-13）依赖**：多张卡改同一个方法（尤其
   `PromotionCalculationService.calculate()`/`calculateCouponDiscount()` 被 PROMO-2/3/5/7/12 五张卡
   接力修改，`OrderService.createOrder()` 被 PROMO-4/8/11/13 接力修改）。**必须按编号顺序应用**，
   每张卡的「现状」都是"前面编号的卡已生效"这个前提下写的，不要跳着改。
3. 多张卡会改到**已存在的单元测试文件**（`code/` 下 JUnit，不计分但会参与
   `mvn -f code/pom.xml install -DskipTests` 的 test-compile 阶段——**编译不过会导致该步骤失败，
   进而无法 `install` 到本地仓库，黑盒测试将 0/24**）。凡是改了生产代码方法签名的卡，都在
   「改法」里列出了必须同步改的测试文件调用点，不要漏。
4. **本批 13 张卡必须一次性全部改完后才 verify——严禁批中 verify**：PROMO-8 落地而 PROMO-11 未
   落地的中间态会让全部普通下单请求 500（秒杀探测异常把共享事务标记 rollback-only，机理见
   PROMO-11），此时 verify 必然大幅回归回滚。
5. 公开用例 pub101（券折扣计算）的主责卡是 PROMO-1——若最终公开回归里 pub101 仍失败，优先复查
   PROMO-1 是否漏改/改偏（该卡「验收」末条即 pub101 的具体断言场景）。

---

### PROMO-1 | DISCOUNT 类型优惠券折扣公式反了（PUB-101）

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/service/CouponService.java`
- **现状**: `calculateDiscount(BigDecimal price, CouponTemplate coupon)` 方法（基线约第 78-121 行）的
  `DISCOUNT` 分支（约第 84-93 行）：
  ```java
  case DISCOUNT:
      BigDecimal rate = BigDecimal.ONE.subtract(coupon.getDiscountValue());
      BigDecimal afterDiscount = MonetaryUtil.multiply(price, rate);
      if (coupon.getMaxDiscount() != null) {
          BigDecimal rawDiscount = MonetaryUtil.subtract(price, afterDiscount);
          if (rawDiscount.compareTo(coupon.getMaxDiscount()) > 0) {
              return coupon.getMaxDiscount();
          }
      }
      return MonetaryUtil.subtract(price, afterDiscount);
  ```
  变量名 `afterDiscount` 起错了——它实际存的是 `price × (1 - discountValue)`，这按设计文档的公式
  **本身就是优惠金额**，不是"折后价"。但代码把它当"折后价"用，又做了一次
  `price - afterDiscount`，相当于把"用户该付多少钱"当成"优惠了多少钱"返回。`maxDiscount` 封顶分支
  同理：拿去跟 `maxDiscount` 比较的 `rawDiscount = price - afterDiscount` 也是错的对象。
  结果：8 折券（`discountValue=0.8`）在 100.00 元商品上，`calculateDiscount` 返回 **80.00**
  （该返回 20.00），PUB-101 断言 `discountAmount == 20.00` 会失败。
- **期望**: `design-docs/10-促销服务设计.md` §2：
  ```text
  折后价 = 原价 × discountValue
  优惠金额 = 原价 × (1 - discountValue)
  ```
  示例（文档原文）：8 折券，原价 100 → 优惠金额 = 100 × (1 - 0.8) = 20。`calculateDiscount` 这个方法
  返回的是**优惠金额**（供 `PromotionCalculateResponse.couponDiscount`/`Order.discountAmount` 使用），
  不是折后价。依据: 10§2、PUB-101。
- **改法**: 把 DISCOUNT 分支整体替换为：
  ```java
  case DISCOUNT:
      // discountAmount = price * (1 - discountValue), per design-docs/10 §2.
      // e.g. an 80%-price ("8折") coupon on 100.00 yields a 20.00 discount.
      BigDecimal discountRate = BigDecimal.ONE.subtract(coupon.getDiscountValue());
      BigDecimal discountAmount = MonetaryUtil.multiply(price, discountRate);
      if (coupon.getMaxDiscount() != null && discountAmount.compareTo(coupon.getMaxDiscount()) > 0) {
          return coupon.getMaxDiscount();
      }
      return discountAmount;
  ```
  即：不再对 `discountAmount` 做二次 `price - x` 减法，算出来的折扣金额直接（或按 `maxDiscount`
  封顶后）返回。`AMOUNT_OFF`/`THRESHOLD_OFF` 两个分支不动。只改这一个文件。
- **验收**:
  - `calculateDiscount(new BigDecimal("100.00"), coupon{type=DISCOUNT, discountValue=0.8})`
    == `20.00`（不是 `80.00`）。
  - 同上但 `maxDiscount=10.00` → 结果被封顶为 `10.00`（原始折扣 20.00 > 封顶 10.00）。
  - 同上但 `maxDiscount=90.00` → 不封顶，结果仍是 `20.00`（原始折扣 20.00 < 封顶 90.00）。
  - PUB-101（`pub101_couponDiscountShouldBeCorrect`）：100.00 元商品 + 8 折券 + 关闭会员折扣
    （`member.discount-rate=1.0`）下单，`discountAmount` 断言为 `20.00`。

---

### PROMO-2 | 优惠叠加顺序反了（应 满减→券→会员，实际 会员→满减→券）

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/service/PromotionCalculationService.java`
- **现状**: `calculate(PromotionCalculateRequest request)` 方法（基线第 46-73 行左右）执行顺序是
  **会员折扣（第一步，直接作用于 `itemTotal`）→ 满减（作用于会员折后金额）→ 优惠券（作用于满减后金额）**：
  ```java
  BigDecimal itemTotal = computeItemTotal(request.getItems());
  BigDecimal memberDiscount = calculateMemberDiscount(request.getUserId(), itemTotal);
  BigDecimal afterMember = MonetaryUtil.subtract(itemTotal, memberDiscount);
  BigDecimal fullReductionDiscount =
          fullReductionService.calculateBestReduction(afterMember).orElse(BigDecimal.ZERO);
  BigDecimal afterFullReduction = MonetaryUtil.subtract(afterMember, fullReductionDiscount);
  BigDecimal couponDiscount = calculateCouponDiscount(request.getUserId(),
          request.getCouponIds(), afterFullReduction);
  ```
  与设计文档规定的顺序完全相反。
- **期望**: `design-docs/10` §3：
  ```text
  优惠叠加顺序固定为：满减活动 → 优惠券折扣 → 会员专属折扣
  后一步基于前一步的结果计算。
  ```
  文档给的验证例子：`商品金额 300 → 满减 -30 后为 270 → 8 折优惠券后为 216 → 会员 95 折后为 205.20`。
- **改法**: 把 `calculate()` 方法体（从 `BigDecimal itemTotal = computeItemTotal(...)` 到
  `finalAmount` clamp 之前）替换为：
  ```java
  BigDecimal itemTotal = computeItemTotal(request.getItems());

  // Stacking order per design-docs/10 §3: full-reduction → coupon → member,
  // each step applied to the result of the previous one.

  // Step 1: full reduction, based on the raw item total.
  BigDecimal fullReductionDiscount =
          fullReductionService.calculateBestReduction(itemTotal)
                  .orElse(BigDecimal.ZERO);
  BigDecimal afterFullReduction = MonetaryUtil.subtract(itemTotal, fullReductionDiscount);

  // Step 2: coupon discount, based on the full-reduction result.
  BigDecimal couponDiscount = calculateCouponDiscount(request.getUserId(),
          request.getCouponIds(), afterFullReduction);
  BigDecimal afterCoupon = MonetaryUtil.subtract(afterFullReduction, couponDiscount);

  // Step 3: member discount, applied last, based on the coupon result.
  BigDecimal memberDiscount = calculateMemberDiscount(request.getUserId(), afterCoupon);

  BigDecimal totalDiscount = MonetaryUtil.add(
          MonetaryUtil.add(memberDiscount, fullReductionDiscount), couponDiscount);
  BigDecimal finalAmount = MonetaryUtil.subtract(itemTotal, totalDiscount);
  ```
  紧接着原有的 `if (finalAmount.compareTo(BigDecimal.ZERO) < 0) { finalAmount = BigDecimal.ZERO; }`
  以及构造 `response` 的代码**保持不动**（`totalDiscount` 的封顶问题由 PROMO-7 单独处理，本卡先只管顺序）。
  `calculateCouponDiscount(...)` 调用本卡先保持基线的 3 参数签名不变（`userId, couponIds, currentAmount`）
  ——第 4 个参数 `skuIds` 由 PROMO-3 引入，此处不要提前加。
- **验收**（用 `design-docs/10` 原例回归）:
  - 输入：单条目 `price=300.00, quantity=1`；满减命中 `-30.00`；8 折券（`discountValue=0.8`）；
    `member.discount-rate=0.95`（默认值）。
  - 期望：`fullReductionDiscount=30.00`（作用于 300 得 270）→
    `couponDiscount=54.00`（270×0.2，作用得 216）→
    `memberDiscount=10.80`（216×0.05，作用得 205.20）→ `finalAmount=205.20`。
  - 第二组回归（单测里更常见的数字）：`price=100.00`，满减 `-10.00`→90；8 折券折扣 `18.00`→72；
    会员折扣 `3.60`→`finalAmount=68.40`，`totalDiscount=31.60`。

---

### PROMO-3 | 优惠券校验形同虚设：过期/门槛/适用性/已用全未检查

- 风险: high · 置信度: definite
- **文件**:
  1. `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/service/CouponValidator.java`（主改动）
  2. `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/service/PromotionCalculationService.java`（配合改调用点，**依赖 PROMO-2 已应用**）
  3. `code/ecommerce-promotion/src/test/java/com/ecommerce/promotion/service/CouponValidatorTest.java`（配合改，否则编译不过）
- **现状**:
  - `CouponValidator.validate(UserCoupon userCoupon)`（基线全文，第 32-39 行）：
    ```java
    public void validate(UserCoupon userCoupon) {
        if (userCoupon == null) {
            throw new BusinessException("COUPON_INVALID", "Coupon not found");
        }
        CouponTemplate template = couponTemplateRepository.findById(userCoupon.getCouponTemplateId())
                .orElseThrow(() -> new ResourceNotFoundException("CouponTemplate not found"));
    }
    ```
    只做了"券模板存在"检查，`template` 查出来后**完全没被使用**。有效期、消费门槛、商品适用范围、
    是否已使用——一概不查。README §7 冻结错误码 `COUPON_EXPIRED` 因此在全仓库从未被抛出。
  - 调用方 `PromotionCalculationService.calculateCouponDiscount(...)`（PROMO-2 改完后的版本）里是
    `couponValidator.validate(userCoupon);`（1 参数）。
- **期望**: `design-docs/10` §2 优惠券校验顺序：
  ```text
  1. 优惠券是否存在   2. 是否在有效期内   3. 是否满足使用门槛
  4. 是否适用于当前商品   5. 用户是否满足使用限制   6. 是否已使用
  ```
  第 5 步"用户使用限制"（每人限领 `perUserLimit`）已经在 `CouponService.claim()` 领券时校验过
  （`COUPON_LIMIT_EXCEEDED`），本方法只负责**用券时**还需要的 4 项：有效期、门槛、适用商品、已用状态，
  依据: 10§2、README §7（`COUPON_EXPIRED`/400）。
- **改法**:
  1. `CouponValidator` 构造函数新增 `ObjectMapper objectMapper` 依赖（Spring 已有默认 `ObjectMapper` bean，
     `FullReductionService` 已经这么用，直接照抄即可）：
     ```java
     private final CouponTemplateRepository couponTemplateRepository;
     private final UserCouponRepository userCouponRepository;
     private final ObjectMapper objectMapper;

     public CouponValidator(CouponTemplateRepository couponTemplateRepository,
                             UserCouponRepository userCouponRepository,
                             ObjectMapper objectMapper) {
         this.couponTemplateRepository = couponTemplateRepository;
         this.userCouponRepository = userCouponRepository;
         this.objectMapper = objectMapper;
     }
     ```
  2. `validate` 方法改签名为 `(UserCoupon userCoupon, BigDecimal orderAmount, List<Long> skuIds)`，实现：
     ```java
     public void validate(UserCoupon userCoupon, BigDecimal orderAmount, List<Long> skuIds) {
         if (userCoupon == null) {
             throw new ResourceNotFoundException("Coupon not found");
         }
         CouponTemplate template = couponTemplateRepository.findById(userCoupon.getCouponTemplateId())
                 .orElseThrow(() -> new ResourceNotFoundException("CouponTemplate", userCoupon.getCouponTemplateId()));

         LocalDateTime now = SystemClockService.now();
         if ((template.getStartTime() != null && now.isBefore(template.getStartTime()))
                 || (template.getEndTime() != null && now.isAfter(template.getEndTime()))) {
             throw new BusinessException("COUPON_EXPIRED", "Coupon is not within its valid time window");
         }
         if (template.getThresholdAmount() != null
                 && (orderAmount == null || orderAmount.compareTo(template.getThresholdAmount()) < 0)) {
             throw new BusinessException("COUPON_THRESHOLD_NOT_MET", "Order amount below coupon threshold");
         }
         if (!isApplicableToSkus(template, skuIds)) {
             throw new BusinessException("COUPON_NOT_APPLICABLE", "Coupon does not apply to the purchased items");
         }
         if (userCoupon.getStatus() != CouponStatus.AVAILABLE) {
             throw new BusinessException("COUPON_ALREADY_USED", "Coupon has already been used or is unavailable");
         }
     }

     private boolean isApplicableToSkus(CouponTemplate template, List<Long> skuIds) {
         String json = template.getApplicableProductIds();
         if (json == null || json.isBlank()) {
             return true; // no restriction configured
         }
         List<Long> applicableIds = parseIds(json);
         if (applicableIds == null || applicableIds.isEmpty()) {
             return true;
         }
         return skuIds != null && skuIds.stream().anyMatch(applicableIds::contains);
     }

     private List<Long> parseIds(String json) {
         try {
             return objectMapper.readValue(json, new TypeReference<List<Long>>() {});
         } catch (JsonProcessingException e) {
             return null; // fail open rather than blocking checkout on a data-quality issue
         }
     }
     ```
     需要的新 import：`com.ecommerce.common.test.SystemClockService`、`com.ecommerce.promotion.entity.CouponStatus`、
     `com.fasterxml.jackson.core.JsonProcessingException`、`com.fasterxml.jackson.core.type.TypeReference`、
     `com.fasterxml.jackson.databind.ObjectMapper`、`java.time.LocalDateTime`。
     `CouponTemplate.getApplicableProductIds()`/`setApplicableProductIds()` 已经存在于实体上
     （`applicable_product_ids` 列），不需要改实体。
  3. **配合改 `PromotionCalculationService`**（依赖 PROMO-2）：
     - `calculate()` 里 `computeItemTotal` 之后新增一行：`List<Long> skuIds = computeSkuIds(request.getItems());`，
       并把 `calculateCouponDiscount(request.getUserId(), request.getCouponIds(), afterFullReduction)`
       改为 `calculateCouponDiscount(request.getUserId(), request.getCouponIds(), afterFullReduction, skuIds)`。
     - 新增私有方法：
       ```java
       private List<Long> computeSkuIds(List<PromotionCalculateRequest.CalculateItem> items) {
           if (items == null) {
               return List.of();
           }
           return items.stream()
                   .map(PromotionCalculateRequest.CalculateItem::getSkuId)
                   .collect(Collectors.toList());
       }
       ```
       需要新增 `import java.util.stream.Collectors;`（基线没有这个 import）。
     - `calculateCouponDiscount(...)` 方法签名加第 4 个参数 `List<Long> skuIds`，方法体内把
       `couponValidator.validate(userCoupon);` 改为 `couponValidator.validate(userCoupon, currentAmount, skuIds);`。
       其余逻辑不动（归属校验是 PROMO-5 的事，去重是 PROMO-12 的事，这两张卡都在本卡之后）。
  4. **配合改测试 `CouponValidatorTest.java`**（否则 `mvn -f code/pom.xml install -DskipTests` 会在
     test-compile 阶段直接失败，黑盒 0/24）：
     - 类里新增一个 mock 字段：`@Spy private ObjectMapper objectMapper = new ObjectMapper();`
       （用 `@Spy` 装真实实例，而不是 `@Mock`——这样如果某个用例真的走到 JSON 解析分支也不会因为
       mock 返回 null 而炸；本卡改动的 6 个基线用例都不会走到该分支，用 `@Mock` 理论上也行，
       `@Spy` 更保险）。
     - 全文件把所有 `couponValidator.validate(xxxCoupon)`（共 6 处：
       `testValidate_existingCoupon_returnsTrue`、`testValidate_nonExistentCoupon_returnsFalse`、
       `testValidate_expiredCoupon_throwsCouponExpired`、`testValidate_usedCoupon_throwsCouponAlreadyUsed`、
       `testValidate_nullCoupon_throwsException`、`testValidate_couponWithFutureStartTime_throwsCouponExpired`）
       改为三参数调用，例如：
       ```java
       couponValidator.validate(validUserCoupon, new BigDecimal("100.00"), List.of(1L))
       ```
       该文件里的 `existingTemplate`/`expiredTemplate` fixture 都没有设置 `thresholdAmount` 或
       `applicableProductIds`，所以传什么样的金额/skuIds 都不会触发新增的门槛/适用性检查，
       不会让这几个原有用例意外变红——用一个固定的 `ORDER_AMOUNT`/`SKU_IDS` 静态量或字面量都可以，
       和知识库最终写法一致即可，不强求逐字一致。
     - 之后建议再补 4 类新用例（可选，不计分但有助于自查）：门槛未满足抛
       `COUPON_THRESHOLD_NOT_MET`、门槛满足通过、`applicableProductIds` 不含所购 SKU 抛
       `COUPON_NOT_APPLICABLE`、不含限制时任意 SKU 都通过。
- **验收**:
  - 已过期券（`endTime` 早于当前系统时钟）用于计算优惠 → 抛 `BusinessException("COUPON_EXPIRED", ...)`。
  - 未达 `thresholdAmount` 的 `THRESHOLD_OFF` 类券校验 → 抛 `COUPON_THRESHOLD_NOT_MET`。
  - `applicableProductIds` 设置了但所购 `skuIds` 不在其中 → 抛 `COUPON_NOT_APPLICABLE`。
  - `status != AVAILABLE`（已用/已过期状态）的券再次校验 → 抛 `COUPON_ALREADY_USED`。
  - `mvn -s maven-settings.xml -f code/pom.xml test-compile`（或直接 `install -DskipTests`）通过，
    `ecommerce-promotion` 模块不因本卡改动而编译失败。
- **勿犯**: 不要漏改 `CouponValidatorTest.java` 的 6 个调用点——`validate()` 签名从 1 参数变 3 参数
  是**硬编译错误**，一旦漏改，`code/ecommerce-promotion` 测试源码编译失败，`mvn install -DskipTests`
  整体中止，后续所有黑盒用例（包括跟本卡无关的）全部 0/24。不要给 `CouponTemplate` 实体加新字段
  ——`applicableProductIds` 已经存在，不需要动实体/建表。

---

### PROMO-4 | 优惠券使用后从不标记 USED，可无限重复使用

- 风险: high · 置信度: definite
- **文件**:
  1. `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/service/CouponService.java`（新增方法）
  2. `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderService.java`（跨模块接入点）
  3. `code/ecommerce-order/src/test/java/com/ecommerce/order/service/OrderServiceTest.java`（配合改）
- **现状**: 全仓库搜索 `CouponStatus.USED` 的赋值点——**不存在**。`UserCoupon` 实体已经有
  `status`/`usedOrderId`/`usedAt` 三个字段（基线 `UserCoupon.java` 就有，字段本身没问题），
  但没有任何 service 方法会把已使用的券置为 `USED`，也没有任何调用方在下单后去消费优惠券。
  同一张优惠券可以在多笔订单里反复传入 `couponIds` 反复享受折扣。
- **期望**: 优惠券一次使用后即失效。依据: `design-docs/10` §2（优惠券状态流转含"已使用"）、
  附录C `coupons`/`user_coupon` 表。消费时机：**订单创建成功持久化之后**才消费（避免订单创建失败时
  白白烧掉用户的券——这个"仅在持久化成功后消费"的模式后续也用在秒杀名额上，见 PROMO-8）。
- **改法**:
  1. **`CouponService.java`** 新增方法（放在 `calculateDiscount` 和 `generateCouponCode` 之间即可）：
     ```java
     /**
      * Mark a claimed coupon as used against a successfully-created order.
      * Called by the order module after an order that applied this coupon
      * has been persisted (never before, so a failed order never consumes it).
      */
     @Transactional
     public void markUsed(Long userCouponId, Long orderId) {
         UserCoupon userCoupon = userCouponRepository.findById(userCouponId)
                 .orElseThrow(() -> new ResourceNotFoundException("UserCoupon", userCouponId));
         userCoupon.setStatus(CouponStatus.USED);
         userCoupon.setUsedOrderId(orderId);
         userCoupon.setUsedAt(SystemClockService.now());
         userCouponRepository.save(userCoupon);
     }
     ```
     新增 import：`com.ecommerce.common.test.SystemClockService`（`ResourceNotFoundException`/
     `CouponStatus` 基线已导入，不用重复加）。
     **本卡先不做归属校验**（不检查 `userCoupon.getUserId()`）——归属校验是 PROMO-13 单独加的，
     不要在本卡里提前实现，否则和 PROMO-13 的"现状"对不上。
  2. **`OrderService.java`**（跨模块，依赖注入 `CouponService`）：
     - 在 class 字段区（`private final ... promotionCalculationService;` 之后）追加一行：
       `private final CouponService couponService;`
     - 构造函数参数列表末尾追加 `CouponService couponService` 形参，方法体末尾追加
       `this.couponService = couponService;`（**只追加，不要重写整个构造函数**——`OrderService`
       构造函数可能已经被 `order.md` 的卡片改过，追加式编辑不会冲突）。
     - 新增 import：`com.ecommerce.promotion.service.CouponService;`。
     - 在 `createOrder(...)` 方法里找到 **"Step 10: Reserve inventory"** 这段（锚点文本
       `inventoryReservationService.reserve(orderId, reserveItems);`）之后、
       **"Step 11: Publish OrderCreatedEvent"**（锚点文本
       `eventPublisher.publish(new OrderCreatedEvent(...`）之前，插入一个新的 "Step 10b" 区块：
       ```java
       // ===== Step 10b: Mark applied coupons used =====
       // Only after the order is persisted, so a failed order never consumes a coupon.
       if (request.getCouponIds() != null && !request.getCouponIds().isEmpty()
               && discountAmount.compareTo(BigDecimal.ZERO) > 0) {
           for (Long couponId : request.getCouponIds()) {
               try {
                   couponService.markUsed(couponId, orderId);
               } catch (Exception e) {
                   log.warn("Failed to mark coupon {} as used for order {}: {}",
                           couponId, orderId, e.getMessage());
               }
           }
       }
       ```
       用 `try/catch` 包一层是因为标记失败（比如券已经被并发消费）**不应该让整个订单创建失败**——
       订单已经落库了。`discountAmount` 变量、`orderId` 变量在 baseline 里都已经在这个位置的作用域内
       存在，不用额外声明。
  3. **`OrderServiceTest.java`** 新增一个 mock 字段（在其余 `@Mock` 字段旁边）：
     `@Mock private CouponService couponService;`。**不需要**改任何构造调用——该测试类用
     `@InjectMocks`（反射注入），不是手写 `new OrderService(...)`，新增构造参数不会导致编译错误；
     但如果不加这个 `@Mock` 字段，`@InjectMocks` 会把 `couponService` 注入为 `null`，
     一旦某条已有的 `createOrder(...)` 测试用例带了非空 `couponIds` 并让 `discountAmount>0`，
     就会在调用 `couponService.markUsed(...)` 时空指针，把原本通过的用例改红。
     Mockito 对未 `when(...)` stub 的 mock，`void` 方法调用默认什么都不做——不加任何 stub 即可。
- **验收**:
  - 单测：`markUsed(userCouponId, orderId)` 后，`userCouponRepository.save(...)` 收到的对象
    `status == CouponStatus.USED`、`usedOrderId == orderId`、`usedAt` 为当前系统时钟时间。
  - 集成行为：用同一张券下单两次（第二次用同一个 `userCouponId`），若 `PromotionCalculationService`
    的归属/已用校验生效（PROMO-3 已修），第二次应在计算优惠阶段就因 `COUPON_ALREADY_USED` 被拒，
    或至少 `GET /api/v1/promotions/coupons/my` 能看到该券 `status=USED`。
  - `mvn -f code/pom.xml install -DskipTests` 正常通过（无编译错误）。
- **勿犯**: 不要在本卡里加 `userId` 参数或归属校验——那是 PROMO-13 的范围，提前做会导致 PROMO-13
  的"现状"描述和实际代码对不上，接手 PROMO-13 的人可能会懵。不要把 `try/catch` 去掉直接让
  `markUsed` 失败时抛出——那会把一个已经成功创建的订单变成 500。

---

### PROMO-5 | 从不校验优惠券归属，可用他人优惠券

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/service/PromotionCalculationService.java`
- **现状**（依赖 PROMO-3 已应用，即 `calculateCouponDiscount` 已经是 4 参数版本）：
  ```java
  BigDecimal calculateCouponDiscount(Long userId, List<Long> couponIds,
                                      BigDecimal currentAmount, List<Long> skuIds) {
      ...
      for (Long couponId : couponIds) {
          Optional<UserCoupon> userCouponOpt = userCouponRepository.findById(couponId);
          if (!userCouponOpt.isPresent()) {
              continue;
          }
          UserCoupon userCoupon = userCouponOpt.get();

          couponValidator.validate(userCoupon, currentAmount, skuIds);
          ...
      }
  }
  ```
  拿到 `userCoupon` 后直接校验/计算折扣，**从未检查 `userCoupon.getUserId()` 是否等于当前请求的
  `userId`**。任何登录用户只要在 `couponIds` 里填别人的 `userCouponId`，就能借用其折扣力度。
- **期望**: 优惠券只能被其所有者使用。依据: `design-docs/10`（归属校验）、附录C `user_coupon.user_id`。
  非本人的券应**静默跳过**（不抛异常），避免通过错误响应让攻击者探测出别人有哪些 `userCouponId`
  存在。
- **改法**: 在 `Optional<UserCoupon> userCouponOpt = userCouponRepository.findById(couponId);` 取到
  `userCoupon` 之后、调用 `couponValidator.validate(...)` 之前，插入归属检查：
  ```java
  UserCoupon userCoupon = userCouponOpt.get();

  if (!userId.equals(userCoupon.getUserId())) {
      // Not this user's coupon — silently skip rather than leaking
      // its existence to a caller who doesn't own it via an error.
      continue;
  }

  couponValidator.validate(userCoupon, currentAmount, skuIds);
  ```
  只加这 3 行 `if`，其余不动。
- **验收**:
  - 单测：`calculateCouponDiscount(1L, List.of(couponIdOfUser999), amount, skuIds)` 返回
    `BigDecimal.ZERO`，且 `couponValidator.validate(...)`/`couponTemplateRepository.findById(...)`
    **都不会被调用**（在非本人券这一步就 `continue` 了，验证用 Mockito `verify(..., never())`）。
  - 本人的券（`userCoupon.getUserId().equals(userId)`）不受影响，正常计算折扣。

---

### PROMO-6 | `PromotionController` 硬编码 `userId=1`

- 风险: low · 置信度: definite
- **文件**:
  1. `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/controller/PromotionController.java`
  2. `code/ecommerce-promotion/src/test/java/com/ecommerce/promotion/controller/PromotionControllerTest.java`（配合改，否则原有用例会全部因 NPE 变红）
- **现状**: `extractUserId()`（基线第 115-119 行）：
  ```java
  private Long extractUserId() {
      // Placeholder: would be replaced with actual security context extraction
      // e.g. SecurityContextHolder.getContext().getAuthentication().getPrincipal()
      return 1L;
  }
  ```
  领券 (`claimCoupon`)、查我的券 (`getMyCoupons`)、计算优惠 (`calculate`，当 request 里没带 `userId`
  时) 三个端点都调用这个方法，**不管谁登录，`userId` 恒为 1**——用户 A 登录后领的券会记在用户 1
  账下，用户 A 自己反而查不到。
- **期望**: 从当前登录态取真实 `userId`。依据: `design-docs/02-系统架构.md`（从 SecurityContext 取
  当前用户）。项目里 JWT 认证成功后，`Authentication.getName()` 就是 `userId` 的字符串形式
  （其他模块的 `SecurityContextHolder` 用法与此一致）。
- **改法**: 把 `extractUserId()` 替换为：
  ```java
  private Long extractUserId() {
      String principal = SecurityContextHolder.getContext().getAuthentication().getName();
      try {
          return Long.parseLong(principal);
      } catch (NumberFormatException e) {
          log.warn("Failed to parse user ID from principal '{}'", principal);
          throw new com.ecommerce.common.exception.AuthorizationException(
                  "UNAUTHORIZED", "Invalid user principal: " + principal);
      }
  }
  ```
  需要新增 import：`org.springframework.security.core.context.SecurityContextHolder`、
  `org.slf4j.Logger`、`org.slf4j.LoggerFactory`，以及类里加一个
  `private static final Logger log = LoggerFactory.getLogger(PromotionController.class);` 字段
  （若类里还没有 logger 的话）。`AuthorizationException(String code, String message)` 构造函数
  在 `com.ecommerce.common.exception.AuthorizationException` 里已经存在，不用新增。
- **配合改测试**: `PromotionControllerTest.java` 是 `@WebMvcTest(PromotionController.class)`，
  基线完全没有设置任何 `Authentication`，改完 `extractUserId()` 后所有原有用例会在
  `SecurityContextHolder.getContext().getAuthentication()` 返回 `null` 时空指针。加一对
  `@BeforeEach`/`@AfterEach`：
  ```java
  @BeforeEach
  void setUpSecurityContext() {
      // Simulates what the JWT auth filter does in production: the
      // authenticated principal's name is the stringified userId.
      SecurityContextHolder.getContext().setAuthentication(
              new UsernamePasswordAuthenticationToken("1", null,
                      List.of(new SimpleGrantedAuthority("ROLE_USER"))));
  }

  @AfterEach
  void tearDownSecurityContext() {
      SecurityContextHolder.clearContext();
  }
  ```
  需要新增 import：`org.junit.jupiter.api.AfterEach`、
  `org.springframework.security.authentication.UsernamePasswordAuthenticationToken`、
  `org.springframework.security.core.authority.SimpleGrantedAuthority`、
  `org.springframework.security.core.context.SecurityContextHolder`。注意这是**类级别**的
  `@BeforeEach`（不是某个 `@Nested` 内部），因为三个端点（claim/my/calculate）用的测试类都要覆盖到。
  用 `"1"` 是因为原有用例的断言大多期望 `userId=1`（例如 `jsonPath("$.userId").value(1)`），
  这样可以保持原有断言不变。
- **验收**:
  - 未认证请求（`SecurityContextHolder` 里没有 `Authentication`，走真实 Spring Security 过滤链）
    应该在到达 controller 之前就被拦成 401，不会走到 `extractUserId()`。
  - 已认证但 principal 不是数字字符串（不应该在正常场景发生，属于防御性分支）→ 抛
    `AuthorizationException("UNAUTHORIZED", ...)`。
  - `PromotionControllerTest` 全部原有用例保持通过（不因本卡改动变红）。

---

### PROMO-7 | `totalDiscount` 未按"不得大于商品金额"封顶

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/service/PromotionCalculationService.java`
- **现状**（依赖 PROMO-2 已应用）: `calculate()` 方法尾部：
  ```java
  BigDecimal totalDiscount = MonetaryUtil.add(
          MonetaryUtil.add(memberDiscount, fullReductionDiscount), couponDiscount);
  BigDecimal finalAmount = MonetaryUtil.subtract(itemTotal, totalDiscount);

  if (finalAmount.compareTo(BigDecimal.ZERO) < 0) {
      finalAmount = BigDecimal.ZERO;
  }
  ```
  只有 `finalAmount` 被下限钳制到 0，`totalDiscount` 本身**从未被封顶**。如果多个满减/优惠券叠加
  出的折扣总额超过商品金额（比如满减规则配置不当，或多张券叠加），`finalAmount` 虽然被夹到 0，
  但 `totalDiscount` 会是一个**大于 `itemTotal` 的荒谬值**（例如 `itemTotal=100` 但
  `totalDiscount=200`），违反"优惠金额不得大于商品金额"的约束，且 `itemTotal - totalDiscount`
  与 `finalAmount` 两个字段互相对不上。
- **期望**: `design-docs/03-通用规范与非功能设计.md` §1：优惠金额不得大于商品金额。
  `totalDiscount` 应该反推自封顶后的 `finalAmount`，保证 `itemTotal - totalDiscount == finalAmount`
  恒成立，且 `totalDiscount` 永不超过 `itemTotal`。
- **改法**: 把上面那段替换为：
  ```java
  BigDecimal finalAmount = MonetaryUtil.subtract(afterCoupon, memberDiscount);
  if (finalAmount.compareTo(BigDecimal.ZERO) < 0) {
      finalAmount = BigDecimal.ZERO;
  }
  // Derive totalDiscount from the clamped finalAmount so it can never
  // exceed itemTotal, even if the individual discounts would overshoot.
  BigDecimal totalDiscount = MonetaryUtil.subtract(itemTotal, finalAmount);
  ```
  注意 `finalAmount` 现在是从 `afterCoupon`（PROMO-2 引入的中间变量，= 满减+优惠券之后、会员折扣
  之前的金额）减 `memberDiscount` 直接算出来的，不再经过"先加三项折扣、再从 itemTotal 减"这条路径；
  `totalDiscount` 则反过来由 `itemTotal - finalAmount` 得到。`memberDiscount`/`fullReductionDiscount`/
  `couponDiscount` 三个字段各自的 setter 调用不变（它们各自的值不受影响，只有 `totalDiscount` 的
  **计算方式**变了）。
- **验收**:
  - 构造一个满减规则被 mock 成 `200.00`（大于 `itemTotal=100.00`）、无优惠券、无会员折扣
    （`userId=null`）的场景：`finalAmount == 0.00`，`totalDiscount == itemTotal == 100.00`
    （不是 `200.00`）。
  - 正常场景（折扣总和小于商品金额）下 `totalDiscount` 数值与改动前一致（比如 PROMO-2 验收里的
    `itemTotal=100, totalDiscount=31.60` 例子应保持不变）。
  - 任意场景下恒有 `itemTotal - totalDiscount == finalAmount`（在 `BigDecimal.compareTo` 意义下相等）。

---

### PROMO-8 | 秒杀完全没接入下单流程（含限购/库存校验补全）

- 风险: high · 置信度: definite
- **文件**（5 个，2 个新增）:
  1. `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/service/SeckillService.java`（重写）
  2. `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/entity/SeckillPurchaseRecord.java`（**新增**）
  3. `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/repository/SeckillPurchaseRecordRepository.java`（**新增**）
  4. `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderService.java`（跨模块接入点，依赖 PROMO-4 已应用）
  5. 配合改测试：`SeckillServiceTest.java`、`OrderServiceTest.java`
- **现状**: `SeckillService`（基线全文）有 `create`/`validateSeckill(Long skuId)`/
  `recordPurchase(Long activityId)` 三个方法，逻辑本身基本对（校验时间窗口、库存 `<=0`），但
  **全仓库没有任何地方调用 `validateSeckill`/`recordPurchase`**（`OrderService`/`CartService`
  都没有 `SeckillService` 依赖）。秒杀活动创建后对下单流程毫无影响——用户按秒杀价买东西这条路径
  根本不存在，`SECKILL_NOT_STARTED`/`SECKILL_ENDED`/`SECKILL_SOLD_OUT` 都是死代码。另外基线
  `validateSeckill` 本身也没有限购校验（design-docs 要求"用户未超过限购数量"），`SeckillActivity`
  实体虽有 `perUserLimit` 字段但从未被读取；库存校验用 `availableStock <= 0`，没考虑"本次购买数量"
  （买 5 个但只剩 3 个也会通过）。
- **期望**: `design-docs/10` §4 秒杀规则：
  ```text
  1. 活动处于进行中。 2. SKU 参与活动。 3. 用户未超过限购数量。
  4. 秒杀库存充足。   5. 秒杀价格不参与普通满减。
  ```
  下单时，购物车/订单里若某 SKU 命中一个进行中的秒杀活动，应按秒杀价结算、走上述 4 项校验、
  成功下单后扣减秒杀库存并记录该用户的购买量（供以后限购判断累加）；第 5 条（不参与普通满减）
  由订单侧在计算优惠时把秒杀条目排除在外来保证。
- **改法**（先促销侧，再订单侧，缺一不可）：

  **① `SeckillService.java` 整体重写：**
  ```java
  @Service
  public class SeckillService {

      private final SeckillRepository seckillRepository;
      private final SeckillPurchaseRecordRepository purchaseRecordRepository;

      public SeckillService(SeckillRepository seckillRepository,
                             SeckillPurchaseRecordRepository purchaseRecordRepository) {
          this.seckillRepository = seckillRepository;
          this.purchaseRecordRepository = purchaseRecordRepository;
      }

      @Transactional
      public SeckillActivity create(SeckillActivity activity) {
          if (activity.getStartTime() != null && activity.getEndTime() != null
                  && !activity.getEndTime().isAfter(activity.getStartTime())) {
              throw new ValidationException("endTime", "End time must be after start time");
          }
          activity.setSoldQuantity(0);
          activity.setStatus("ACTIVE");
          return seckillRepository.save(activity);
      }

      @Transactional(readOnly = true)
      public SeckillActivity validateSeckill(Long userId, Long skuId, Integer quantity) {
          SeckillActivity activity = seckillRepository.findBySkuIdAndStatus(skuId, "ACTIVE")
                  .orElseThrow(() -> new ResourceNotFoundException("SeckillActivity for SKU", skuId));

          int purchaseQuantity = quantity != null ? quantity : 1;

          LocalDateTime now = SystemClockService.now();
          if (activity.getStartTime() != null && now.isBefore(activity.getStartTime())) {
              throw new BusinessException("SECKILL_NOT_STARTED", "Seckill activity has not started yet");
          }
          if (activity.getEndTime() != null && now.isAfter(activity.getEndTime())) {
              throw new BusinessException("SECKILL_ENDED", "Seckill activity has already ended");
          }

          if (activity.getPerUserLimit() != null && userId != null) {
              int alreadyPurchased = purchaseRecordRepository
                      .findByActivityIdAndUserId(activity.getId(), userId)
                      .stream()
                      .mapToInt(record -> record.getQuantity() != null ? record.getQuantity() : 0)
                      .sum();
              if (alreadyPurchased + purchaseQuantity > activity.getPerUserLimit()) {
                  throw new BusinessException("SECKILL_LIMIT_EXCEEDED",
                          "Exceeds the per-user purchase limit for this seckill activity");
              }
          }

          int availableStock = (activity.getStockQuantity() != null ? activity.getStockQuantity() : 0)
                  - (activity.getSoldQuantity() != null ? activity.getSoldQuantity() : 0);
          if (availableStock < purchaseQuantity) {
              throw new BusinessException("SECKILL_SOLD_OUT", "Seckill stock has been exhausted");
          }

          return activity;
      }

      @Transactional
      public void recordPurchase(Long activityId, Long userId, Integer quantity) {
          SeckillActivity activity = seckillRepository.findById(activityId)
                  .orElseThrow(() -> new ResourceNotFoundException("SeckillActivity", activityId));

          int purchaseQuantity = quantity != null ? quantity : 1;
          int sold = activity.getSoldQuantity() != null ? activity.getSoldQuantity() : 0;
          activity.setSoldQuantity(sold + purchaseQuantity);
          seckillRepository.save(activity);

          SeckillPurchaseRecord record = new SeckillPurchaseRecord();
          record.setActivityId(activityId);
          record.setUserId(userId);
          record.setQuantity(purchaseQuantity);
          purchaseRecordRepository.save(record);
      }
  }
  ```
  新增 import：`com.ecommerce.common.test.SystemClockService`、
  `com.ecommerce.promotion.entity.SeckillPurchaseRecord`、
  `com.ecommerce.promotion.repository.SeckillPurchaseRecordRepository`（其余基线已有）。
  注意时间判断从 `LocalDateTime.now()` 改成了 `SystemClockService.now()`（黑盒测试可能通过
  `PUT /api/v1/admin/system/clock` 设置测试时钟，用真实系统时钟会导致时钟相关用例不受控）；
  库存校验从 `availableStock <= 0` 改成了 `availableStock < purchaseQuantity`。

  **② 新增 `SeckillPurchaseRecord.java`**（`@Entity`，Hibernate `ddl-auto: update`/`create-drop`
  会自动建表，不需要手写 schema）：
  ```java
  package com.ecommerce.promotion.entity;

  import com.ecommerce.common.model.BaseEntity;
  import jakarta.persistence.Column;
  import jakarta.persistence.Entity;
  import jakarta.persistence.Table;

  @Entity
  @Table(name = "seckill_purchase_record")
  public class SeckillPurchaseRecord extends BaseEntity {

      @Column(name = "activity_id", nullable = false)
      private Long activityId;

      @Column(name = "user_id", nullable = false)
      private Long userId;

      @Column(nullable = false)
      private Integer quantity;

      public SeckillPurchaseRecord() {
      }

      public Long getActivityId() { return activityId; }
      public void setActivityId(Long activityId) { this.activityId = activityId; }
      public Long getUserId() { return userId; }
      public void setUserId(Long userId) { this.userId = userId; }
      public Integer getQuantity() { return quantity; }
      public void setQuantity(Integer quantity) { this.quantity = quantity; }
  }
  ```

  **③ 新增 `SeckillPurchaseRecordRepository.java`：**
  ```java
  package com.ecommerce.promotion.repository;

  import com.ecommerce.promotion.entity.SeckillPurchaseRecord;
  import org.springframework.data.jpa.repository.JpaRepository;
  import org.springframework.stereotype.Repository;

  import java.util.List;

  @Repository
  public interface SeckillPurchaseRecordRepository extends JpaRepository<SeckillPurchaseRecord, Long> {
      List<SeckillPurchaseRecord> findByActivityIdAndUserId(Long activityId, Long userId);
  }
  ```

  **④ `OrderService.java`（跨模块，依赖 PROMO-4 已应用，即已有 `couponService` 字段/Step 10b）：**
  - 字段区追加：`private final SeckillService seckillService;`
  - 构造函数参数列表末尾追加 `SeckillService seckillService` 形参（跟在 PROMO-4 加的
    `CouponService couponService` 后面），方法体追加 `this.seckillService = seckillService;`。
  - 新增 import：`com.ecommerce.promotion.entity.SeckillActivity;`、
    `com.ecommerce.promotion.service.SeckillService;`（`ResourceNotFoundException` 基线已导入）。
  - 找到 **"Step 2: Validate SKUs and get product data"** 循环（锚点：
    `for (CreateOrderRequest.OrderItemRequest reqItem : requestItems) {`），把循环前的局部变量声明
    和循环体改成：
    ```java
    List<CreateOrderRequest.OrderItemRequest> requestItems = request.getItems();
    List<OrderItem> orderItems = new ArrayList<>();
    List<OrderItem> promotionEligibleItems = new ArrayList<>();
    List<SeckillPurchase> seckillPurchases = new ArrayList<>();
    BigDecimal itemTotal = BigDecimal.ZERO;

    for (CreateOrderRequest.OrderItemRequest reqItem : requestItems) {
        orderValidator.validateQuantity(reqItem.getQuantity());

        SkuDto sku = productQueryService.getSkuForSale(reqItem.getSkuId());

        // Seckill check: if this SKU is part of an active seckill activity,
        // buy at the seckill price instead of list price (design-docs/10 §4).
        BigDecimal effectivePrice = sku.getPrice();
        boolean seckillItem = false;
        try {
            SeckillActivity activity = seckillService.validateSeckill(
                    userId, sku.getSkuId(), reqItem.getQuantity());
            if (activity != null && activity.getSeckillPrice() != null) {
                effectivePrice = activity.getSeckillPrice();
                seckillItem = true;
                seckillPurchases.add(new SeckillPurchase(activity.getId(), reqItem.getQuantity()));
            }
        } catch (ResourceNotFoundException e) {
            // SKU is not part of any active seckill activity — normal price.
        }

        OrderItem orderItem = new OrderItem();
        orderItem.setSkuId(sku.getSkuId());
        orderItem.setSkuName(sku.getName());
        orderItem.setSkuCode(sku.getSkuCode());
        orderItem.setPrice(effectivePrice);
        orderItem.setQuantity(reqItem.getQuantity());
        orderItem.setSubtotal(MonetaryUtil.multiply(effectivePrice,
                BigDecimal.valueOf(reqItem.getQuantity())));
        orderItems.add(orderItem);
        if (!seckillItem) {
            promotionEligibleItems.add(orderItem);
        }

        itemTotal = MonetaryUtil.add(itemTotal, orderItem.getSubtotal());
    }
    ```
    这里 `try/catch ResourceNotFoundException` 是**故意**的：`validateSeckill` 对"该 SKU 没有秒杀
    活动"这个正常情况就是抛 `ResourceNotFoundException`，订单侧把它当"走普通价格"的信号吞掉。
    **这个 try/catch 本身会在同一个 `@Transactional` 事务里毒化事务**（Spring 一旦看到受检异常/
    运行时异常穿过一个参与事务的方法就会把事务标记 rollback-only），修复方式是 PROMO-11
    （`BUG-INT-2`），本卡先只管把调用接上，不要在本卡里改 `validateSeckill` 的 `@Transactional`
    注解。
  - 找到 **"Step 6: Calculate promotions and discounts"**（锚点：
    `BigDecimal discountAmount = calculateDiscounts(userId, request, orderItems, itemTotal);`），
    把入参 `orderItems` 改成 `promotionEligibleItems`：
    ```java
    // Seckill-priced items are excluded from ordinary full-reduction/coupon
    // stacking, per design-docs/10 §4 rule 5.
    BigDecimal discountAmount = calculateDiscounts(userId, request, promotionEligibleItems, itemTotal);
    ```
    `calculateDiscounts` 方法本身不用改，只改这一处调用的实参。
  - 在 PROMO-4 已经加好的 "Step 10b" 区块里，`markUsed` 的 `for` 循环**之后**追加：
    ```java
    for (SeckillPurchase purchase : seckillPurchases) {
        seckillService.recordPurchase(purchase.activityId, userId, purchase.quantity);
    }
    ```
  - 在类的最后（最后一个方法的闭合 `}` 之后、类闭合 `}` 之前）新增一个私有静态内部类：
    ```java
    /**
     * A seckill purchase to record (decrement stock, track per-user purchase
     * count) once the order that used it has been successfully persisted.
     */
    private static final class SeckillPurchase {
        private final Long activityId;
        private final Integer quantity;

        private SeckillPurchase(Long activityId, Integer quantity) {
            this.activityId = activityId;
            this.quantity = quantity;
        }
    }
    ```
  - **不要**改 `ecommerce-cart` 模块——尽管 findings 里提到"order/cart 下单前查有效秒杀"，
    实际验证通过的修复只接入了 `order` 一侧（购物车预估 `/cart/estimate` 目前仍按列表价估算，
    这是已知的、经过风险评估后暂缓的范围，不在本卡内，不要额外去改 `CartService`）。

  **⑤ 配合改测试：**
  - `SeckillServiceTest.java`：
    - 新增 mock 字段 `@Mock private SeckillPurchaseRecordRepository purchaseRecordRepository;`
      （否则 `recordPurchase` 的 3 个用例会因为 `purchaseRecordRepository` 为 `null` 而空指针）。
    - 全文件把所有 `seckillService.validateSeckill(xxxL)`（1 参数，约 12 处）改成
      `seckillService.validateSeckill(SOME_USER_ID, xxxL, 1)`（可以定义一个 `private static final
      Long USER_ID = 1L;` 常量复用）——由于原有 fixture 的 `SeckillActivity` 大多没设置
      `perUserLimit`，`userId` 传什么值都不会误触发新的限购分支，可以直接传常量。
    - 全文件把所有 `seckillService.recordPurchase(xxxL)`（1 参数，3 处）改成
      `seckillService.recordPurchase(xxxL, USER_ID, 1)`。
  - `OrderServiceTest.java`：新增 `@Mock private SeckillService seckillService;` 字段（同 PROMO-4，
    `@InjectMocks` 反射注入，不需要改构造调用；不加则未 stub 的 `validateSeckill` 调用返回 `null`，
    代码里 `if (activity != null && ...)` 已经处理了 `null`，不会 NPE，但**必须**加这个 `@Mock`
    字段本身，否则字段是"没有这个 mock 对象"而不是"mock 对象但方法返回 null"——两者对 Mockito
    `@InjectMocks` 的反射构造行为是一致的（缺失的类型一样注入 `null`），这里不加也不会编译失败，
    但为了跟 PROMO-4 保持一致的可读性、以及方便以后针对秒杀场景写新单测，建议加上）。
- **验收**:
  - 某 SKU 有进行中的秒杀活动（`seckillPrice=50.00`，列表价 `100.00`），下单购买该 SKU → 订单项
    `price` 为 `50.00` 而非 `100.00`；`recordPurchase` 被调用，活动 `soldQuantity` 增加对应购买数量；
    该 SKU 的 `discountAmount` 计算基数里不含这笔（不参与满减/优惠券）。
  - 普通 SKU（不在任何秒杀活动内）下单 → `validateSeckill` 抛 `ResourceNotFoundException` 被内部
    catch 吞掉，订单按列表价正常创建（**创建本身应该成功**——若创建失败/500，说明 PROMO-11 还没生效）。
  - 秒杀限购：用户已购买量 + 本次购买量 > `perUserLimit` → 抛 `SECKILL_LIMIT_EXCEEDED`。
  - 秒杀库存：`stockQuantity - soldQuantity < 本次购买数量` → 抛 `SECKILL_SOLD_OUT`（哪怕
    `availableStock > 0`，只是不够本次购买的量）。
- **勿犯**: 不要漏加 `SeckillServiceTest.java` 的 `@Mock purchaseRecordRepository` 字段——这个不是
  编译错误，是**运行时空指针**，容易被"反正模块单测不计分"的心态忽略，但会让原本全绿的模块自测
  出现新的失败，影响自查判断。不要在 Step 2 循环里去掉 `try/catch ResourceNotFoundException`
  ——普通订单（无秒杀）必须能正常创建。不要碰 `ecommerce-cart` 模块。

---

### PROMO-9 | 满减活动从不校验起止时间窗口

- 风险: low · 置信度: suspicious
- **文件**: `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/service/FullReductionService.java`
- **现状**: `calculateBestReduction(BigDecimal orderTotal)`（基线第 63-83 行）遍历
  `listActive()`（即 `status="ACTIVE"` 的活动）逐个比较 `orderTotal >= threshold`，**完全不看
  `activity.getStartTime()`/`getEndTime()`**。一个已经过期（`endTime` 在过去）但还没被人工下线
  （`status` 仍是 `ACTIVE`）的满减活动会一直生效；一个还没开始（`startTime` 在未来）的活动也会
  提前生效。
- **期望**: 只有当前时刻落在 `[startTime, endTime]` 窗口内（某一端为 `null` 视为不限）的活动才参与
  "取最优减免金额"的比较。依据: `design-docs/10` §3（满减活动"按订单金额阶梯匹配"隐含活动必须
  处于有效期内；`FullReductionActivity` 实体本身就有 `startTime`/`endTime` 字段，说明设计意图是
  要校验）。
- **改法**: 在 `calculateBestReduction` 的 `for` 循环体最前面加一个窗口过滤，并把时间源从
  `LocalDateTime.now()` 改成 `SystemClockService.now()`（与黑盒测试的可控时钟保持一致）：
  ```java
  public Optional<BigDecimal> calculateBestReduction(BigDecimal orderTotal) {
      if (orderTotal == null || orderTotal.compareTo(BigDecimal.ZERO) <= 0) {
          return Optional.empty();
      }

      List<FullReductionActivity> activeActivities = listActive();
      LocalDateTime now = SystemClockService.now();
      BigDecimal bestReduction = BigDecimal.ZERO;

      for (FullReductionActivity activity : activeActivities) {
          if (!isWithinWindow(activity, now)) {
              continue;
          }
          if (orderTotal.compareTo(activity.getThresholdAmount()) >= 0) {
              if (activity.getReductionAmount().compareTo(bestReduction) > 0) {
                  bestReduction = activity.getReductionAmount();
              }
          }
      }

      if (bestReduction.compareTo(BigDecimal.ZERO) > 0) {
          return Optional.of(MonetaryUtil.roundToCent(bestReduction));
      }
      return Optional.empty();
  }

  /**
   * Whether an activity's start/end time window currently covers {@code now}.
   * A null bound is treated as unbounded on that side.
   */
  private boolean isWithinWindow(FullReductionActivity activity, LocalDateTime now) {
      return (activity.getStartTime() == null || !now.isBefore(activity.getStartTime()))
              && (activity.getEndTime() == null || !now.isAfter(activity.getEndTime()));
  }
  ```
  新增 import：`com.ecommerce.common.test.SystemClockService`、`java.time.LocalDateTime`
  （后者基线可能已经因为其他用法导入了，没有就加）。
- **验收**:
  - 活动 A：`startTime=null, endTime=昨天`（已过期），`status=ACTIVE`，`threshold=50`；订单金额
    `100` → `calculateBestReduction` 不应选中活动 A（返回 `Optional.empty()` 或跳过它去比较其他
    活动）。
  - 活动 B：`startTime=明天`（未开始）→ 同样被排除。
  - 活动 C：`startTime=昨天, endTime=明天`（在窗口内）→ 正常参与比较。
  - `startTime`/`endTime` 都为 `null` 的活动（无限期）→ 视为始终在窗口内，行为与改动前一致。

---

### PROMO-10 | 舍入模式 HALF_DOWN，应为 HALF_UP（跨模块根因，已在别处修复）

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-common/src/main/java/com/ecommerce/common/money/MonetaryUtil.java`
- **现状**: `roundToCent()` 用 `RoundingMode.HALF_DOWN`，导致 `CouponService`/
  `PromotionCalculationService`/`FullReductionService` 里所有经 `MonetaryUtil.add/subtract/multiply`
  的促销金额计算，在 `.005` 边界上舍入方向错误。
- **期望**: `RoundingMode.HALF_UP`。依据: `design-docs/03` §1。
- **改法**: **本卡不需要在 `promotion` 相关文件里做任何改动**——这是全系统单点根因，已经由
  `work/bugs/S1-quick-wins.md` 的卡片 **S1-1** 统一修复（`B01` 批次，早于本文件所在的 `B05` 批次
  执行）。本条目在这里列出只是为了对齐 `findings.md` promotion 模块 10 项的完整清单，**不要在本卡
  下再去改 `MonetaryUtil.java`，也不要在 promotion 模块任何文件里绕开它自己实现舍入**。
- **验收**: 确认 `MonetaryUtil.roundToCent(new BigDecimal("0.005"))` 已经是 `0.01`（说明 S1-1 已生效）；
  若发现这一步还没生效，先去执行 `S1-quick-wins.md` 的 S1-1，而不是在本文件里补一份重复修复。

---

### PROMO-11 | BUG-INT-2：秒杀事务毒化导致所有下单 500

- 风险: high · 置信度: definite
- **文件**: `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/service/SeckillService.java`
- **现状**（依赖 PROMO-8 已应用，即 `OrderService.createOrder` 已经在 Step 2 循环里用
  `try { seckillService.validateSeckill(userId, sku.getSkuId(), reqItem.getQuantity()); } catch
  (ResourceNotFoundException e) { }` 的方式调用秒杀探测）：
  `OrderService.createOrder(...)` 整体是一个 `@Transactional`（类默认或方法级，取决于 `order.md`
  之前的改动，但至少参与一个 Spring 管理事务）。它在 Step 2 循环里调用
  `SeckillService.validateSeckill(...)`，后者标注为 `@Transactional(readOnly = true)`
  （**没有** `noRollbackFor`）。对于**不参与任何秒杀活动的普通 SKU**（绝大多数订单），
  `validateSeckill` 必然抛 `ResourceNotFoundException`（"该 SKU 没有秒杀活动"），`OrderService`
  这边用 `catch (ResourceNotFoundException e) {}` 吞掉、当作"走普通价格"处理——**但这个异常已经
  从一个参与事务的方法里抛出过一次**，Spring 事务基础设施在异常离开 `validateSeckill` 方法边界的
  那一刻，已经把它所属的（与 `createOrder` 共享的）事务标记为 **rollback-only**。`OrderService`
  这边虽然用 try/catch"处理"了异常本身，但事务已经回不去了——`createOrder` 方法正常 return 后，
  Spring 尝试 `commit` 这个已被标记 rollback-only 的事务，抛出 `UnexpectedRollbackException`，
  外层变成 HTTP 500。**结果：只要接入了 PROMO-8 的秒杀探测调用，所有不涉及秒杀的普通下单请求都会
  500**（这条连锁反应会波及依赖"能成功下单"的其余 7+ 个黑盒用例）。
- **期望**: "SKU 不在任何秒杀活动中"是一个**正常的业务信号**（不是真正的错误），不应该有让调用方
  事务失败的副作用。真正的秒杀失败（`SECKILL_SOLD_OUT`/`SECKILL_ENDED`/`SECKILL_NOT_STARTED`/
  `SECKILL_LIMIT_EXCEEDED`，均以 `BusinessException` 抛出）仍然应该正常回滚——这些是货真价实的
  下单失败原因。依据：Spring 事务传播语义（`@Transactional(noRollbackFor=...)`）、
  `design-docs/03` §8（后置/探测性检查不得拖累主流程）。
- **改法**: 只改 `validateSeckill` 方法头上的注解，从
  ```java
  @Transactional(readOnly = true)
  public SeckillActivity validateSeckill(Long userId, Long skuId, Integer quantity) {
  ```
  改成
  ```java
  @Transactional(readOnly = true, noRollbackFor = ResourceNotFoundException.class)
  public SeckillActivity validateSeckill(Long userId, Long skuId, Integer quantity) {
  ```
  就这一处。可以在方法上方补一句注释说明原因（非必需，但强烈建议，方便下一个人理解为什么这里
  要加 `noRollbackFor`）：
  ```java
  // The order-creation flow calls this as a probe to decide whether a SKU is on
  // an active seckill, treating "no active seckill for this SKU"
  // (ResourceNotFoundException) as a normal, non-error signal and falling back to
  // the list price. Since this method participates in the caller's transaction,
  // a plain throw would mark that transaction rollback-only — so the caller's
  // legitimate swallow of the signal would still make the whole order fail at
  // commit (UnexpectedRollbackException). noRollbackFor keeps the benign
  // not-found case from poisoning the caller's transaction, while genuine seckill
  // failures (SECKILL_SOLD_OUT / SECKILL_ENDED / ... , thrown as BusinessException)
  // still propagate and roll back as before.
  ```
- **验收**:
  - 创建一个**不涉及任何秒杀活动**的普通订单（SKU 无秒杀）→ HTTP 201，订单正常创建成功
    （这是最关键的回归点——PUB-008/PUB-102 等基础下单用例都必须继续通过）。
  - 创建一个 SKU 命中秒杀但库存已售罄的订单 → 仍然按预期抛 `SECKILL_SOLD_OUT`（`BusinessException`
    不在 `noRollbackFor` 白名单里，事务正常回滚，订单不会被创建）。
  - 全量黑盒 24 例跑一遍，确认没有因为"事务被标记 rollback-only"产生的 `UnexpectedRollbackException`
    / 500。
- **勿犯**: **只加 `noRollbackFor = ResourceNotFoundException.class` 这一个属性**，不要把
  `@Transactional(readOnly = true)` 整个去掉（`validateSeckill` 内部会查
  `SeckillPurchaseRecordRepository`，去掉事务注解不会报错但破坏了只读事务的一致性语义，且如果
  后续有人在此方法里加写操作会失去事务边界）。不要去改 `OrderService` 侧的
  `catch (ResourceNotFoundException e) {}` 逻辑——那段 catch 本身没有错，错的是被 catch 之前事务
  已经"死"了，本卡修的是"别让它死"，不是"catch 之后再做点什么补救"。不要把 `noRollbackFor` 加到
  别的方法上（比如 `recordPurchase`）——只有 `validateSeckill` 存在"探测性调用+良性 not-found"
  这个模式。

---

### PROMO-12 | 同一 `couponId` 在一次请求里出现两次会被双重计算折扣

- 风险: low · 置信度: likely
- **文件**: `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/service/PromotionCalculationService.java`
- **现状**（依赖 PROMO-3/PROMO-5 已应用，即 `calculateCouponDiscount` 已是 4 参数版本、已有归属
  校验）: 循环头是
  ```java
  for (Long couponId : couponIds) {
  ```
  如果调用方（不管是前端 bug 还是恶意构造）在 `couponIds` 里传了 `[10, 10]`（同一个 `userCouponId`
  出现两次），循环会对 `couponId=10` 处理两遍：查两次、校验两次（`couponValidator.validate` 不检查
  "是否已经在本次计算中用过"，两次都能通过）、`calculateDiscount` 算两次、`totalCouponDiscount`
  被累加了两倍。一张券的折扣力度被放大了一倍。
- **期望**: 同一张优惠券在一次计算/下单请求里最多只应用一次。依据: `design-docs/10` §2
  （一券一单一次的隐含约束——`CouponStatus.USED` 状态模型本身就是"一张券只能被消费一次"）。
- **改法**: 把循环头改成对 `couponIds` 先去重：
  ```java
  // De-duplicate: a coupon listed twice in the same request must be counted
  // at most once (10§2 / CouponStatus.USED — a coupon is consumed once per
  // order). Without this, [10, 10] would double-count coupon 10's discount.
  for (Long couponId : couponIds.stream().distinct().collect(Collectors.toList())) {
  ```
  若 PROMO-3 已经在文件顶部加过 `import java.util.stream.Collectors;`，这里不用重复加；如果因为
  某种原因 PROMO-3 没有加成（比如被跳过了），这里要自己确认该 import 存在。**只改循环头这一行**，
  循环体不动。
- **验收**:
  - `calculateCouponDiscount(1L, List.of(10L, 10L), amount, skuIds)` 与
    `calculateCouponDiscount(1L, List.of(10L), amount, skuIds)`（只传一次）返回**相同**的折扣金额
    （而不是两倍）。
  - `couponTemplateRepository.findById(...)`/`couponService.calculateDiscount(...)` 对 `couponId=10`
    只被调用一次（可用 Mockito `verify(..., times(1))` 断言），不是两次。
  - `couponIds` 里两张不同的券（如 `[10, 20]`）不受影响，各自正常计算、正常累加。

---

### PROMO-13 | `markUsed` 不校验券归属：可核销他人优惠券

- 风险: high · 置信度: definite
- **文件**（跨模块，列全）:
  1. `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/service/CouponService.java`（依赖 PROMO-4 已应用）
  2. `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderService.java`（依赖 PROMO-4 已应用）
  3. `code/ecommerce-promotion/src/test/java/com/ecommerce/promotion/service/CouponServiceTest.java`（配合改）
- **现状**（依赖 PROMO-4 已应用）: `CouponService.markUsed(Long userCouponId, Long orderId)`：
  ```java
  @Transactional
  public void markUsed(Long userCouponId, Long orderId) {
      UserCoupon userCoupon = userCouponRepository.findById(userCouponId)
              .orElseThrow(() -> new ResourceNotFoundException("UserCoupon", userCouponId));
      userCoupon.setStatus(CouponStatus.USED);
      userCoupon.setUsedOrderId(orderId);
      userCoupon.setUsedAt(SystemClockService.now());
      userCouponRepository.save(userCoupon);
  }
  ```
  只按 `userCouponId` 查券，**完全不检查这张券的 `userId` 是否等于下单用户**。`calculateDiscount`
  阶段（`PromotionCalculationService.calculateCouponDiscount`，PROMO-5 已修）已经强制了归属校验，
  但 `markUsed` 是**订单持久化之后**独立触发的第二条路径——只要请求里的 `couponIds` 恰好让
  `discountAmount>0`（哪怕是靠别的、真正属于自己的券贡献的折扣），下单请求里混进的他人
  `userCouponId` 一样会被 `markUsed` 循环遍历到并烧掉，而这条路径**没有走计算侧的归属校验**。
  等价于：用户 A 可以传入用户 B 的 `userCouponId`，把 B 的券消耗掉（状态变 `USED`），即使 A 自己
  完全没有从这张券里获得任何折扣。
- **期望**: 核销侧的归属校验要和计算侧对称——不属于当前下单用户的券，`markUsed` 应该静默跳过
  （不抛异常、不消耗），而不是"只要 ID 对得上就烧"。依据: 附录C `user_coupon.user_id`；
  计算侧 `PromotionCalculationService#calculateCouponDiscount`（PROMO-5）已经确立的"非本人券静默
  跳过"模式，核销侧应保持一致。
- **改法**:
  1. **`CouponService.markUsed`** 加 `userId` 参数、加归属检查：
     ```java
     /**
      * Mark a claimed coupon as used against a successfully-created order.
      * Called by the order module after an order that applied this coupon
      * has been persisted (never before, so a failed order never consumes it).
      *
      * <p>The coupon is only consumed when it actually belongs to {@code userId}.
      * A coupon that is not the ordering user's is silently skipped — mirroring
      * the calculation side ({@code PromotionCalculationService#calculateCouponDiscount},
      * which already ignores non-owned coupons) — so listing another user's
      * {@code userCouponId} in a create-order request can never consume it.
      */
     @Transactional
     public void markUsed(Long userCouponId, Long orderId, Long userId) {
         UserCoupon userCoupon = userCouponRepository.findById(userCouponId)
                 .orElseThrow(() -> new ResourceNotFoundException("UserCoupon", userCouponId));
         if (userId != null && !userId.equals(userCoupon.getUserId())) {
             return;
         }
         userCoupon.setStatus(CouponStatus.USED);
         userCoupon.setUsedOrderId(orderId);
         userCoupon.setUsedAt(SystemClockService.now());
         userCouponRepository.save(userCoupon);
     }
     ```
     注意：找不到券（`userCouponId` 不存在）仍然抛 `ResourceNotFoundException`（不是静默跳过）——
     "不存在"和"不是我的"是两种不同的情况，只有后者才静默跳过。`userId != null` 的判断是防御性的
     （正常调用路径 `userId` 不会是 `null`，但保持和 `PromotionCalculationService` 里
     `userId.equals(...)` 的写法呼应，这里反过来写 `!userId.equals(...)` 是为了在 `userId` 为
     `null` 时不误伤——虽然实际不会发生，写法上更安全）。
  2. **`OrderService.java`** 的 Step 10b 里，把
     ```java
     couponService.markUsed(couponId, orderId);
     ```
     改成
     ```java
     couponService.markUsed(couponId, orderId, userId);
     ```
     （`userId` 是 `createOrder(Long userId, CreateOrderRequest request)` 的方法参数，本来就在作用域内，
     不需要新增变量）。**只改这一个调用点的实参**，其余 Step 10b 逻辑（`try/catch`、外层 `if` 判断）
     不动。
  3. **`CouponServiceTest.java`** 配合改：找到 `markUsed` 相关的测试（大致会有"设置 USED 状态"、
     "找不到券抛异常"这两类），把调用点从 `couponService.markUsed(userCouponId, orderId)` 改成
     `couponService.markUsed(userCouponId, orderId, someUserId)`（对于"应该成功核销"的用例，传入
     跟 fixture 里 `userCoupon.getUserId()` 一致的值；对于"找不到券"的用例，传入任意值即可，因为
     还没走到归属检查那一步就已经抛了 `ResourceNotFoundException`）。另外补一个新用例验证非本人
     券被跳过：
     ```java
     @Test
     @DisplayName("markUsed: does NOT consume a coupon that belongs to another user")
     void testMarkUsed_notOwned_skipped() {
         // userCoupon belongs to (fixture's) owner. A create-order request from a
         // different user that lists this userCouponId must never burn it.
         when(userCouponRepository.findById(userCouponId)).thenReturn(Optional.of(userCoupon));

         couponService.markUsed(userCouponId, orderId, someOtherUserId);

         verify(userCouponRepository, never()).save(any(UserCoupon.class));
         assertThat(userCoupon.getStatus()).isEqualTo(CouponStatus.AVAILABLE);
     }
     ```
- **验收**:
  - `markUsed(userCouponId, orderId, ownerUserId)`（归属匹配）→ 正常置 `USED`，`save` 被调用一次。
  - `markUsed(userCouponId, orderId, someOtherUserId)`（归属不匹配）→ `save` **不会**被调用，券
    `status` 保持 `AVAILABLE`，方法**不抛异常**（静默返回）。
  - `markUsed(不存在的Id, orderId, anyUserId)` → 仍然抛 `ResourceNotFoundException`（这一步的行为
    不因本卡改动而变化）。
  - 端到端：用户 A 下单时在 `couponIds` 里混入用户 B 的 `userCouponId`（且订单本身因为 A 自己的
    其他券/满减产生了 `discountAmount>0`）→ 订单创建成功，但 B 的券
    `GET /api/v1/promotions/coupons/my`（B 登录查询）里状态仍是 `AVAILABLE`，没有被消耗。
- **勿犯**: 不要把"找不到券"也改成静默跳过——只有"券存在但不属于我"才静默跳过，"券根本不存在"
  仍然是 `ResourceNotFoundException`（调用方传了个野 ID，这是调用方的错，该报错）。不要忘记同步改
  `OrderService.java` 的调用点——只改 `CouponService.markUsed` 签名而不改调用方会导致**编译错误**
  （`code/ecommerce-order` 编译不过，`mvn install -DskipTests` 整体失败，比"没修好这个 bug"后果
  严重得多）。不要在这一层再加金额相关的校验（比如"这张券对本单的折扣贡献是否为正"）——这不是
  本条 finding 的范围，`PromotionCalculateResponse` 目前也没有回传"计算阶段实际应用了哪些券"这个
  字段，做金额级别的核销校验需要跨模块 DTO 变更，属于 `findings.md` 里明确标注"已识别但因改动面
  更大暂缓"的项，不要在本卡顺手做。
