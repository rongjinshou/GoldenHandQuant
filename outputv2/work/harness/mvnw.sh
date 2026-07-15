#!/usr/bin/env bash
grep -q "$(printf '\r')" "$0" 2>/dev/null && { _t="${TMPDIR:-/tmp}/lf$$-$(basename "$0")"; tr -d '\r' <"$0" >"$_t" && exec bash "$_t" "$@"; } # CRLF 自愈：被错误打包成 CRLF 时转成 LF 副本重新执行
#
# mvnw.sh — 工程内 Maven 入口：环境守卫后把参数原样透传给系统 mvn。
#
# 为什么存在：headless 评测运行时里，**子会话（subagent）的命令行一旦引用工程外路径**
# （$HOME、~、/home/... 等）会触发运行时的外部目录权限询问，而无人值守模式下该询问永远
# 无人应答——整个评测运行就地挂死（第四轮模拟实测：一条 `cat $HOME/tools/env.sh` 挂了
# 5 小时）。所以修复 subagent 跑 Maven 一律经由本脚本，命令行里只出现工程内相对路径。
#
# 环境假设（评测机已确认）：系统预装完整 JDK 21（含 javac，工程按 release 17 交叉编译）
# 与 Maven。缺什么直接报错停止——不探测、不下载、不自救；agent 把报错原文记进
# result/output.md 即可。
#
# 用法（在工程根目录下）：bash work/harness/mvnw.sh <mvn 参数…>
#   例：bash work/harness/mvnw.sh -s maven-settings.xml -Dmaven.repo.local="$PWD/maven-repo" \
#       -f code/pom.xml -pl ecommerce-user -am test-compile -q
set -uo pipefail

command -v java  >/dev/null 2>&1 || { echo "mvnw.sh 环境缺陷：PATH 中没有 java（评测机不应出现）。如实记录本报错后停止本批。"; exit 2; }
command -v javac >/dev/null 2>&1 || { echo "mvnw.sh 环境缺陷：有 java 但没有 javac——这是 JRE 不是 JDK，无法编译。如实记录后停止本批。"; exit 2; }
command -v mvn   >/dev/null 2>&1 || { echo "mvnw.sh 环境缺陷：PATH 中没有 mvn（评测机不应出现）。如实记录本报错后停止本批。"; exit 2; }
JMAJ="$(java -version 2>&1 | awk -F'"' '/version/{split($2,a,"."); print (a[1]==1)?a[2]:a[1]; exit}')"
JMAJ="${JMAJ%%[!0-9]*}"
[ "${JMAJ:-0}" -ge 17 ] || { echo "mvnw.sh 环境缺陷：java 主版本为 ${JMAJ:-未知}，需要 ≥17（17~21 均可）。如实记录后停止本批。"; exit 2; }

exec mvn "$@"
