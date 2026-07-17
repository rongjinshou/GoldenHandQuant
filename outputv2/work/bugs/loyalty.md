# B15 · loyalty — 积分赚取/抵扣汇率 · 冻结-过期 · 等级

本文件覆盖 `findings.md`「loyalty 模块（§6.9）」11 项中的 9 项，加上第三轮深审·模块内 的 #1、#2
（积分汇率两个 bug），再加 Wave-2 契约复核后补的 3 张（LOY-12 取消退积分——**文件清单跨
order/loyalty 两模块，整卡随本批 B15 执行**，由 `order.md` 末尾的 ORD-A22 指针卡防漏；LOY-13/14
响应契约补字段），合计 **14 张卡（LOY-1..LOY-14）**。§6.9 原表的 #2（监听本模块影子
`OrderPaidEvent`）、#3（同理，影子 `ReviewApprovedEvent`）**不在本文件**——两项的修复本质是
"事件权威类迁移到 common + 既有监听器改 `@TransactionalEventListener(AFTER_COMMIT)`/
`@Transactional(REQUIRES_NEW)`/显式 bean 名"，属于事件批（`S2-events.md`，批次 B13/B16），需要
和 logistics 的同名监听器一起处理 bean 名冲突，不适合拆散到各模块文件里各改一半。

四个主题分组：

- **汇率/倍率（LOY-1~4）**：GOLD 倍率写错、赚取积分误用抵扣汇率（放大100倍，本组里唯一
  `definite` 级别、优先级最高）、抵扣侧四个常量可配置化、`estimate-redeem` 端点的汇率与舍入。
  四张卡都改 `LoyaltyPointService.java`/`LoyaltyController.java` 里紧邻的代码区，方法级切分不
  重叠、谁先执行都能收敛到同一终态，但**全部标 high**——都存在"把两个数值相近/命名相近但语义
  完全不同的汇率搞混"的陷阱，每张都配了「勿犯」。
- **年度消费与等级（LOY-5~7）**：拆掉直查 `orders` 表的 `JdbcTemplate`（跨模块违规）、改用测试
  时钟、支付计分前先刷新等级三件事，共享 `OrderDataFetcher`/`LoyaltyAccount`/`MemberLevelService`
  一小簇文件；LOY-7 的调用点要插进事件批负责的监听器文件里，需要跨批协调，卡片里已写明如何在
  不确定那个文件当前状态的情况下安全插入。
- **积分生命周期（LOY-8~9）**：过期批处理（完整定时任务实现，high 风险）与积分冻结（尽调后
  判定"不实现"，low 风险的显式跳过卡，防止有人看着 `frozenPoints` 恒为 0 就自己瞎猜着实现）。
- **跨模块接线（LOY-10~12）**：订单创建成功后真正调用 `redeemPoints` 扣减积分（**改动文件在
  order 模块，与 `order.md §B`/B04"order-pricing"批次的声明范围重叠**，卡片里给了查重步骤）、
  评价奖励积分读运行时配置、订单取消后退还已抵扣积分（LOY-12：loyalty 侧新增幂等
  `refundPointsForOrder` + REFUND 流水，order 侧四条取消路径接线——扣减侧 LOY-10/ORD-B8 的逆操作，
  与 B05 已落地的券/秒杀释放 PROMO-14/15/ORD-A17/A21 同一"取消归还资源"家族）。
- **响应契约字段（LOY-13~14）**：`estimate-redeem` 响应补 `deductedAmount`/`redeemPoints` 两个别名字段、
  `member-level` 响应补 `pointsToNextLevel`——冻结黑盒 fixture 用 `has()` 容错读取、基线一直缺失
  的两个字段，纯增量不动既有字段。

---

