# Harness — 修复效果自检

纯 AI 修复版的 Harness 只做一件事：**客观检验 agent 改完的工程效果**，不依赖任何"参考答案"。

## `check-all.sh`

```bash
bash work/harness/check-all.sh [TARGET_ROOT]     # TARGET_ROOT 省略 = 当前工作目录；需 JDK17 + Maven
```

两道门：

1. **编译门**：`mvn install -DskipTests` 必须 `BUILD SUCCESS`（改坏或漏改导致编译错会暴露）。
2. **回归门**：公开黑盒 24 例（`test-cases`，只运行不修改）——报出通过例数；有未过则列出失败，
   提示对照 `work/bugs/findings.md` 的设计依据继续修。

全绿即：编译成功 + 公开 24 例全通过。隐藏用例由评测平台判定——那正是本方案要检验的「纯 AI
修复」能力，取决于 agent 照卡片修复的质量，无参考答案兜底。

## 构建规范（脚本内部即按此执行，手动构建也须照此）

- `maven-settings.xml` **存在才用** `-s`（否则走默认 Maven Central；内网镜像不可达时其内容可按
  README 置为空的 `<settings/>`）。
- 所有 Maven 命令**显式指定** `-Dmaven.repo.local=<target>/maven-repo`，避免依赖/污染用户目录
  `.m2` 缓存、保证各 agent 工作目录相互隔离。
- `test-cases` 是**独立 reactor**，从该本地仓库消费刚 `install` 的业务模块，因此它的 `mvn test`
  必须带**同一个** `-Dmaven.repo.local`，否则找不到业务模块。

> 单个 subagent 也可在改完自己模块后局部编译自检（同样带 settings 防御与本地仓库）：
> `S=""; [ -f maven-settings.xml ] && S="-s maven-settings.xml"; mvn $S -Dmaven.repo.local="$PWD/maven-repo" -f code/pom.xml -pl <module> -am compile -q`。
