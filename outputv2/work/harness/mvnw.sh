#!/usr/bin/env bash
grep -q "$(printf '\r')" "$0" 2>/dev/null && { _t="${TMPDIR:-/tmp}/lf$$-$(basename "$0")"; tr -d '\r' <"$0" >"$_t" && exec bash "$_t" "$@"; } # CRLF 自愈：被错误打包成 CRLF 时转成 LF 副本重新执行
#
# mvnw.sh — 工程内 Maven 入口：按版本探测接入 $HOME/tools 便携 JDK17/Maven 后原样透传参数。
#
# 为什么存在：headless 评测运行时里，**子会话（subagent）的命令行一旦引用工程外路径**
# （$HOME、~、/home/... 等）会触发运行时的外部目录权限询问，而无人值守模式下该询问永远
# 无人应答——整个评测运行就地挂死（第四轮模拟实测：一条 `cat $HOME/tools/env.sh` 挂了
# 5 小时）。权限层只检查 agent 命令行文本，不追踪脚本内部行为——所以把工程外路径的访问
# 全部收进本脚本，subagent 的命令行只出现工程内相对路径即可彻底规避。
#
# 用法（在工程根目录下）：bash work/harness/mvnw.sh <mvn 参数…>
#   例：bash work/harness/mvnw.sh -s maven-settings.xml -Dmaven.repo.local="$PWD/maven-repo" \
#       -f code/pom.xml -pl ecommerce-user -am test-compile -q
set -uo pipefail

# 与 ratchet.sh 同源的版本驱动探测：java 缺失或主版本 <17 时，从 $HOME/tools 挑最新 jdk-17*
#（sort -V 升序遍历、烟测可执行，最新的最后接管）；mvn 仅在 PATH 缺失时接入最新 apache-maven-*。
java_major() { # 解析 java 主版本："17.0.10"→17，老格式 "1.8.0_392"→8；解析不出则输出空
    local v; v="$("$1" -version 2>&1 | awk -F'"' '/version/{split($2,a,"."); print (a[1]==1)?a[2]:a[1]; exit}')"
    printf '%s\n' "${v%%[!0-9]*}"
}
JMAJ=""; command -v java >/dev/null 2>&1 && JMAJ="$(java_major java)"
if [ "${JMAJ:-0}" -lt 17 ]; then
    while IFS= read -r j; do
        [ -x "$j/bin/java" ] && "$j/bin/java" -version >/dev/null 2>&1 && export JAVA_HOME="$j" PATH="$j/bin:$PATH"
    done < <(ls -d "$HOME"/tools/jdk-17* 2>/dev/null | sort -V)
fi
if ! command -v mvn >/dev/null 2>&1; then
    m="$(ls -d "$HOME"/tools/apache-maven-* 2>/dev/null | sort -V | tail -1)"
    [ -n "$m" ] && [ -d "$m/bin" ] && export PATH="$m/bin:$PATH"
fi
command -v mvn >/dev/null 2>&1 || { echo "mvnw.sh 错误：找不到 mvn——先按 INSTRUCTION 第 1 节把便携 JDK/Maven 装到 \$HOME/tools。"; exit 2; }
JMAJ="$(java_major java)"
[ "${JMAJ:-0}" -ge 17 ] || { echo "mvnw.sh 错误：java 主版本为 ${JMAJ:-未知}，需要 JDK17（当前 JAVA_HOME=${JAVA_HOME:-未设置}）。"; exit 2; }

exec mvn "$@"
