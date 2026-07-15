#!/usr/bin/env bash
grep -q "$(printf '\r')" "$0" 2>/dev/null && { _t="${TMPDIR:-/tmp}/lf$$-$(basename "$0")"; tr -d '\r' <"$0" >"$_t" && exec bash "$_t" "$@"; } # CRLF 自愈：被错误打包成 CRLF 时转成 LF 副本重新执行
#
# check-all.sh — 修复效果自检：编译 + 黑盒用例回归（用例总数以本环境实际运行数为准，可能不是 24）。
#
# 纯 AI 修复版：不依赖任何"参考答案"，只客观检验 agent 改完的工程能否编译、
# 用例通过多少。用法：
#   bash check-all.sh [TARGET_ROOT]   # TARGET_ROOT 省略 = 当前工作目录；需 PATH 有 JDK17+（含 javac）与 Maven
set -uo pipefail
TARGET_ROOT="${1:-$PWD}"

echo "=================================================================="
echo " ShopHub 修复效果自检  ·  target = $TARGET_ROOT"
echo "=================================================================="
# 环境守卫（快速失败，不探测不自救）：评测机预装完整 JDK 21 + Maven，release 17 交叉编译，
# java ≥17 且 javac 在即满足；缺什么明确报错并停，agent 把报错记进 result/output.md。
java_major() { # 解析 java 主版本："17.0.10"→17、"21.0.10"→21，老格式 "1.8.0_392"→8
    local v; v="$("$1" -version 2>&1 | awk -F'"' '/version/{split($2,a,"."); print (a[1]==1)?a[2]:a[1]; exit}')"
    printf '%s\n' "${v%%[!0-9]*}"
}
command -v java  >/dev/null 2>&1 || { echo "环境缺陷：PATH 中没有 java（评测机不应出现）。如实记录后停止。"; exit 2; }
command -v javac >/dev/null 2>&1 || { echo "环境缺陷：有 java 但没有 javac——是 JRE 不是 JDK，无法编译。如实记录后停止。"; exit 2; }
command -v mvn   >/dev/null 2>&1 || { echo "环境缺陷：PATH 中没有 mvn（评测机不应出现）。如实记录后停止。"; exit 2; }
JMAJ="$(java_major java)"
[ "${JMAJ:-0}" -ge 17 ] || { echo "环境缺陷：java 主版本为 ${JMAJ:-未知}，需要 ≥17（17~21 均可）。如实记录后停止。"; exit 2; }
[ -f "$TARGET_ROOT/code/pom.xml" ] || { echo "当前目录下没有 code/pom.xml（先按第①步复制源码）。"; exit 2; }

# 单实例锁：与 ratchet.sh 共用同一把（.ratchet/lock）——自检同样要起 mvn，与正在进行的
# snapshot/verify 并行会互踩本地仓库与 surefire 报告，抢不到锁就稍后再来。
if command -v flock >/dev/null 2>&1; then
    mkdir -p "$TARGET_ROOT/.ratchet"; exec 9>"$TARGET_ROOT/.ratchet/lock"
    flock -n 9 || { echo "另一个 harness 构建正在运行（$TARGET_ROOT/.ratchet/lock 被占用）——稍后再自检。"; exit 3; }
fi

# maven 设置：存在才用 -s；内网镜像不可达时其内容可按 README 置为空的 <settings/>。
# 本地仓库：显式指定 -Dmaven.repo.local，避免依赖/污染用户目录 .m2 缓存、保证各 agent 工作目录
# 相互隔离。test-cases 是独立 reactor，从这个本地仓库消费刚 install 的业务模块，故下面两条 mvn
# 都带同样的选项，否则跑公开用例时找不到业务模块。参数用数组传递，路径含空格也安全。
MVN_OPTS=()
[ -f "$TARGET_ROOT/maven-settings.xml" ] && MVN_OPTS+=(-s "$TARGET_ROOT/maven-settings.xml")
MVN_OPTS+=("-Dmaven.repo.local=$TARGET_ROOT/maven-repo")
BUILD_LOG="$(mktemp)"; TEST_LOG="$(mktemp)"

echo; echo "① 编译 + 安装业务模块（mvn install -DskipTests）"
if mvn "${MVN_OPTS[@]}" -f "$TARGET_ROOT/code/pom.xml" install -DskipTests -q >"$BUILD_LOG" 2>&1; then
    echo "   BUILD SUCCESS"
else
    echo "   BUILD FAILED（末尾日志；完整日志 $BUILD_LOG）："; tail -15 "$BUILD_LOG" | sed 's/^/     /'
    grep -qE 'error reading|zip END header|invalid LOC header|Could not resolve dependencies' "$BUILD_LOG" && \
        echo "   疑似本地 Maven 仓库损坏（上次构建中断残留）：执行 rm -rf \"$TARGET_ROOT/maven-repo\" 后重跑本命令即可自愈。"
    echo; echo " 结论：编译未通过，还有 BUG 未修好或引入了编译错误。修正后重跑。"; exit 1
fi

echo; echo "② 黑盒用例回归（test-cases，只运行不修改；总数以实际运行为准）"
if [ ! -f "$TARGET_ROOT/test-cases/pom.xml" ]; then
    echo "   未找到 test-cases，跳过回归门。"; echo; echo " 结论：编译通过（未跑公开用例）。"; exit 0
fi
# 只统计 surefire 报告、不信 mvn 退出码（与 ratchet.sh count_pass 完全同构）：
# 通过数 = Σ(run - failures - errors - skipped)，skipped 不算通过；上下文整体起不来时无报告 = 0
rm -rf "$TARGET_ROOT/test-cases/target/surefire-reports"
mvn "${MVN_OPTS[@]}" -f "$TARGET_ROOT/test-cases/pom.xml" test -q >"$TEST_LOG" 2>&1 || true
read -r PASS RUN <<<"$(grep -rhoE 'Tests run: [0-9]+, Failures: [0-9]+, Errors: [0-9]+, Skipped: [0-9]+' \
        "$TARGET_ROOT/test-cases/target/surefire-reports"/*.txt 2>/dev/null |
    awk -F'[:,]' '{run+=$2; fail+=$4; err+=$6; skip+=$8} END{print run-fail-err-skip+0, run+0}')"
if [ "${RUN:-0}" -gt 0 ] && [ "$PASS" -eq "$RUN" ]; then
    echo "   公开用例全部通过：$PASS/$RUN —— PASS"
    echo; echo "=================================================================="
    echo " 自检通过：编译 BUILD SUCCESS + 公开 $RUN 例全绿。隐藏用例由评测平台判定。"
    echo "=================================================================="
    exit 0
else
    echo "   有用例未通过：通过 $PASS / 运行 ${RUN:-0}（还有 BUG 未修好、或修改改错/引入回归）。"
    echo "   失败用例与断言摘要（完整报告：$TARGET_ROOT/test-cases/target/surefire-reports/）："
    awk '/<<< (FAILURE|ERROR)!/{print "✗ " $0; p=3; next} p && p-- {print "    " $0}' \
        "$TARGET_ROOT/test-cases/target/surefire-reports"/*.txt 2>/dev/null | head -24 | sed 's/^/     /'
    [ "${RUN:-0}" -eq 0 ] && echo "   （没有任何 surefire 报告——多半是 Spring 上下文整体起不来，看 $TEST_LOG 排查）"
    echo "   完整 mvn 日志：$TEST_LOG"
    echo; echo " 结论：公开用例未全绿。对照 work/bugs/README.md 批次表定位对应卡片文件继续修。"; exit 1
fi