### LOY-1 | GOLD 会员倍率写成 1.1（和 SILVER 一样），应为 1.2

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/entity/MemberLevel.java`
- **现状**: 枚举定义（全文件仅24行）第11行：
  ```java
  NORMAL(1.0),
  SILVER(1.1),
  GOLD(1.1),
  PLATINUM(1.5);
  ```
  GOLD 和 SILVER 倍率完全相同，GOLD 会员比 SILVER 会员多消费才升到的等级，计分却毫无优势。
- **期望**: GOLD 倍率应为 `1.2`。依据: `design-docs/12-积分与会员服务设计.md` §5（会员等级表：
  NORMAL 1.0 / SILVER 1.1 / GOLD 1.2 / PLATINUM 1.5）。
- **改法**: 第11行 `GOLD(1.1),` 改为 `GOLD(1.2),`。只改这一个字面量，NORMAL/SILVER/PLATINUM
  三个值本身正确，不要动；阈值（年消费门槛）定义在 `MemberLevelService.java` 里，本卡不涉及。
- **验收**: `MemberLevel.GOLD.getMultiplier()` 返回 `1.2`，且不等于 `MemberLevel.SILVER.getMultiplier()`
  (1.1)。GOLD 会员支付 100.00 元订单，默认配置下（依赖 LOY-2 把赚取汇率修对）应得
  `100 × 1 × 1.2 × 1.0 × 1.0 = 120` 积分；若 LOY-2 还没做，`calcOrderPoints` 仍会按错误的抵扣
  汇率放大到 12000，那是 LOY-2 的职责范围，不代表本卡没生效。

---

### LOY-2 | 订单赚积分误用抵扣汇率 loyalty.redeem-rate(100)，应为赚取汇率 loyalty.points-per-yuan(1)——积分放大约100倍

- 风险: high · 置信度: definite （来源：findings.md 第三轮深审·模块内 #1）
- **文件**: `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/service/LoyaltyPointService.java`
- **现状**: 基线里只有一个常量同时服务"赚取"和"抵扣"两种完全不同的业务含义，第34-35行：
  ```java
  /** 100 points = 1 yuan */
  private static final int POINTS_PER_YUAN = 100;
  ```
  这个"100"本应只是**抵扣兑换比例**（design-docs/12 §3："100 积分 = 1 元"），却在
  `calcOrderPoints()`（第153-163行，赚取积分的核心公式）第158行被直接拿来当**赚取倍率**：
  ```java
  BigDecimal points = amount.multiply(BigDecimal.valueOf(POINTS_PER_YUAN))
          .multiply(levelMultiplier)
          .multiply(BigDecimal.valueOf(activityMultiplier))
          .multiply(BigDecimal.valueOf(configuredActivityMultiplier));
  ```
  design-docs/附录B §1 里赚取汇率 `loyalty.points-per-yuan` 的默认值是 **1**，不是 100；把抵扣
  汇率错当赚取倍率用，导致每笔订单实际发放的积分是设计值的 **100 倍**（100.00 元订单本应得
  100 积分，实际发出 10000 积分）。
- **期望**: 赚取积分必须使用独立的、可运行时覆盖的赚取汇率 `loyalty.points-per-yuan`（默认1），
  与抵扣汇率 `loyalty.redeem-rate`（默认100）完全分开、互不影响。依据: design-docs/12 §2（赚取
  公式"订单实付金额 × 会员等级倍率 × 活动系数"）+ §3（抵扣公式，二者是两个不同汇率）、
  design-docs/附录B §1（`points-per-yuan: 1` / `redeem-rate: 100` 是两个独立配置项）。
- **改法**:
  1. 把第34-35行的常量改名为 `DEFAULT_POINTS_PER_YUAN`（标注它只是抵扣侧兜底值），注释写明
     "不要用于赚取"：
     ```java
     /**
      * Fallback for the REDEEM-side exchange rate (100 points = 1 yuan) when
      * {@code loyalty.redeem-rate} has no runtime override
      * (design-docs/附录B §1: default 100). Used only by pointsPerYuan()
      * for the redeem-ratio cap (12§3) and points→amount conversion.
      */
     private static final int DEFAULT_POINTS_PER_YUAN = 100;
     ```
     该常量后续在 `estimateRedeemPoints()`/`earnPoints()` 里的其余引用改名，统一交给 LOY-3
     处理——本卡不要求你现在就去改那几处，两卡谁先做都行，最终收敛到同一份代码。
  2. 紧邻着新增一个**赚取专用**的常量和私有方法（不要复用抵扣侧的方法/常量）：
     ```java
     /**
      * Fallback for the EARN-side rate ({@code loyalty.points-per-yuan},
      * design-docs/附录B §1: default 1). Per design-docs/12 §2 the earn formula
      * is "实付金额 × 会员等级倍率 × 活动系数" (i.e. 1 point per yuan) — a
      * DIFFERENT rate from the redeem exchange rate above; the two must not be
      * conflated.
      */
     private static final int DEFAULT_EARN_RATE_PER_YUAN = 1;

     /** EARN rate: points awarded per yuan of paid amount (12§2). */
     private int earnRatePerYuan() {
         return RuntimeConfigRegistry.getInt("loyalty.points-per-yuan", DEFAULT_EARN_RATE_PER_YUAN);
     }
     ```
     方法放在类里靠近其它 helper 的位置即可，具体位置不重要。
  3. `calcOrderPoints()` 第158行改为：
     ```java
     BigDecimal points = amount.multiply(BigDecimal.valueOf(earnRatePerYuan()))
     ```
     这是本卡**唯一必须现在就改**的调用点；其余 `POINTS_PER_YUAN`/`MAX_REDEEM_POINTS`/
     `MAX_REDEEM_RATIO`/`DEFAULT_EXPIRE_MONTHS` 引用留给 LOY-3。
- **验收**:
  - NORMAL 会员（倍率1.0），`calcOrderPoints(new BigDecimal("100"), userId, 1.0)` 默认配置下应
    返回 `100`（**不是 10000**）。
  - GOLD 会员（倍率1.2，依赖 LOY-1）同样 100.00 元订单应得 `120`（不是 12000）。
  - `RuntimeConfigRegistry.put("loyalty.points-per-yuan", 10)` 后，NORMAL 会员 100.00 元订单
    应得 `1000` 积分，且**不受** `loyalty.redeem-rate` 的覆盖值影响。
  - `calcOrderPoints()` 方法体内不应再出现 `POINTS_PER_YUAN`/`DEFAULT_POINTS_PER_YUAN` 字样，
    只应出现 `earnRatePerYuan()`。
- **勿犯**: 不要为了省代码让 `earnRatePerYuan()` 直接调用/复用抵扣侧的
  `pointsPerYuan()`/`POINTS_PER_YUAN`——哪怕两者当前默认值一眼就能看出不同（1 vs 100），一旦
  有人图省事把两个方法合并回一个，就是本卡要修的原始 bug 原样复现。两个方法必须各自独立读取
  **不同的配置 key**（`loyalty.points-per-yuan` vs `loyalty.redeem-rate`），谁都不许调用对方。

---

### LOY-3 | 抵扣侧四个常量硬编码，不支持运行时配置覆盖（默认值本身正确）

- 风险: high · 置信度: suspicious （来源：findings.md loyalty §6.9 item 9）
- **文件**: `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/service/LoyaltyPointService.java`
- **现状**: 四个抵扣/过期相关常量是裸的 `private static final` 字面量，全仓库没有一处经过
  `RuntimeConfigRegistry` 读取，管理员 `PUT /api/v1/admin/configs/{key}` 覆盖对积分抵扣完全无效：
  - 第34-35行 `POINTS_PER_YUAN = 100`（抵扣兑换比例）——**同一常量在基线里也被 `calcOrderPoints`
    误用为赚取倍率，那部分由 LOY-2 专门处理，本卡不动 `calcOrderPoints`**。
  - 第37-38行 `MAX_REDEEM_POINTS = 10_000`（单笔订单最多抵扣积分）
  - 第40-41行 `MAX_REDEEM_RATIO = new BigDecimal("0.5")`（最多抵扣订单金额比例）
  - 第43行 `DEFAULT_EXPIRE_MONTHS = 12`（积分有效期月数）

  分别在 `estimateRedeemPoints()`（第62-75行，用前三个）和 `earnPoints()`（第174-199行，第195行
  用第四个）里被直接引用。`RuntimeConfigRegistry.getInt`/`getBigDecimal` 方法本身已存在
  （`code/ecommerce-common/.../test/RuntimeConfigRegistry.java`），不用新增基础设施。
- **期望**: 四项都应支持 `RuntimeConfigRegistry` 运行时覆盖，无覆盖时保持原默认值。依据:
  design-docs/附录B §1（`loyalty.redeem-rate: 100` / `loyalty.max-redeem-points-per-order: 10000`
  / `loyalty.max-redeem-ratio: 0.5` / `loyalty.expire-months: 12`）。
- **改法**: 把四个常量改名为 `DEFAULT_*` 前缀（兜底值），各配一个私有读取方法：
  ```java
  /** Fallback for the REDEEM-side exchange rate... (见 LOY-2 卡关于本常量的说明) */
  private static final int DEFAULT_POINTS_PER_YUAN = 100;
  /** Fallback for the maximum redeemable points per order (design-docs/附录B §1: default 10,000). */
  private static final int DEFAULT_MAX_REDEEM_POINTS = 10_000;
  /** Fallback for the maximum redeem ratio (design-docs/附录B §1: default 0.5). */
  private static final BigDecimal DEFAULT_MAX_REDEEM_RATIO = new BigDecimal("0.5");
  /** Fallback for the points validity window in months (design-docs/附录B §1: default 12). */
  private static final int DEFAULT_EXPIRE_MONTHS = 12;

  /** REDEEM exchange rate: points that equal one yuan when redeeming (12§3). */
  private int pointsPerYuan() {
      return RuntimeConfigRegistry.getInt("loyalty.redeem-rate", DEFAULT_POINTS_PER_YUAN);
  }
  private int maxRedeemPoints() {
      return RuntimeConfigRegistry.getInt("loyalty.max-redeem-points-per-order", DEFAULT_MAX_REDEEM_POINTS);
  }
  private BigDecimal maxRedeemRatio() {
      return RuntimeConfigRegistry.getBigDecimal("loyalty.max-redeem-ratio", DEFAULT_MAX_REDEEM_RATIO);
  }
  private int expireMonths() {
      return RuntimeConfigRegistry.getInt("loyalty.expire-months", DEFAULT_EXPIRE_MONTHS);
  }
  ```
  三处调用点改为走这些方法。`estimateRedeemPoints()` 第68-74行：
  ```java
  int ratioCapped = orderAmount.multiply(BigDecimal.valueOf(pointsPerYuan()))
          .multiply(maxRedeemRatio())
          .setScale(0, RoundingMode.DOWN)
          .intValue();
  return Math.min(Math.min(available, maxRedeemPoints()), ratioCapped);
  ```
  `earnPoints()` 第195行：
  ```java
  tx.setExpiresAt(SystemClockService.now().plusMonths(expireMonths()));
  ```
- **验收**:
  - `RuntimeConfigRegistry.put("loyalty.max-redeem-points-per-order", 500)`，可用积分50000、
    订单金额1000元 → `estimateRedeemPoints` 返回 `500`（不设覆盖时是 `min(50000,10000,50000)=10000`）。
  - `RuntimeConfigRegistry.put("loyalty.max-redeem-ratio", "0.1")`，可用积分50000、订单金额100元
    → `estimateRedeemPoints` 返回 `1000`（100×100×0.1）。
  - `RuntimeConfigRegistry.put("loyalty.expire-months", 1)`，`SystemClockService` 固定在
    2026-01-01 → `earnPoints(...)` 后交易的 `expiresAt` 应为 `2026-02-01`（不是默认的 2027-01-01）。
  - 不设任何覆盖时，三个方法行为与修复前完全一致（100/10000/0.5/12）。
  - `LoyaltyPointService.java` 里裸的 `POINTS_PER_YUAN` 标识符应清零（只应剩 `DEFAULT_POINTS_PER_YUAN`
    和 `pointsPerYuan()`）。
- **勿犯**: 不要把 `pointsPerYuan()` 接回 `calcOrderPoints()`（赚取积分公式）——那正是 LOY-2 要
  修的原始 bug（用抵扣汇率当赚取倍率）。两个方法读取两个不同的配置 key，任何"合并成一个方法
  省代码"的重构冲动都会让 LOY-2 的修复失效。

---

### LOY-4 | estimate-redeem 抵扣金额硬编码 /100 且用 DOWN 舍入，不随配置变化

- 风险: high · 置信度: definite （来源：findings.md 第三轮深审·模块内 #2）
- **文件**:
  1. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/service/LoyaltyPointService.java`（新增方法）
  2. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/controller/LoyaltyController.java`（改调用点）
- **现状**: `LoyaltyController.estimateRedeem()`（第71-87行，`POST /api/v1/loyalty/points/estimate-redeem`）
  第78-79行把"积分转金额"的换算写死在 controller 里：
  ```java
  BigDecimal redeemAmount = BigDecimal.valueOf(actual)
          .divide(BigDecimal.valueOf(100), 2, java.math.RoundingMode.DOWN);
  ```
  两个问题：① 除数字面量 `100` 不读任何配置，管理员覆盖 `loyalty.redeem-rate` 后这个接口算出
  的金额和 `LoyaltyPointService` 内部（LOY-3 落地后）用的汇率对不上；② 用 `RoundingMode.DOWN`，
  design-docs/03§1 要求金额舍入统一 `HALF_UP`。
- **期望**: 积分转金额换算集中到 `LoyaltyPointService` 一处（复用 LOY-3 的 `pointsPerYuan()`），
  并用 `HALF_UP`。依据: design-docs/12§3（"抵扣金额 = 实际可用积分 / 兑换比例"，示例1：10000积分
  →100元）、design-docs/03§1（HALF_UP）。
- **改法**:
  1. 在 `LoyaltyPointService.java` 新增一个 `public` 方法（放在 LOY-3 的 `pointsPerYuan()` 附近）：
     ```java
     /**
      * Convert redeemed points to the equivalent deduction amount using the
      * configurable redeem exchange rate (12§3: 抵扣金额 = 实际可用积分 / 兑换比例)
      * and HALF_UP rounding to the cent (03§1).
      */
     public BigDecimal pointsToAmount(int points) {
         if (points <= 0) {
             return BigDecimal.ZERO;
         }
         return BigDecimal.valueOf(points)
                 .divide(BigDecimal.valueOf(pointsPerYuan()), 2, RoundingMode.HALF_UP);
     }
     ```
     如果 LOY-3 还没执行、`pointsPerYuan()` 尚不存在，本卡可以先内联 `RuntimeConfigRegistry.getInt(
     "loyalty.redeem-rate", 100)`，等 LOY-3 落地后自然收敛成调用同一方法——但**不要**图省事直接写
     `RuntimeConfigRegistry.getInt("loyalty.points-per-yuan", 1)`，那是 LOY-2 的赚取汇率 key，读错
     key 会让抵扣金额变成"积分数÷1"，比例错100倍。
  2. `LoyaltyController.java` 第78-79行改为：
     ```java
     BigDecimal redeemAmount = loyaltyPointService.pointsToAmount(actual);
     ```
     删掉旧的两行 `.divide(...)` 计算。
- **验收**:
  - 默认配置：`actual=500` 积分 → `redeemAmount=5.00`（500/100；默认汇率100整除任何积分数到2位
    小数必然精确，DOWN 和 HALF_UP 在默认配置下结果永远一致，看不出舍入差异——差异要在下面的
    覆盖场景里才能观察到）。
  - 覆盖场景（验证读配置而非硬编码）：`RuntimeConfigRegistry.put("loyalty.redeem-rate", 50)` 后，
    `pointsToAmount(200)` 应为 `4.00`（200/50）；**修复前**的硬编码实现会算成 `2.00`（200/100，
    无视覆盖），是明显可观测的差异。
  - 覆盖场景（验证 HALF_UP，需要不能整除的汇率才能看出舍入分歧）：`RuntimeConfigRegistry.put(
    "loyalty.redeem-rate", 6)` 后，`pointsToAmount(10)` → `10÷6=1.6666...`，`HALF_UP` 到分应为
    `1.67`；若误用 `DOWN` 会得到 `1.66`。
  - `LoyaltyController.java` 里不应再出现 `RoundingMode.DOWN`。
- **勿犯**: `pointsToAmount()` 的除数必须来自**抵扣汇率** `loyalty.redeem-rate`（默认100），绝不
  是 `loyalty.points-per-yuan`（默认1，那是 LOY-2 的赚取汇率）——两个 key 名字都含"points"/"yuan"
  字样、极易看错。写完务必对照上面"覆盖场景"里 `redeem-rate=50 → 200点=4.00元` 这个例子手工验
  一遍，如果算出来是 `200.00`（200/1），说明读错了 key。

---

### LOY-5 | 会员等级年消费统计用 JdbcTemplate 直查 orders 表，违反跨模块访问规则

- 风险: high · 置信度: definite （来源：findings.md loyalty §6.9 item 5）
- **文件**:
  1. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/repository/OrderDataFetcher.java`（重写）
  2. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/entity/LoyaltyAccount.java`（新增字段）
- **现状**: `OrderDataFetcher`（全文件39行）直接注入 `JdbcTemplate`，对 `orders` 表跑原始 SQL
  （第27-37行）：
  ```java
  public BigDecimal getAnnualConsumption(Long userId) {
      LocalDate startOfYear = LocalDate.now().withDayOfYear(1);
      return jdbcTemplate.queryForObject(
              "SELECT COALESCE(SUM(payable_amount), 0) FROM orders"
              + " WHERE user_id = ?"
              + " AND status IN ('PAID', 'SHIPPED', 'DELIVERED', 'COMPLETED')"
              + " AND paid_at >= ?",
              BigDecimal.class,
              userId,
              startOfYear);
  }
  ```
  design-docs/02§3 第4条明令"禁止跨模块直接注入对方 Repository 或直接查询对方表"；`orders`
  表属于 order 模块，loyalty 手写 SQL 直查，是最直白的违反。
- **期望**: 年度消费统计必须改走合规路径。依据: design-docs/02§3、design-docs/12§5（"会员等级
  统计需要订单累计消费数据时…必须通过 OrderQueryService、订单销售统计接口或公开的本地查询契约
  获取"）。
- **改法**: **不要**直接注入 `OrderQueryService`——`ecommerce-order/pom.xml` 已经依赖
  `ecommerce-loyalty`（下单要调 `LoyaltyCommandService`，见 LOY-10），如果 `ecommerce-loyalty/pom.xml`
  反过来依赖 `ecommerce-order`，两模块互相依赖，Maven reactor 编译直接失败。改用"本地查询契约"
  方案：loyalty 本来就会收到每一笔 `OrderPaidEvent`（design-docs/附录D§2），与其查时读表，不如
  把收到的支付金额自己攒成按年滚动的合计，存进 `loyalty_account` 自己的表。
  1. `LoyaltyAccount.java`：在 `annualConsumption` 字段（约第45-46行）后新增：
     ```java
     @Column(name = "consumption_year")
     private Integer consumptionYear;
     ```
     配标准 getter/setter（`getConsumptionYear()`/`setConsumptionYear(Integer)`）。
  2. `OrderDataFetcher.java` 整体重写：构造器不再要 `JdbcTemplate`，改要同模块已有的
     `LoyaltyAccountRepository`（`findByUserId` 已存在，不用新增）：
     ```java
     private final LoyaltyAccountRepository accountRepository;

     public OrderDataFetcher(LoyaltyAccountRepository accountRepository) {
         this.accountRepository = accountRepository;
     }

     public BigDecimal getAnnualConsumption(Long userId) {
         return accountRepository.findByUserId(userId)
                 .map(this::currentYearConsumption)
                 .orElse(BigDecimal.ZERO);
     }

     @Transactional
     public void recordPayment(Long userId, BigDecimal paidAmount) {
         if (userId == null || paidAmount == null) {
             return;
         }
         LoyaltyAccount account = accountRepository.findByUserId(userId)
                 .orElseGet(() -> createAccount(userId));

         BigDecimal current = currentYearConsumption(account);
         account.setAnnualConsumption(current.add(paidAmount));
         account.setConsumptionYear(SystemClockService.now().getYear());
         accountRepository.save(account);
     }

     private BigDecimal currentYearConsumption(LoyaltyAccount account) {
         int currentYear = SystemClockService.now().getYear();
         Integer trackedYear = account.getConsumptionYear();
         if (trackedYear == null || trackedYear != currentYear) {
             return BigDecimal.ZERO;
         }
         BigDecimal annual = account.getAnnualConsumption();
         return annual == null ? BigDecimal.ZERO : annual;
     }

     private LoyaltyAccount createAccount(Long userId) {
         LoyaltyAccount account = new LoyaltyAccount();
         account.setUserId(userId);
         account.setTotalPoints(0);
         account.setAvailablePoints(0);
         account.setFrozenPoints(0);
         account.setRedeemedPoints(0);
         account.setExpiredPoints(0);
         account.setMemberLevel(MemberLevel.NORMAL);
         account.setAnnualConsumption(BigDecimal.ZERO);
         return accountRepository.save(account);
     }
     ```
     需要 `import`：`com.ecommerce.common.test.SystemClockService`、
     `com.ecommerce.loyalty.entity.{LoyaltyAccount,MemberLevel}`、
     `org.springframework.transaction.annotation.Transactional`；删掉不再用的
     `org.springframework.jdbc.core.JdbcTemplate`、`java.time.LocalDate`。
  3. `recordPayment(userId, paidAmount)` 需要在每次订单支付成功时被调用一次——接线属于 LOY-7
     （`MemberLevelService.recordPaymentAndEvaluate`）的职责，本卡只负责把 `recordPayment` 方法
     准备好、可独立单测，不要求现在就找调用方接线。
- **验收**（可参照 kb 测试 `OrderDataFetcherTest` 的用例设计）：
  - 无账户：`getAnnualConsumption(userId)` 返回 `BigDecimal.ZERO`。
  - 同年：账户 `annualConsumption=3000`、`consumptionYear=2026`，固定时钟 2026-06-01 → 返回 `3000`。
  - 跨年（陈旧数据）：账户 `annualConsumption=25000`、`consumptionYear=2025`，固定时钟 2026-01-15
    → 返回 `ZERO`（不能把去年额度带到今年）。
  - `recordPayment`：同年账户已有 `1000`，`recordPayment(userId, 500)` 后应存成 `1500`，
    `consumptionYear` 仍为当前年。
  - `recordPayment` 跨年：账户 `annualConsumption=25000`/`consumptionYear=2025`，固定时钟
    2026-01-05，`recordPayment(userId, 200)` 后应存成 `200`（**不是** 25200）。
  - `recordPayment` 账户不存在时应新建（`memberLevel=NORMAL`、`annualConsumption`=本次金额）。
  - `OrderDataFetcher.java` 不应再出现 `JdbcTemplate`/`LocalDate.now`。
- **勿犯**:
  1. 不要给 `ecommerce-loyalty/pom.xml` 加 `ecommerce-order` 依赖去直接注入 `OrderQueryService`——
     `ecommerce-order` 已依赖 `ecommerce-loyalty`（LOY-10），反向加依赖会形成 Maven 模块环，
     reactor 编译直接失败，且这类错误往往要等 `mvn install` 全量构建才暴露。
  2. 年份翻转判断必须用"存的 `consumptionYear` 是否等于当前年"，不能用"距今是否超过365天"之类
     的近似——自然年边界（1月1日）和"365天前"是两回事。
  3. `createAccount` 必须把其它两处账户初始化（`LoyaltyPointService.createDefaultAccount`、
     `MemberLevelService.getOrCreateAccount`）同样出现的六个字段全部初始化，`memberLevel` 是
     引用类型，漏设会导致后续任何读 `getMultiplier()` 的地方 NPE。

---

### LOY-6 | 年度消费统计用 LocalDate.now() 而非 SystemClockService，测试时钟覆盖不生效

- 风险: low · 置信度: suspicious （来源：findings.md loyalty §6.9 item 10）
- **文件**: `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/repository/OrderDataFetcher.java`
- **现状**: 基线第28行 `LocalDate startOfYear = LocalDate.now().withDayOfYear(1);`——用的是 JDK
  墙上时钟，不是全仓库黑盒测试用来做时间穿越的 `SystemClockService`
  （design-docs/03§5、`com.ecommerce.common.test.SystemClockService`）。
- **期望**: 涉及"现在是哪一年"的判断一律经 `SystemClockService.now()`。依据: design-docs/03§5
  （黑盒隔离与测试时钟）。
- **改法**: 这一处和 LOY-5 是**同一个方法、同一次重写**——LOY-5 给出的 `OrderDataFetcher.java`
  目标代码（`currentYearConsumption()`/`recordPayment()`）已经全部改用
  `SystemClockService.now().getYear()`，不再有任何 `LocalDate.now()`。若 LOY-5 已执行，本卡不需
  要额外改动，只需按下面验收单独确认；若只想单独做这一条而不做 LOY-5 的整体重写，最小改法是把
  第28行替换成 `SystemClockService.now().toLocalDate().withDayOfYear(1)`（需
  `import com.ecommerce.common.test.SystemClockService;`）——但这样 LOY-5 的 JdbcTemplate 直查表
  问题原样保留，不推荐只做一半。
- **验收**: `SystemClockService.setFixed(LocalDateTime.of(2026, 1, 15, 0, 0))` 后，跨年判断（见
  LOY-5 验收的"跨年"用例）必须生效；`OrderDataFetcher.java` 不应再出现 `LocalDate.now`。

---

### LOY-7 | 会员等级只在查询 /member-level 时重算，支付时不刷新，可能用旧等级倍率算分

- 风险: high · 置信度: suspicious （来源：findings.md loyalty §6.9 item 11）
- **文件**:
  1. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/service/MemberLevelService.java`（新增组合方法）
  2. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/event/OrderPaidEventListener.java`（接线调用点，见改法第二段）
- **现状**: `evaluateAndUpgrade(Long userId)`（第52-78行）是唯一的等级重算入口，全仓库只有
  `LoyaltyController.getMemberLevel()`（`GET /api/v1/loyalty/member-level`，第122-123行注释
  "Re-evaluate before returning to keep level current"）调用它。真正会让等级变化的地方——用户
  支付成功那一刻——完全没有调用它：用户这笔支付把年消费从 4900 冲到 5100（跨过 GOLD 的 5000
  门槛），但**这笔支付本身**的积分仍按旧的 SILVER 倍率（1.1）计算，只有下次手动查
  `/member-level` 等级才会更新——已发放的积分不会补算。
- **期望**: 支付成功、发放积分之前，必须先按这笔支付更新年消费并重新评级，让这笔支付本身也
  享受/受限于刚跨过的新等级。依据: design-docs/12§2（"订单积分 = 订单实付金额 × 会员等级倍率
  × 活动系数"，隐含"用的是计分那一刻的等级"）、design-docs/12§5。
- **改法**: 新增一个组合方法，"记账"与"评级"绑定、顺序固定为先记账后评级：
  ```java
  /**
   * Records a newly paid order against the user's running annual
   * consumption (via {@link OrderDataFetcher#recordPayment}) and then
   * immediately re-evaluates their member level.
   *
   * @param userId     the user ID
   * @param paidAmount the order's paid amount
   * @return the new (or unchanged) membership level
   */
  @Transactional
  public MemberLevel recordPaymentAndEvaluate(Long userId, BigDecimal paidAmount) {
      orderDataFetcher.recordPayment(userId, paidAmount);
      return evaluateAndUpgrade(userId);
  }
  ```
  放在 `evaluateAndUpgrade` 前面即可（`OrderDataFetcher orderDataFetcher` 字段已是既有依赖，
  不用新增注入）。**本方法依赖 LOY-5 新增的 `OrderDataFetcher.recordPayment(...)`**——LOY-5
  未做的话这里编译不过，先做 LOY-5。

  要让它真正生效，还需要在"订单支付成功、发放积分之前"的入口调用它，且必须在计分
  （`calcOrderPoints`）**之前**。这个入口是
  `com.ecommerce.loyalty.event.OrderPaidEventListener.onOrderPaid(...)`。该文件的事件类型迁移
  （从 loyalty 本模块影子 `OrderPaidEvent` 切到 `com.ecommerce.common.event.OrderPaidEvent`）和
  事务注解（`@TransactionalEventListener(AFTER_COMMIT)` + `@Transactional(REQUIRES_NEW)`）是另
  一批卡片（事件批）的职责，不属于本卡——本卡只要求：不管那个文件此刻长什么样，在它现有
  `onOrderPaid(...)` 方法体 try 块最开头（调用 `loyaltyPointService.calcOrderPoints(...)` 之前）
  插入一行：
  ```java
  memberLevelService.recordPaymentAndEvaluate(event.getUserId(), event.getPaidAmount());
  ```
  **插入前先看 try 块里有没有兜底行**：若 try 块内已有 `memberLevelService.evaluateAndUpgrade(...)`
  调用（B13/EVT-A4 在 `recordPaymentAndEvaluate` 尚不存在时插入的临时兜底），用上面这行新调用
  **替换**该兜底行，而不是并存插入（并存=同一笔支付双重评级）；若无兜底行则按上述位置插入。
  如果该事件类当时还是 loyalty 本模块的影子类（事件批卡片尚未执行），取支付金额的 getter 可能
  叫 `event.getPayableAmount()` 而非 `event.getPaidAmount()`——按当时实际能编译通过的 getter 名
  取值即可，字段名本身不是本卡职责。同时该监听器构造器需要能拿到 `MemberLevelService`（若还没
  注入，加一个构造器参数）。
- **验收**:
  - 单测（对照 kb `MemberLevelServiceTest.testRecordPaymentAndEvaluate_recordsThenEvaluates`）：
    `recordPaymentAndEvaluate(userId, new BigDecimal("6000"))`，mock
    `orderDataFetcher.getAnnualConsumption(userId)` 返回 `6000` → 结果应为 `MemberLevel.GOLD`；
    用 `InOrder` 校验 `recordPayment` 先于 `getAnnualConsumption`（即先于 `evaluateAndUpgrade`
    内部读取）被调用。
  - 端到端：NORMAL 会员（年消费0）本次支付 6000.00 元，若等级在计分前刷新，本次积分应按 GOLD
    倍率(1.2，依赖LOY-1)计算 = `6000×1×1.2=7200`；若像修复前那样计分时仍用旧的 NORMAL 倍率
    (1.0)，会算出 `6000`——用这个数值差直接判断修复是否生效。
  - `GET /api/v1/loyalty/member-level` 在这笔支付完成后应立即返回 GOLD，不需要额外一次"唤醒"
    调用。
- **勿犯**:
  1. `recordPaymentAndEvaluate` 内部两行顺序不能颠倒——必须先 `recordPayment` 把这笔钱记进年
     消费，再 `evaluateAndUpgrade` 读取"含本笔在内的最新年消费"来评级；先评级再记账，这笔支付
     永远不会影响它自己触发的等级判定，等于没修。
  2. 不要在本卡顺带修改 `OrderPaidEventListener` 的事件类型导入、
     `@EventListener`/`@TransactionalEventListener`/`@Transactional` 注解或 bean 名——那些是事件
     批的职责，本卡只新增一行方法调用；抢先改这些注解容易和事件批的卡片相互覆盖，产生冲突的
     中间态。
  3. 调用点必须在 `calcOrderPoints(...)` **之前**，不是之后、也不是并列在 catch 块外——插错
     位置起不到"让这笔支付享受新等级"的效果。

---

### LOY-8 | 积分过期是空实现，也没有任何定时任务

- 风险: high · 置信度: definite （来源：findings.md loyalty §6.9 item 4）
- **文件**:
  1. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/service/PointsExpireService.java`（重写）
  2. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/entity/PointsTransaction.java`（新增字段）
  3. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/repository/PointsTransactionRepository.java`（新增查询方法）
