# work/bugs — BUG 卡片库（按执行批次组织）

这是「检查」阶段的全部成果：ShopHub `code/` 与冻结设计（`design-docs/` + `README.md` 契约）之间
**已定位的每一处不一致**，写成可直接执行的修复卡片。12 个模块审查 agent 逐模块比对 + 全系统集成
联调 + 三轮深审，合计 **150+ 项**。你（评测机上的修复 agent）只需照卡片改代码——**发现环节已经
做完，不需要你重新诊断**。

## 术语约定

- **基线 / 未修复的原始代码**：你按 `INSTRUCTION.md` 第①步复制到当前工作目录的 ShopHub 源码
  （`code/`）——就是你打开文件时看到的样子。卡片「现状」描述的行号/代码片段都以它为准；由于
  先执行的批次可能已改过同一文件，遇到行号漂移时以卡片给的**锚点文本**（方法名/变量名/注释）
  定位，不要机械依赖行号。
- **参考实现**：作者侧已实修并通过全部 24 例公开黑盒验证（17+ 次重复独立运行）的最终代码。
  各卡片「改法」给出的目标代码即来自它——**卡片本身就是你的唯一真相源**，不需要也无法在
  评测环境里找到这份参考实现的原始文件。

## 卡片字段

每张卡片固定六段：

| 字段 | 含义 |
|---|---|
| **文件** | 要改的精确路径（`code/` 相对路径；新增/删除会明确标注） |
| **现状** | 该文件现在错在哪（含方法名/行号线索） |
| **期望** | 设计要求的正确行为 + 依据（`design-docs/NN §X` / `README §6/§7`） |
| **改法** | 方法级修改说明，关键处直接给目标代码片段；新增类给包路径+类骨架 |
| **验收** | 改完后可自查的行为断言 |
| **勿犯** | （高危卡才有）此卡最容易引入的事故，落笔前必读 |

风险标注：`low` = 单文件行为修正；`high` = 新增/删除类、跨文件结构性改动——**high 卡改完必须
立刻整批 verify，不与下一批合并**。

## 批次执行顺序（严格按下表行序 B01→B19 执行；每批修完必跑 `bash work/harness/ratchet.sh verify`）

排序原则：**已知影响公开用例的模块最先修**（基线上有公开用例失败的 user/order/promotion/payment
排在最前，早修早锁分），其余模块批居中，**结构性高危改动（事件迁移/监听器/审计/配置）殿后**——
失败代价大的放在公开分锁定之后做。**注意：本环境可见的用例集（总数以 ratchet 输出的 total 为准，评测机可能是全量集）只是评分的一部分，
B07 及之后的批次正是深层契约分的主要来源——当前用例全绿之后，
这些批次不是"可选加分项"，而是主要得分战场，必须逐批全部执行。**

| 批次 | 卡片 | 内容 | 风险 |
|---|---|---|---|
| B01 | `S1-quick-wins.md` | 全局单点速赢：金额舍入 / 错误码 / 异常构造器 | low |
| B02 | `user.md` | 注册激活 / 登录错误语义 / 地址 / 安全配置去重（公开 pub001/pub105 在此） | mid |
| B03 | `order.md` §A（order-core） | 订单状态机 / 错误码 / 校验 / 幂等（公开 pub102 在此） | mid |
| B04 | `order.md` §B（order-pricing） | 订单金额 / 配置接入 / 积分抵扣 / 批量（公开 pub104 在此） | mid |
| B05 | `promotion.md` | 优惠计算 / 秒杀（含事务毒化修复）/ 券核销归属 / 取消释放（含 order 侧接线卡 ORD-A17，经 PROMO-16 指针执行）（公开 pub101 在此） | mid |
| B06 | `payment.md` §A（pay-core） | 支付 / 回调 / 退款（公开 pub009 在此） | mid |
| B07 | `payment.md` §B（pay-ext） | 发票 / 结算 / 支付侧通知渠道 | mid |
| B08 | `product.md` | 搜索 / 上下架 / 库存摘要 / 重复冲突语义 | mid |
| B09 | `inventory.md` | 预占-释放-扣减守恒 / 错误码 / 仓库排序 | mid |
| B10 | `cart.md` | 纯缓存购物车（删落库残留）/ 估价同源 | mid |
| B11 | `common.md` | 通知组件 / 全局异常处理 | low |
| B12 | `app.md` | 安全边界：401/403 契约错误体 / CORS / 管理支撑 | mid |
| B13 | `S2-events.md` §A | 事件权威定义迁移 common + 影子类删除 + 既有监听器事务语义与 bean 名 | high |
| B14 | `logistics.md` | 拣货-面单-出库链 / 回调幂等 / 运费模板 / 订单物流状态推进（LOGI-11，high 卡） | mid |
| B15 | `loyalty.md` | 积分赚取-抵扣汇率 / 冻结-过期 / 等级 | mid |
| B16 | `S2-events.md` §B | 新增跨模块监听器（库存扣减 / 订单送达 / 退款完成）+ 监听失败落库 | high |
| B17 | `review.md` | 评价链路 / 审核冲突语义 / 敏感词播种 | mid |
| B18 | `S3-audit.md` | 审计基础设施 + 7 类操作接入 | high |
| B19 | `S4-config.md` | 4 处限流注解 + 商品详情缓存（手写 Caffeine Cache，绝非新建 CacheManager） | high |

