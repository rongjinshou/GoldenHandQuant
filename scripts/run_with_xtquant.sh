#!/bin/bash
# 在 WSL 中运行需要 xtquant 的 Python 脚本
# 用法: ./scripts/run_with_xtquant.sh your_script.py [args...]

# Windows conda Python 路径
WIN_PYTHON="/mnt/c/Users/11492/.conda/envs/goldenhandquant/python.exe"

# 检查是否在 WSL 中
if grep -qi microsoft /proc/version 2>/dev/null; then
    echo "检测到 WSL 环境，使用 Windows Python..."
    $WIN_PYTHON "$@"
else
    echo "使用当前 Python 环境..."
    python "$@"
fi
