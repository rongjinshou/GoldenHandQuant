# INSTRUCTION — ShopHub 设计实现一致性修复（赛题 02_04 · AI 修复版）

> 读者是执行本作品的 **AI agent**。本作品：我们已完成「检查」——在 `work/bugs/findings.md` 里
> 给出了 ShopHub 与冻结设计（`design-docs/` + `README.md`）之间**已定位的全部 BUG 卡片**（每条含
> 症状、位置、设计依据、修法方向）。你要做「修复」：**照着 BUG 卡片，逐条修改工作目录下的源代码**。

## 1. 环境准备（GUIDANCE 4.1）

- 需要 `bash`、`JDK 17`、`Maven 3.6+`（用于第 ③ 步编译 + 跑公开用例自检；评测平台通常已具备）。
- 无需 Docker / 网络 / 其他服务。

## 2. 执行方式（GUIDANCE 4.2）

### 第 ① 步 — 把待修复源码复制到当前工作目录

```bash
cp -a /app/code/judge-assets/02_04_design_implementation_consistency/. .
```

这是平台提供的、**未修复**的 ShopHub 材料（含 `code/`、`design-docs/`、`README.md`、`test-cases/`）。
它是只读的——**复制到当前工作目录后改副本，不要去改原路径**。复制完成后，当前工作目录下应
出现 `code/`、`design-docs/`、`README.md`、`test-cases/`。

> 若上述路径在你的环境中不存在，自行定位含 `code/pom.xml` 的 ShopHub 工程根目录
> （`pom.xml` 带 `shophub`/`com.ecommerce` 指纹）后 `cp -a <该目录>/. .`。

### 第 ② 步 — 照 BUG 卡片修改源代码

打开 **`work/bugs/findings.md`**——已定位的全部设计-实现不一致，按模块组织，每条卡片含：
**症状 / 位置（文件）/ 设计依据（`design-docs/` 章节 + `README.md` 契约）/ 修法方向**。

**逐条修复**（推荐按模块并行派 subagent）：

1. 按**模块**（user / product / inventory / … / review）分组，每组启动一个 **subagent**，
   交付内容 = 该模块在 `findings.md` 里的 BUG 卡片 + 本仓库 `work/skills/bug-fixer/SKILL.md`（行为规范）。
   *（不支持 subagent 的环境：主 agent 自己按同一规范逐条修。）*
2. 每条卡片：**读设计依据** → 打开工作目录下 `code/` 里的目标文件 → **按设计修改**（代码错了改
   代码，绝不改文档）→ 确认改动符合卡片的设计依据。
3. 对"应新增的类"（卡片标注）新建文件；对"应删除的文件"（如模块内影子事件类）删除。

### 第 ③ 步 — 自检修复效果（需 JDK + Maven）

```bash
bash work/harness/check-all.sh
```

它对工作目录做：① 编译 + 安装业务模块 ② 跑公开黑盒 24 例回归。用来观察修复效果。
`work/checklist/<module>.md` 提供逐模块强规则速查，可辅助复核。

**构建规范（`check-all.sh` 内部即按此执行；若你手动构建，也必须照此来）**：`maven-settings.xml`
存在才用 `-s`（否则走默认 Maven Central）；所有 Maven 命令显式指定 `-Dmaven.repo.local`，避免
依赖/污染用户目录 `.m2` 缓存；`test-cases` 是独立 reactor，从该本地仓库消费刚 `install` 的业务
模块，故它的 `mvn test` 必须带**同一个** `-Dmaven.repo.local`：

```bash
TARGET="$PWD"    # 第①步复制源码后的当前工作目录

# maven 设置：存在则用；内网镜像不可达时其内容可按 README 置为空的 <settings/>
SETTINGS_OPT=""; [ -f "$TARGET/maven-settings.xml" ] && SETTINGS_OPT="-s $TARGET/maven-settings.xml"

# 本地仓库：README 要求所有 Maven 命令显式指定 -Dmaven.repo.local，避免依赖用户目录缓存
REPO_OPT="-Dmaven.repo.local=$TARGET/maven-repo"

# 构建修复后的业务工程（始终执行，证明可编译）
mvn $SETTINGS_OPT $REPO_OPT -f "$TARGET/code/pom.xml" install -DskipTests           # 期望 BUILD SUCCESS

# 公开黑盒 24 例（同一个 REPO_OPT）
[ -f "$TARGET/test-cases/pom.xml" ] && mvn $SETTINGS_OPT $REPO_OPT -f "$TARGET/test-cases/pom.xml" test   # 期望 Tests run: 24, Failures: 0, Errors: 0
```

## 3. 执行完成判定（GUIDANCE 4.3）

- 已照 `work/bugs/findings.md` 逐条修改工作目录下的 `code/` 源码；
- （自检）`check-all.sh` 输出 **编译 BUILD SUCCESS + 公开 24 例全绿**。

**当前工作目录下的 `code/` 即为修复后的工程。**（隐藏用例由评测平台判定。）

## 4. 修复结果获取方式（GUIDANCE 4.4）

- **修复后的工程**：`<当前工作目录>/code/`。
- **BUG 卡片清单与设计依据**：`work/bugs/findings.md`。
- **方案说明**：`work/DESIGN.md`。

## 禁止事项

1. 不修改 `design-docs/`、`README.md`、`test-cases/`、REST API 的 URL/方法/请求头/字段名与类型、`/api/v1/` 前缀。
2. 不针对某个测试用例硬编码逻辑——朝**设计与契约**修，而非迎合可见用例。
3. 不新增数据库 reset/bootstrap 钩子。
4. 只改 BUG 卡片涉及的源码，不"顺手优化"无关代码。