依赖关系：**B14（logistics）、B15（loyalty）、B16（S2 §B）都依赖 B13（S2 §A）建好的
`com.ecommerce.common.event.*` 事件类**——若 B13 最终被跳过：B16 整批连带跳过；B14/B15 中
明确标注引用 common 事件类的卡片跳过，其余卡片照常执行。**B17（review）依赖 B16（S2 §B）的
"订单送达推进"监听器**——REV-1 的"购买 + 签收"校验要求订单能被推进到 DELIVERED（13 §2 前提 3），
该推进由 B16 新增的送达监听器完成；若 B16 被跳过，B17 的评价创建在黑盒链路上必被拒（曾实测
稳定打掉 pub014 触发回滚），可直接连带跳过 B17。**B18 内自包含**（基础设施与接入同批）。
其余批次相互独立，某批被跳过不影响后续。若依赖链上有批次被跳过，INSTRUCTION 第 ④ 步补救
循环重开时按批次号升序：先 B13，后 B16，再 B17。

## 执行协议（每批相同，以 INSTRUCTION 第 ③ 步 a→b→c→d 为准）

1. **派 bug-fixer subagent**（派不出时按 INSTRUCTION 的 general 递降链，prompt 首行要求先读
   `work/skills/bug-fixer/SKILL.md`）逐卡修改——主 agent 不要自己展开卡片正文；
2. `bash work/harness/ratchet.sh verify`；
3. 按 RATCHET_RESULT 走：`ADVANCED`/`OK` → 固化进下一批；`ROLLED_BACK` → 重试一次，
   再败跳过；`BUSY` → 已有构建在跑，轮询等待，绝不并行；
3.5 固化（`ADVANCED`/`OK`）后**立即**跑 `bash work/harness/check-batch.sh <本批批次号>` 做批次
   产物确定性核验（秒级、不跑 Maven，断言来自 `work/bugs/artifacts.tsv`）：最后一行
   `BATCH_ARTIFACTS: MISSING` = 本批有卡没真正落地（"无回归"挡不住整批做空），按 INSTRUCTION
   第 ③ 步 c 的附加动作把「缺失:」清单转交 subagent 重开本批补齐；
4. **立即**把本批一行结果追加进 `result/output.md` 顶部『本次评测运行记录』节，再进下一批。

绝不对同一批在本轮内重试第二次（第 ④ 步补救循环重开时重新获得一次重试额度）。

## 绝不做清单（尽调确认会炸的操作——不是建议，是禁令）

1. **`OrderLogisticsStatusUpdater` 的生产实现只按 LOGI-11 卡（B14）的 `@Primary` 方案落地，
   四条红线一条都不能碰。** 冻结的 `test-cases/BlackboxHarnessConfig` 注册了一个无限定符的该接口
   no-op bean；LOGI-11 的实现类靠 **`@Primary`** 在两个候选中确定性胜出、与 harness bean 共存
   （已实证 24/24 全绿——早前"生产实现必撞 bean 冲突"的弃项结论只对无消歧的裸实现成立）。因此：
   ①绝不能去掉 `@Primary`（裸第二候选 = `NoUniqueBeanDefinitionException`，上下文启动失败，
   **全部用例全灭**——这正是当年弃项担心的事故）；②绝不能给 harness 的 no-op bean 想任何办法
   （`test-cases/` 冻结红线）；③绝不能把实现放进 `ecommerce-order`（order 看不见 logistics 接口，
   强加依赖成环；只能放 app 组合根）；④绝不能出现第二个 `@Primary` 同类型 bean（歧义等价于没加）。
2. **不加 `@EnableMethodSecurity`。** README §6 全部 61 个端点已被 URL 级安全规则 100% 覆盖；
   启用只会让从未被执行过的 `@PreAuthorize` 注解突然生效，静默改变既有端点鉴权行为。
3. **不新建 Spring `CacheManager` bean。** 全系统唯一真正实现 `org.springframework.cache.CacheManager`
   接口的是 inventory 模块的 `InventoryCacheConfig`（显式命名 `inventoryCacheManager`，自包含、
   不与其他模块竞争）。**cart / product / logistics 的"缓存"都不是 `CacheManager`**——它们各自是
   一个 `@Component` 包装类持有一个手写的 Caffeine `Cache<K,V>` bean（get/put/evict 全手动），
   模式上刻意回避 Spring 的 `CacheManager` 抽象。商品详情缓存卡片（S4/CFG-5）必须**照抄这个
   手写 Cache 模式**，绝不能创建第二个真正的 `CacheManager` 实现——基线 `SystemAdminController`
   曾以无 `@Qualifier` 的类型注入 `CacheManager cacheManager`，若该字段的移除卡片被跳过、又
   同时出现第二个真 `CacheManager` bean，注入点在两者间无法消歧，`NoUniqueBeanDefinitionException`，
   上下文启动失败，**全部用例全灭**——这正是早期评测实际发生过的事故。
4. **不动 `test-cases/` 下任何文件**（含其 harness 配置），不修改冻结契约与 `design-docs/`。
5. **不加"物流状态单调性校验"。** 会打掉黑盒依赖的跳跃式状态前进路径（PUB-014/107/108）。
6. **不实施卡片之外的任何"发现"。** 你若觉得"还有个 bug 卡片没写"，把它记进 `result/output.md`
   即可，**不要改**——检查阶段三轮深审后仍留在代码里的行为，多数是尽调后"风险高于收益"的
   明确弃项（如运费模板接线、DELIVERED→COMPLETED 触发等——注意「优惠券/秒杀名额/积分在订单取消后的释放与退还」曾在此列，后已补卡实施：见 PROMO-14/15/16、ORD-A17/A21/A22、LOY-12）。
