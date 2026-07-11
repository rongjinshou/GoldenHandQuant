# B17 · review — 评价链路 / 审核冲突语义 / 敏感词

本文件覆盖 findings.md「review 模块（§6.10）」全部 6 项中的 4 项，外加「第二轮深审」#23/#24/#25、
「第三轮深审·跨领域」#4，共 **8 张卡（REV-1..REV-8）**。

**执行前提**：`work/bugs/README.md` 的批次表把本文件排在 `B16 · S2-events.md §B`（跨模块监听器
网络）**之后**执行——REV-1 的"购买 + 签收"校验（13 §2 前提 3：订单状态为 DELIVERED 或
COMPLETED）依赖 B16 新增的"订单送达推进"监听器把已签收订单推进到 DELIVERED。若 B16 尚未执行或
被跳过，黑盒链路里订单会停在 SHIPPED，REV-1 生效后创建评价必被拒（实测会稳定打掉
`pub014_createReview` 并触发整批回滚）。脱离批次顺序单独跑本文件前，先确认订单侧的送达推进
监听器已存在：`grep -rn "ShipmentDeliveredEvent" code/ecommerce-order/src/main/`。

**范围排除（不在本文件，已跳过）**：§6.10 #3（事件缺 orderId/productId 字段）与 #4（发布方发的是
review 模块自己的 `ReviewApprovedEvent` 影子类，非 loyalty 监听的 common 包权威类）——这两项的修复
本质是**事件类定义本身**（字段补齐 + 类迁移到 `ecommerce-common` + 删除模块内影子类/`ReviewApprovedEventListener`），
归 `S2-events.md`。按 `README.md` 的批次顺序，`S2-events.md §A`（B13）先于本文件（B17）执行，
下面几张卡在描述"现状"时仍如实按**未修复的原始代码**描述（此时事件类还是 review 模块自己的 2 参数影子类），
但"改法"对涉及事件的部分做了顺序无关的表述，不论 B13 是否已跑都适用。

**跨卡协作说明**：REV-1、REV-2、REV-4、REV-6 都会改到
`ReviewService.java` 的 `createReview()`/`appendReview()`/构造函数，但四张卡分别落在方法体内**互不重叠**
的代码区域（购买校验在方法开头新插入一段、重复评价校验、敏感词分支、事件发布收尾各占一块），可按任意顺序
逐张应用，互不冲突；构造函数的参数增减（REV-1 加 `OrderQueryService`、REV-2 删 `DomainEventPublisher`）
两张卡都写了"若对方已先应用怎么办"，同样顺序无关。REV-6 依赖 `ConflictException(String code, String message)`
双参构造函数，该构造函数由 `S1-quick-wins.md`（B01）新增，B01 先于 B17 执行，本文件内不重复给出。

**测试提示（不计分，但建议顺手改，避免模块自测变红）**：`ReviewServiceTest.java`、
`ReviewModerationServiceTest.java`、`SensitiveWordFilterTest.java`、`AdminReviewControllerTest.java`
里 mock 的协作者类型、注入的依赖、部分异常类型断言会因为下面的生产代码改动而需要同步调整（例如
`ReviewServiceTest` 需要把 mock 从 `DomainEventPublisher` 换成 `OrderQueryService`）。这些文件在
`code/` 下允许修改且不计入评分。

---

### REV-1 | 评价创建从不校验购买+签收，未购买也能评价

- 风险: high（批次顺序敏感——实测曾因执行前提未满足打掉 pub014 触发整批回滚） · 置信度: definite
- **文件**: `code/ecommerce-review/src/main/java/com/ecommerce/review/service/ReviewService.java`
- **现状**: `createReview()`（第60行起）校验评分范围后直接查重复评价、过滤敏感词、建实体保存——
  全程没有调用 `OrderQueryService.verifyPurchase`。该接口在 order 模块早已存在
  （`OrderQueryService.verifyPurchase(Long userId, Long productId)` 返回 `VerifyPurchaseResponse`，
  `isPurchased()` 方法已就绪），`ecommerce-review/pom.xml` 也已声明 `ecommerce-order` 依赖，
  但 `ReviewService` 从未注入/调用它——未购买、未签收的商品也能被评价。
