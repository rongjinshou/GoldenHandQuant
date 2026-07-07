# 运行记录 — outputv2（AI 修复版）

> 让评测 AI agent 照 BUG 卡片（`work/bugs/findings.md`）逐条修改工作目录下的源码，编译 + 公开
> 24 例自检效果。**纯 AI 正面解题，不依赖参考答案。**

## 运行环境

- JDK 17（Temurin 17.0.19）、Maven 3.9.9、bash
- `maven-settings.xml` 存在才用 `-s`（指向 Maven Central；内网镜像不可达时按 README 允许置空）
- 所有 `mvn` 命令显式带 `-Dmaven.repo.local=<target>/maven-repo`（构建规范见 `work/harness/README.md`）

## 执行步骤

### 1. 复制源码到工作目录

```bash
cp -a /app/code/judge-assets/02_04_design_implementation_consistency/. .
```

→ 当前工作目录得到 `code/`、`design-docs/`、`README.md`、`test-cases/`。

### 2. 照 BUG 卡片修复

主 agent 读 `work/bugs/findings.md`，按模块启动 subagent（`bug-fixer` 技能），逐条修改 `code/`
下对应源文件：读设计依据 → 改文件 → 确认符合设计；卡片标注的新增类新建、影子类删除。

### 3. 自检效果

```bash
bash work/harness/check-all.sh
#   ① 编译 + 安装业务模块（mvn install -DskipTests）→ BUILD SUCCESS
#   ② 公开黑盒 24 例（test-cases）             → 通过 N 例
```

## 说明（取证）

修复由评测 AI agent **现场完成**，公开/隐藏用例的通过率取决于 agent 照卡片修复的质量——这正是
本方案要检验的「纯 AI 修复效果」，**无参考答案兜底**。

作者侧已确认**自检链路可用**：`check-all` 的编译门 + 24 例回归门在完成态工程上运行为
`BUILD SUCCESS + 24/24`（该完成态即 `output/` 变体的已验证工作树）；`findings.md` 卡片覆盖全部
已定位不一致（166 改 + 37 增 + 13 删）。

STATUS: 方案就绪（修复效果由评测运行现场产生）
