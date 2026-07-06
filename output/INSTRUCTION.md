# INSTRUCTION — ShopHub 设计实现一致性修复（赛题 02_04）

本工具对**全新、未修复**的 ShopHub 工程施加已验证的设计一致性修复。全流程**确定性、无人工干预、可重复**。评测方只需按下面四步执行，即可得到修复后的工程。

> 目标工程（judge material）默认位于
> `/app/code/judge-assets/02_04_design_implementation_consistency`
> 该目录下含 `code/`、`test-cases/`、`design-docs/`、`README.md`。
> 下文用 `TARGET` 指代该根路径；若实际路径不同，把它作为参数传给 `apply.sh` 即可。

---

## 步骤 1 · 环境准备

需要 **JDK 17+** 与 **Maven 3.6+**。先检查：

```bash
java -version   # 期望 17 及以上
mvn  -version   # 期望 3.6 及以上
```

若已满足，跳到步骤 2。若缺失，用下面的免 root 便携安装（不依赖包管理器、不需人工确认）：

```bash
mkdir -p "$HOME/tools" && cd "$HOME/tools"
# JDK 17 (Temurin, 便携 tar.gz)
curl -fsSL -o jdk.tar.gz https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.19%2B7/OpenJDK17U-jdk_x64_linux_hotspot_17.0.19_7.tar.gz
tar -xzf jdk.tar.gz
# Maven 3.9.9 (便携)
curl -fsSL -o mvn.tar.gz https://archive.apache.org/dist/maven/maven-3/3.9.9/binaries/apache-maven-3.9.9-bin.tar.gz
tar -xzf mvn.tar.gz
export JAVA_HOME="$HOME/tools/jdk-17.0.19+7"
export PATH="$JAVA_HOME/bin:$HOME/tools/apache-maven-3.9.9/bin:$PATH"
java -version && mvn -version
```

`work/` 本身不含任何三方依赖（纯 bash + 知识库文本文件），无需额外安装。

---

## 步骤 2 · 施加修复（核心，确定性）

在本 `work/` 目录所在位置运行修复引擎，指向目标工程根：

```bash
bash work/fixer/apply.sh "$TARGET"
# 例：bash work/fixer/apply.sh /app/code/judge-assets/02_04_design_implementation_consistency
```

它会读取知识库、逐文件比对基线哈希、施加整份替换/新增/删除，并打印 apply-report（形如
`checked=193 applied(fix)=150 added=31 deleted=12 failed=0` `RESULT: OK`）。
**退出码 0 = 成功**，非 0 = 有文件写入失败。此步执行完，`"$TARGET"/code/` 即为修复后的工程。引擎幂等，可重复运行。

---

## 步骤 3 · 验证（构建 + 公开黑盒自检）

下面对材料结构做了防御性处理：`maven-settings.xml` 存在才用 `-s`（否则走默认 Maven Central），`test-cases/` 存在才跑黑盒——无论哪种情况，修复后的 `code/` 都已由步骤 2 产出。

```bash
# maven 设置：存在则用；内网镜像不可达时其内容可按 README 置为空的 <settings/>
SETTINGS_OPT=""; [ -f "$TARGET/maven-settings.xml" ] && SETTINGS_OPT="-s $TARGET/maven-settings.xml"

# 3a. 构建修复后的业务工程（始终执行，证明可编译）
mvn $SETTINGS_OPT -f "$TARGET/code/pom.xml" install -DskipTests           # 期望 BUILD SUCCESS

# 3b. 材料内含 test-cases/ 时，跑公开黑盒自检
if [ -f "$TARGET/test-cases/pom.xml" ]; then
  mvn $SETTINGS_OPT -f "$TARGET/test-cases/pom.xml" test                  # 期望 Tests run: 24, Failures: 0, Errors: 0
fi
```

---

## 步骤 4 ·（可选）在线深核复核

若希望在确定性修复之外再加一层 agent 复核，让执行 agent 把
`work/skills/design-consistency-fixer/SKILL.md`
作为普通 Markdown 读入并按其步骤执行——它**验证优先**：先跑步骤 3，全绿即止；仅对任何未通过用例，依 `work/fixer/checklist/<module>.md` 对照 `design-docs/` 深核，并**带护栏**（备份→编译→失败回滚）修复。此步不修改契约、不针对具体用例硬编码。

---

## 执行完成判定

- `bash work/fixer/apply.sh` 退出码为 0，且步骤 3 黑盒输出 `Failures: 0, Errors: 0`；或
- 本包内 `result/output.md` 存在且含 `STATUS: DONE` 标记行（记录了一次成功运行）。

## 修复结果获取方式

- **修复后的工程**：`"$TARGET"/code/`（`apply.sh` 原地写入）。
- **修复清单与设计依据**：`work/fixer/knowledge-base/findings.md`。
- **方案说明**：`work/DESIGN.md`。
- **过程日志**：`logs/trace/`；**运行报告**：`result/output.md`。