- **期望**: 用户必须已购买该商品且订单状态为 DELIVERED 或 COMPLETED 才能评价；不满足应抛
  `REVIEW_PURCHASE_REQUIRED`（403）。依据: design-docs/13 §2（评价前提第2-3条："用户通过订单服务
  验证已购买该商品"/"订单状态为 DELIVERED 或 COMPLETED"；第1条"用户已登录"由 Spring Security 保证，
  不在本卡范围）、README §7（`REVIEW_PURCHASE_REQUIRED` | 403）。
- **改法**:
  1. 构造函数新增 `OrderQueryService orderQueryService` 参数与对应类字段 `private final
     OrderQueryService orderQueryService;`（新增 import `com.ecommerce.order.query.OrderQueryService`、
     `com.ecommerce.order.dto.VerifyPurchaseResponse`）。目标最终构造函数（若 REV-2 卡已移除
     `DomainEventPublisher eventPublisher`，在其基础上加本参数；若尚未移除，先不动 `eventPublisher`
     相关代码，只加本参数——两卡各自只负责一个参数的增/删，互不冲突）：
     ```java
     public ReviewService(ReviewRepository reviewRepository,
                          ReviewAppendRepository reviewAppendRepository,
                          SensitiveWordFilter sensitiveWordFilter,
                          OrderQueryService orderQueryService) {
         this.reviewRepository = reviewRepository;
         this.reviewAppendRepository = reviewAppendRepository;
         this.sensitiveWordFilter = sensitiveWordFilter;
         this.orderQueryService = orderQueryService;
     }
     ```
  2. 在 `createReview()` 第62-65行的评分校验之后、第67行起的重复评价校验之前，插入：
     ```java
     VerifyPurchaseResponse purchase = orderQueryService.verifyPurchase(userId, request.getProductId());
     if (purchase == null || !purchase.isPurchased()) {
         throw new AuthorizationException("REVIEW_PURCHASE_REQUIRED",
                 "You must purchase and receive this product before reviewing it");
     }
     ```
     新增 import `com.ecommerce.common.exception.AuthorizationException`（若 REV-5 卡已加，勿重复加）。
  3. `purchase == null` 必须按"未购买"处理，不可 NPE（`verifyPurchase` 的实现细节不在本卡控制范围，
     防御性判空即可）。
- **验收**: 对未购买/未签收商品发起评价，返回 403、`code=REVIEW_PURCHASE_REQUIRED`，且
  `reviewRepository.save` 从未被调用；对已购买且订单 DELIVERED 的商品正常创建，状态为
  PENDING_REVIEW；可用 Mockito 断言 `verify(orderQueryService).verifyPurchase(eq(userId), eq(productId))`
  确实发生了调用。
- **勿犯**:
  1. **本卡是 `pub014_createReview` 的敏感点**。若本批 verify 回滚且失败用例是 pub014
     （评价创建被 403 拒），根因几乎必然是**执行前提未满足**——B16 的"订单送达推进"监听器
     缺失时，黑盒链路里订单停在 SHIPPED，永远到不了 13 §2 要求的 DELIVERED。正确处理：核对
     文件头部的执行前提、确认 B16 已固化后再重开本批；**绝不允许**删除或放宽本卡的
     购买+签收校验来"让测试通过"——那直接违背 13 §2 前提 1–3，隐藏用例必挂。
  2. `verifyPurchase(userId, request.getProductId())` 保持**原样透传**，不要"改进"成按 skuId
     匹配、也不要顺手改 order 侧 `OrderQueryServiceImpl.verifyPurchase` 的匹配实现——那是
     order 模块的既定行为（黑盒基准以它为准），不在本卡范围。

---