- **现状**: `PointsExpireService`（全文件24行）：
  ```java
  public void expire() {
      log.info("PointsExpireService.expire() called");
  }
  ```
  只打一行日志，不扫描、不扣减、不记录，也没有 `@Scheduled`——不管是每月自动跑还是通过
  `POST /api/v1/admin/loyalty/points/expire`（`AdminLoyaltyController` 已正确接了这个端点，不用
  改）手动触发，实际效果都是"什么都没发生"。`PointsTransaction` 实体（`expiresAt` 字段第45-46行
  已存在，`earnPoints()` 已在发放积分时写入"12个月后"的过期时间）没有任何"是否已处理过期"的标
  记，`PointsTransactionRepository`（仅15行）也没有按过期时间查询的方法。
- **期望**: 每月1号凌晨自动扫描已过期且未处理的 EARN 流水，按用户分组，扣减对应积分（不能扣成
  负数）、记一条 EXPIRE 流水。依据: design-docs/12§4（"积分有效期为12个自然月。每月1号凌晨系统
  批量扫描过期积分，将过期积分扣减并记录日志。积分抵扣时不得使用已过期积分"）。
- **改法**:
  1. `PointsTransaction.java`：在 `expiresAt` 字段（约第45-46行）后新增：
     ```java
     /**
      * Whether this EARN transaction's points have already been processed by
      * PointsExpireService. Prevents the monthly expiry scan from
      * re-processing the same earn batch twice. Irrelevant for non-EARN types.
      */
     @Column(nullable = false)
     private boolean expired;
     ```
     配 `isExpired()`/`setExpired(boolean)`（boolean 的 getter 惯例是 `isExpired`，不是
     `getExpired`）。
  2. `PointsTransactionRepository.java`：新增（需要 `import com.ecommerce.loyalty.entity.PointsTransactionType;`、
     `java.time.LocalDateTime`、`java.util.List`）：
     ```java
     List<PointsTransaction> findByTypeAndExpiredFalseAndExpiresAtLessThanEqual(
             PointsTransactionType type, LocalDateTime cutoff);
     ```
  3. `PointsExpireService.java` 整体重写（构造器改注入 `LoyaltyAccountRepository` 和
     `PointsTransactionRepository`，均是已有 repository）：
     ```java
     @Scheduled(cron = "0 0 0 1 * *")
     @Transactional
     public void expire() {
         LocalDateTime cutoff = SystemClockService.now();
         List<PointsTransaction> expirable = transactionRepository
                 .findByTypeAndExpiredFalseAndExpiresAtLessThanEqual(PointsTransactionType.EARN, cutoff);

         if (expirable.isEmpty()) {
             log.info("PointsExpireService.expire(): no expirable points found as of {}", cutoff);
             return;
         }

         Map<Long, List<PointsTransaction>> byUser = expirable.stream()
                 .collect(Collectors.groupingBy(PointsTransaction::getUserId));

         byUser.forEach(this::expireForUser);
     }

     private void expireForUser(Long userId, List<PointsTransaction> earnTransactions) {
         LoyaltyAccount account = accountRepository.findByUserId(userId).orElse(null);
         if (account == null) {
             earnTransactions.forEach(tx -> tx.setExpired(true));
             transactionRepository.saveAll(earnTransactions);
             return;
         }

         int totalEligible = earnTransactions.stream().mapToInt(PointsTransaction::getAmount).sum();
         int toExpire = Math.min(totalEligible, account.getAvailablePoints());

         earnTransactions.forEach(tx -> tx.setExpired(true));
         transactionRepository.saveAll(earnTransactions);

         if (toExpire <= 0) {
             return;
         }

         account.setAvailablePoints(account.getAvailablePoints() - toExpire);
         account.setTotalPoints(account.getTotalPoints() - toExpire);
         account.setExpiredPoints(account.getExpiredPoints() + toExpire);
         accountRepository.save(account);

         PointsTransaction expireTx = new PointsTransaction();
         expireTx.setUserId(userId);
         expireTx.setType(PointsTransactionType.EXPIRE);
         expireTx.setAmount(-toExpire);
         expireTx.setBalance(account.getAvailablePoints());
         expireTx.setBizType("POINTS_EXPIRE");
         expireTx.setDescription("Points expired: " + toExpire + " points past the validity window");
         expireTx.setExpired(true);
         transactionRepository.save(expireTx);
     }
     ```
     需要的 import：`com.ecommerce.common.test.SystemClockService`、
     `com.ecommerce.loyalty.entity.{LoyaltyAccount,PointsTransaction,PointsTransactionType}`、
     `com.ecommerce.loyalty.repository.{LoyaltyAccountRepository,PointsTransactionRepository}`、
     `org.springframework.scheduling.annotation.Scheduled`、
     `org.springframework.transaction.annotation.Transactional`、`java.time.LocalDateTime`、
     `java.util.{List,Map}`、`java.util.stream.Collectors`。`@EnableScheduling` 已经在
     `ShopHubApplication` 上，不用新增，`@Scheduled` 直接生效。
