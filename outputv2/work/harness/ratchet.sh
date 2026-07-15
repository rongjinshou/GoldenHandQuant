#!/usr/bin/env bash
grep -q "$(printf '\r')" "$0" 2>/dev/null && { _t="${TMPDIR:-/tmp}/lf$$-$(basename "$0")"; tr -d '\r' <"$0" >"$_t" && exec bash "$_t" "$@"; } # CRLF 自愈：被错误打包成 CRLF 时转成 LF 副本重新执行
#
# ratchet.sh — 修复过程的确定性护栏（棘轮）：快照 / 验证-固化 / 自动回滚。
#
# 设计前提：AI 修复一定会犯错，护栏保证错误不出门 ——
#   · 任何时刻工作树要么等于最后一个「已验证良好」状态（golden），要么正在被验证；
#   · 验证失败（编译不过 / 通过数下降 / 上下文起不来）自动回滚到 golden；
#   · 最坏交付 = max(基线, 已固化的最佳)，「交付一个 0 分工程」在结构上不可能。
#
# 用法（TARGET_ROOT 省略 = 当前工作目录；需 PATH 里有 JDK 17+（含 javac）与 Maven——评测机预装 JDK21 即满足）：
#   bash ratchet.sh snapshot [TARGET_ROOT]   # 修改前执行一次：跑基线检验，建立 golden 快照
#   bash ratchet.sh verify   [TARGET_ROOT]   # 每修完一批执行：无逐用例回归且通过数不降 → 固化；否则自动回滚
#   bash ratchet.sh status   [TARGET_ROOT]   # 查看 golden / 最佳通过数 / 最近历史
#
# 结论行都带 total=<本环境用例总数>（评测机的 test-cases 可能是全量集而非 24 例——
# "跑完没跑完/要不要补救"一律以 total 为准，绝不假设 24）。机器可读结论（最后一行）：
#   RATCHET_RESULT: ADVANCED pass=<n> best=<n> total=<t>  # 通过数提升，已固化 → 修下一批
#   RATCHET_RESULT: OK pass=<n> best=<n> total=<t>        # 持平且无逐用例回归，已固化 → 修下一批
#   RATCHET_RESULT: OK_NO_CHANGES pass=<n> best=<n> total=<t> # 工作树与 golden 无差异 = 没改任何东西
#                                                   #（回滚后未实际重修就 verify 的防呆；收尾终验时=正常）
#   RATCHET_RESULT: ROLLED_BACK reason=<r> ...      # 已自动回滚到 golden → 本批重试一次或跳过
#                                                   #（reason=regression 含"总数没降但改坏了此前通过的用例"）
#   RATCHET_RESULT: BUSY best=<n>                   # 单实例锁被占：另一个构建还在跑（snapshot/verify
#                                                   # 都可能返回）→ 轮询等它结束，绝不并行起第二个构建
set -uo pipefail

CMD="${1:-}"; TARGET_ROOT="${2:-$PWD}"
RS="$TARGET_ROOT/.ratchet"            # 状态目录：golden 快照 + 最佳通过数 + 历史
GOLDEN="$RS/golden-code"
BEST_F="$RS/best"
LOG_F="$RS/history.log"

usage() { grep '^#   bash' "$0" | sed 's/^# *//'; exit 2; }
[ -n "$CMD" ] || usage
[ -f "$TARGET_ROOT/code/pom.xml" ] || { echo "错误：$TARGET_ROOT 下没有 code/pom.xml（先按 INSTRUCTION 第①步复制源码）。"; exit 2; }

# 单实例锁：snapshot/verify 都要起 mvn 写同一个本地仓库与 surefire 报告，并行必然互踩——
# 非阻塞抢锁，占用时输出 BUSY 让调用方轮询等待；status 是纯读操作，保持无锁随时可查。
case "$CMD" in snapshot|verify)
    if command -v flock >/dev/null 2>&1; then
        mkdir -p "$RS"; exec 9>"$RS/lock"
        flock -n 9 || {
            echo "另一个 harness 构建正在运行（$RS/lock 被占用，可能含尚未退出的 mvn 进程）。"
            echo "绝不并行启动第二个构建——轮询等待其输出 RATCHET_RESULT 后再继续。"
            echo "RATCHET_RESULT: BUSY best=$(cat "$BEST_F" 2>/dev/null || echo 0)"; exit 3
        }
    fi ;;
esac