### REV-2 | 提交评价时就发布 ReviewApprovedEvent，审核通过又发一次，被拒的评价也已抢先发过

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-review/src/main/java/com/ecommerce/review/service/ReviewService.java`
- **现状**: `createReview()` 保存评价后、返回前（第99行）无条件执行
  `eventPublisher.publish(new ReviewApprovedEvent(this, saved.getId(), userId));`——不管这条评价最终
  会不会通过管理员审核，**提交那一刻**就先发布了一次事件。`ReviewModerationService.approve()`
  （第63行）审核通过时又发布一次。结果：一条评价被批准会触发两次 `ReviewApprovedEvent`（loyalty
  侧监听器可能重复发放积分）；一条最终被拒绝的评价，其实在提交阶段就已经发布过一次（`reject()`
  本身不发布，问题根源在 `createReview()` 抢先发）。
- **期望**: `ReviewApprovedEvent` 只应在管理员审核**通过**时发布一次；提交评价、审核拒绝都不应发布。
  依据: design-docs/13 §3（审核流程：提交→敏感词过滤→PENDING_REVIEW→管理员审核→**审核通过后**→
  发布 ReviewApprovedEvent→积分服务发放奖励）、design-docs/附录D §5。
- **改法**: 只改 `ReviewService.java`；`ReviewModerationService.approve()` 里已有的那次发布调用保留
  不动（其构造参数由 `S2-events.md` 事件卡负责改造，本卡不碰）。若发布调用行已被 B13/EVT-A6 第5步
  先行删除（`grep -n "eventPublisher" code/ecommerce-review/src/main/java/com/ecommerce/review/service/ReviewService.java`
  零命中即是），本卡已完成，跑一遍下方验收通过即可，勿再改动。
  1. 删除第99行整行 `eventPublisher.publish(new ReviewApprovedEvent(this, saved.getId(), userId));`。
     无论此时 `ReviewApprovedEvent` 是本模块 `com.ecommerce.review.event` 下的影子类（2参数构造）还是
     已被 S2 事件卡迁到 `com.ecommerce.common.event` 的权威类（多参数构造），本卡只关心"这一行调用
     整体要不要存在"——答案是不要，整行删除即可，不需要先弄清楚它当前的构造参数长什么样。
  2. 删除不再使用的字段 `private final DomainEventPublisher eventPublisher;`、构造参数
     `DomainEventPublisher eventPublisher`、构造函数体内对应赋值 `this.eventPublisher = eventPublisher;`，
     以及第3行 import `com.ecommerce.common.event.DomainEventPublisher`。第13行
     `import com.ecommerce.review.event.ReviewApprovedEvent;` 若仍在（说明 S2 卡尚未执行），一并删除；
     若已经被 S2 卡替换成 `com.ecommerce.common.event.ReviewApprovedEvent` 的 import，那不是本卡引入的
     import，不用管它。
  3. 若 REV-1 卡已经把构造函数加了 `OrderQueryService orderQueryService` 参数，删除 `eventPublisher`
     后保留该参数不动——两卡叠加后，构造函数最终应恰好 4 个参数
     （`reviewRepository`、`reviewAppendRepository`、`sensitiveWordFilter`、`orderQueryService`）。
- **验收**: `createReview()` 方法体内不再出现 `ReviewApprovedEvent`/`eventPublisher`/
  `DomainEventPublisher` 字样；对同一条评价，从提交到审核通过的整个流程里
  `eventPublisher.publish(...)` 只被调用一次，且只发生在 `ReviewModerationService.approve()` 内部；
  `reject()` 全程（含之前的提交阶段）都不会触发该事件发布。

---

### REV-3 | 敏感词匹配用完全相等，应为包含匹配

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-review/src/main/java/com/ecommerce/review/service/SensitiveWordFilter.java`
- **现状**: `containsSensitiveWord()`（第31-42行）用 `sw.getWord().equals(content)` 判断命中——只有
  整条评价内容与某个敏感词**逐字完全相等**才算命中；`filter()`（第50-61行）同样先
  `sw.getWord().equals(result)` 判相等才替换。只要评价内容在敏感词前后多写一个字，就完全绕过过滤。
- **期望**: 采用包含（子串）匹配——评价内容中任意位置出现敏感词即命中/替换。依据: design-docs/13 §3
  （"敏感词过滤采用包含匹配：只要评价内容包含任一敏感词……不得只做完全相等匹配"）。
- **改法**:
  1. `containsSensitiveWord()`：方法开头加 `if (content == null) { return false; }`；把
     `if (sw.getWord().equals(content))` 改为 `if (content.contains(sw.getWord()))`。
  2. `filter()`：方法开头加 `if (content == null) { return null; }`；把
     ```java
     for (SensitiveWord sw : words) {
         if (sw.getWord().equals(result)) {
             result = result.replace(sw.getWord(), "***");
         }
     }
     ```
     改为去掉 `equals` 判断，对每个敏感词无条件替换（`String.replace` 本身会替换全部出现，不需要
     额外判断"是否命中"再替换）：
     ```java
     for (SensitiveWord sw : words) {
         result = result.replace(sw.getWord(), "***");
     }
     ```