- **验收**（对照 kb 测试 `PointsExpireServiceTest` 的四个场景）：
  - 无到期流水：`expire()` 不调用任何 `save`/`saveAll`。
  - 单笔到期：账户可用积分5000、总积分5000，一笔1200的EARN流水已过期 → 扣完后可用积分
    `3800`、总积分`3800`、`expiredPoints`累加`1200`，该EARN流水`isExpired()`变`true`，另生成
    一条金额`-1200`、余额`3800`的EXPIRE流水。
  - 封顶场景：账户可用/总积分只剩300（早先1000中的700已被抵扣消费掉），一笔1000的EARN流水到
    期 → 扣减必须封顶在`300`，`availablePoints`变`0`，`expiredPoints`加`300`（不是1000）。
  - 同一用户多笔EARN同时到期：400+600两笔都到期，账户可用积分10000 → 两笔都标记
    `isExpired()=true`，账户可用积分扣减`1000`（400+600之和）变`9000`。
  - `expire()` 方法上 `@Scheduled` 的 `cron` 属性必须是 `"0 0 0 1 * *"`（每月1日00:00，Spring
    6段格式：秒 分 时 日 月 周）。
  - `POST /api/v1/admin/loyalty/points/expire` 端到端调用后效果同上（`AdminLoyaltyController`
    不用改）。
- **勿犯**:
  1. 扣减必须 `Math.min(totalEligible, account.getAvailablePoints())` 封顶，不能让可用积分变
     负——即使这批到期流水加总超过当前余额（说明一部分早被抵扣消费掉了，design-docs/12§4 明确
     "积分抵扣时不得使用已过期积分"，已经花掉的不能再扣一次）。
  2. 不管最终有没有真的扣减，被扫描到的这批 EARN 流水都必须整体 `saveAll` 标记
     `expired=true`——否则下个月扫描会重复捞到同一批流水。
  3. 找不到账户时（理论上不应发生，防御性分支）同样要标记流水为已处理并直接返回，不要抛异
     常——`expire()` 是定时任务，抛异常不会导致数据损坏，但会让这批流水永远卡在"未处理"反复
     重试失败。
  4. `@Scheduled(cron = "0 0 0 1 * *")` 是 Spring 6 段格式（秒 分 时 日 月 周），不是 Unix
     crontab 的5段格式——不要写成 `"0 0 1 * *"`。

---

### LOY-9 | 积分冻结（frozenPoints）完全无实现——本卡结论：不实现，保持现状