# 环境守卫（快速失败，不做任何自救/探测/下载）：评测机预装完整 JDK 21 + Maven，工程按
# release 17 交叉编译，java 主版本 ≥17 且 javac 存在即满足。缺什么就明确报错并停——
# agent 应把报错原文记进 result/output.md，绝不要去找不存在的安装目录或尝试自行下载。
java_major() { # 解析 java 主版本："17.0.10"→17、"21.0.10"→21，老格式 "1.8.0_392"→8
    local v; v="$("$1" -version 2>&1 | awk -F'"' '/version/{split($2,a,"."); print (a[1]==1)?a[2]:a[1]; exit}')"
    printf '%s\n' "${v%%[!0-9]*}"
}
if [ "$CMD" != status ]; then
    command -v java  >/dev/null 2>&1 || { echo "环境缺陷：PATH 中没有 java（评测机不应出现）。如实记录本报错后停止本批。"; exit 2; }
    command -v javac >/dev/null 2>&1 || { echo "环境缺陷：有 java 但没有 javac——这是 JRE 不是 JDK，无法编译（评测机不应出现）。如实记录后停止本批。"; exit 2; }
    command -v mvn   >/dev/null 2>&1 || { echo "环境缺陷：PATH 中没有 mvn（评测机不应出现）。如实记录本报错后停止本批。"; exit 2; }
    JMAJ="$(java_major java)"
    [ "${JMAJ:-0}" -ge 17 ] || { echo "环境缺陷：java 主版本为 ${JMAJ:-未知}，需要 ≥17（工程按 release 17 交叉编译，17~21 均可）。如实记录后停止本批。"; exit 2; }
fi

# 构建规范：maven-settings.xml 存在才用 -s；所有 mvn 显式 -Dmaven.repo.local，避免依赖/污染
# 用户 .m2；test-cases 是独立 reactor，用同一本地仓库才找得到刚 install 的业务模块。
# 参数用数组传递，目标路径含空格/非 ASCII 字符也安全。
MVN_OPTS=()
[ -f "$TARGET_ROOT/maven-settings.xml" ] && MVN_OPTS+=(-s "$TARGET_ROOT/maven-settings.xml")
MVN_OPTS+=("-Dmaven.repo.local=$TARGET_ROOT/maven-repo")

log() { printf '%s  %s\n' "$(date '+%F %T')" "$*" >>"$LOG_F"; }

# —— code/ 的快照与恢复：排除 target/ 派生物。换目录用 mv 交换而不是 rm 旧目录再 mv：
# rm -rf 旧目录中途被杀会留下删了一半的 golden，之后回滚就会拿坏 golden 覆盖 code/；
# mv 重命名是原子的，唯一空窗是两次 mv 之间（旧的已挪成 .old、新的还没就位），
# 由 verify/status 入口的 .old 自愈兜住 ——
copy_code() { # $1=src  $2=dst
    rm -rf "$2.tmp" "$2.old"
    cp -a "$1" "$2.tmp" || return 1
    find "$2.tmp" -type d -name target -prune -exec rm -rf {} + 2>/dev/null
    { [ ! -e "$2" ] || mv "$2" "$2.old"; } && mv "$2.tmp" "$2" && rm -rf "$2.old"
}

build() { # 编译门：业务模块 install（黑盒从本地仓库消费业务模块）
    mvn "${MVN_OPTS[@]}" -f "$TARGET_ROOT/code/pom.xml" install -DskipTests -q >"$RS/build.log" 2>&1
}

run_tests() { # 跑公开黑盒；不看 mvn 退出码，只统计 surefire 报告（部分失败也要计数）
    rm -rf "$TARGET_ROOT/test-cases/target/surefire-reports"
    mvn "${MVN_OPTS[@]}" -f "$TARGET_ROOT/test-cases/pom.xml" test -q >"$RS/test.log" 2>&1 || true
}

count_pass() { # 通过数 = Σ(run - failures - errors - skipped)；无报告（上下文全炸/依赖缺失）= 0
    local d="$TARGET_ROOT/test-cases/target/surefire-reports"
    [ -d "$d" ] || { echo 0; return; }
    grep -rhoE 'Tests run: [0-9]+, Failures: [0-9]+, Errors: [0-9]+, Skipped: [0-9]+' "$d"/*.txt 2>/dev/null |
        awk -F'[:,]' '{run+=$2; fail+=$4; err+=$6; skip+=$8} END{print run-fail-err-skip+0}'
}

count_total() { # 本次运行的用例总数——评测机上的 test-cases 可能是全量集（≠24），
                # 一切"跑完没跑完/该不该补救"的判断都以此为准，绝不硬编码用例数
    local d="$TARGET_ROOT/test-cases/target/surefire-reports"
    [ -d "$d" ] || { echo 0; return; }
    grep -rhoE 'Tests run: [0-9]+, Failures: [0-9]+, Errors: [0-9]+, Skipped: [0-9]+' "$d"/*.txt 2>/dev/null |
        awk -F'[:,]' '{run+=$2} END{print run+0}'
}

failing_set() { # 本次运行"失败/错误"的用例全名（排序去重）；排除类级汇总行
    local d="$TARGET_ROOT/test-cases/target/surefire-reports"
    [ -d "$d" ] || return 0
    grep -rhE '<<< (FAILURE|ERROR)!' "$d"/*.txt 2>/dev/null | grep -v 'Tests run:' |
        sed -E 's/ --.*//; s/^[[:space:]]*//' | sort -u
}