- **验收**: 敏感词库含 `"badword"` 时，`containsSensitiveWord("this contains badword here")` 返回
  `true`；`filter("badword and badword again")` 结果为 `"*** and *** again"`（两处出现都被替换，
  不只是第一处）；`containsSensitiveWord(null)`/`filter(null)` 不抛 NPE。

---

### REV-4 | 命中敏感词直接抛异常丢弃请求，评价从未落库为 REJECTED 终态

- 风险: low · 置信度: suspicious
- **文件**: `code/ecommerce-review/src/main/java/com/ecommerce/review/service/ReviewService.java`
- **现状**: `createReview()` 第74-78行，命中敏感词直接
  `throw new BusinessException("SENSITIVE_CONTENT", "Your review contains prohibited content");`——
  整条评价（评分、商品、订单等全部合法字段）连同其一起被丢弃，从未写入 `reviews` 表。
  `appendReview()` 第127-131行的追评敏感词命中同样直接抛异常丢弃追评内容。评价状态机
  （design-docs/13 §4：PENDING_REVIEW / APPROVED / REJECTED / HIDDEN）里没有"请求直接被拒、
  连记录都不存在"这一种落地方式。
- **期望**: 命中敏感词不应丢弃请求——评价应正常落库，但状态直接为 `REJECTED`（而非
  `PENDING_REVIEW`），内容用过滤后（`***` 替换）的版本保存；未命中则正常进入
  `PENDING_REVIEW`，任何情况下都不允许自动落成 `APPROVED`。依据: design-docs/13 §3
  ("只要评价内容包含任一敏感词，即不得直接进入 APPROVED，应进入 PENDING_REVIEW 或 REJECTED")、
  附录C reviews.status。追评（`ReviewAppend`）本身没有独立于 `Review` 的审核状态字段
  （design-docs/13 §4 的四态只定义给 Review），命中敏感词按同一条"不得丢弃请求"的原则处理为
  遮蔽后照常保存，不追加单独状态机。
- **改法**:
  1. `createReview()`：把第74-78行的
     ```java
     if (sensitiveWordFilter.containsSensitiveWord(request.getContent())) {
         throw new BusinessException("SENSITIVE_CONTENT",
                 "Your review contains prohibited content");
     }
     ```
     改为只记录命中结果、不抛异常：
     ```java
     boolean sensitiveHit = sensitiveWordFilter.containsSensitiveWord(request.getContent());
     ```
     其后 `String filteredContent = sensitiveWordFilter.filter(request.getContent());` 保留不动。
     第91行 `review.setStatus(ReviewStatus.PENDING_REVIEW);` 改为按命中结果分支：
     ```java
     if (sensitiveHit) {
         review.setStatus(ReviewStatus.REJECTED);
         review.setReviewedAt(LocalDateTime.now());
         review.setReviewerResponse("Automatically rejected: content contains prohibited words");
     } else {
         review.setStatus(ReviewStatus.PENDING_REVIEW);
     }
     ```
     （`LocalDateTime` 已有 import，不需新增。）
  2. `appendReview()`：删除第127-131行整个 if 块
     ```java
     if (sensitiveWordFilter.containsSensitiveWord(request.getContent())) {
         throw new BusinessException("SENSITIVE_CONTENT",
                 "Your append contains prohibited content");
     }
     ```
     只保留其后的 `String filteredContent = sensitiveWordFilter.filter(request.getContent());`
     （直接遮蔽即可，不再前置校验+抛异常丢弃）。
  3. 本卡依赖 REV-3 卡：`containsSensitiveWord`/`filter` 必须先改成包含匹配，这里的分支才可能被
     真正命中过的内容触发（若 REV-3 尚未应用，本卡的分支逻辑本身仍然正确，只是暂时只对"内容与
     敏感词完全相等"的极端情况生效）。
- **验收**: 内容含敏感词的评价提交后返回 200/201（不是 400），响应体 `status=REJECTED`、
  `content` 为 `***` 替换后的版本，且确实经 `reviewRepository.save` 落库；干净内容的评价
  `status=PENDING_REVIEW`，绝不是 `APPROVED`；追评命中敏感词后 `appended=true` 且追评内容被遮蔽，
  请求本身不再返回 400。

---

