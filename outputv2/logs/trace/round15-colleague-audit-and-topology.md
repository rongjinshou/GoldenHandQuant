# round-15 复盘：同事 400 用例核对 → 三路盲区扫描 → 修复批 + 平台拓扑重构

## 一、输入与方法

两个外部输入触发本轮：①同事按设计文档自研 400 黑盒用例的失败分析（22 条指控）；②平台人员
确认的关键运行时事实——**opencode 工作目录是全局根目录、每个作品解压在 /app/tasks/xxx 独立
路径且可写、公开用例非全量、每天每题 5 次提交机会**。

处理流水线：4 路只读核查（每条指控 = 文档逐字 × 当前代码 × 基线 git 考古 × 官方冻结资产，
四方裁决）→ 3 路盲区类全量扫描（词表泄漏 / 配置旋钮+静态单例 / 时钟源+文档算例+疑点回收）→
三簇并行实修（每项独立 24/24 门禁）→ 双 JDK 统一门禁 → 新拓扑认证跑。

核对结论：22 条中 7 条真问题（2 条 P1）、4 条事实属实不够违规（顺手补）、11 条不成立（含同事
06 号报告把 5 条代码真错误判为"测试错"——按错误表名检索的幻觉，其 13 号报告才是对的）。
详见 `docs/2026-07-15-同事400用例核对报告.md`（仓库 docs/，非交付物）。

## 二、修复批（三簇 18 项，全部逐项门禁 + 卡片 + 断言）

- **A·payment**：退款状态枚举对齐附录C:146（`APPLIED/REVIEWED/ACCEPTED/REFUNDED/REJECTED`，
  删死值 APPROVED——历轮审计漏掉的经典植入，被同事用例撞出、四方核查坐实）；结算批次修复
  （查询含 CLOSED + 删空批次短路——前者是我们此前收窄 SUCCESS-only 的自伤回归，诚实留档）；
  payment 5+2 处裸时钟成套接 SystemClockService；InvoiceStatus CANCELLED→VOIDED（附录C:159，
  词表扫描找到的"第二个 refunds"）。新卡 PAY-B6/B7。
- **B·order/user/inventory/cart**：order 侧 paidAt/cancelledAt/orderNo 日期段成套换钟（与
  payment 侧同一拨钟断言联动）；昵称登录 email 字段回退 `findFirstByNicknameOrderByIdAsc`
  （04 §4"用户名或邮箱"+基线 Javadoc 植入提示；findFirst 防官方 fixture "Tester" 重名 500）；
  JWT 签发+解析双侧接测试时钟（jjwt 0.12.5 `JwtParserBuilder.clock` 实证）；删除我们自造的
  库存默认预警阈值 10（卡片当年自标 suspicious 无人回收的教训项）；购物车 TTL 应用层过期
  （SystemClockService + `cart.ttl-days`，拒绝 Caffeine Ticker 方案）；下单路径积分兑换率
  接 `loyalty.redeem-rate`；ORDER_CREATED 通知补 receiver；注册通知补幂等键。新卡
  ORD-A23/USER-8/CART-6 + INV-6 修订。
- **C·common**：JPA 审计时钟系统修（`@EnableJpaAuditing(dateTimeProviderRef=...)`——销售统计
  按 createdAt 落日桶，拨钟用例必挂的系统性缺口）；12 处 REST 可见时间戳批量换钟；
  `recordFailure` 增幂等键参数；限流滑动窗接测试时钟（含拨钟解除限流新单测）。新卡 COMMON-5。
  文档收尾：checklist 12 项回勾附证据、findings 增补（order 14 个死 bean"接线即地雷"登记、
  并行/sentRecords 两条注意、frozenPoints 正式接受）、loyalty 取整决策留档。

主会话联动：S3-audit.md 的 AUD-5 卡内嵌代码同步新枚举词表（否则 B18 照卡写出编译错误——
跨批次一致性断点）；全部卡片文件防漏扫描确认冻结错误码 `REFUND_WAITING_WAREHOUSE_ACCEPT`
未被误改。断言 124 → **135 条**，19/19 批全绿。

## 三、INSTRUCTION 第⓪步重构（平台拓扑真相驱动）

首次评测 stability 33 的最大嫌疑更新为：**多个评测 agent 共享全局根 CWD，而旧⓪步"把作品
复制到当前目录工作"会让先后/并发的 executor 在同一目录互相覆盖 code/ 与 .ratchet**（与
"3 次只有第一次稳定"精确吻合）。重构：

1. 锚点 R = INSTRUCTION.md 自身所在目录（绝对路径），一切复制/构建/状态/记录都在 R 内；
   红线"绝不在全局根目录展开任何文件"；R 不可写时 mktemp 兜底并如实记录。
2. **派遣词强制携带绝对路径 R**：子会话初始目录 = 运行时进程启动目录（全局根），相对路径
   必落空——首行改为「工程根目录是 <R>，先 cd <R>，再完整阅读 <R>/work/skills/bug-fixer/
   SKILL.md…」；SKILL.md 对应加 R 锚定规范与"从本文件路径反推 R"的自愈。
3. `.opencode/` 预注册说明修正：平台从全局根启动运行时，包内注册不会被自动发现——递降链
   走 general 是预期路径而非故障。
4. 运行记录直接写在作品目录本体（平台确认可写）= 评分方采集的就是它，同时消除"记录写在
   工作副本未被采集"的隐患；同目录先后 executor 由既有 flock BUSY + 续跑协议兜住。

## 四、执行事故与教训（诚实记录）

合并 W15-B patch 时 shell CWD 漂移在仓库子目录，`git apply` 从子目录运行会**静默跳过子目录
之外的路径**（卡片落了、16 个 code/ 文件被无声丢弃且报 OK）——靠断言扫描（4 条 MISSING）
当场暴露，`--include='code/*'` 从根目录补齐后 19/19 全绿。教训固化：apply 必须与 cd 同命令；
"产物断言扫描在每次合并后强制执行"再次证明是防空心的最后防线。

## 五、验证与交付

双 JDK（17/21）统一门禁 + 全仓单测（838 例）→ commit → 认证跑升级为**新拓扑仿真**：
全局根 CWD + `app/tasks/task-0204/<作品>` 深路径 + 邻居诱饵任务目录哨兵，验证⓪步锚定、
派遣绝对路径、零越界写入 → 通过后打新提交包。结果记录见 result/output.md。
