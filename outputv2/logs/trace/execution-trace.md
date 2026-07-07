# 执行过程记录 — outputv2（AI 修复版）

## 方案

「检查」成果（`findings.md` 全部 BUG 卡片）已在 `output/` 阶段产出；outputv2 让评测 agent 照卡片
**派 subagent 逐条修改 `code/`**，编译 + 公开 24 例自检效果。**纯 AI，不依赖参考答案。**
详见 `work/DESIGN.md`、`work/harness/README.md`。

## 从「参考 oracle 版」到「纯改版」

初版 v2 曾用参考修复作 Harness 的 oracle + 兜底；按需求改为**纯让 agent 照卡片改、看效果**：

- 删除 `work/harness/{reference/, verify.sh, apply-reference.sh}`（不再有参考答案对照与兜底）；
- `check-all.sh` 简化为两道客观门：`mvn` 编译 + 公开黑盒 24 例回归；
- `INSTRUCTION.md` 第 ① 步直接 `cp -a /app/code/judge-assets/02_04_design_implementation_consistency/. .`
  到当前工作目录；第 ② 步照 `findings.md` 卡片改工作目录下的源码。

## 自检链路验证（作者侧）

`check-all` 的编译门 + 24 例门在**完成态工程**（`output/` 的已验证工作树）上运行：
`BUILD SUCCESS + 24/24 PASS`——确认自检门本身有效可用。**真实修复效果由评测 agent 照卡片现场产生**，
不由参考答案决定。

## 与 output/（v1）的关系

同一份 `findings`、两种落地：**v1（`output/`）** 确定性哈希门控引擎**回放**参考修复；
**v2（本目录）** **纯 AI 照卡片修复** + 编译/24 例自检——体现 AI agent 能力，效果由评测检验。
