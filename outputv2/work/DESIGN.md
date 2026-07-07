# DESIGN — AI 修复方案（outputv2）

## 一句话

我们已完成「**检查**」（`work/bugs/findings.md` 给出全部已定位 BUG 卡片）；交付让评测 AI agent
**照卡片逐条修复工作目录下的源码**，用编译 + 公开 24 例自检效果。**纯 AI 正面解题，不依赖任何
参考答案**——修复质量由 agent 现场产生，正是本方案要检验的。

## 为什么是这个形态

赛题是「设计实现一致性检查与修复」，赛道是 AI 竞赛。作品把能力拆两层：

- **检查层（我们已做）**：12 模块逐一 + 集成联调 + 三轮深审，产出 `findings.md`——每条 BUG 的
  症状、位置、**设计依据**（`design-docs/` 章节 + `README.md` 契约）、修法方向。
- **修复层（agent 现场做）**：主 agent 照卡片**分模块派 subagent** 逐条改 `code/`；靠卡片里的
  设计依据把方向，用编译 + 公开 24 例回归看效果。

## 组件

| 组件 | 位置 | 作用 |
|---|---|---|
| BUG 卡片 | `work/bugs/findings.md` | 已定位的全部不一致（症状/位置/设计依据/修法方向） |
| subagent 技能 | `work/skills/bug-fixer/SKILL.md` | 单个/一组 BUG 的修复规范 |
| 效果自检 | `work/harness/check-all.sh` | `mvn` 编译 + 公开黑盒 24 例回归 |
| 复核清单 | `work/checklist/<module>.md` | 逐模块强规则速查 |
| 审查技能 | `work/skills/design-consistency-{auditor,fixer}/` | 检查阶段方法论（可复跑、供查证思路） |

## 执行流（详见 `INSTRUCTION.md`）

```
① cp -a /app/code/judge-assets/02_04_design_implementation_consistency/. .   （源→当前工作目录）
② 读 work/bugs/findings.md 卡片 → 按模块派 subagent（bug-fixer 技能）逐条改 code/
     每条：读设计依据 → 改目标文件 → 确认符合设计（新增/删除按卡片标注处理）
③ bash work/harness/check-all.sh  → 编译 + 公开 24 例，看修复效果
   结果 = 当前工作目录 / code
```

## 与 output/（v1）的关系

同一份检查成果、两种落地：**v1（`output/`）** 确定性哈希门控引擎**回放**已验证修复——快、稳、
可复现，但不体现 AI 解题过程；**v2（本目录）** **纯 AI 照卡片修复** + 编译/24 例自检——体现 AI
agent 的诊断-修复能力，效果由评测检验。v2 复用 v1 的 `findings.md`（BUG 卡片）。

## 目录结构

```
outputv2/
├── INSTRUCTION.md                      评测入口（① cp 源 ② 照卡片改 ③ 自检；对齐 GUIDANCE 4.1–4.4）
├── work/
│   ├── DESIGN.md                       本文件
│   ├── bugs/findings.md                BUG 卡片清单（检查成果）
│   ├── harness/
│   │   ├── check-all.sh                效果自检：mvn 编译 + 公开 24 例
│   │   └── README.md
│   ├── skills/
│   │   ├── bug-fixer/SKILL.md          subagent 修复技能
│   │   └── design-consistency-{auditor,fixer}/   检查阶段方法论
│   └── checklist/<module>.md           逐模块强规则速查
├── result/output.md                    运行记录
└── logs/{interaction.md, trace/}       过程记录
```
