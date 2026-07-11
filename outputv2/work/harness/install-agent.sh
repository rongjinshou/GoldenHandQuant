#!/usr/bin/env bash
grep -q "$(printf '\r')" "$0" 2>/dev/null && { _t="${TMPDIR:-/tmp}/lf$$-$(basename "$0")"; tr -d '\r' <"$0" >"$_t" && _SRC_DIR="$(cd "$(dirname "$0")" && pwd)" exec bash "$_t" "$@"; } # CRLF 自愈：转成 LF 副本重新执行；_SRC_DIR 记住原目录，副本里才定位得到 ../skills 下的 SKILL.md
#
# install-agent.sh — 把 bug-fixer 修复技能注册给评测机的 OpenCode 运行时。
#
# 双保险安装（幂等，重复执行只是原样覆盖）：
#   项目级：<ROOT>/.opencode/…                    OpenCode 以工作目录为项目根时生效
#   全局级：~/.config/opencode/…                  无论从哪个目录启动都生效（保险）
# 每处装三个文件（官方文档的主形态是单数 agent/；复数 agents/ 与之等价，截至 1.17.17 实测
# 两个目录都会被扫描——两处都装，防不同版本口径差异）：
#   agent/bug-fixer.md          subagent（mode: subagent，供 task 派遣）——官方文档主形态
#   agents/bug-fixer.md         同上——等价目录，双保险
#   skills/bug-fixer/SKILL.md   skill 形式（frontmatter name+description 合规）
#
# 某处写失败只警告不中断；两处全部失败才 exit 1——此时主 agent 直接按
# work/skills/bug-fixer/SKILL.md 的规范自行执行每批修复（该文件始终可读）。
# 注意：OpenCode 只在启动时加载 agent 清单（不热加载），注册对之后新启动的会话生效。
#
# 用法：bash work/harness/install-agent.sh [ROOT]   # ROOT 省略 = 当前工作目录
set -uo pipefail

ROOT="${1:-$PWD}"
# 优先用 CRLF 自愈序言传下来的原目录（自愈后 $0 是临时副本，dirname 会指错地方）
SCRIPT_DIR="${_SRC_DIR:-$(cd "$(dirname "$0")" && pwd)}"
SRC="$SCRIPT_DIR/../skills/bug-fixer/SKILL.md"
[ -f "$SRC" ] || { echo "错误：找不到 $SRC"; exit 2; }

# 从 SKILL.md 提取 description（frontmatter 单行）与正文（第二个 --- 之后的全部内容）
DESC="$(awk '/^description:/{sub(/^description:[ ]*/,""); print; exit}' "$SRC")"
BODY="$(awk 'f>=2{print} /^---[[:space:]]*$/{f++}' "$SRC")"
[ -n "$DESC" ] || { echo "错误：$SRC 的 frontmatter 里没有 description"; exit 2; }
# 生成的 frontmatter 用 YAML 双引号串——值里的 \ 与 " 先转义（先 \ 后 "，顺序不能反），
# 否则 description 含冒号/引号时会产出非法 YAML，整个 agent 定义会被 OpenCode 静默丢弃
DESC_ESC="${DESC//\\/\\\\}"; DESC_ESC="${DESC_ESC//\"/\\\"}"

OK_N=0
install_to() { # $1 = opencode 配置根（其下建 agent/、agents/ 与 skills/）
    local base="$1"
    if mkdir -p "$base/agents" "$base/agent" "$base/skills/bug-fixer" 2>/dev/null &&
       { printf -- '---\ndescription: "%s"\nmode: subagent\n---\n' "$DESC_ESC"; printf '%s\n' "$BODY"; } >"$base/agents/bug-fixer.md" 2>/dev/null &&
       cp -f "$base/agents/bug-fixer.md" "$base/agent/bug-fixer.md" 2>/dev/null &&
       cp -f "$SRC" "$base/skills/bug-fixer/SKILL.md" 2>/dev/null; then
        echo "  已安装：$base/{agent,agents}/bug-fixer.md + skills/bug-fixer/SKILL.md"
        OK_N=$((OK_N + 1))
    else
        echo "  警告：$base 写入失败（跳过此处，不影响其他位置）"
    fi
}

echo "注册 bug-fixer subagent/skill……"
install_to "$ROOT/.opencode"                               # 项目级
install_to "${XDG_CONFIG_HOME:-$HOME/.config}/opencode"    # 全局（评测环境 ~ 目录，保险）

if [ "$OK_N" -eq 0 ]; then
    echo "0 处注册成功——主 agent 请直接按 work/skills/bug-fixer/SKILL.md 的规范自行执行每批修复。"
    exit 1
fi
echo "完成（$OK_N/2 处注册成功）。注意：OpenCode 仅在启动时加载 agent 清单——本注册对之后新启动的会话生效；"
echo "当前已在运行的会话内派不出 bug-fixer 属正常，请按 INSTRUCTION 第③步a 的递降链改派内建 general subagent"
echo "（派遣 prompt 首行要求先读 work/skills/bug-fixer/SKILL.md），或由主 agent 直接照 SKILL.md 执行。"
