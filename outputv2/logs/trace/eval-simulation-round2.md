# 评测模拟复盘 — 两轮无人值守全流程运行（OpenCode + MiMo）

作者侧在提交前搭建了与评测机制一致的模拟环境，让真实的 agent 运行时读取 `INSTRUCTION.md`
从零执行本作品，验证交付物的无人值守可执行性并暴露流程缺陷。本文是两轮运行的完整复盘。

## 模拟环境

- 源码入口按评测约定放置：`/app/code/judge-assets/02_04_design_implementation_consistency/`
  （未修复基线：`code/` + `design-docs/` + `README.md` + `test-cases/`）
- agent 运行时：OpenCode 1.17.17，headless `opencode run --auto`（自动批准，等价无人值守）
- 模型：`mimo/mimo-v2.5-pro`（OpenAI 兼容接口）
- 每轮都从全新工作目录开始，kickoff 提示只说"读 INSTRUCTION.md 并从头到尾执行"，
  所有行为约束均来自交付物本身——与真实评测的信息边界一致

## 两轮结果对比

| 维度 | 第一轮（改造前交付物） | 第二轮（改造后交付物） |
|---|---|---|
| 运行时长 | 10 分钟 | 105 分钟 |
| 批次执行 | 3/19，自称"时间限制"提前收尾 | **19/19 全部执行** |
| 公开用例 | 18 → 18（净增 0） | **18 → 24 全绿**（32 分钟锁定） |
| subagent | 0 次（全塞主上下文） | 21 次派遣 |
| 棘轮出手 | 0 次 | 3 次回滚全部兜住 |
| 收尾 | 摘要式弃跑 | 逐批记录 + 终验 + STATUS: DONE |

## 第一轮暴露的问题与对应改造

1. **agent 凭空发明"时间限制"提前收工**（实际仅运行 10 分钟、无任何预算约束），而交付物
   心法中"时间受限时停在批次边界永远安全"恰好成了它的说辞。
   → 心法第 4 条改写为"19 批必须全部执行完——本任务不存在时间限制"，安全停靠语义只保留给
   外部强制中断。
2. **公开分批次埋得太后**：旧顺序前 3 批（速赢/事件迁移/common）不触及任何基线失败用例，
   agent 弃跑时公开分颗粒无收。
   → 批次表按"公开分优先、结构性高危殿后"重排：基线 6 个失败公开用例所在的
   user/order/promotion/payment 提到 B02–B06；事件迁移/监听器/审计/配置移至 B13–B19。
   全部 ~130 处批次号交叉引用同步重映射，并为"S2 §A 晚于模块批执行"补写顺序反转防御说明。
3. **不派 subagent 导致主上下文膨胀**，加剧"该收尾了"的直觉。
   → INSTRUCTION 第③步把 subagent 从"推荐"升格为"必须优先"，并新增第 d 步
   （每批结果即时追加 result/output.md，禁止攒批总结）。

## 第二轮的关键事件

- **公开分曲线**：B02 user +2（pub001/105）、B03 order §A +1（pub102）、B04 order §B +1
  （pub104）、B05 promotion +1（pub101）、B06 payment §A +1（pub009）——6 个基线失败用例
  被前置批次逐一精确消灭，24/24 此后由棘轮锁死。
- **棘轮三次出手**：review 批两次引入回归（`pub014_createReview`，24→23）当场回滚、按协议
  跳过；S2 §B 批一次编译失败被编译门回滚、agent 对照错误摘要修正后重试成功。
- **协议纪律零违规**：重试一次/再败跳过/不第三次重试/逐批记录/收尾终验全部按 INSTRUCTION
  执行。

## 第二轮暴露的缺陷：review ↔ S2 §B 批次顺序死锁（已修复）

**现象**：review 批（当时 B16）两次尝试均稳定打掉 `pub014_createReview`。

**根因链**（三方证据对齐）：
1. 设计 13 §2 评价前提 3："订单状态为 DELIVERED 或 COMPLETED"；
2. REV-1 卡忠实实现该校验（`verifyPurchase` 不通过即 403）；
3. 但把签收订单推进到 DELIVERED 的"订单送达推进"监听器由 S2 §B（当时 B17）新增——
   **被依赖批排在依赖批之后**，review 批执行时订单永远停在 SHIPPED，评价必被拒。
   该死锁在旧批次表中同样存在（review B15 < S2§B B17），只是从未被真实运行触达过。

**修复**：交付物中两批互换（S2 §B=B16、review=B17），批次表依赖说明新增
"B17（review）依赖 B16（订单送达推进）"，`review.md` 与 `S2-events.md` §B 头部各写明
双向依赖与脱序运行自检命令。

## 第四轮设计-实现对比（模拟运行期间并行完成）

以"附录B 配置键零读取"与"265 个零修改源文件"两个筛法对完成态做了一轮补充审查，
新增 2 张卡：LOGI-9（面单承运商硬编码占位符 "DEFAULT"，应取 `logistics.default-carrier`
默认 LOCAL_EXPRESS）、PAY-B3（发票抬头长度上限 `invoice.max-title-length` 全工程零校验）。
其余候选（cart TTL 硬编码但行为达标、促销叠加顺序、支付重试/回调超时配置无行为语义等）
经查证均排除，详见卡片文件内说明。

## 结论

- 交付物的无人值守可执行性已被真实 agent 运行时端到端验证：环境准备、subagent 注册、
  源码复制、19 批修复、棘轮门禁、收尾记录全链路自动完成。
- 棘轮护栏在真实回归/编译失败场景下按设计工作，"最坏交付 = max(基线, 已固化最佳)"成立。
- 两处流程缺陷（提前收工话术、批次顺序死锁）均已在交付物中修复；修复后的批次表在
  依赖关系上经过重放验证。

---

## 附：本轮原始运行记录（原 result/output.md 存档，第四轮起该位置改放最新全绿运行）

环境：OpenCode 1.17.17 headless `--auto`，模型 mimo-v2.5-pro；起止 2026-07-10 02:04 → 03:49（约 105 分钟）；
派遣 21 次 subagent。批次记录（运行时批次表为互换前版本：B16=review、B17=S2 §B）：

```text
B01 S1-quick-wins.md → OK pass=18 best=18
B02 user.md → ADVANCED pass=20 best=20
B03 order.md §A → ADVANCED pass=21 best=21
B04 order.md §B → ADVANCED pass=22 best=22
B05 promotion.md → ADVANCED pass=23 best=23
B06 payment.md §A → ADVANCED pass=24 best=24
B07..B15 → OK pass=24（逐批固化）
B16 review.md → ROLLED_BACK reason=regression pass=23 best=24 (重试失败，跳过)
B17 S2-events.md §B → OK pass=24 best=24（一次 compile_failed 回滚后重试固化）
B18 S3-audit.md → OK pass=24 best=24
B19 S4-config.md → OK pass=24 best=24
最终：18 → 24/24，跳过 1 批（review）；STATUS: DONE
```

棘轮历史要点：02:05 snapshot base=18；24 次 verify；3 次回滚（review 回归 ×2 → 按协议跳过、
S2 §B 编译失败 ×1 → 重试固化）；其余全部 OK/ADVANCED。
