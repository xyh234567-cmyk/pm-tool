#!/bin/bash
# ═══════════════════════════════════════════════════════════
#  项目管理工具 · 一键启动（全清 + 重启）
#  用法: ./start.sh          → 默认端口 8888
#        ./start.sh 8899     → 指定端口
#  效果: 杀旧进程 → 清缓存 → 装依赖 → 启动服务
# ═══════════════════════════════════════════════════════════
set -e
cd "$(dirname "$0")"

PORT="${1:-8888}"
PYTHON=/Users/starboy/.pyenv/versions/3.12.0/bin/python3

# ── 1. 杀掉旧进程 ──────────────────────────────────────
echo ">>> 清理旧进程..."
pkill -f "uvicorn app.main" 2>/dev/null && echo "   已终止旧 uvicorn" || true
# 释放端口（macOS 用 lsof）
lsof -ti :"$PORT" 2>/dev/null | xargs kill -9 2>/dev/null && echo "   已释放端口 $PORT" || true
sleep 1

# ── 2. 清除 Python 缓存 ─────────────────────────────────
echo ">>> 清除缓存..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name '*.pyc' -delete 2>/dev/null || true
echo "   __pycache__ / .pyc 已清除"

# ── 3. 安装/更新依赖 ────────────────────────────────────
echo ">>> 依赖..."
$PYTHON -m pip install -q -r requirements.txt 2>/dev/null
echo "   依赖就绪"

# ── 4. 启动 ────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  项目管理工具                              ║"
echo "║  http://127.0.0.1:$PORT                           ║"
echo "║  Ctrl+C 停止                                ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
$PYTHON -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --reload
