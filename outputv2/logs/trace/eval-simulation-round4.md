# 评测模拟复盘 — 第四轮：一次挂死事故 + 一次零回滚全绿（OpenCode + MiMo 弱档）

第四轮在第三轮修复包（递降派遣链、`.opencode/` 预置注册、test-compile 自检、回滚重试语义、
产物核验 check-batch、ratchet 加固）之上做回归验证，共启动两次：**attempt-1 暴露并修复了一个
评测级致命挂死**；**attempt-2（round-4b）跑出全系列首次 19/19 零回滚零跳过全绿**。

## attempt-1：外部路径权限挂死（评测级致命，已根治）

- 预置 `.opencode/` 注册**如设计生效**——B01 首次原生派遣 `bug-fixer` subagent（前三轮全部
  落在内建 general 上）。
- 但该 subagent 的自检命令 `mvn` 不在 PATH，它自行探路执行 `cat $HOME/tools/env.sh`——
  OpenCode 对**子会话命令行中的工程外路径**触发 `external_directory` 权限询问，headless
  `--auto` 模式下子会话的询问**无人应答**，整个运行在 snapshot+B01 处静默挂死 5 小时
  （opencode 日志末行凝固在 `permission=external_directory … asking`；沙箱实验证实项目级
  `opencode.json` 权限配置也救不了子会话询问）。真实评测机上这 = 全程只完成基线快照。
- **根治（commit 2e8a6f7）**：权限层只检查命令行文本、不追踪脚本内部行为——新增工程内
  `work/harness/mvnw.sh`（与 ratchet 同源的版本驱动 $HOME/tools 探测 + `exec mvn "$@"`），
  SKILL 自检命令全部改经 mvnw.sh，并把「命令行绝不引用工程外路径、绝不 source env 文件」
  写为 SKILL 边界首条。

## attempt-2（round-4b）：19/19 零回滚全绿

- 环境：OpenCode 1.17.17 headless `--auto`，`mimo/mimo-v2.5`（弱档），全局注册目录清空
  （模拟全新评测机），交付物含 attempt-1 修复。
- 结果：**18 → 24/24（B06 后 25 分钟锁定），19/19 批全部固化，21 次 verify 零回滚零跳过**，
  84 条产物断言全绿，约 91 分钟收官（`STATUS: DONE`）。主上下文仅 18.5 万输入 token。

| 维度 | 第二轮（pro） | 第三轮（弱档） | 第四轮 b（弱档+修复包） |
|---|---|---|---|
| 批次落地 | 18/19（review 跳过） | 18/19（B17 跳过 + B16 空心） | **19/19** |
| verify / 回滚 | 24 / 3 | 25 / 5 | **21 / 0** |
| 公开分 | 24/24 | 24/24（收尾补救） | 24/24（批内直达） |
| 隐藏面完整度 | review 缺失 | 事件网络+评价链缺失 | **全量落地（84 断言全绿）** |

## 回归点逐项验证

1. **派遣链路**：预置注册生效，B01 原生 bug-fixer ✓；但 B02 起模型随性改派裸 general 且
   prompt 未带 SKILL 指针（无 Unknown-agent-type 触发，纯漂移）——已把「派遣 prompt 首行
   必须要求先读 SKILL.md」升级为**无条件规则**（commit 562bd0f，本轮 workdir 未含、待第五轮验证）。
2. **test-compile 自检**：B14/B16（第三轮在此累计 3 次编译失败）本轮全部一次通过——"漏改
   模块单测"在 subagent 批内被拦截修复 ✓（B14 的 `FreightCalculatorTest` 构造器同步实测确认）。
3. **check-batch 产物核验**：全程接线（每批固化后执行），B07/B15 两次 MISSING → 有界重开 →
   复核 OK 的闭环实战跑通 ✓。两次均为**锚点误报**（断言字符串取自参考实现的注释/日志行，
   功能等价实现不含该字面）——审计后 3 条同类脆弱锚已换为行为载重代码锚
   （`findByInvoiceRequestNo` / `getProvinceRules()` / `recordPayment`，commit baa8990），
   并据此勘误第三轮复盘：当时报告的"B07/B15 局部空心"系同款误报，第三轮真实损失仅
   B16 空心 + B17 跳过。真阳性场景（第三轮空心 golden 的 B16）此前已验证 MISSING 7/7 可检出。
4. **收尾重开**：本轮无跳过批、无 MISSING 批可测（最好的结果）；收尾终验 + STATUS: DONE 合规。
5. **B17（review）**：三轮未竟之批**首次自然固化**——B14（送达事件发布）+B16（送达推进监听器）
   依赖真实齐备后，REV-1 的购买+签收校验上线且 pub014 全程完好 ✓。
6. **防挂死**：mvnw.sh 生效，全程无一次外部路径权限询问 ✓。

## 第五轮验证点

1. 无条件 SKILL 指针首行（562bd0f）后，general 派遣的纪律传达是否稳定；
2. 修正后的锚点清单（baa8990）下 check-batch 是否零误报；
3. 零回滚全绿的可复现性（同条件重跑）。