- 风险: low · 置信度: suspicious （来源：findings.md loyalty §6.9 item 6）
- **文件**: 不改动任何文件。
- **现状**: `LoyaltyAccount.frozenPoints` 字段全仓库只在创建账户时被显式设成 `0`
  （`LoyaltyPointService.createDefaultAccount`、`MemberLevelService.getOrCreateAccount`、LOY-5
  新增的 `OrderDataFetcher.createAccount` 三处），此后**没有任何代码路径**会让它变化——没有
  "冻结"方法，没有"解冻"方法。`LoyaltyController.getPoints()` 会把它读出来放进
  `PointsResponse.frozenPoints` 字段（恒为0）返回，仅此而已。
- **期望/尽调结论**: design-docs/12§1 模块职责列表写了"积分与会员服务负责积分赚取、积分抵扣、
  积分冻结、积分过期、会员等级…"，把"积分冻结"列为职责之一，但通篇 design-docs/12 其余章节
  （§2~§6）**没有任何一处**具体说明冻结的触发场景、解冻条件、或与退款/售后流程的联动规则——不
  像"过期"有 §4 整节的具体算法（LOY-8 已实现）。design-docs/08/09/14（订单/支付/发票结算）三
  份文档同样找不到只字提及"积分冻结"，24个公开黑盒用例也没有一个断言 `frozenPoints` 非零。
  **本条最终判定为"先确认触发场景，再实现"，评估后不实现**——猜错触发条件引入的行为，比"保持
  恒为0"风险更高（例如：如果错误地在退款申请时就冻结积分，而设计意图其实是退款成功才冻结，会
  让正常退款流程中途多出一段用户看不懂的"积分被冻结"状态）。
- **改法**: **不改**。不要新增冻结/解冻方法，不要在退款/取消/售后任何流程里调用
  `setFrozenPoints`。如果在 payment/order/review 的退款相关卡片里看到"积分冻结"字样、且那些
  卡片给出了具体的冻结触发点，以那些卡片的说明为准；本卡的结论只是"loyalty 模块自身不主动
  发起冻结"。
- **验收**: `grep -rn "setFrozenPoints" code/ecommerce-loyalty/src/main/java` 只应命中三处账户
  初始化（值均为 `0`），不应有新增调用点；`frozenPoints` 在黑盒可观测范围内应始终为 `0`。

---

### LOY-10 | redeemPoints 在 order 创建订单流程里零调用——积分抵扣只估算、从未真正扣减