### REV-5 | 非本人追评抛 400（BusinessException("FORBIDDEN")），应为 403

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-review/src/main/java/com/ecommerce/review/service/ReviewService.java`
- **现状**: `appendReview()` 第117-120行，非评价本人追评时
  `throw new BusinessException("FORBIDDEN", "You can only append to your own reviews");`。
  `code` 字段是 `FORBIDDEN`，但普通 `BusinessException` 统一走 `GlobalExceptionHandler` 的兜底
  `@ExceptionHandler(BusinessException.class)`，映射固定 400——`code=FORBIDDEN` 却返回 400，
  与语义自相矛盾（`FORBIDDEN` 应为 403）。
- **期望**: 非本人操作应抛 403。依据: design-docs/03 §2（`AuthorizationException` 对应 401/403）、
  README §7（`FORBIDDEN` | 403）。
- **改法**: 把
  ```java
  throw new BusinessException("FORBIDDEN",
          "You can only append to your own reviews");
  ```
  改为
  ```java
  throw AuthorizationException.forbidden("You can only append to your own reviews");
  ```
  `AuthorizationException.forbidden(String message)` 是 common 模块已有的静态工厂方法（返回码固定
  `FORBIDDEN`），直接可用，不需要改 `GlobalExceptionHandler`——它对非 `CODE_UNAUTHORIZED` 的
  `AuthorizationException` 已经统一映射 403。新增 import `com.ecommerce.common.exception.AuthorizationException`
  （若 REV-1 卡已加，勿重复添加）。
- **验收**: 用户 A 对用户 B 的评价发起追评，返回 403、`code=FORBIDDEN`；评价作者本人追评仍然正常
  成功（不影响其后 `REVIEW_NOT_APPROVED` 分支的既有行为）。

---

### REV-6 | 重复提交评价 / 对非 PENDING_REVIEW 状态重复审核，应 409 而非 400

- 风险: low · 置信度: likely
- **文件**:
  1. `code/ecommerce-review/src/main/java/com/ecommerce/review/service/ReviewService.java`
  2. `code/ecommerce-review/src/main/java/com/ecommerce/review/service/ReviewModerationService.java`
- **现状**:
  - `ReviewService.createReview()` 第67-72行，同一 `(userId, orderItemId)` 已存在评价时
    `throw new BusinessException("DUPLICATE_REVIEW", "You have already reviewed this order item");`
    → 落到通用 `BusinessException` 处理器，400。
  - `ReviewModerationService.approve()` 第47-50行、`reject()` 第79-82行，对当前状态已经不是
    `PENDING_REVIEW`（即已 APPROVED / REJECTED / HIDDEN）的评价再次调用审核，都
    `throw new BusinessException("INVALID_REVIEW_STATUS", "Only PENDING_REVIEW reviews can be
    approved/rejected, current status: " + review.getStatus());` → 400。
  - 评价状态机（design-docs/13 §4，四态 PENDING_REVIEW/APPROVED/REJECTED/HIDDEN）合法迁移只有两条：
    `PENDING_REVIEW → APPROVED`、`PENDING_REVIEW → REJECTED`。对处于非 `PENDING_REVIEW` 状态的评价
    再次 approve/reject，属于**状态冲突**，不是入参格式错误；重复提交评价属于**重复请求**，同样不是
    参数校验问题。
- **期望**: 重复提交评价、审核状态冲突统一 409。依据: README §7（`CONFLICT` | 409「状态冲突或重复
  请求」）、design-docs/03 §2（`ConflictException` = 409）。
- **改法**（三处都只是把异常类型从 `BusinessException` 换成 `ConflictException`，`code` 字符串与
  `message` 原样保留）：
  1. `ReviewService.createReview()`：`new BusinessException("DUPLICATE_REVIEW", ...)` →
     `new ConflictException("DUPLICATE_REVIEW", ...)`。新增 import
     `com.ecommerce.common.exception.ConflictException`。
  2. `ReviewModerationService.approve()`：`new BusinessException("INVALID_REVIEW_STATUS", ...)` →
     `new ConflictException("INVALID_REVIEW_STATUS", ...)`。
  3. `ReviewModerationService.reject()`：同上。
  4. `ReviewModerationService.java` 改完后该文件不再直接使用 `BusinessException`（原本仅这两处用到），
     新增 import `com.ecommerce.common.exception.ConflictException`，可以顺手删掉现在多余的
     `import com.ecommerce.common.exception.BusinessException;`——留着也不影响编译，非强制。
  - **前置依赖**：`ConflictException` 需要 `(String code, String message)` 双参构造函数——这是
    `S1-quick-wins.md`（B01 批次）已新增的构造函数，B01 先于本文件（B17）执行，正常情况下无需在本卡
    重复处理；如果发现 `ConflictException` 只有单参构造函数（说明 B01 尚未落地），先补上
    `public ConflictException(String code, String message) { super(code, message); }` 再回来做本卡。
- **验收**: 同一 `(userId, orderItemId)` 重复提交评价，第二次返回 409、`code=DUPLICATE_REVIEW`；
  对已是 APPROVED（或 REJECTED/HIDDEN）的评价再次调用 `/approve` 或 `/reject`，返回 409、
  `code=INVALID_REVIEW_STATUS`；首次对处于 PENDING_REVIEW 状态的评价审核仍然 200 正常通过/拒绝
  （合法迁移路径不受影响）。

---

### REV-7 | sensitive_words 表恒为空，敏感词过滤算法正确也永不触发（新增 SensitiveWordSeeder）

- 风险: high · 置信度: definite
- **文件**: `code/ecommerce-review/src/main/java/com/ecommerce/review/config/SensitiveWordSeeder.java`
  【新增】
- **现状**: 全仓库没有任何地方向 `sensitive_words` 表写入初始数据——`SensitiveWordRepository` 只有
  基础 `JpaRepository` 方法，没有管理接口，也没有启动播种逻辑。哪怕 REV-3 卡把匹配算法从"完全相等"
  改成了"包含匹配"，`sensitiveWordRepository.findAll()` 在任何环境下都返回空列表，过滤器实际永远不会
  命中任何内容——算法本身修对了，但因为词表是空的，功能整体仍然从未生效过。
- **期望**: 应用启动时，若 `sensitive_words` 表为空，自动播种一份默认敏感词列表；表非空则跳过
  （幂等，且不覆盖后续可能维护的数据）。依据: design-docs/13 §3（敏感词过滤是评价提交的强制步骤，
  隐含"词表必须非空才有意义"）。
- **改法**: 新增类 `com.ecommerce.review.config.SensitiveWordSeeder`，完整骨架如下（与最终验收
  代码逐字一致，直接照抄）：
  ```java
  package com.ecommerce.review.config;

  import com.ecommerce.review.entity.SensitiveWord;
  import com.ecommerce.review.repository.SensitiveWordRepository;
  import org.slf4j.Logger;
  import org.slf4j.LoggerFactory;
  import org.springframework.boot.ApplicationRunner;
  import org.springframework.context.annotation.Bean;
  import org.springframework.context.annotation.Configuration;

  import java.util.List;

  @Configuration
  public class SensitiveWordSeeder {

      private static final Logger log = LoggerFactory.getLogger(SensitiveWordSeeder.class);

      private static final List<String> DEFAULT_WORDS = List.of(
              "垃圾产品", "假货", "骗子", "傻逼", "妈的");

      @Bean
      public ApplicationRunner sensitiveWordSeedRunner(SensitiveWordRepository sensitiveWordRepository) {
          return args -> {
              if (sensitiveWordRepository.count() > 0) {
                  return;
              }
              for (String word : DEFAULT_WORDS) {
                  SensitiveWord entity = new SensitiveWord();
                  entity.setWord(word);
                  entity.setCategory("DEFAULT");
                  sensitiveWordRepository.save(entity);
              }
              log.info("Seeded {} default sensitive words", DEFAULT_WORDS.size());
          };
      }
  }
  ```
  不需要任何 DDL/migration 改动——`sensitive_words` 表已经通过既有 `SensitiveWord` 实体
  （`@Entity @Table(name="sensitive_words")`）由 Hibernate 自动建表，本卡只通过
  `SensitiveWordRepository` 插入数据行，绝不新建/修改表结构。
- **验收**: 全新（空库）启动后，`sensitiveWordRepository.count() > 0`；对含默认词表任一词（如
  "假货"）的评价内容提交，能被过滤器命中（配合 REV-3/REV-4 卡后可观察为落库 `REJECTED`）；同一进程
  内重复触发该 `ApplicationRunner`（或表已非空时再次启动）不会产生重复行，`count()` 保持不变。
- **勿犯**:
  1. 类名、包路径必须与上面骨架逐字一致（`com.ecommerce.review.config.SensitiveWordSeeder`）。
     不要图省事把播种逻辑塞进模块里别的既有 `@Configuration`/`@Component` 类"顺便"加一段
     初始化代码——独立成类，便于单独定位/回滚，也避免和其他配置类的职责混在一起。
  2. 播种逻辑必须挂在 `ApplicationRunner` 上（Spring 容器完全刷新、JPA/Repository 基础设施都已就绪
     之后才执行），不要改成构造函数内联执行或 `@PostConstruct`——这两者可能在 `EntityManager`/事务
     基础设施尚未完全就绪时执行，属于时序风险，与是否用 `@Configuration` 无关。
  3. 必须先判断 `sensitiveWordRepository.count() > 0` 再决定要不要插入——漏掉这个判断会导致每次
     应用重启（非黑盒测试的一次性 H2 场景）都重复插入整份默认词表，而 `SensitiveWord.word` 字段有
     `unique = true` 约束，第二次启动会直接抛 `DataIntegrityViolationException` 导致启动失败。
  4. 不要修改 `SensitiveWord` 实体定义，也不要新增 Flyway/Liquibase 之类的迁移脚本去"建表"——表已
     经由 JPA 自动 DDL 管理，本卡只做数据播种，不碰表结构。

---

### REV-8 | AdminReviewController 的 approve/reject 用 required=true，冻结 ReviewFixture 以空 body 调用会被拒

- 风险: low · 置信度: definite（冻结黑盒 fixture 源码为铁证）
- **文件**: `code/ecommerce-review/src/main/java/com/ecommerce/review/controller/AdminReviewController.java`
- **现状**: `approveReview()`（第43-52行）、`rejectReview()`（第62-71行）都用
  `@Valid @RequestBody ReviewApprovalRequest request`（`@RequestBody` 默认 `required=true`）。
  冻结黑盒测试基础设施 `test-cases/src/test/java/com/ecommerce/blackbox/common/fixture/ReviewFixture.java`
  的 `approveReview`/`rejectReview` 方法调用
  `apiClient.post("/api/v1/admin/reviews/" + reviewId + "/approve", null, headers)`——请求体显式传
  `null`（无 body）。Spring 在 `required=true` 且请求没有 body 时会抛
  `HttpMessageNotReadableException` → 400，而不是契约期望的 200。评价审核→积分奖励这条链路在冻结
  调用约定下整条不可用。
- **期望**: 请求体应为可选；不传 body 时按 `reviewerNote=null` 处理，正常走审核逻辑并返回 200。
  依据: README §6.7（approve/reject 契约响应为 200，未冻结请求体 schema）、design-docs/13 §5
  （REST API 表未定义请求体字段）、冻结 `ReviewFixture`（黑盒调用以 null body 为唯一实际约定，
  没有其他黑盒调用方式）。
- **改法**: 两个方法都把
  ```java
  @Valid @RequestBody ReviewApprovalRequest request
  ```
  改为
  ```java
  @Valid @RequestBody(required = false) ReviewApprovalRequest request
  ```
  （`@Valid` 保留；`request` 为 null 时 `@Valid` 不会触发任何校验，不会因此抛异常）。方法体内所有对
  `request` 字段的直接访问都要做判空：
  - `approveReview()`：删除第48-49行日志里的 `approved={}", ..., request.isApproved()` 片段
    （`request` 可能为 null，直接调用会 NPE），日志改为不引用 `request.isApproved()`；第50行
    `reviewModerationService.approve(reviewId, adminId, request.getReviewerNote())` 改为先算出
    `String reviewerNote = request == null ? null : request.getReviewerNote();`，再传
    `reviewModerationService.approve(reviewId, adminId, reviewerNote)`。
  - `rejectReview()`：同样先算 `String reviewerNote = request == null ? null :
    request.getReviewerNote();`，第67-68行日志与第69行
    `reviewModerationService.reject(reviewId, adminId, request.getReviewerNote())` 里对
    `request.getReviewerNote()` 的引用都换成局部变量 `reviewerNote`。
- **验收**: `POST /api/v1/admin/reviews/{id}/approve` 不带请求体（或 `Content-Length: 0`）调用返回
  200，评价状态变为 `APPROVED`；带正常 `{"approved":true,"reviewerNote":"..."}` 请求体依然 200 且
  `reviewerNote` 生效并被保存；`reject` 同理返回 200 且状态变 `REJECTED`。冻结
  `ReviewFixture.approveReview`/`rejectReview`（null body 调用）能跑通，不再触发 400。
