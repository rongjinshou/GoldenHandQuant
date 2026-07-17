## 本次评测运行记录（评测机 agent 逐批追加于此节；作者交付时此节为空）

---

## 附录：作者侧提交前模拟运行存档（非本次运行，不作为任何完成证据）

# 运行记录 — 第二十一轮终版认证跑（B05 拆分后 20 批全程 · 全新环境 · 含 API 故障日全链路压测）

> 本文件主体是**评测机 agent 的真实运行输出**。本轮输入为正式提交 zip（含 B05→B05+B05b
> 拆分、check-batch 大小写修复、终验一次化、5 项 accuracy 缺口卡）全新解压；全新数据目录、
> 全局 agent 注册目录清空；`opencode run --auto`（mimo/mimo-v2.5 弱档）+ 系统 JDK 21 +
> Maven 3.9，提示词为平台确认的最简形态。运行当日 mimo API 严重不稳（多次 2~18 分钟停顿、
> 两次 TLS 断连致进程退出），反而完成了一次全链路容灾压测——全部护栏机制实战通过。
> 历轮复盘见 `logs/trace/`（本轮：`round21-split-certification.md`；三判并发同构实证见
> round-17 存档）。

## 评测机 agent 逐批写入的执行记录（原样保留）

基线通过数：18 / 总数：24

| 批次 | 卡片文件 | RATCHET_RESULT | 未完成卡 |
|---|---|---|---|
| B01 | S1-quick-wins.md | OK pass=18 best=18 total=24 | 无 |
| B02 | user.md | ADVANCED pass=20 best=20 total=24 | 无 |
| B03 | order.md §A | ALREADY_APPLIED（续跑核验确认） | 无 |
| B04 | order.md §B | OK pass=22 best=22 total=24 | 无 |
| B05 | promotion.md | ADVANCED pass=23 best=23 total=24 | 无 |
| B05b | promotion-release.md | OK pass=23 best=23 total=24 | 无 |
| B06 | payment.md §A | OK pass=24 best=24 total=24 | 无 |
| B07 | payment.md §B | OK pass=24 best=24 total=24 | 无 |
| B08 | product.md | OK pass=24 best=24 total=24 | 无 |
| B09 | inventory.md | OK pass=24 best=24 total=24 | 无 |
| B10 | cart.md | OK pass=24 best=24 total=24 | 无 |
| B11 | common.md | OK pass=24 best=24 total=24 | 无 |
| B12 | app.md | OK pass=24 best=24 total=24 | 无 |
| B13 | S2-events.md §A | OK pass=24 best=24 total=24 | 无 |
| B14 | logistics.md | OK pass=24 best=24 total=24 | 无 |
| B15 | loyalty.md | OK pass=24 best=24 total=24 | 无 |
| B16 | S2-events.md §B | OK pass=24 best=24 total=24 | 无 |
| B17 | review.md | OK pass=24 best=24 total=24 | 无 |
| B18 | S3-audit.md | OK pass=24 best=24 total=24 | 无 |
| B19 | S4-config.md | OK pass=24 best=24 total=24 | 无 |

最终通过数：24 / 总数：24
跳过批次：无
STATUS: DONE

## 棘轮护栏完整历史（`.ratchet/history.log` 原文）

```text
2026-07-17 09:50:01  snapshot base=18 total=24
2026-07-17 10:04:10  verify pass=18 best=18 total=24 -> OK
2026-07-17 10:44:04  verify pass=20 best=18 total=24 -> ADVANCED
2026-07-17 11:38:47  verify pass=21 best=20 total=24 -> ADVANCED
2026-07-17 13:44:01  verify pass=21 best=21 total=24 -> OK
2026-07-17 15:33:46  verify compile_failed -> rolled back (best=21)
2026-07-17 16:15:31  verify pass=22 best=21 total=24 -> ADVANCED
2026-07-17 19:19:53  verify pass=22 best=22 total=24 -> OK
2026-07-17 20:21:06  verify pass=23 best=22 total=24 -> ADVANCED
2026-07-17 20:43:26  verify pass=23 best=23 total=24 -> OK
2026-07-17 21:56:54  verify pass=24 best=23 total=24 -> ADVANCED
2026-07-17 21:59:13  verify pass=24 best=24 total=24 -> OK
2026-07-17 22:10:31  verify pass=24 best=24 total=24 -> OK
2026-07-17 22:13:46  verify pass=24 best=24 total=24 -> OK
2026-07-17 22:19:17  verify pass=24 best=24 total=24 -> OK
2026-07-17 22:23:08  verify pass=24 best=24 total=24 -> OK
2026-07-17 22:28:17  verify pass=24 best=24 total=24 -> OK
2026-07-17 22:31:02  verify pass=24 best=24 total=24 -> OK
2026-07-17 22:36:57  verify pass=24 best=24 total=24 -> OK
2026-07-17 22:43:42  verify pass=24 best=24 total=24 -> OK
2026-07-17 22:53:07  verify pass=24 best=24 total=24 -> OK
2026-07-17 22:55:38  verify pass=24 best=24 total=24 -> OK
2026-07-17 22:59:28  verify pass=24 best=24 total=24 -> OK
2026-07-17 23:04:10  verify pass=24 best=24 total=24 -> OK
2026-07-17 23:07:10  verify pass=24 best=24 total=24 -> OK
```

> 注：`compile_failed -> rolled back` 一行是 B04 首试编译失败被护栏自动回滚（golden 无损），
> 重试即固化——护栏按设计工作。第 5 行是 B03 空心重开后的固化；第 8 行与末行是两次外部
> 中断（API TLS 断连/提前收话）后续跑协议的对齐 verify。**执行器自身的收尾终验只跑了一次**
> （终验一次化生效）。

## 结果解读

- **20/20 批全部执行**（B01–B19 + 拆分批 B05b），最终 **24/24**，零跳过、零未完成卡；
  修复树上 **139 条产物断言 20 批全 OK**。
- **上下文（本轮核心验证目标）**：主会话峰值 **66K（33%）**、违规读卡 **0**；27 个 subagent
  峰值前二 134.6K（B05，拆前 152.5K）/ 128.9K（B03 重开），**全程无一超过 150K**（平台
  200K 上限余量 ≥33%）；B05b 新批仅 **68K（34%）**。
- **全链路容灾实战**（当日 API 故障反复触发，全部按协议恢复、零损失）：
  ① B03 subagent 被 API 打断致空心（断言 8/9 MISSING）→ check-batch 抓获 → 重开 → 9/9 落齐；
  ② B04 首试编译失败 → 棘轮回滚 → 带失败上下文重试 → 固化；
  ③ 两次进程死亡（TLS 断连/提前收话）→ 续跑协议两次完整走通（golden 识别、20 批核验重建
  进度、`ALREADY_APPLIED（续跑核验确认）` 记账）；
  ④ 后启会话真实派出预注册 `bug-fixer` agent（install-agent 全局注册对新会话生效的设计
  首次实战验证）。
- 根目录零污染、邻居诱饵哨兵原封；`B05b` 断言经 check-batch 大小写修复后可正常命中
  （`checked=4`，含 `releasePromotions`/`refundLoyaltyPoints` 均恰为 4 的路径计数自检）。
- 参考实现侧：双 JDK 门禁 24/24 + 全仓单测 + 139 断言参考树全绿（历轮持续）。