- 风险: high · 置信度: suspicious （来源：findings.md loyalty §6.9 item 7；**本卡与 `order.md §B`/
  B04"order-pricing"批次的 ORD-B8 是同一修复，按"去重占位卡"执行**——先做改法第 0 步查重，
  另见下方「勿犯」第1条）
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderService.java`
- **现状**: `LoyaltyCommandService`（`code/ecommerce-loyalty/.../query/LoyaltyCommandService.java`）
  定义了 `redeemPoints(Long userId, int points, BigDecimal orderAmount)` 和 `earnPaymentPoints(...)`
  两个命令方法，`LoyaltyPointService` 已正确实现（loyalty 侧代码不需要改）。但基线 `OrderService`
  第84行只注入了 `LoyaltyQueryService loyaltyQueryService`（只读，用于第176-192行 Step 7"计算积
  分抵扣"时估算 `pointsDeductionAmount` 并算进 `payableAmount`），全类没有一处引用
  `LoyaltyCommandService`。也就是说：订单价格计算时"预扣"了积分对应的金额优惠，但从未真正调用
  命令接口把这些积分从用户账户里扣掉——用户 `availablePoints` 永远不变，同一批积分可以在无数笔
  订单里反复"抵扣"，等同于免费打折且无限次数。
- **期望**: 订单创建成功持久化后，如果本次用了积分抵扣，必须调用
  `LoyaltyCommandService.redeemPoints` 真正扣减。依据: design-docs/08§3 步骤7"计算积分抵扣"、§4
  计价公式含"积分抵扣金额"、design-docs/附录A `pointsDeductionAmount` 字段、design-docs/12（积分
  抵扣的两个上限）。`earnPaymentPoints` 不在本卡范围——订单支付成功后的积分**发放**走另一条链
  路（`OrderPaidEvent` → loyalty 自己的监听器，见 LOY-2/LOY-7），`earnPaymentPoints` 这个命令方
  法在修复后的代码里仍然零调用，这是预期状态、不是遗漏，不要额外去接线它。
- **改法**（对照 baseline 第75-260行左右的 `createOrder` 方法）：
  0. **先查重（去重占位步骤，决定后面第 1~3 步做不做）：先执行
     `grep -n "loyaltyCommandService" code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderService.java`
     ——若已有命中（B04/ORD-B8 已接入），本卡即已完成，跑一遍下方验收后跳过本卡，绝不重复插入
     代码块（会造成每单积分双扣）；仅当零命中（B04 被跳过）才继续以下第 1~3 步（即 ORD-B8 的
     等价实现，仅 B04 未执行时适用）。**
  1. 构造器新增一个字段和参数（放在既有 `loyaltyQueryService` 后面即可，具体位置不重要）：
     ```java
     private final com.ecommerce.loyalty.query.LoyaltyCommandService loyaltyCommandService;
     ```
     构造器参数同步加，构造器体加 `this.loyaltyCommandService = loyaltyCommandService;`。
     **执行前先 grep 这个字段是否已经存在**（见「勿犯」第1条）。
  2. Step 7"计算积分抵扣"里，把只在 `if` 块内部声明的局部变量 `prePointsAmount` 提到 `if` 判断
     之前（这样 Step 10b 才能用到它）。基线原文：
     ```java
     BigDecimal pointsDeductionAmount = BigDecimal.ZERO;
     int redeemedPoints = 0;
     if (request.getRedeemPoints() > 0) {
         // Need a preliminary payable amount for points estimation
         BigDecimal prePointsAmount = MonetaryUtil.add(itemTotal, packagingFee);
         prePointsAmount = MonetaryUtil.subtract(prePointsAmount, discountAmount);

         int redeemable = loyaltyQueryService.estimateRedeemPoints(prePointsAmount, userId);
         redeemedPoints = Math.min(request.getRedeemPoints(), redeemable);
         // ...（其余 pointsDeductionAmount 计算不变）
     }
     ```
     改为：
     ```java
     BigDecimal pointsDeductionAmount = BigDecimal.ZERO;
     int redeemedPoints = 0;
     // Preliminary payable amount for points estimation; also passed to
     // loyaltyCommandService.redeemPoints() after the order persists, so its
     // internal cap recomputation uses the exact same base amount.
     BigDecimal prePointsAmount = MonetaryUtil.subtract(
             MonetaryUtil.add(itemTotal, packagingFee), discountAmount);
     if (request.getRedeemPoints() > 0) {
         int redeemable = loyaltyQueryService.estimateRedeemPoints(prePointsAmount, userId);
         redeemedPoints = Math.min(request.getRedeemPoints(), redeemable);
         // ...（其余 pointsDeductionAmount 计算不变，仍是硬编码 /100，见下方说明，本卡不动）
     }
     ```
  3. 在库存预占（baseline 注释"Step 10: Reserve inventory"）之后、发布 `OrderCreatedEvent`
     （baseline 注释"Step 11: Publish OrderCreatedEvent"）之前，插入：
     ```java
     if (redeemedPoints > 0) {
         try {
             loyaltyCommandService.redeemPoints(userId, redeemedPoints, prePointsAmount);
         } catch (Exception e) {
             log.warn("Failed to redeem {} points for user {} on order {}: {}",
                     redeemedPoints, userId, orderId, e.getMessage());
         }
     }
     ```
     如果这段区间已经有其他卡片（促销券核销、秒杀购买记录等）插入的代码，追加在它们后面即
     可，顺序不敏感，只要都夹在 Step 10 和 Step 11 之间。
- **验收**:
  - 用户可用积分5000，下单时请求抵扣 `redeemPoints=2000`、预估基准金额约100元（50%上限=5000，
    10000上限，取min后可抵扣上限5000）→ 实际抵扣 `min(2000,5000)=2000`，订单创建成功后，用户
    `availablePoints` 应变为 `3000`（`5000-2000`），而不是修复前那样恒为 `5000`。
  - 同一批2000积分不能在第二笔订单里重复抵扣满额——第二次下单时 `estimateRedeemPoints` 应该
    已经只看到剩余的 `3000` 可用积分。
  - 积分服务故障（如故障注入）时，订单创建本身仍应成功（try/catch 吞掉异常只警告日志），不
    应该因为积分扣减失败导致整个下单事务回滚。
  - `grep -n "loyaltyCommandService" OrderService.java` 命中字段声明、构造器参数、构造器赋值、
    `redeemPoints(...)` 调用**恰好 4 处**（不多不少——多于 4 处=重复插入，轻则重复构造器参数编译
    失败，重则每单积分双扣，必须回退到只剩一份；不管走的是本卡还是 B04/ORD-B8，终态都是这 4 处。注意：数的是**代码位点**——
    Step 7 附近还有 1 行注释提及 `loyaltyCommandService.redeemPoints()`，`grep` 原始输出会是
    5 行，注释行不计、也不用删；本批随后的 LOY-12 会给调用行追加第 4 个实参 `orderId`，
    同样不改变以上位点数）。
- **勿犯**:
  1. **先查重复**：本卡改的 `OrderService.createOrder` 是 order 模块核心方法，README.md 的批
     次表把"积分抵扣"接线也列进了 B04/`order.md §B`（order-pricing）批次——如果 `order.md` 里
     也有一张功能等价的卡片且已先执行过，本卡描述的字段/构造器参数/Step 10b 代码块可能已经存
     在。执行本卡前先 `grep -n "loyaltyCommandService" OrderService.java`，如果已经命中同样的
     字段+调用，本卡视为已满足，直接跳过，**不要重复插入**（重复的构造器参数会直接编译失败；
     侥幸不重复也会导致同一笔订单积分被扣两次）。
  2. `redeemPoints(...)` 调用必须放在 `orderRepository.save(order)` **之后**（订单已成功落库）
     才允许执行，绝不能挪到价格计算/校验阶段——校验失败的半成品订单绝不能真的扣用户积分（对
     照同一方法里"优惠券标记已用""秒杀购买记录"两处既有代码都遵循"只在订单成功持久化后才消
     费资源"这一模式）。
  3. 必须包 `try/catch` 吞异常（`log.warn`），不能让积分扣减的偶发失败拖累整个下单事务——与
     同一 Step 10b 区间里优惠券核销的写法完全一致，照抄即可。
  4. 不要顺手把 `pointsDeductionAmount` 那行硬编码的 `new BigDecimal("0.01")`（"100点=1元"）改
     成调用 LOY-4 的 `pointsToAmount()`——这处不一致在参考实现最终代码里也**没有**修
     （已用 `grep` 确认该行原样保留），一并改动超出本卡授权范围；如果想修，请作为新发现记录，
     不要在本卡里顺带做。

---

### LOY-11 | 评价奖励积分数硬编码20，不读运行时配置

- 风险: low · 置信度: suspicious （来源：findings.md loyalty §6.9 item 8）
- **文件**: `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/event/ReviewApprovedEventListener.java`
- **现状**: **先看**：若 `ReviewApprovedEventListener` 已被 B13/EVT-A4 整体重写（方法体内已是
  `RuntimeConfigRegistry.getInt("loyalty.review-reward-points", ...)` 赋给局部变量 `rewardPoints`
  的形态），本卡目标已满足——跑一遍下方验收确认后直接跳过；以下现状描述仅适用于 B13 未执行的场景。
  基线第18行 `private static final int REVIEW_REWARD_POINTS = 20;`，`onReviewApproved(...)`
  方法体内（约第33行）直接把这个常量传给 `earnPoints(...)`：
  ```java
  loyaltyPointService.earnPoints(
          event.getUserId(), REVIEW_REWARD_POINTS, "REVIEW",
          event.getReviewId().toString(),
          "Review reward, reviewId=" + event.getReviewId());
  ```
  管理员通过 `PUT /api/v1/admin/configs/loyalty.review-reward-points` 覆盖这个值，对实际发放的
  积分数没有任何效果。
- **期望**: 奖励积分数应支持 `RuntimeConfigRegistry` 覆盖，默认值仍为20。依据:
  design-docs/附录B§1（`loyalty.review-reward-points: 20`）。
- **改法**: **只改 `onReviewApproved` 方法体内部这一处调用**，不要动方法签名、注解
  （`@EventListener`/`@TransactionalEventListener` 等属于事件批职责）或类的其它部分：
  ```java
  int rewardPoints = RuntimeConfigRegistry.getInt(
          "loyalty.review-reward-points", REVIEW_REWARD_POINTS);
  loyaltyPointService.earnPoints(
          event.getUserId(), rewardPoints, "REVIEW",
          event.getReviewId().toString(),
          "Review reward, reviewId=" + event.getReviewId());
  ```
  同时把紧随其后的成功日志（原 `log.info(...REVIEW_REWARD_POINTS...)`）里的
  `REVIEW_REWARD_POINTS` 也换成 `rewardPoints`，避免日志和实际发放数不一致。需要新增
  `import com.ecommerce.common.test.RuntimeConfigRegistry;`。`REVIEW_REWARD_POINTS` 常量本身
  保留不删（仍作为无覆盖时的默认值，也仍有单测通过反射断言其值为20）。
- **验收**:
  - 无覆盖：审核通过一条评价，`earnPoints` 应以 `20` 被调用（行为与修复前一致）。
  - `RuntimeConfigRegistry.put("loyalty.review-reward-points", 50)` 后再触发一次评价审核通过，
    `earnPoints` 应以 `50` 被调用。
  - `ReviewApprovedEventListener.java` 里 `REVIEW_REWARD_POINTS` 常量声明保留1处，方法体内不
    应再直接引用该常量（应引用局部变量 `rewardPoints`）。

---

### LOY-12 | 订单取消后从不退还已抵扣积分——扣减侧（LOY-10/ORD-B8）的逆操作全缺（跨模块整卡）

- 风险: high · 置信度: definite （来源：Wave-2 契约复核·取消资源对称性专项）
- **执行时机（先读这条再动手）**: 本卡是 `order.md` 末尾指针卡 **ORD-A22** 的实体。改动文件跨
  order/loyalty 两模块，但**整卡必须随本批（B15）一次性落地**：order 侧接线引用的
  `refundPointsForOrder` 由本卡第 3~4 步现场新增，早于 B15 单独应用 order 侧改动必编译失败。
  本卡也是本文件内**必须排在 LOY-10 之后执行**的卡（第 5 步要改 LOY-10/ORD-B8 接的那行调用）。
- **文件**（7 个生产 + 3 个测试）:
  1. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/entity/PointsTransactionType.java`
  2. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/repository/PointsTransactionRepository.java`
  3. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/query/LoyaltyCommandService.java`
  4. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/service/LoyaltyPointService.java`
  5. `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderService.java`（1 行实参）
  6. `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderCancelService.java`
  7. `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderTimeoutService.java`
  8. （同步测试）`LoyaltyPointServiceTest.java`、`OrderCancelServiceTest.java`、`OrderTimeoutServiceTest.java`
- **现状**: B04/ORD-B8（或本批 LOY-10）之后，创建订单 Step 10b 已真正调用
  `loyaltyCommandService.redeemPoints(userId, redeemedPoints, prePointsAmount)` 把抵扣积分从用户
  账户扣掉——**扣减发生在下单流程里，而不是支付后**。但四条真正到达 CANCELLED 的取消路径
  （用户取消 CREATED/PAYING、商家审核通过、超时自动取消）无一退还这笔积分：loyalty 全模块没有任何
  refund 方法，`PointsTransactionType` 只有 EARN/REDEEM/EXPIRE/ADJUST，也没有任何
  `OrderCancelledEvent` 监听器补偿。更糟的是 `redeemPoints` 写 REDEEM 流水时 `bizId` 恒为
  null（不记 orderId），loyalty 侧**无从按订单回冲**。结果：用户下单抵扣积分后取消/超时弃单，
  钱没花出去，积分永久蒸发——与 B05 已修复的"券/秒杀名额单向棘轮"（PROMO-14/15/ORD-A17/A21）
  完全同型的资损缺陷，且不可自愈。
- **期望**: 每条到达 CANCELLED 的路径都退还该订单**实际扣减**的积分。依据: design-docs/08 §6
  （取消规则表——取消必须归还订单占用的资源；设计文档没有逐字"退积分"条款，一致性原则依据与
  PROMO-14「期望」的论证完全同构：积分与券/库存同是订单消费的用户资产）+ 08 §3 步骤7/12 §3
  （被回冲的正是这套抵扣规则扣掉的积分）+ design-docs/03（后置动作失败不得回滚主流程）。
  实现要求：**幂等**（按 orderId 查 REDEEM 流水回冲、以 REFUND 流水做重入挡板，重复调用无副作用）、
  **账本权威**（退多少由 loyalty 自己的流水说了算，不信调用方报数）、**永不抛错**（order 侧在取消
  事务里 best-effort 调用，机理同 PROMO-14「勿犯」的事务毒化警告）。
- **改法**（loyalty 侧 1~4，order 侧 5~7，测试 8；顺序执行）:
  1. **`PointsTransactionType.java`**——`REDEEM` 与 `EXPIRE` 之间插入新枚举值（存库为字符串，
     无迁移问题）：
     ```java
     /** Points given back when an order that had redeemed them is cancelled. */
     REFUND,
     ```
  2. **`PointsTransactionRepository.java`**——末尾追加两个派生查询：
     ```java
     /**
      * Find the transactions of a given type recorded against a business id.
      * For REDEEM rows, {@code bizId} is the id of the order that consumed the
      * points — used to reverse that deduction when the order is cancelled.
      *
      * @param type  the transaction type
      * @param bizId the business entity id the transaction references
      * @return the matching transactions (empty if none)
      */
     List<PointsTransaction> findByTypeAndBizId(PointsTransactionType type, String bizId);

     /**
      * Whether a transaction of the given type already references this
      * business id. Idempotency guard for order-cancel refunds: a REFUND row
      * with the order's id means that order's deduction was already given back.
      *
      * @param type  the transaction type
      * @param bizId the business entity id the transaction references
      * @return {@code true} if such a transaction exists
      */
     boolean existsByTypeAndBizId(PointsTransactionType type, String bizId);
     ```
  3. **`LoyaltyCommandService.java`**——`redeemPoints` 追加第 4 个参数 `Long orderId`（javadoc 的
     `@param orderId` 写明"记在 REDEEM 流水上，取消时按它回冲"），并新增：
     ```java
     /**
      * Give back the points a cancelled order had redeemed at creation time.
      *
      * <p>Looks up the REDEEM transaction(s) recorded against {@code orderId}
      * and reverses them: the available/total balances are restored and a
      * REFUND transaction is written. Idempotent — an order whose deduction
      * was already given back, or that never redeemed any points, is a no-op
      * returning 0. Never throws in normal operation: the order module calls
      * this best-effort on its cancellation paths and a refund failure must
      * not block the cancellation itself.
      *
      * @param orderId the cancelled order's id
      * @return the number of points given back (0 if nothing to refund)
      */
     int refundPointsForOrder(Long orderId);
     ```
  4. **`LoyaltyPointService.java`**——加 `import java.util.List;`；`redeemPoints` 签名同步加
     `Long orderId`，写流水处在 `tx.setBizType("ORDER_REDEEM");` 之后插入：
     ```java
     // Record which order consumed the points, so refundPointsForOrder can
     // reverse exactly this deduction if that order is cancelled.
     tx.setBizId(orderId != null ? String.valueOf(orderId) : null);
     ```
     （尾部 `log.info` 建议一并带上 orderId。）然后在 `redeemPoints` 之后新增实现：
     ```java
     /**
      * {@inheritDoc}
      *
      * <p>The refund is derived from the loyalty ledger itself — the REDEEM
      * rows {@link #redeemPoints} recorded with the order's id as
      * {@code bizId} — never from a caller-supplied amount, so it always gives
      * back exactly what was actually deducted. Like the promotion-side
      * {@code releaseForOrder} methods, the body deliberately never throws in
      * normal operation ("no deduction for this order" is a legal empty
      * result): the order module invokes it inside its cancellation
      * transaction, and a refund failure must never block the cancellation.
      */
     @Override
     @Transactional
     public int refundPointsForOrder(Long orderId) {
         if (orderId == null) {
             return 0;
         }
         String bizId = String.valueOf(orderId);

         // Idempotency guard: this order's deduction was already given back.
         if (transactionRepository.existsByTypeAndBizId(PointsTransactionType.REFUND, bizId)) {
             return 0;
         }

         List<PointsTransaction> redeems =
                 transactionRepository.findByTypeAndBizId(PointsTransactionType.REDEEM, bizId);
         int points = redeems.stream().mapToInt(tx -> -tx.getAmount()).sum();
         if (points <= 0) {
             // The order never redeemed any points — a perfectly normal no-op.
             return 0;
         }

         Long userId = redeems.get(0).getUserId();
         LoyaltyAccount account = getAccount(userId);
         account.setAvailablePoints(account.getAvailablePoints() + points);
         account.setRedeemedPoints(Math.max(0, account.getRedeemedPoints() - points));
         account.setTotalPoints(account.getTotalPoints() + points);
         accountRepository.save(account);

         PointsTransaction tx = new PointsTransaction();
         tx.setUserId(userId);
         tx.setType(PointsTransactionType.REFUND);
         tx.setAmount(points);
         tx.setBalance(account.getAvailablePoints());
         tx.setBizType("ORDER_CANCEL_REFUND");
         tx.setBizId(bizId);
         tx.setDescription("Points refunded for cancelled order " + orderId);
         tx.setExpiresAt(null);
         transactionRepository.save(tx);

         log.info("Refunded {} redeemed points to userId={} for cancelled order {}, balance={}",
                 points, userId, orderId, account.getAvailablePoints());
         return points;
     }
     ```
  5. **`OrderService.java`**——Step 10b 的调用行追加实参（LOY-10/ORD-B8 若因故未接线，先按
     LOY-10 改法把 3 实参版本接好再改本步）：
     ```java
     loyaltyCommandService.redeemPoints(userId, redeemedPoints, prePointsAmount, orderId);
     ```
  6. **`OrderCancelService.java`**——加 `import com.ecommerce.loyalty.query.LoyaltyCommandService;`
     （order 模块 pom 已依赖 ecommerce-loyalty，不用动 pom）；字段区加
     `private final LoyaltyCommandService loyaltyCommandService;`，构造函数参数列表末尾**增量追加**
     同名参数并赋值。类末尾（`releasePromotions` 之后）新增：
     ```java
     /**
      * Give back the loyalty points a cancelled order had redeemed at creation
      * time (mirrors the consumption side, {@code OrderService} Step 10b).
      * Same best-effort contract as {@link #releasePromotions}: the refund is
      * idempotent on the loyalty side and a failure is logged and swallowed —
      * it must never block the cancellation itself. Only invoked on paths that
      * actually reach CANCELLED — a PAID order entering CANCEL_REVIEWING keeps
      * its points deduction until the review is approved.
      */
     private void refundLoyaltyPoints(Long orderId) {
         try {
             loyaltyCommandService.refundPointsForOrder(orderId);
         } catch (Exception e) {
             log.warn("Failed to refund redeemed points for cancelled order {}: {}",
                     orderId, e.getMessage());
         }
     }
     ```
     三个调用点，每处紧跟既有的 `releasePromotions(...)` 调用之后（若 B05 被跳过导致
     `releasePromotions` 不存在，锚点改为"库存释放 try/catch 之后、`recordEvent` 之前"）：
     - `cancelCreatedOrder(...)`：
       ```java
       // Give back the loyalty points redeemed by this order
       refundLoyaltyPoints(order.getId());
       ```
     - `cancelPayingOrder(...)`：`orderRepository.save(order)` 之后、`recordEvent` 之前，加（**此路径三判最易被漏，勿用"同上"略写，必须贴字面代码**）：
       ```java
       // Give back the loyalty points redeemed by this order
       refundLoyaltyPoints(order.getId());
       ```
     - `reviewCancel(...)` 的 `approved` 分支：库存释放之后、`recordEvent` 之前，加 `refundLoyaltyPoints(orderId);`（形参本来就叫 `orderId`）。
     `requestPaidOrderCancelReview` 与 `reviewCancel` 驳回分支**不加**（ORD-A17 同款边界）。
     **落地自检**：`grep -c "refundLoyaltyPoints(" OrderCancelService.java` 必须 == 4（1 定义 + 3 调用）；< 4 说明漏了路径，补齐再 verify。
  7. **`OrderTimeoutService.java`**——加同一 import；字段/构造参数**增量追加**
     `LoyaltyCommandService loyaltyCommandService`；`cancelExpiredOrder(...)` 里紧跟
     `releasePromotions(order.getId());`（ORD-A21 所加；若不存在，锚点为库存释放之后）插入：
     ```java
     // Give back the loyalty points redeemed by this order
     refundLoyaltyPoints(order.getId());
     ```
     类末尾（`releasePromotions` helper 之后）新增：
     ```java
     /**
      * Give back the loyalty points an expired order had redeemed at creation
      * time. Same best-effort contract as {@link #releasePromotions}: the
      * refund is idempotent on the loyalty side and a failure is logged and
      * swallowed — it must never block the timeout cancellation itself.
      */
     private void refundLoyaltyPoints(Long orderId) {
         try {
             loyaltyCommandService.refundPointsForOrder(orderId);
         } catch (Exception e) {
             log.warn("Failed to refund redeemed points for expired order {}: {}",
                     orderId, e.getMessage());
         }
     }
     ```
  8. **测试同步（三个文件都要，漏一个则 `install` 的 test-compile 阶段就失败）**:
     - **`LoyaltyPointServiceTest.java`**：`import static org.mockito.Mockito.never;`；两处
       `service.redeemPoints(1L, ..., BigDecimal.valueOf(100))` 调用追加第 4 实参 `900L`；
       `testRedeemPoints_withinLimits_deductsPoints` 的流水断言组末尾加
       ```java
       assertEquals("900", tx.getBizId(),
               "REDEEM transaction should record the consuming order's id for cancel refunds");
       ```
       再新增三个用例（放在 redeemPoints 区块之后）：回冲恢复余额并写 REFUND 流水
       （`existsByTypeAndBizId(REFUND,"900")` 桩 false、`findByTypeAndBizId(REDEEM,"900")` 桩一条
       `amount=-2000` 的流水 → `refundPointsForOrder(900L)` 返回 2000，账户
       available/total +2000、redeemedPoints 归 0，保存的流水 type=REFUND、amount=2000、
       bizType="ORDER_CANCEL_REFUND"、bizId="900"）；重入 no-op（exists 桩 true → 返回 0 且
       零 save）；无抵扣订单 no-op（exists false + find 空列表 → 返回 0 且零 save，**不抛错**）。
     - **`OrderCancelServiceTest.java`**：加 import 与 `@Mock private LoyaltyCommandService
       loyaltyCommandService;`；既有用例逐处补断言——CREATED 取消用例加
       `verify(loyaltyCommandService).refundPointsForOrder(1L);`、PAYING 用例加 `(5L)`、
       `testReviewCancel_approve` 加 `(10L)`、券释放失败用例加 `(1L)`（前一段失败不影响退积分）、
       `testCancel_paidOrder_movesToCancelReviewing` 加
       `verify(loyaltyCommandService, never()).refundPointsForOrder(anyLong());`（审核前不退）。
     - **`OrderTimeoutServiceTest.java`**：加 import 与 `@Mock private LoyaltyCommandService
       loyaltyCommandService;`；把 ORD-A21 加的两个用例扩成终态——
       ```java
       @Test
       @DisplayName("timeout gives back coupons, seckill allocation and redeemed points")
       void testCancelExpiredOrder_releasesPromotionsAndRefundsPoints() {
           orderTimeoutService.cancelExpiredOrder(expiredOrder);

           verify(couponService).releaseForOrder(1L);
           verify(seckillService).releaseForOrder(1L);
           verify(loyaltyCommandService).refundPointsForOrder(1L);
       }

       @Test
       @DisplayName("timeout release/refund failures are swallowed and never block the cancellation")
       void testCancelExpiredOrder_releaseFailureDoesNotBlockCancel() {
           doThrow(new RuntimeException("release boom")).when(couponService).releaseForOrder(1L);
           doThrow(new RuntimeException("refund boom")).when(loyaltyCommandService).refundPointsForOrder(1L);

           orderTimeoutService.cancelExpiredOrder(expiredOrder);

           // The cancellation still completes: order flipped, seckill half still
           // released, event recorded and published despite both failures.
           assertThat(expiredOrder.getStatus()).isEqualTo(OrderStatus.CANCELLED);
           verify(seckillService).releaseForOrder(1L);
           verify(orderService).recordEvent(eq(1L), eq(OrderStatus.CREATED), eq(OrderStatus.CANCELLED),
                   eq("TIMEOUT_CANCEL"), eq("SYSTEM"), anyString());
           verify(eventPublisher).publish(any(com.ecommerce.order.event.OrderCancelledEvent.class));
       }
       ```
- **验收**:
  - 单测：三个测试文件全绿，覆盖"回冲恢复余额、REFUND 流水字段、重入 no-op、无抵扣 no-op、
    四条取消路径都退、CANCEL_REVIEWING 阶段不退、退还失败不阻断取消"。
  - 端到端：用户有 5000 积分，下单抵扣 2000（available 变 3000）→ 取消该订单 →
    `GET /api/v1/loyalty/points` 的 `availablePoints` 回到 5000；再对同一订单重复触发取消相关
    动作，余额仍是 5000（不重复退）；`GET /api/v1/loyalty/points/history` 出现一条
    type=REFUND、amount=+2000 的流水。未用积分的订单取消后余额不变。
  - `grep -n "refundPointsForOrder"`：`LoyaltyCommandService.java`/`LoyaltyPointService.java`/
    `OrderCancelService.java`/`OrderTimeoutService.java` 均命中；`OrderService.java` 的
    `redeemPoints` 调用为 4 实参（`loyaltyCommandService` 的**代码位点**仍是 LOY-10 验收的那
    4 处——调用行只是加实参不加行，注释行照旧不计）。
  - 公开 24 例回归全绿。
- **勿犯**: ①`refundPointsForOrder` 方法体**永不抛错**（"没有这个订单的抵扣流水"是合法空结果，
  没有任何 `orElseThrow`）——order 侧虽有 try/catch，但它是 `@Transactional` 代理 bean，抛
  RuntimeException 会把共享事务标记 rollback-only，取消请求提交时 500（机理同 PROMO-14「勿犯」）。
  ②退还数量只信 loyalty 自己的 REDEEM 流水（`-tx.getAmount()` 求和），**不要**改成读
  `order.redeemedPoints` 传数——调用方报数一旦与账本漂移就会多退/少退。③幂等挡板必须查
  REFUND+bizId，**不要**用"把 REDEEM 行删掉/置负"的方式实现回冲（审计流水只增不改）。
  ④`requestPaidOrderCancelReview`（PAID→CANCEL_REVIEWING）与审核驳回分支绝不退积分——资源随
  订单回到 PAID 原样保留（ORD-A17 同款边界）。⑤REFUND 流水 `expiresAt` 置 null 且**不要**把
  REFUND 掺进 `PointsExpireService` 的 EARN 扫描——过期扫描按"池余额封顶"模型工作，退回的积分
  自然受既有 EARN 批次的过期约束，不需要（也不能）新造一个可过期批次。⑥别忘三个测试文件的
  `@Mock`——`@InjectMocks` 对缺失 mock 注入 null，helper 的 NPE 会被 try/catch 吞掉，用例
  照绿但断言全空转。⑦头部红线依旧：不得借机接线 `OrderLifecycleService` 等死服务。

---

### LOY-13 | estimate-redeem 响应缺 `deductedAmount` 与 `redeemPoints`——冻结 fixture 容错读取的两个别名字段

- 风险: low · 置信度: definite （来源：Wave-2 契约复核·冻结 fixture 反查）
- **文件**:
  1. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/dto/PointsEstimateResponse.java`
  2. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/controller/LoyaltyController.java`
- **现状**: 冻结的 `test-cases/.../LoyaltyFixture.parseRedeemEstimateResult` 从
  `POST /api/v1/loyalty/points/estimate-redeem` 的响应里读三个字段：`redeemAmount`、
  **`deductedAmount`**、`redeemPoints`，全部套 `data.has(...)` 容错守卫。响应 DTO
  `PointsEstimateResponse` 只有 `maxRedeemablePoints`/`actualRedeemPoints`/`redeemAmount`/
  `remainingPoints`——`deductedAmount` 与 `redeemPoints` 都缺失时 fixture 不报错，但解析结果里
  它们恒为 `ZERO`/`0` 初值，任何基于"本次抵扣金额/实抵积分数"的隐藏断言必踩。
- **期望**: 响应补两个别名字段（additive，不删不改既有字段）：`deductedAmount` = 本次估算的抵扣
  金额，恒等于既有 `redeemAmount`（fixture 把两者当同一个量读，`BigDecimal` 同型同值）；
  `redeemPoints` = 本次实抵积分数，恒等于既有 `actualRedeemPoints`（int 同型同值）。依据:
  冻结 fixture 的读取契约 + design-docs/12 §3（抵扣金额 = 实际可用积分 / 兑换比例——`redeemAmount`
  即该公式产物，LOY-4 已接 `pointsToAmount()`）。
- **改法**:
  1. **`PointsEstimateResponse.java`**——字段区末尾（`remainingPoints` 之后）加：
     ```java
     /**
      * The amount this estimate would deduct from the order — always equal to
      * {@link #redeemAmount}. The frozen black-box fixture reads the deduction
      * under this field name, so it is exposed as an additive alias (existing
      * fields are untouched) and must always be populated alongside
      * {@code redeemAmount}, never left null.
      */
     private BigDecimal deductedAmount;

     /**
      * The number of points this estimate would actually redeem — always equal
      * to {@link #actualRedeemPoints}. Same additive-alias rationale as
      * {@link #deductedAmount}: the frozen black-box fixture reads the redeemed
      * count under this field name.
      */
     private int redeemPoints;
     ```
     并在类末尾补标准 getter/setter（`getDeductedAmount`/`setDeductedAmount`、
     `getRedeemPoints`/`setRedeemPoints`）。
  2. **`LoyaltyController.java`**——`estimateRedeem(...)` 组装响应处，`setRedeemAmount` 之后加：
     ```java
     // Alias fields the frozen black-box fixture reads the deduction and the
     // redeemed count under — same values as redeemAmount/actualRedeemPoints,
     // never null.
     resp.setDeductedAmount(redeemAmount);
     resp.setRedeemPoints(actual);
     ```
- **验收**:
  - `POST /api/v1/loyalty/points/estimate-redeem`（orderAmount=100、redeemPoints=2000、用户有
    5000 积分）→ 响应同时含 `"redeemAmount":20.00`、`"deductedAmount":20.00`（两值恒等）与
    `"redeemPoints":2000`（= `actualRedeemPoints`）；`actualRedeemPoints=0` 的边界（如请求
    redeemPoints=0）下金额两者同为 `0`（非 null）、`redeemPoints` 为 `0`。
  - 既有字段名/类型/值全部不变；公开 24 例回归全绿。
  - `grep -qF "private int redeemPoints;" code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/dto/PointsEstimateResponse.java`
    命中（artifacts.tsv B15 断言）。
- **勿犯**: `deductedAmount` **必须恒非空**——Jackson 会把 null 序列化成 JSON null，而 fixture 的
  `has("deductedAmount")` 对显式 null 节点返回 true，随后 `new BigDecimal(asText())` 直接抛
  NumberFormatException，比"缺字段"更糟。两个别名都别算成别的口径（`deductedAmount` 就是
  `redeemAmount` 的别名、`redeemPoints` 就是 `actualRedeemPoints` 的别名——注意响应别名
  `redeemPoints` 与**请求** DTO `PointsEstimateRequest.redeemPoints`（用户想抵多少）不是一个量，
  响应侧必须回显**实抵** `actual`，不要回显请求原值）。不要动 fixture 读取的第三个字段
  `redeemAmount`——它本就存在。

---

### LOY-14 | member-level 响应缺 `pointsToNextLevel`——距下一等级积分数（12 §5 等级表推导）

- 风险: low · 置信度: definite （来源：Wave-2 契约复核·冻结 fixture 反查）
- **文件**:
  1. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/dto/MemberLevelResponse.java`
  2. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/service/MemberLevelService.java`
  3. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/controller/LoyaltyController.java`
  4. （同步测试）`code/ecommerce-loyalty/src/test/java/com/ecommerce/loyalty/service/MemberLevelServiceTest.java`