HAS_TESTS=1; [ -f "$TARGET_ROOT/test-cases/pom.xml" ] || HAS_TESTS=0

case "$CMD" in
snapshot)
    if [ -d "$GOLDEN" ]; then
        B="$(cat "$BEST_F" 2>/dev/null || echo 0)"; T="$(cat "$RS/total" 2>/dev/null || echo 0)"
        echo "已有 golden 快照（best=$B/total=$T）。快照只建一次；之后请用 verify。"
        echo "RATCHET_RESULT: OK pass=$B best=$B total=$T"; exit 0
    fi
    mkdir -p "$RS"
    echo "① 基线检验（修改前的原始工程）……"
    BASE=0; TOT=0
    if build; then
        echo "   基线编译：BUILD SUCCESS"
        if [ "$HAS_TESTS" = 1 ]; then
            run_tests; BASE="$(count_pass)"; TOT="$(count_total)"
            echo "$TOT" >"$RS/total"; failing_set >"$RS/failing.golden"
            echo "   基线用例通过：$BASE / 总数：$TOT（此环境的用例总数以此为准，可能不是 24）"
        else
            echo "   （未找到 test-cases，只启用编译门）"
        fi
    else
        echo "   警告：基线编译失败（原始工程即不可构建？）。best 记 0，之后任何可编译状态都会被固化。"
        tail -5 "$RS/build.log" | sed 's/^/     /'
        grep -qE 'error reading|zip END header|invalid LOC header|Could not resolve dependencies' "$RS/build.log" && \
            echo "   疑似本地 Maven 仓库损坏（上次构建中断残留）：执行 rm -rf \"$TARGET_ROOT/maven-repo\" 后重跑本命令即可自愈。"
    fi
    echo "② 建立 golden 快照……"
    # 先写 best 再建 golden：中间被杀只留下「best 在、golden 缺」的惰性状态，重跑 snapshot 即可；
    # 反序会留下「golden 在、best 缺」——那会被 verify 误读成 best=0，是 verify 入口防呆要拦的损坏态
    echo "$BASE" >"$BEST_F"
    copy_code "$TARGET_ROOT/code" "$GOLDEN" || { echo "快照失败（磁盘空间？）"; exit 2; }
    log "snapshot base=$BASE total=$TOT"
    echo "golden 已建立。此后每修完一批跑：bash ratchet.sh verify"
    echo "RATCHET_RESULT: OK pass=$BASE best=$BASE total=$TOT"
    ;;
