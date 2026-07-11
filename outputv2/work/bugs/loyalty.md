# B15 · loyalty — 积分赚取/抵扣汇率 · 冻结-过期 · 等级

本文件覆盖 `findings.md`「loyalty 模块（§6.9）」11 项中的 9 项，加上第三轮深审·模块内 的 #1、#2
（积分汇率两个 bug），合计 **11 张卡（LOY-1..LOY-11）**。§6.9 原表的 #2（监听本模块影子
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
- **跨模块接线（LOY-10~11）**：订单创建成功后真正调用 `redeemPoints` 扣减积分（**改动文件在
  order 模块，与 `order.md §B`/B04"order-pricing"批次的声明范围重叠**，卡片里给了查重步骤）、
  评价奖励积分读运行时配置。

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
    失败，重则每单积分双扣，必须回退到只剩一份；不管走的是本卡还是 B04/ORD-B8，终态都是这 4 处）。
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