- **现状**: 冻结的 `LoyaltyFixture.parseMemberLevelResult` 从 `GET /api/v1/loyalty/member-level`
  的响应里读 `level` 和 **`pointsToNextLevel`**（`asInt()`，`has()` 容错）。响应 DTO
  `MemberLevelResponse` 只有 `level`/`levelName`/`multiplier`/`annualConsumption`/
  `nextLevelCondition`——`pointsToNextLevel` 缺失，fixture 解析结果恒为 0 初值，隐藏断言必踩。
- **期望**: 响应补 `pointsToNextLevel`（additive）。取值推导：design-docs/12 §5 等级表以**年消费
  （元）**划档（SILVER 1,000 / GOLD 5,000 / PLATINUM 20,000），12 §2 赚取汇率为 1 积分/元——
  所以"距下一等级还差的积分数"与"距下一档年消费的缺口（元）"是同一个数：
  `下一档门槛 − annualConsumption`，向上取整、下限 0；PLATINUM 已是最高档，恒 0。
- **改法**:
  1. **`MemberLevelResponse.java`**——字段区末尾加（javadoc 写明推导依据，getter/setter 标准补齐）：
     ```java
     /**
      * How far this account still is from the next membership tier, expressed
      * in points. design-docs/12 §5 sets the tier thresholds in annual
      * consumption yuan and §2 sets the earn rate at 1 point per yuan, so the
      * remaining-consumption gap and the remaining-points gap are the same
      * number: {@code nextTierThreshold - annualConsumption}, floored at 0.
      * 0 for PLATINUM (already the highest tier). Read by the frozen
      * black-box fixture under exactly this field name (additive — existing
      * fields are untouched).
      */
     private int pointsToNextLevel;
     ```
  2. **`MemberLevelService.java`**——加 `import java.math.RoundingMode;`，`getOrCreateAccount`
     之前新增 public 方法（**复用类里已有的三个 `*_THRESHOLD` 常量**，别再写字面量）：
     ```java
     /**
      * How many more points the account needs to reach the next membership
      * tier.
      *
      * <p>design-docs/12 §5 defines the tiers by annual consumption
      * (SILVER 1,000 / GOLD 5,000 / PLATINUM 20,000 yuan) and §2 defines the
      * earn rate as 1 point per yuan of paid amount, so the remaining
      * consumption gap and the remaining points gap are the same number:
      * {@code nextTierThreshold - annualConsumption}, rounded up to a whole
      * point and floored at 0. PLATINUM is the highest tier, so its gap is 0.
      *
      * @param level             the account's current member level
      * @param annualConsumption the account's running annual consumption
      *                          ({@code null} is treated as 0)
      * @return the points still needed for the next tier (0 at the top tier)
      */
     public int pointsToNextLevel(MemberLevel level, BigDecimal annualConsumption) {
         BigDecimal nextThreshold;
         switch (level) {
             case NORMAL:
                 nextThreshold = SILVER_THRESHOLD;
                 break;
             case SILVER:
                 nextThreshold = GOLD_THRESHOLD;
                 break;
             case GOLD:
                 nextThreshold = PLATINUM_THRESHOLD;
                 break;
             default:
                 // PLATINUM — already at the highest tier.
                 return 0;
         }
         BigDecimal consumed = annualConsumption != null ? annualConsumption : BigDecimal.ZERO;
         BigDecimal gap = nextThreshold.subtract(consumed);
         if (gap.compareTo(BigDecimal.ZERO) <= 0) {
             return 0;
         }
         return gap.setScale(0, RoundingMode.CEILING).intValue();
     }
     ```
  3. **`LoyaltyController.java`**——`getMemberLevel()` 组装响应处，`setNextLevelCondition` 之后加：
     ```java
     resp.setPointsToNextLevel(
             memberLevelService.pointsToNextLevel(level, account.getAnnualConsumption()));
     ```
  4. **`MemberLevelServiceTest.java`**——`createAccount` 帮助方法之前追加一组用例：
     NORMAL+0 → 1000；SILVER+1200 → 3800；GOLD+6000 → 14000；PLATINUM+50000 → 0；
     NORMAL+1200 → 0（不为负）；NORMAL+999.50 → 1（CEILING 取整）；NORMAL+null → 1000。
