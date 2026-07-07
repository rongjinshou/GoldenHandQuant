#!/usr/bin/env bash
#
# check-all.sh — 修复效果自检：编译 + 公开黑盒 24 例回归。
#
# 纯 AI 修复版：不依赖任何"参考答案"，只客观检验 agent 改完的工程能否编译、
# 公开用例通过多少。用法：
#   bash check-all.sh [TARGET_ROOT]    # TARGET_ROOT 省略 = 当前工作目录；需 JDK17 + Maven
set -uo pipefail
TARGET_ROOT="${1:-$PWD}"

echo "=================================================================="
echo " ShopHub 修复效果自检  ·  target = $TARGET_ROOT"
echo "=================================================================="
command -v mvn >/dev/null 2>&1 || { echo "需要 mvn（JDK17 + Maven）来编译并运行公开用例。"; exit 2; }
[ -f "$TARGET_ROOT/code/pom.xml" ] || { echo "当前目录下没有 code/pom.xml（先按第①步复制源码）。"; exit 2; }

# maven 设置：存在才用 -s；内网镜像不可达时其内容可按 README 置为空的 <settings/>
S=""; [ -f "$TARGET_ROOT/maven-settings.xml" ] && S="-s $TARGET_ROOT/maven-settings.xml"
# 本地仓库：显式指定 -Dmaven.repo.local，避免依赖/污染用户目录 .m2 缓存、保证各 agent 工作目录
# 相互隔离。test-cases 是独立 reactor，从这个本地仓库消费刚 install 的业务模块，故下面两条 mvn
# 都带同一个 REPO_OPT，否则跑公开用例时找不到业务模块。
REPO_OPT="-Dmaven.repo.local=$TARGET_ROOT/maven-repo"
BUILD_LOG="$(mktemp)"; TEST_LOG="$(mktemp)"

echo; echo "① 编译 + 安装业务模块（mvn install -DskipTests）"
if mvn $S $REPO_OPT -f "$TARGET_ROOT/code/pom.xml" install -DskipTests -q >"$BUILD_LOG" 2>&1; then
    echo "   BUILD SUCCESS"
else
    echo "   BUILD FAILED（末尾日志）："; tail -15 "$BUILD_LOG" | sed 's/^/     /'
    echo; echo " 结论：编译未通过，还有 BUG 未修好或引入了编译错误。修正后重跑。"; exit 1
fi

echo; echo "② 公开黑盒 24 例（test-cases，只运行不修改）"
if [ ! -f "$TARGET_ROOT/test-cases/pom.xml" ]; then
    echo "   未找到 test-cases，跳过回归门。"; echo; echo " 结论：编译通过（未跑公开用例）。"; exit 0
fi
if mvn $S $REPO_OPT -f "$TARGET_ROOT/test-cases/pom.xml" test -q >"$TEST_LOG" 2>&1; then
    n="$(grep -rhoE 'Tests run: [0-9]+' "$TARGET_ROOT"/test-cases/target/surefire-reports/*.txt 2>/dev/null | awk '{s+=$3} END{print s}')"
    echo "   公开用例全部通过：${n:-?} 例 —— PASS"
    echo; echo "=================================================================="
    echo " 自检通过：编译 BUILD SUCCESS + 公开 24 例全绿。隐藏用例由评测平台判定。"
    echo "=================================================================="
    exit 0
else
    echo "   有用例未通过（还有 BUG 未修好、或修改改错/引入回归）："
    grep -E 'Tests run:|<<< (FAILURE|ERROR)|FAIL' "$TEST_LOG" | tail -10 | sed 's/^/     /'
    echo; echo " 结论：公开用例未全绿。对照 findings.md 的设计依据继续修。"; exit 1
fi