verify)
    # golden 自愈：copy_code 若恰在两次 mv 之间被杀，会留下「golden 缺、golden.old 在」——先恢复再判断
    [ -d "$GOLDEN" ] || { [ -d "$GOLDEN.old" ] && mv "$GOLDEN.old" "$GOLDEN"; }
    [ -d "$GOLDEN" ] || { echo "错误：还没有 golden 快照。先跑：bash ratchet.sh snapshot"; exit 2; }
    [ -f "$BEST_F" ] || { echo "状态损坏：golden 在而 best 缺失。请 rm -rf \"$RS\" 后重跑 snapshot。"; exit 2; }
    BEST="$(cat "$BEST_F" 2>/dev/null || echo 0)"
    # 防"空重试"：工作树与 golden 无任何差异时，没有东西可验证——直接短路，
    # 避免把"什么都没改的 OK"误读成"重修成功"（ROLLED_BACK 后最常见的误判）。
    if diff -rq --exclude=target "$GOLDEN" "$TARGET_ROOT/code" >/dev/null 2>&1; then
        echo "工作树与 golden 完全一致——没有任何新改动可验证。"
        echo "· 若你刚经历 ROLLED_BACK 并认为已经重修：你的改动并没有写入 code/，请先实际修改再 verify；"
        echo "· 若这是收尾终验：一切正常，交付态 = 已验证良好态。"
        echo "RATCHET_RESULT: OK_NO_CHANGES pass=$BEST best=$BEST total=$(cat "$RS/total" 2>/dev/null || echo 0)"; exit 0
    fi
    echo "① 编译门（mvn install -DskipTests）……"
    if ! build; then
        echo "   BUILD FAILED（编译错误摘要；完整日志 $RS/build.log）："
        ERRS="$(grep -E '\[ERROR\] .+\.java:\[[0-9]+' "$RS/build.log" | head -6)"
        if [ -n "$ERRS" ]; then printf '%s\n' "$ERRS" | sed 's/^/     /'; else tail -10 "$RS/build.log" | sed 's/^/     /'; fi
        grep -qE 'error reading|zip END header|invalid LOC header|Could not resolve dependencies' "$RS/build.log" && \
            echo "   疑似本地 Maven 仓库损坏（上次构建中断残留）：执行 rm -rf \"$TARGET_ROOT/maven-repo\" 后重跑本命令即可自愈。"
        copy_code "$GOLDEN" "$TARGET_ROOT/code" || { echo "回滚失败！"; exit 2; }
        log "verify compile_failed -> rolled back (best=$BEST)"
        echo "   已自动回滚到 golden（工作树 = 最后已验证良好状态）。本批改动请修正后重来（或跳过本批）。"
        echo "RATCHET_RESULT: ROLLED_BACK reason=compile_failed best=$BEST"; exit 1
    fi
    echo "   BUILD SUCCESS"
    if [ "$HAS_TESTS" = 0 ]; then
        copy_code "$TARGET_ROOT/code" "$GOLDEN" || { echo "固化失败（磁盘空间？）"; exit 2; }
        log "verify compile_only -> ok"
        echo "RATCHET_RESULT: OK pass=0 best=0 total=0"; exit 0
    fi
    echo "② 黑盒回归……"
    run_tests; PASS="$(count_pass)"; TOT="$(count_total)"
    # 逐用例回归判定：除通过数不回退外，还要求「没有任何此前通过的用例本批变红」——
    # 只比数量会放过"修好 A 同时改坏 B"的等额交换（数量不变、集合已恶化），
    # 那正是评分里 stability 维度的杀手。failing.golden 缺失时（旧状态目录）退化为纯数量比较。
    failing_set >"$RS/failing.now"
    NEWFAIL=""
    [ -f "$RS/failing.golden" ] && NEWFAIL="$(comm -13 "$RS/failing.golden" "$RS/failing.now" 2>/dev/null)"
    if [ "$PASS" -ge "$BEST" ] && [ -z "$NEWFAIL" ]; then
        copy_code "$TARGET_ROOT/code" "$GOLDEN" || { echo "固化失败（磁盘空间？）"; exit 2; }
        echo "$PASS" >"$BEST_F"; echo "$TOT" >"$RS/total"; mv "$RS/failing.now" "$RS/failing.golden"
        if [ "$PASS" -gt "$BEST" ]; then VERDICT="ADVANCED"; else VERDICT="OK"; fi
        echo "   通过 $PASS / $TOT（此前最佳 $BEST）—— 已固化为新 golden。"
        log "verify pass=$PASS best=$BEST total=$TOT -> $VERDICT"
        echo "RATCHET_RESULT: $VERDICT pass=$PASS best=$PASS total=$TOT"; exit 0
    else
        if [ -n "$NEWFAIL" ]; then
            echo "   本批把此前通过的用例改坏了（即使总通过数未降，这也是回归）——新增失败用例："
            printf '%s\n' "$NEWFAIL" | sed 's/^/     ✗ /'
        else
            echo "   通过 $PASS < 此前最佳 $BEST —— 本批引入了回归。"
        fi
        echo "   失败用例与断言摘要（完整报告：$TARGET_ROOT/test-cases/target/surefire-reports/）："
        awk '/<<< (FAILURE|ERROR)!/{print "✗ " $0; p=3; next} p && p-- {print "    " $0}' \
            "$TARGET_ROOT/test-cases/target/surefire-reports"/*.txt 2>/dev/null | head -24 | sed 's/^/     /'
        copy_code "$GOLDEN" "$TARGET_ROOT/code" || { echo "回滚失败！"; exit 2; }
        log "verify pass=$PASS best=$BEST newfail=$(printf '%s' "$NEWFAIL" | grep -c . || true) -> rolled back"
        echo "   已自动回滚到 golden（工作树 = 最后已验证良好状态）。本批改动请修正后重来（或跳过本批）。"
        echo "RATCHET_RESULT: ROLLED_BACK reason=regression pass=$PASS best=$BEST total=$TOT"; exit 1
    fi
    ;;
status)
    # golden 自愈（同 verify 入口）：把中断残留的 golden.old 恢复为 golden，再报告状态
    [ -d "$GOLDEN" ] || { [ -d "$GOLDEN.old" ] && mv "$GOLDEN.old" "$GOLDEN"; }
    if [ -d "$GOLDEN" ]; then
        echo "golden: 存在   best=$(cat "$BEST_F" 2>/dev/null || echo '?')"
        # 否定式守卫：没有历史文件时也保证 status 以 0 退出（纯读操作不该报失败）
        [ ! -f "$LOG_F" ] || { echo "最近历史："; tail -5 "$LOG_F" | sed 's/^/  /'; }
    else
        echo "golden: 不存在（还没跑 snapshot）"
    fi
    ;;
*) usage ;;
esac