- **验收**:
  - 新注册用户（零消费、NORMAL）`GET /api/v1/loyalty/member-level` → `"pointsToNextLevel":1000`；
    年消费 1200 的 SILVER 用户 → `3800`；PLATINUM → `0`。字段恒存在（int 原生类型不可能为 null）。
  - 既有字段全部不变；`MemberLevelServiceTest` 全绿；公开 24 例回归全绿。
- **勿犯**: 阈值**必须**复用 `MemberLevelService` 的三个常量，别在新方法里再写 `1000/5000/20000`
  字面量（一处改配四处漂）。别发明别的口径（比如按 `totalPoints`/`availablePoints` 距离算）——
  等级由**年消费**驱动（12 §5），积分余额与等级无关；换算成"积分数"只因 12 §2 的 1 积分/元汇率，
  这也是唯一有文档依据的整数化路径。取整用 CEILING（"还差多少"语义：差 0.5 元也得再花 1 元），
  已达标或超出一律 0，绝不能出负数。

---

## 附注 · 决策留档（W15-C，第十五轮；只作裁决记录，不改上文任何卡片）

1. **积分取整用 `RoundingMode.DOWN` —— 裁决：维持，不改**。质疑点是 03 §1 规定舍入 `HALF_UP`，
   而积分计算用 DOWN（`LoyaltyPointService.java:86`、`:238`）。裁决理由：03 §1 通篇只约束**金额**
   （"所有金额使用 BigDecimal…金额计算统一规则"，表内场景均为金额/税额/优惠额），**不约束积分这种
   整数计数**；12 §2 的积分公式（`订单积分 = 实付金额 × 等级倍率 × 活动系数`）未规定取整方向，
   向下取整（不奖励未满 1 分的零头）是唯一不多发积分的保守语义，且现状已被黑盒绿灯锚定。注意
   `LoyaltyPointService.java:310` 积分→抵扣金额换算保留 2 位小数用的是 `HALF_UP`——那是金额输出，
   恰好落在 03 §1 的约束面内，两者并不矛盾。**不要**有人再把 `:86/:238` 的 DOWN"统一"成 HALF_UP。
2. **`frozenPoints` ≡ 0 —— 裁决：正式接受，结案**。全套文档只定义了列、没有任何冻结触发场景，
   期望行为文档不可推导；决议全文与依据见 `findings.md` 文末《W15-C 增补》§3。checklist/loyalty.md
   对应 suspicious 条目已同步标注，不再悬置。
