#!/usr/bin/env bash
grep -q "$(printf '\r')" "$0" 2>/dev/null && { _t="${TMPDIR:-/tmp}/lf$$-$(basename "$0")"; _d="$(cd "$(dirname "$0")" && pwd)"; tr -d '\r' <"$0" >"$_t" && CHECK_BATCH_HOME="$_d" exec bash "$_t" "$@"; } # CRLF 自愈：被错误打包成 CRLF 时转成 LF 副本重新执行（CHECK_BATCH_HOME 记住原目录，副本据此仍能定位 ../bugs/artifacts.tsv）
#
# check-batch.sh — 批次产物确定性核验（防「空心批次」）：不信模型口供，只看文件系统。
#
# 设计动机：ratchet.sh verify 只证明「编译过 + 公开 24 例无回归」——它挡得住**修坏**，
# 挡不住**没修**。实测发生过：subagent 在 ROLLED_BACK 重试时只补上次报错的文件，整批
# 结构性产物（如 B16 的三个跨模块监听器）全部缺失，verify 因"无回归"照样把空心状态
# 固化为 golden，subagent 还回报全部完成。本脚本按 work/bugs/artifacts.tsv 登记的
# 「正常执行本批必然产生」的确定性断言逐条机械核验：
#   exists = 卡片【新增】的文件必须存在；absent = 卡片【删除】的文件必须不存在；
#   grep   = 文件里必须能 grep -F 命中卡片「改法」的载重锚点字符串（固定串，非正则）。
# 纯文件系统操作 + grep，不跑 Maven、不写任何文件、不碰棘轮状态，秒级返回，随时可跑
# （与 ratchet 的构建锁无关，无锁）。每批 verify 固化（ADVANCED/OK）后立即执行本脚本。
#
# 用法（TARGET_ROOT 省略 = 当前工作目录；工程需位于 <TARGET_ROOT>/code/）：
#   bash check-batch.sh <批次号如B16> [TARGET_ROOT]
#
# 机器可读结论（最后一行，照此判断下一步）：
#   BATCH_ARTIFACTS: OK batch=<B> checked=<n>          # n 条断言全部成立（该批未登记条目时 checked=0）
#   BATCH_ARTIFACTS: MISSING batch=<B> missing=<k>/<n> # k 条不成立（明细已按「缺失: 类型 路径 参数」
#                                                      # 逐条打印）→ 本批按未完成卡处理，把缺失清单
#                                                      # 转交 subagent 重开补齐（INSTRUCTION 第③步 c）
set -uo pipefail

BATCH_RAW="${1:-}"; TARGET_ROOT="${2:-$PWD}"

usage() { grep '^#   bash' "$0" | sed 's/^# *//'; exit 2; }
[ -n "$BATCH_RAW" ] || usage
# 批次号容错：b16 → B16（清单里统一大写）
BATCH="$(printf '%s' "$BATCH_RAW" | tr '[:lower:]' '[:upper:]')"

# 断言清单按【脚本自身位置】定位（../bugs/artifacts.tsv），不依赖调用方 CWD；
# CRLF 自愈重执行时脚本副本在 /tmp，用序言里记下的 CHECK_BATCH_HOME 回到原目录。
SCRIPT_DIR="${CHECK_BATCH_HOME:-$(cd "$(dirname "$0")" && pwd)}"
TSV="$SCRIPT_DIR/../bugs/artifacts.tsv"
[ -f "$TSV" ] || { echo "错误：找不到断言清单 $TSV（它应随交付物固定位于 work/bugs/ 下，与本脚本同包分发）。"; exit 2; }
[ -f "$TARGET_ROOT/code/pom.xml" ] || { echo "错误：$TARGET_ROOT 下没有 code/pom.xml（先按 INSTRUCTION 第①步复制源码，或把工程根作为第二个参数传入）。"; exit 2; }

echo "批次 $BATCH 产物核验：清单 $TSV → 目标 $TARGET_ROOT/code/ ……"

TOTAL=0; MISS=0
while IFS=$'\t' read -r B T P A; do
    # 逐字段剥掉可能的 \r 残留（*.sh 之外的清单文件不在 INSTRUCTION 第①步 sed 归一范围内，
    # 万一整包被转成 CRLF，行尾 \r 会黏在最后一个字段上）
    B="${B%$'\r'}"; T="${T%$'\r'}"; P="${P%$'\r'}"; A="${A%$'\r'}"
    case "$B" in ''|'#'*) continue ;; esac      # 跳过空行与注释行
    [ "$B" = "$BATCH" ] || continue             # 只核验目标批次的条目
    TOTAL=$((TOTAL+1))
    F="$TARGET_ROOT/code/$P"
    OK=1
    case "$T" in
        exists) [ -f "$F" ] || OK=0 ;;
        absent) [ ! -e "$F" ] || OK=0 ;;
        grep)
            if [ -z "$A" ]; then
                echo "警告：$P 的 grep 断言缺少参数列（清单行损坏），按不成立计。"; OK=0
            else
                { [ -f "$F" ] && grep -qF -- "$A" "$F"; } || OK=0
            fi ;;
        *) echo "警告：未知断言类型「$T」（$P，清单行损坏），按不成立计。"; OK=0 ;;
    esac
    if [ "$OK" = 0 ]; then
        MISS=$((MISS+1))
        echo "缺失: $T $P${A:+ $A}"
    fi
done <"$TSV"

if [ "$TOTAL" -eq 0 ]; then
    echo "artifacts.tsv 里没有 $BATCH 的断言条目——该批未登记确定性产物，按通过处理。"
    echo "BATCH_ARTIFACTS: OK batch=$BATCH checked=0"; exit 0
fi
if [ "$MISS" -eq 0 ]; then
    echo "全部 $TOTAL 条断言成立：本批卡片的确定性产物已真实落进 code/。"
    echo "BATCH_ARTIFACTS: OK batch=$BATCH checked=$TOTAL"; exit 0
fi
echo "以上 $MISS 条断言不成立：verify 的「无回归」挡不住整批做空——本批卡片声称的产物没有"
echo "真正落进 code/（空心批次）。请把上面「缺失:」清单整段转交 subagent 重开本批补齐，"
echo "补齐后重跑 verify 再跑本脚本（处置协议见 INSTRUCTION 第③步 c 与第④步补救循环）。"
echo "BATCH_ARTIFACTS: MISSING batch=$BATCH missing=$MISS/$TOTAL"; exit 1
